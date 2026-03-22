from __future__ import annotations

from typing import Optional


class CurrencyDetectionService:
    """Deterministic fallback currency detection from city / locale signals."""

    CITY_TO_CURRENCY = {
        # India
        "chennai": "INR",
        "mumbai": "INR",
        "delhi": "INR",
        "new delhi": "INR",
        "bengaluru": "INR",
        "bangalore": "INR",
        "hyderabad": "INR",
        "kolkata": "INR",
        "pune": "INR",
        # UAE
        "dubai": "AED",
        "abu dhabi": "AED",
        # US
        "new york": "USD",
        "los angeles": "USD",
        "san francisco": "USD",
        "chicago": "USD",
        # UK
        "london": "GBP",
        "manchester": "GBP",
        # Europe
        "paris": "EUR",
        "berlin": "EUR",
        "rome": "EUR",
        "amsterdam": "EUR",
        # APAC
        "singapore": "SGD",
        "tokyo": "JPY",
        "sydney": "AUD",
    }

    LOCALE_TO_CURRENCY = {
        "en-in": "INR",
        "en-us": "USD",
        "en-gb": "GBP",
        "fr-fr": "EUR",
        "de-de": "EUR",
        "ja-jp": "JPY",
        "en-sg": "SGD",
        "en-au": "AUD",
    }

    def _normalize(self, code: Optional[str], fallback: str = "INR") -> str:
        if not code:
            return fallback
        code = code.strip().upper()
        if len(code) != 3:
            return fallback
        return code

    def detect_home_currency(self, home_currency: Optional[str], locale: Optional[str] = None) -> str:
        normalized = self._normalize(home_currency, fallback="")
        if normalized:
            return normalized

        if locale:
            code = self.LOCALE_TO_CURRENCY.get(locale.strip().lower())
            if code:
                return code

        return "INR"

    def detect_destination_currency(self, city: Optional[str], fallback: str = "INR") -> str:
        if not city:
            return fallback
        key = city.strip().lower()
        return self.CITY_TO_CURRENCY.get(key, fallback)
