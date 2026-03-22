from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class RecommendationService:
    _model: SentenceTransformer | None = None

    def __init__(self):
        if RecommendationService._model is None:
            RecommendationService._model = SentenceTransformer("all-MiniLM-L6-v2")
        self.model = RecommendationService._model

    def _catalog_for_city(self, city: str | None) -> list[dict[str, Any]]:
        city_name = (city or "destination").strip()
        return [
            {
                "name": f"{city_name} Street Food Trail",
                "description": "authentic local flavors, quick bites, casual dining",
                "avg_price": 180,
                "tags": ["food", "street", "quick", "afternoon", "evening", "budget"],
            },
            {
                "name": f"{city_name} Heritage Walk",
                "description": "historic neighborhoods, architecture, storytelling with local guides",
                "avg_price": 350,
                "tags": ["culture", "history", "walking", "morning", "afternoon"],
            },
            {
                "name": f"{city_name} Panorama Rooftop",
                "description": "sunset skyline views and premium lounge experience",
                "avg_price": 1400,
                "tags": ["premium", "night", "romantic", "evening", "view"],
            },
            {
                "name": f"{city_name} Market Explorer",
                "description": "shopping district, craft stores, hidden budget deals",
                "avg_price": 600,
                "tags": ["shopping", "family", "afternoon", "budget", "local"],
            },
            {
                "name": f"{city_name} Nature Escape",
                "description": "parks and scenic outdoor trails for a relaxed half-day",
                "avg_price": 250,
                "tags": ["nature", "outdoor", "morning", "afternoon", "family"],
            },
            {
                "name": f"{city_name} Nightlife Circuit",
                "description": "music venues and lively nightlife around top districts",
                "avg_price": 1200,
                "tags": ["nightlife", "music", "night", "evening", "premium"],
            },
        ]

    def _extract_budget(self, text: str) -> float | None:
        if not text:
            return None
        match = re.search(r"(?:budget|under|within|max)\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)", text, re.IGNORECASE)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except Exception:
            return None

    def _time_tags(self, time_of_day: str | None) -> set[str]:
        tod = (time_of_day or "").lower()
        if tod == "morning":
            return {"morning", "breakfast", "walking"}
        if tod == "afternoon":
            return {"afternoon", "quick", "family", "shopping"}
        if tod == "evening":
            return {"evening", "dinner", "sunset"}
        if tod == "night":
            return {"night", "nightlife", "music"}
        return set()

    def _mode_weights(self, mode: str) -> dict[str, float]:
        mode = (mode or "pre_trip_plan").lower()
        if mode == "delay_mode":
            return {"semantic": 0.35, "memory": 0.20, "budget": 0.30, "time": 0.15}
        if mode == "in_destination":
            return {"semantic": 0.50, "memory": 0.20, "budget": 0.20, "time": 0.10}
        return {"semantic": 0.45, "memory": 0.25, "budget": 0.20, "time": 0.10}

    def _normalized_budget_score(self, avg_price: float, target_budget: float | None) -> float:
        if not target_budget or target_budget <= 0:
            return 0.6
        diff = abs(avg_price - target_budget)
        scale = max(target_budget, 1.0)
        return max(0.0, 1.0 - min(1.0, diff / scale))

    def _build_plan(
        self,
        *,
        destination: str | None,
        days: int,
        ranked: list[dict[str, Any]],
        mode: str,
        budget: float | None,
    ) -> list[dict[str, Any]]:
        if not ranked:
            return []
        total_days = max(1, min(21, int(days or 1)))
        plans = []
        for idx in range(total_days):
            slot = ranked[idx % len(ranked)]
            plans.append(
                {
                    "day": idx + 1,
                    "city": destination,
                    "focus": slot["name"],
                    "budget_split": {
                        "food": round((budget or slot["price"] * 2) * 0.35, 2),
                        "transport": round((budget or slot["price"] * 2) * 0.25, 2),
                        "activities": round((budget or slot["price"] * 2) * 0.40, 2),
                    },
                    "mode": mode,
                }
            )
        return plans

    def recommend(
        self,
        context: dict[str, Any] | None = None,
        target_price: float | None = None,
        memory_docs: list[dict[str, Any]] | None = None,
        *,
        mode: str = "pre_trip_plan",
        origin: str | None = None,
        destination: str | None = None,
        days: int = 3,
        budget: float | None = None,
        traveler_type: str = "foodie",
        user_lat: float | None = None,
        user_lon: float | None = None,
        image_context: str | None = None,
        user_preferences: str | None = None,
    ) -> dict[str, Any]:
        _ = (origin, user_lat, user_lon)
        context = context or {}
        mode = (mode or context.get("mode") or "pre_trip_plan").lower()

        destination = destination or context.get("destination") or "destination"
        time_of_day = context.get("time_of_day") or datetime.now().strftime("%p").lower()
        context_text = context.get("text") or image_context or f"Plan trip for {destination} as a {traveler_type} traveler"

        memory_docs = memory_docs or []
        memory_text = " ".join(
            [d.get("document", "") for d in memory_docs if isinstance(d, dict) and d.get("document")]
        )[:4000]
        if user_preferences:
            memory_text = f"{memory_text} {user_preferences}".strip()

        derived_budget = budget if budget is not None else target_price
        if derived_budget is None:
            derived_budget = self._extract_budget(memory_text or context_text)

        places = self._catalog_for_city(destination)
        context_vector = context.get("embedding")
        if not context_vector or not isinstance(context_vector, list):
            context_vector = self.model.encode(context_text).tolist()
        memory_vector = self.model.encode(memory_text).tolist() if memory_text else None
        desired_tags = self._time_tags(time_of_day)
        weights = self._mode_weights(mode)

        ranked: list[dict[str, Any]] = []
        for place in places:
            tag_text = " ".join(place.get("tags", []))
            place_text = f"{place.get('description', '')} {tag_text}".strip()
            place_vector = self.model.encode(place_text).tolist()

            semantic_score = float(cosine_similarity([context_vector], [place_vector])[0][0])
            memory_score = 0.0
            if memory_vector is not None:
                memory_score = float(cosine_similarity([memory_vector], [place_vector])[0][0])

            budget_score = self._normalized_budget_score(place["avg_price"], derived_budget)
            tag_overlap = len(desired_tags.intersection({t.lower() for t in place.get("tags", [])}))
            time_score = min(1.0, tag_overlap / max(len(desired_tags), 1)) if desired_tags else 0.6

            final_score = (
                semantic_score * weights["semantic"]
                + memory_score * weights["memory"]
                + budget_score * weights["budget"]
                + time_score * weights["time"]
            )

            ranked.append(
                {
                    "name": place["name"],
                    "score": round(float(final_score), 4),
                    "price": float(place["avg_price"]),
                    "tags": place.get("tags", []),
                    "why": (
                        f"Matches {traveler_type} interests, {time_of_day} timing, "
                        f"and budget target {derived_budget if derived_budget is not None else 'flexible'}."
                    ),
                    "semantic_score": round(semantic_score, 4),
                    "memory_score": round(memory_score, 4),
                    "budget_score": round(budget_score, 4),
                    "time_score": round(time_score, 4),
                }
            )

        ranked.sort(key=lambda item: item["score"], reverse=True)
        ranked = ranked[:5]

        alternate_flight_message = None
        if mode == "delay_mode":
            alternate_flight_message = "Potential delay risk detected. Keep buffer time and consider flexible bookings."

        plans = self._build_plan(
            destination=destination,
            days=days,
            ranked=ranked,
            mode=mode,
            budget=derived_budget,
        )

        return {
            "mode": mode,
            "recommendations": ranked,
            "plans": plans,
            "alternate_flight_message": alternate_flight_message,
            "input_signals": {
                "destination": destination,
                "traveler_type": traveler_type,
                "budget": derived_budget,
                "memory_tokens": int(math.ceil(len(memory_text) / 4)) if memory_text else 0,
            },
        }
