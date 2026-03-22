from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from dotenv import load_dotenv

load_dotenv()


class LLMProvider(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        ...


@dataclass
class EchoFallbackProvider:
    """Deterministic fallback used when no external provider is available."""

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        _ = (system_prompt, model)
        return user_prompt


class GroqProvider:
    def __init__(self) -> None:
        from groq import Groq

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured")
        self._client = Groq(api_key=api_key)

    def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> str:
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        return content or ""


def get_default_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider == "groq":
        try:
            return GroqProvider()
        except Exception:
            return EchoFallbackProvider()
    return EchoFallbackProvider()
