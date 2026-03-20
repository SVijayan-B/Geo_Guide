import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


class PriceAgent:

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    # ------------------------
    # 🧠 STEP 1: EXTRACT PRODUCT NAME
    # ------------------------
    def extract_product(self, description):
        prompt = f"""
        Identify the product name from this description:

        {description}

        Return only the product name (e.g., "Nike running shoes", "luxury watch").
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content.strip()

    # ------------------------
    # 💰 STEP 2: ESTIMATE PRICE RANGE
    # ------------------------
    def estimate_price_range(self, product_name):
        prompt = f"""
        Estimate the typical price range for this product in India:

        {product_name}

        Respond ONLY in JSON:
        {{
            "min_price": number,
            "max_price": number,
            "currency": "INR"
        }}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        output = response.choices[0].message.content.strip()

        # parse JSON safely
        import json
        try:
            return json.loads(output)
        except:
            cleaned = output.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)

    # ------------------------
    # 🔥 MAIN FUNCTION
    # ------------------------
    def estimate_price(self, description):

        product = self.extract_product(description)

        price_range = self.estimate_price_range(product)

        avg_price = (price_range["min_price"] + price_range["max_price"]) / 2

        return {
            "product": product,
            "price_range": price_range,
            "estimated_price": round(avg_price, 2)
        }