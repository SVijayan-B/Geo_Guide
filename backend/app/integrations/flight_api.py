from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()


class FlightAPI:
    def __init__(self):
        self.api_key = os.getenv("AVIATION_API_KEY")

    def get_flights(self, origin: str, destination: str) -> list[dict[str, str]]:
        if not self.api_key or not origin or not destination:
            return []

        try:
            response = requests.get(
                "http://api.aviationstack.com/v1/flights",
                params={"access_key": self.api_key, "dep_iata": origin, "arr_iata": destination},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        flights = []
        for flight in (data.get("data") or [])[:5]:
            flights.append(
                {
                    "flight": (flight.get("flight") or {}).get("iata"),
                    "status": flight.get("flight_status"),
                    "departure": (flight.get("departure") or {}).get("scheduled"),
                }
            )
        return flights
