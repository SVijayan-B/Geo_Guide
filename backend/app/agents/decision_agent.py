import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DecisionAgent:

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")

        self.client = Groq(api_key=api_key)

        # Optional: make model configurable
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    def make_decision(self, context, recommendations, disruption):
        prompt = f"""
        You are an intelligent travel assistant.

        CONTEXT:
        {context}

        RECOMMENDATIONS:
        {recommendations}

        DISRUPTION ANALYSIS:
        {disruption}

        TASK:
        1. If delay_probability > 0.5 → suggest rebooking
        2. Otherwise → suggest best experience
        3. Give clear action

        Respond ONLY in JSON:
        {{
            "decision": "...",
            "reason": "...",
            "action": "...",
            "rebooking_required": true/false
        }}
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a smart travel decision-making AI agent."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        raw_output = response.choices[0].message.content.strip()

        # 🔥 JSON PARSING (PRODUCTION SAFE)
        try:
            parsed_output = json.loads(raw_output)

        except json.JSONDecodeError:
            # Handle cases like ```json ... ```
            cleaned = raw_output.replace("```json", "").replace("```", "").strip()

            try:
                parsed_output = json.loads(cleaned)
            except:
                # अंतिम fallback (never crash system)
                parsed_output = {
                    "decision": "Unable to parse decision",
                    "reason": raw_output,
                    "action": "Retry or check system logs"
                }

        return parsed_output