from typing import Optional


class CurrencyDetectionService:
    """
    Lightweight currency detection.

    Production-grade solution would use geocoding/reverse geocoding to infer
    country/currency. For now, we keep it deterministic with a small mapping.
    """

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
        "ahmedabad": "INR",
        # UAE
        "dubai": "AED",
        "abu dhabi": "AED",
        # USA
        "new york": "USD",
        "los angeles": "USD",
        "san francisco": "USD",
        # UK
        "london": "GBP",
        # Singapore
        "singapore": "SGD",
    }

    def _normalize(self, code: Optional[str], fallback: str = "INR") -> str:
        if not code:
            return fallback
        code = code.strip().upper()
        if len(code) < 3:
            return fallback
        return code

    def detect_home_currency(self, home_currency: Optional[str]) -> str:
        return self._normalize(home_currency, fallback="INR")

    def detect_destination_currency(self, city: str, fallback: str = "INR") -> str:
        if not city:
            return fallback
        key = city.strip().lower()
        return self.CITY_TO_CURRENCY.get(key, fallback)

