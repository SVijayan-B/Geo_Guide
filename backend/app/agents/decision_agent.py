from __future__ import annotations

import json
import os

from dotenv import load_dotenv

load_dotenv()


class DecisionAgent:
    def __init__(self):
        self.use_groq = os.getenv("USE_GROQ_DECISION", "0") == "1"
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self.client = None

        if self.use_groq:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    from groq import Groq

                    self.client = Groq(api_key=api_key)
                except Exception:
                    self.client = None

    def _heuristic_decision(self, context, recommendations, disruption) -> dict:
        _ = context
        delay_prob = float((disruption or {}).get("delay_probability") or 0.0)
        risk_level = (disruption or {}).get("risk_level") or "low"
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
1. If delay_probability > 0.5 suggest rebooking.
2. Otherwise suggest the best experience.
3. Give one clear action.

Respond ONLY in JSON:
{{
  "decision": "...",
  "reason": "...",
  "action": "...",
  "rebooking_required": true
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a smart travel decision-making AI agent."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw_output = (response.choices[0].message.content or "").strip()
            try:
                parsed_output = json.loads(raw_output)
            except json.JSONDecodeError:
                cleaned = raw_output.replace("```json", "").replace("```", "").strip()
                parsed_output = json.loads(cleaned)

            if isinstance(parsed_output, dict) and "decision" in parsed_output:
                return parsed_output
            return heuristic
        except Exception:
            return heuristic
