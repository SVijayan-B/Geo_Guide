import os
from groq import Groq
from dotenv import load_dotenv
from app.integrations.weather_api import WeatherAPI

load_dotenv()


class DisruptionAgent:

    def __init__(self):
        self.weather_api = WeatherAPI()
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

        # Cost optimization: allow disabling Groq by default.
        self.use_groq = os.getenv("USE_GROQ_DISRUPTION", "0") == "1"
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key) if (self.use_groq and api_key) else None

    def _heuristic_delay(self, weather: dict, context: dict) -> dict:
        main = (weather.get("main") or "").lower()
        description = weather.get("description") or ""

        # Rough heuristic based on typical delay drivers. Tune later with real data.
        prob_map = {
            "thunderstorm": 0.78,
            "tornado": 0.85,
            "drizzle": 0.35,
            "rain": 0.40,
            "snow": 0.55,
            "mist": 0.30,
            "fog": 0.42,
            "clouds": 0.22,
            "clear": 0.10,
        }

        # Pick the closest key via substring match.
        delay_probability = 0.25
        for key, value in prob_map.items():
            if key in main:
                delay_probability = value
                break

        risk_level = "low"
        if delay_probability >= 0.6:
            risk_level = "high"
        elif delay_probability >= 0.3:
            risk_level = "medium"

        reason = (
            f"Weather is {weather.get('main')} ({description}). "
            f"Using typical conditions for {context.get('travel_phase')} during "
            f"{context.get('time_of_day')}, delay risk is {risk_level}."
        )

        return {
            "delay_probability": delay_probability,
            "risk_level": risk_level,
            "reason": reason,
        }

    def predict_delay(self, trip, context):

        # 🔥 HANDLE BOTH dict + object
        if isinstance(trip, dict):
            origin = trip.get("origin")
        else:
            origin = trip.origin

        # 🌦️ Real weather
        weather = self.weather_api.get_weather(origin)

        heuristic = self._heuristic_delay(weather=weather, context=context)
        heuristic["weather"] = weather

        # Only call Groq when explicitly enabled OR heuristic can't classify well.
        if self.client is None:
            return heuristic

        main = (weather.get("main") or "").lower()
        known_weather = any(k in main for k in ["thunderstorm", "tornado", "drizzle", "rain", "snow", "mist", "fog", "clouds", "clear"])
        if known_weather and heuristic["risk_level"] in ("low", "medium", "high"):
            return heuristic

        # Fallback to Groq for unknown/edge weather.
        prompt = f"""
You are an AI system predicting flight delays.

INPUT:
- Weather: {weather}
- Time of Day: {context['time_of_day']}
- Travel Phase: {context['travel_phase']}

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
                {"role": "user", "content": prompt},
            ],
        )
        raw_output = response.choices[0].message.content.strip()

        import json

        try:
            parsed = json.loads(raw_output)
        except Exception:
            cleaned = raw_output.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)

        parsed["weather"] = weather
        return parsed