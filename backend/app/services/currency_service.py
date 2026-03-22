from __future__ import annotations

import time
from typing import Any

import requests
from dotenv import load_dotenv
import os

load_dotenv()


class CurrencyService:
    _rate_cache: dict[str, tuple[float, float]] = {}

    FALLBACK_RATES = {
        "USD": 1.0,
        "INR": 83.0,
        "EUR": 0.92,
        "GBP": 0.79,
        "AED": 3.67,
        "SGD": 1.35,
        "JPY": 150.0,
        "AUD": 1.52,
        "CAD": 1.36,
    }

    def __init__(self):
        self.api_key = os.getenv("EXCHANGE_API_KEY")
        self.cache_ttl_seconds = int(os.getenv("CURRENCY_CACHE_TTL_SECONDS", "1800"))

    def _normalize(self, code: str | None, fallback: str = "USD") -> str:
        if not code:
            return fallback
        code = code.strip().upper()
        if len(code) != 3:
            return fallback
        return code

    def _cache_key(self, from_currency: str, to_currency: str) -> str:
        return f"{from_currency}->{to_currency}"

    def _read_cache(self, from_currency: str, to_currency: str) -> float | None:
        key = self._cache_key(from_currency, to_currency)
        cached = self._rate_cache.get(key)
        if not cached:
            return None
        rate, ts = cached
        if time.time() - ts > self.cache_ttl_seconds:
            return None
        return rate

    def _write_cache(self, from_currency: str, to_currency: str, rate: float) -> None:
        self._rate_cache[self._cache_key(from_currency, to_currency)] = (rate, time.time())

    def _fallback_rate(self, from_currency: str, to_currency: str) -> float | None:
        base_from = self.FALLBACK_RATES.get(from_currency)
        base_to = self.FALLBACK_RATES.get(to_currency)
        if base_from is None or base_to is None:
            return None
        if base_from == 0:
            return None
        return float(base_to / base_from)

    def _fetch_rate(self, from_currency: str, to_currency: str) -> float | None:
        cached = self._read_cache(from_currency, to_currency)
        if cached is not None:
            return cached

        if self.api_key:
            url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/pair/{from_currency}/{to_currency}"
            try:
                response = requests.get(url, timeout=6)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                if data.get("result") == "success":
                    value = float(data.get("conversion_rate"))
                    self._write_cache(from_currency, to_currency, value)
                    return value
            except Exception:
                pass

        fallback = self._fallback_rate(from_currency, to_currency)
        if fallback is not None:
            self._write_cache(from_currency, to_currency, fallback)
        return fallback

    def convert(self, amount: float, from_currency: str = "INR", to_currency: str = "USD") -> float | None:
        try:
            amount = float(amount)
        except Exception:
            return None

        from_currency = self._normalize(from_currency, fallback="USD")
        to_currency = self._normalize(to_currency, fallback="USD")

        if from_currency == to_currency:
            return round(amount, 2)

        rate = self._fetch_rate(from_currency, to_currency)
        if rate is None:
            return None
        return round(amount * rate, 2)

    def compare_home_and_destination(
        self,
        *,
        amount: float,
        source_currency: str,
        home_currency: str,
        destination_currency: str,
    ) -> dict[str, Any]:
        source_currency = self._normalize(source_currency, fallback=destination_currency)
        home_currency = self._normalize(home_currency, fallback="USD")
        destination_currency = self._normalize(destination_currency, fallback=source_currency)

        destination_amount = amount
        if source_currency != destination_currency:
            converted_dest = self.convert(amount, source_currency, destination_currency)
            if converted_dest is not None:
                destination_amount = converted_dest

        home_amount = self.convert(destination_amount, destination_currency, home_currency)

        return {
            "source_currency": source_currency,
            "destination_currency": destination_currency,
            "home_currency": home_currency,
            "amount_in_destination": round(float(destination_amount), 2),
            "amount_in_home": round(float(home_amount), 2) if home_amount is not None else None,
        }
