import requests
import os
from dotenv import load_dotenv

load_dotenv()


class FlightAPI:

    def __init__(self):
        self.api_key = os.getenv("AVIATION_API_KEY")

    def get_flights(self, origin, destination):
        url = f"http://api.aviationstack.com/v1/flights?access_key={self.api_key}&dep_iata={origin}&arr_iata={destination}"

        response = requests.get(url)
        data = response.json()

        flights = []

        for flight in data.get("data", [])[:5]:
            flights.append({
                "flight": flight.get("flight", {}).get("iata"),
                "status": flight.get("flight_status"),
                "departure": flight.get("departure", {}).get("scheduled")
            })

        return flights