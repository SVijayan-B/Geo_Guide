import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class PriceAgent:
    """
    Estimate a realistic price for an item described by an image caption.

    Cost optimization:
    - If the description contains an explicit price, we skip Groq entirely.
    - Otherwise, we use Groq once to get both product + price range + currency.
    """

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    def _symbol_to_currency(self, symbol: str) -> str | None:
        return {"₹": "INR", "$": "USD", "€": "EUR", "£": "GBP"}.get(symbol)

    def _heuristic_product(self, description: str) -> str:
        cleaned = description or ""
        cleaned = re.sub(r"[₹$€£]\s*[0-9]+(?:[.,][0-9]+)?", "", cleaned)
        cleaned = re.sub(r"\b(INR|USD|EUR|GBP|AED|SGD)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\d+", "", cleaned)
        cleaned = re.sub(r"[^a-zA-Z0-9\s-]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if not cleaned:
            return "item"
        return " ".join(cleaned.split()[:8])

    def _extract_explicit_price(self, description: str) -> dict | None:
        if not description:
            return None

        # Symbol-based: "$ 120", "₹500", "€ 29.99"
        symbol_match = re.search(r"([₹$€£])\s*([0-9]+(?:[.,][0-9]+)?)", description)
        if symbol_match:
            symbol = symbol_match.group(1)
            amount_raw = symbol_match.group(2).replace(",", "")
            try:
                amount = float(amount_raw)
            except Exception:
                return None

            currency = self._symbol_to_currency(symbol)
            if not currency:
                return None

            product = self._heuristic_product(description)
            return {
                "product": product,
                "price_range": {"min_price": amount * 0.9, "max_price": amount * 1.1, "currency": currency},
                "estimated_price": round(amount, 2),
            }

        # ISO code + number: "INR 500", "USD 6"
        iso_match = re.search(
            r"\b(INR|USD|EUR|GBP|AED|SGD)\b\s*([0-9]+(?:[.,][0-9]+)?)",
            description,
            flags=re.IGNORECASE,
        )
        if iso_match:
            currency = iso_match.group(1).upper()
            amount_raw = iso_match.group(2).replace(",", "")
            try:
                amount = float(amount_raw)
            except Exception:
                return None

            product = self._heuristic_product(description)
            return {
                "product": product,
                "price_range": {"min_price": amount * 0.9, "max_price": amount * 1.1, "currency": currency},
                "estimated_price": round(amount, 2),
            }

        return None

    def _estimate_with_llm(self, description: str, city: str | None) -> dict:
        city_hint = f" in {city}" if city else ""
        prompt = f"""
You are a pricing assistant.

Given this description of an item from an image:
{description}

Estimate the typical market price range for the product{city_hint}.

Return ONLY valid JSON with this schema:
{{
  "product": string,
  "min_price": number,
  "max_price": number,
  "currency": string   // ISO 4217 currency code, e.g. "INR", "USD"
}}
"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()

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
            "product": data.get("product") or self._heuristic_product(description),
            "min_price": min_price,
            "max_price": max_price,
            "currency": (data.get("currency") or "INR").upper(),
        }

    def estimate_price(self, description: str, city: str | None = None) -> dict:
        explicit = self._extract_explicit_price(description)
        if explicit is not None:
            return explicit

        price_range = self._estimate_with_llm(description, city=city)
        avg_price = (price_range["min_price"] + price_range["max_price"]) / 2

        return {
            "product": price_range["product"],
            "price_range": {
                "min_price": price_range["min_price"],
                "max_price": price_range["max_price"],
                "currency": price_range["currency"],
            },
            "estimated_price": round(float(avg_price), 2),
        }