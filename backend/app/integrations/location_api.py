import requests
import os
from dotenv import load_dotenv

load_dotenv()


class LocationAPI:

    def __init__(self):
        self.api_key = os.getenv("OPENTRIPMAP_API_KEY")

    def get_places(self, city):
        geo_url = f"https://api.opentripmap.com/0.1/en/places/geoname?name={city}&apikey={self.api_key}"
        geo_data = requests.get(geo_url).json()

        lat = geo_data.get("lat")
        lon = geo_data.get("lon")

        places_url = f"https://api.opentripmap.com/0.1/en/places/radius?radius=5000&lon={lon}&lat={lat}&apikey={self.api_key}"

        places_data = requests.get(places_url).json()

        results = []

        for place in places_data.get("features", [])[:5]:
            results.append({
                "name": place["properties"].get("name"),
                "category": place["properties"].get("kinds")
            })

        return results