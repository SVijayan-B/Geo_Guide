import os
from groq import Groq
from dotenv import load_dotenv
from app.integrations.weather_api import WeatherAPI

load_dotenv()


class DisruptionAgent:

    def __init__(self):
        self.weather_api = WeatherAPI()

        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key)

        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    def predict_delay(self, trip, context):

        # 🔥 HANDLE BOTH dict + object
        if isinstance(trip, dict):
            origin = trip.get("origin")
        else:
            origin = trip.origin

        # 🌦️ Real weather
        weather = self.weather_api.get_weather(origin)

        prompt = f"""
        You are an AI system predicting flight delays.

        INPUT:
        - Weather: {weather}
        - Time of Day: {context["time_of_day"]}
        - Travel Phase: {context["travel_phase"]}

        TASK:
        1. Estimate delay probability (0 to 1)
        2. Explain reason
        3. Assess risk level (low/medium/high)

        Respond ONLY in JSON:
        {{
            "delay_probability": 0.0,
            "risk_level": "...",
            "reason": "..."
        }}
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a flight disruption prediction AI."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_output = response.choices[0].message.content.strip()

        # 🔥 Safe JSON parsing
        import json
        try:
            parsed = json.loads(raw_output)
        except:
            cleaned = raw_output.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)

        parsed["weather"] = weather

        return parsed