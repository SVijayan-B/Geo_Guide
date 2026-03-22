from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()


class LocationAPI:
    def __init__(self):
        self.api_key = os.getenv("OPENTRIPMAP_API_KEY")

    def get_places(self, city: str) -> list[dict[str, str]]:
        if not self.api_key or not city:
            return []

        try:
            geo_response = requests.get(
                "https://api.opentripmap.com/0.1/en/places/geoname",
                params={"name": city, "apikey": self.api_key},
                timeout=6,
            )
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            lat = geo_data.get("lat")
            lon = geo_data.get("lon")
            if lat is None or lon is None:
                return []

            places_response = requests.get(
                "https://api.opentripmap.com/0.1/en/places/radius",
                params={"radius": 5000, "lon": lon, "lat": lat, "apikey": self.api_key},
                timeout=6,
            )
            places_response.raise_for_status()
            places_data = places_response.json()

            results = []
            for place in (places_data.get("features") or [])[:5]:
                props = place.get("properties") or {}
                name = props.get("name")
                if not name:
                    continue
                results.append({"name": name, "category": props.get("kinds", "")})
            return results
        except Exception:
            return []
