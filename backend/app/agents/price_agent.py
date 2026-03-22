from __future__ import annotations

import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class PriceAgent:
    """Hybrid price estimator with rule-based first-pass and optional LLM fallback."""

    PRODUCT_HINTS = {
        "coffee": (120, 350, "INR"),
        "tea": (40, 180, "INR"),
        "pizza": (250, 900, "INR"),
        "burger": (120, 500, "INR"),
        "headphone": (800, 4500, "INR"),
        "phone": (8000, 65000, "INR"),
        "shoes": (1200, 8500, "INR"),
        "bag": (700, 5000, "INR"),
        "watch": (1000, 12000, "INR"),
        "jacket": (900, 6000, "INR"),
        "book": (150, 900, "INR"),
    }

    CITY_FACTOR = {
        "mumbai": 1.15,
        "delhi": 1.1,
        "bangalore": 1.2,
        "new york": 4.5,
        "london": 4.0,
        "dubai": 3.3,
        "singapore": 3.8,
    }

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self.use_groq = os.getenv("USE_GROQ_PRICE_AGENT", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.client = None

        if self.use_groq:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    from groq import Groq

                    self.client = Groq(api_key=api_key)
                except Exception:
                    self.client = None

    def _symbol_to_currency(self, symbol: str) -> str | None:
        return {
            "$": "USD",
            "EUR": "EUR",
            "GBP": "GBP",
            "INR": "INR",
            "\u20b9": "INR",
            "\u20ac": "EUR",
            "\u00a3": "GBP",
        }.get(symbol)

    def _extract_explicit_price(self, description: str) -> dict[str, Any] | None:
        if not description:
            return None

        symbol_match = re.search(r"([$\u20b9\u20ac\u00a3])\s*([0-9]+(?:[.,][0-9]+)?)", description)
        if symbol_match:
            symbol, raw_amount = symbol_match.groups()
            currency = self._symbol_to_currency(symbol)
            if not currency:
                return None
            amount = float(raw_amount.replace(",", ""))
            return {
                "amount": amount,
                "currency": currency,
                "source": "explicit",
            }

        iso_match = re.search(r"\b(INR|USD|EUR|GBP|AED|SGD)\b\s*([0-9]+(?:[.,][0-9]+)?)", description, re.IGNORECASE)
        if iso_match:
            currency, raw_amount = iso_match.groups()
            amount = float(raw_amount.replace(",", ""))
            return {
                "amount": amount,
                "currency": currency.upper(),
                "source": "explicit",
            }

        return None

    def _detect_product(self, description: str) -> str:
        text = (description or "").lower()
        for key in self.PRODUCT_HINTS.keys():
            if key in text:
                return key
        words = re.sub(r"[^a-z0-9\s-]", " ", text)
        words = re.sub(r"\s+", " ", words).strip()
        return " ".join(words.split()[:4]) or "item"

    def _city_factor(self, city: str | None) -> float:
        if not city:
            return 1.0
        return self.CITY_FACTOR.get(city.strip().lower(), 1.0)

    def _heuristic_estimate(self, description: str, city: str | None) -> dict[str, Any]:
        explicit = self._extract_explicit_price(description)
        product = self._detect_product(description)

        if explicit is not None:
            amount = float(explicit["amount"])
            return {
                "product": product,
                "price_range": {
                    "min_price": round(amount * 0.9, 2),
                    "max_price": round(amount * 1.1, 2),
                    "currency": explicit["currency"],
                },
                "estimated_price": round(amount, 2),
                "source": "explicit",
                "confidence": 0.95,
            }

        base = self.PRODUCT_HINTS.get(product)
        if base is None:
            return {
                "product": product,
                "price_range": {
                    "min_price": 200.0,
                    "max_price": 2000.0,
                    "currency": "INR",
                },
                "estimated_price": 1100.0,
                "source": "fallback",
                "confidence": 0.35,
            }

        low, high, currency = base
        factor = self._city_factor(city)
        min_price = round(low * factor, 2)
        max_price = round(high * factor, 2)
        avg = round((min_price + max_price) / 2, 2)
        return {
            "product": product,
            "price_range": {
                "min_price": min_price,
                "max_price": max_price,
                "currency": currency,
            },
            "estimated_price": avg,
            "source": "heuristic",
            "confidence": 0.75,
        }

    def _llm_estimate(self, description: str, city: str | None) -> dict[str, Any] | None:
        if self.client is None:
            return None

        city_hint = f" in {city}" if city else ""
        prompt = f"""
Estimate a practical market price for this described item{city_hint}.
Description: {description}

Return strict JSON with keys:
- product (string)
- min_price (number)
- max_price (number)
- currency (ISO code)
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (response.choices[0].message.content or "").strip()

            import json

            try:
                data = json.loads(raw)
            except Exception:
                cleaned = raw.replace("```json", "").replace("```", "").strip()
                data = json.loads(cleaned)

            min_price = float(data.get("min_price"))
            max_price = float(data.get("max_price"))
            if min_price > max_price:
                min_price, max_price = max_price, min_price

            return {
                "product": data.get("product") or self._detect_product(description),
                "price_range": {
                    "min_price": round(min_price, 2),
                    "max_price": round(max_price, 2),
                    "currency": (data.get("currency") or "INR").upper(),
                },
                "estimated_price": round((min_price + max_price) / 2, 2),
                "source": "llm",
                "confidence": 0.7,
            }
        except Exception:
            return None

    def estimate_price(self, description: str, city: str | None = None) -> dict[str, Any]:
        heuristic = self._heuristic_estimate(description, city)

        if heuristic.get("confidence", 0) >= 0.7:
            return heuristic

        llm = self._llm_estimate(description, city)
        if llm is not None:
            return llm

        return heuristic
