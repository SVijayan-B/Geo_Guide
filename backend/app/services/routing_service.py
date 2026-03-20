import httpx
import os
from dotenv import load_dotenv

load_dotenv()


class RoutingService:

    def __init__(self):
        self.api_key = os.getenv("ORS_API_KEY")

    async def get_coordinates(self, city):
        url = "https://api.openrouteservice.org/geocode/search"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params={
                "api_key": self.api_key,
                "text": city
            })

        data = response.json()

        return data["features"][0]["geometry"]["coordinates"]

    async def get_route(self, start_city, end_city):
        async with httpx.AsyncClient() as client:

            start_coords = await self.get_coordinates(start_city)
            end_coords = await self.get_coordinates(end_city)

            response = await client.post(
                "https://api.openrouteservice.org/v2/directions/driving-car",
                json={"coordinates": [start_coords, end_coords]},
                headers={"Authorization": self.api_key}
            )

        data = response.json()

        summary = data["features"][0]["properties"]["summary"]

        return {
            "distance_km": round(summary["distance"] / 1000, 2),
            "duration_min": round(summary["duration"] / 60, 2)
        }