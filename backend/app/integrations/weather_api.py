from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class WeatherAPI:
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")

    def get_weather(self, city: str) -> dict[str, Any]:
        if not self.api_key or not city:
            return {"main": "Clear", "description": "fallback clear sky"}

        url = "http://api.openweathermap.org/data/2.5/weather"
        try:
            response = requests.get(
                url,
                params={"q": city, "appid": self.api_key, "units": "metric"},
                timeout=6,
            )
            response.raise_for_status()
            data = response.json()
            weather = (data.get("weather") or [{}])[0]
            return {
                "main": weather.get("main", "Clear"),
                "description": weather.get("description", "no description"),
            }
        except Exception:
            return {"main": "Clouds", "description": "fallback cloudy conditions"}
