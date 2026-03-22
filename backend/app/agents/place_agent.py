from __future__ import annotations

import os


class PlaceAgent:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self.use_groq = os.getenv("USE_GROQ_PLACE_AGENT", "0").strip().lower() in {"1", "true", "yes", "on"}
        self.client = None

        if self.use_groq:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    from groq import Groq

                    self.client = Groq(api_key=api_key)
                except Exception:
                    self.client = None

    def _heuristic_explanation(self, description: str) -> dict[str, object]:
        snippet = (description or "the place").strip()
        facts = [
            "Local architecture and cultural context are key to understanding this location.",
            "Visitor experience changes significantly by time of day and season.",
            "Nearby neighborhoods usually offer the best food and practical travel options.",
        ]
        return {
            "summary": f"This looks like {snippet}. It appears to be a noteworthy place worth exploring.",
            "facts": facts,
            "source": "heuristic",
        }

    def explain_place(self, description: str) -> dict[str, object]:
        heuristic = self._heuristic_explanation(description)
        if self.client is None:
            return heuristic

        prompt = f"""
Identify the likely place from this description and provide concise travel guidance.
Description: {description}

Return strict JSON with:
- summary: string
- facts: string[] (3 items)
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (response.choices[0].message.content or "").strip()

            import json

            try:
                payload = json.loads(raw)
            except Exception:
                cleaned = raw.replace("```json", "").replace("```", "").strip()
                payload = json.loads(cleaned)

            summary = payload.get("summary") or heuristic["summary"]
            facts = payload.get("facts") or heuristic["facts"]
            if not isinstance(facts, list):
                facts = heuristic["facts"]

            return {
                "summary": str(summary),
                "facts": [str(item) for item in facts[:3]],
                "source": "llm",
            }
        except Exception:
            return heuristic
