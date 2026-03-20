import requests
import os
from dotenv import load_dotenv

load_dotenv()


class CurrencyService:

    def __init__(self):
        self.api_key = os.getenv("EXCHANGE_API_KEY")

    def convert(self, amount, from_currency="INR", to_currency="USD"):
        url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/pair/{from_currency}/{to_currency}/{amount}"

        response = requests.get(url)
        data = response.json()

        if data.get("result") != "success":
            return None

        return round(data.get("conversion_result"), 2)