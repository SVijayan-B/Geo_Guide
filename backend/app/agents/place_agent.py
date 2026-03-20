import os
from groq import Groq


class PlaceAgent:

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"

    def explain_place(self, description):
        prompt = f"""
        Identify the place from this description:
        {description}

        Then:
        - Explain about it
        - Give 3 interesting facts
        - Keep it engaging
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content