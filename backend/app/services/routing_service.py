from __future__ import annotations

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()


class RoutingService:
    def __init__(self):
        self.api_key = os.getenv("ORS_API_KEY")

    async def _fetch_coordinates(self, client: httpx.AsyncClient, city: str) -> list[float] | None:
        if not self.api_key or not city:
            return None
        try:
            response = await client.get(
                "https://api.openrouteservice.org/geocode/search",
                params={"api_key": self.api_key, "text": city},
                timeout=8.0,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            features = data.get("features") or []
            if not features:
                return None
            coords = features[0].get("geometry", {}).get("coordinates")
            if not isinstance(coords, list) or len(coords) < 2:
                return None
            return [float(coords[0]), float(coords[1])]
        except Exception:
            return None

    async def get_route(self, start_city: str, end_city: str) -> dict[str, Any]:
        if not self.api_key:
            return {"distance_km": None, "duration_min": None}

        async with httpx.AsyncClient() as client:
            start_coords = await self._fetch_coordinates(client, start_city)
            end_coords = await self._fetch_coordinates(client, end_city)
            if not start_coords or not end_coords:
                return {"distance_km": None, "duration_min": None}

            try:
                response = await client.post(
                    "https://api.openrouteservice.org/v2/directions/driving-car",
                    json={"coordinates": [start_coords, end_coords]},
                    headers={"Authorization": self.api_key},
                    timeout=10.0,
                )
                response.raise_for_status()
                data = response.json()
                summary = data["features"][0]["properties"]["summary"]
                return {
                    "distance_km": round(float(summary["distance"]) / 1000, 2),
                    "duration_min": round(float(summary["duration"]) / 60, 2),
                }
            except Exception:
                return {"distance_km": None, "duration_min": None}
