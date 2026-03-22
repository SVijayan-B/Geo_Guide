from __future__ import annotations

from datetime import datetime
from typing import Any

from sentence_transformers import SentenceTransformer


class ContextService:
    _model: SentenceTransformer | None = None

    def __init__(self):
        if ContextService._model is None:
            ContextService._model = SentenceTransformer("all-MiniLM-L6-v2")
        self.model = ContextService._model

    def get_time_of_day(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 21:
            return "evening"
        return "night"

    def get_travel_phase(self, status: str | None) -> str:
        if status == "planned":
            return "pre_departure"
        if status == "ongoing":
            return "in_transit"
        if status == "completed":
            return "post_trip"
        return "conversation"

    def _normalize_trip(self, trip: Any) -> dict[str, Any]:
        if isinstance(trip, dict):
            return {
                "origin": trip.get("origin"),
                "destination": trip.get("destination"),
                "status": trip.get("status"),
            }
        return {
            "origin": getattr(trip, "origin", None),
            "destination": getattr(trip, "destination", None),
            "status": getattr(trip, "status", None),
        }

    def build_context(self, trip: Any) -> dict[str, Any]:
        normalized = self._normalize_trip(trip)
        origin = normalized.get("origin")
        destination = normalized.get("destination")
        status = normalized.get("status")

        time_of_day = self.get_time_of_day()
        phase = self.get_travel_phase(status)

        context_text = (
            f"User is traveling from {origin} to {destination}. "
            f"It is {time_of_day}. "
            f"Travel phase is {phase}."
        )

        embedding = self.model.encode(context_text).tolist()
        return {
            "text": context_text,
            "embedding": embedding,
            "time_of_day": time_of_day,
            "travel_phase": phase,
            "origin": origin,
            "destination": destination,
        }

    def build_query_context(self, *, query: str, city: str | None = None) -> dict[str, Any]:
        city_value = city or "destination"
        time_of_day = self.get_time_of_day()
        context_text = (
            f"User query: {query}. "
            f"Current focus city: {city_value}. "
            f"Time of day is {time_of_day}."
        )

        embedding = self.model.encode(context_text).tolist()
        return {
            "text": context_text,
            "embedding": embedding,
            "time_of_day": time_of_day,
            "travel_phase": "conversation",
            "origin": None,
            "destination": city_value,
        }
