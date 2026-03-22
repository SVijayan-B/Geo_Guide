from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.agents.memory_agent import MemoryAgent
from app.services.chat_memory_service import ChatMemoryService

load_dotenv()


class ChatbotAgent:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self.use_groq = os.getenv("USE_GROQ_CHATBOT", "1").strip().lower() in {"1", "true", "yes", "on"}
        self.client = None

        if self.use_groq:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    from groq import Groq

                    self.client = Groq(api_key=api_key)
                except Exception:
                    self.client = None

        self.memory = MemoryAgent()

    def _format_history(self, history: list[dict[str, str]]) -> str:
        return "\n".join([f'{msg["role"].upper()}: {msg["content"]}' for msg in history])

    def _should_use_llm(
        self,
        *,
        query: str,
        recommendations: list[dict[str, Any]] | None,
        disruption: dict[str, Any] | None,
    ) -> bool:
        if self.client is None:
            return False
        lowered = (query or "").lower()
        has_complex_intent = any(
            token in lowered for token in ["why", "compare", "itinerary", "explain", "optimize", "strategy"]
        )
        high_risk = (disruption or {}).get("risk_level") == "high"
        few_recommendations = len(recommendations or []) < 2
        return has_complex_intent or high_risk or few_recommendations

    def _heuristic_reply(
        self,
        *,
        query: str,
        context: dict[str, Any] | None,
        recommendations: list[dict[str, Any]] | None,
        disruption: dict[str, Any] | None,
    ) -> str:
        recs = recommendations or []
        top_lines = []
        for idx, rec in enumerate(recs[:3], start=1):
            name = rec.get("name", "Option")
            price = rec.get("price")
            why = rec.get("why")
            price_text = f" (est. {price})" if price is not None else ""
            why_text = f" - {why}" if why else ""
            top_lines.append(f"{idx}. {name}{price_text}{why_text}")

        risk_level = (disruption or {}).get("risk_level", "low")
        delay_probability = (disruption or {}).get("delay_probability")
        delay_text = ""
        if delay_probability is not None:
            try:
                delay_text = f"Delay risk: {float(delay_probability) * 100:.0f}% ({risk_level})."
            except Exception:
                delay_text = f"Delay risk: {risk_level}."
        else:
            delay_text = f"Travel risk level: {risk_level}."

        context_text = (context or {}).get("text") or ""
        context_summary = context_text.strip().replace("\n", " ")[:180]

        parts = [f"You asked: {query}"]
        if top_lines:
            parts.append("Top recommendations:")
            parts.extend(top_lines)
        parts.append(delay_text)
        if context_summary:
            parts.append(f"Context used: {context_summary}")

        parts.append("If you want, I can refine this by budget, time, or travel style.")
        return "\n".join(parts)

    def chat(
        self,
        user_id: int,
        query: str,
        context: dict[str, Any] | None = None,
        recommendations: list[dict[str, Any]] | None = None,
        disruption: dict[str, Any] | None = None,
        session_id: int | None = None,
        db: Session | None = None,
        memory: str | None = None,
    ) -> str:
        if memory is not None:
            history_str = memory
        elif session_id is not None and db is not None:
            history = ChatMemoryService().get_recent_messages(db, session_id=session_id)
            history_str = self._format_history(history)
        else:
            history_str = str(self.memory.get(user_id))

        output = self._heuristic_reply(
            query=query,
            context=context,
            recommendations=recommendations,
            disruption=disruption,
        )

        if self._should_use_llm(query=query, recommendations=recommendations, disruption=disruption):
            prompt = f"""
You are AURA Travel AI.

USER QUERY:
{query}

CONTEXT:
{context}

RECOMMENDATIONS:
{recommendations}

DISRUPTION:
{disruption}

MEMORY:
{history_str}

TASK:
- Keep response concise and actionable.
- Explain why top recommendations are relevant.
- Mention disruption impact only if meaningful.
"""
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a smart travel assistant."},
                        {"role": "user", "content": prompt},
                    ],
                )
                llm_output = (response.choices[0].message.content or "").strip()
                if llm_output:
                    output = llm_output
            except Exception:
                pass

        if session_id is not None and db is not None:
            ChatMemoryService().append_message(db, session_id=session_id, role="assistant", content=output)
        else:
            self.memory.save(user_id, {"query": query, "response": output})

        return output
