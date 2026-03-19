import requests
import os
from dotenv import load_dotenv

load_dotenv()


class WeatherAPI:

    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")

    def get_weather(self, city):
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}"

        response = requests.get(url)
        data = response.json()

        weather_main = data["weather"][0]["main"]
        description = data["weather"][0]["description"]

        return {
            "main": weather_main,
            "description": description
        }