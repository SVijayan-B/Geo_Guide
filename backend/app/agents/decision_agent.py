import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DecisionAgent:

    def __init__(self):
        # Cost optimization: heuristics first, Groq only when enabled.
        api_key = os.getenv("GROQ_API_KEY")
        self.use_groq = os.getenv("USE_GROQ_DECISION", "0") == "1"
        self.client = Groq(api_key=api_key) if (self.use_groq and api_key) else None

        # Optional: make model configurable
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

    def _heuristic_decision(self, context, recommendations, disruption) -> dict:
        delay_prob = float(disruption.get("delay_probability") or 0.0)
        risk_level = disruption.get("risk_level") or "low"
        top_reco = None
        try:
            if recommendations and isinstance(recommendations, list):
                top_reco = recommendations[0].get("name")
        except Exception:
            top_reco = None

        if delay_prob > 0.5:
            rebooking_required = True
            decision = "Potential delay detected"
            action = "Consider rebooking or keeping a flexible plan; check alternative options."
        else:
            rebooking_required = False
            decision = "Plan looks stable"
            action = "Proceed with the original plan and focus on the top recommended experience."

        reason = (
            f"Delay probability is {delay_prob:.2f} with risk level '{risk_level}'. "
            f"{'Top recommendation: ' + top_reco + '.' if top_reco else ''}"
        ).strip()

        return {
            "decision": decision,
            "reason": reason,
            "action": action,
            "rebooking_required": rebooking_required,
        }

    def make_decision(self, context, recommendations, disruption):
        heuristic = self._heuristic_decision(context, recommendations, disruption)
        if self.client is None:
            return heuristic

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

        # If Groq parsing fails, return heuristic (never crash the pipeline).
        if isinstance(parsed_output, dict) and "decision" in parsed_output:
            return parsed_output
        return heuristic