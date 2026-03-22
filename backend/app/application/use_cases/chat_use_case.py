from __future__ import annotations

import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agents.chatbot_agent import ChatbotAgent
from app.agents.disruption_agent import DisruptionAgent
from app.application.dto.travel import ChatRequestDTO
from app.application.use_cases.autopilot_use_case import AutopilotUseCase
from app.models.trip import Trip
from app.services.cache_service import CacheService
from app.services.chat_memory_service import ChatMemoryService
from app.services.context_service import ContextService
from app.services.currency_detection_service import CurrencyDetectionService
from app.services.currency_service import CurrencyService
from app.services.image_pipeline_service import ImagePipelineService
from app.services.recommendation_service import RecommendationService
from app.services.vector_memory_service import VectorMemoryService

BASE_PRICE_CURRENCY = "INR"


class ChatUseCase:
    def __init__(self) -> None:
        self.chatbot = ChatbotAgent()
        self.cache = CacheService()
        self.chat_memory = ChatMemoryService()
        self.vector_memory = VectorMemoryService()
        self.currency_detector = CurrencyDetectionService()
        self.currency_service = CurrencyService()
        self.recommendation_service = RecommendationService()
        self.autopilot = AutopilotUseCase()

    def _is_nearby_query(self, query: str | None) -> bool:
        if not query:
            return False
        q = query.lower()
        tokens = ("near me", "nearby", "around me", "here", "closest", "near by")
        return any(t in q for t in tokens)

    def _safe_amount(self, value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None

    def _derive_user_preferences(self, memory_docs: list[dict[str, Any]]) -> str | None:
        snippets = []
        for doc in memory_docs:
            metadata = doc.get("metadata") or {}
            memory_type = metadata.get("memory_type")
            if memory_type in {"preference", "viewed_place"} and doc.get("document"):
                snippets.append(str(doc.get("document")))
        if not snippets:
            return None
        return " | ".join(snippets[:5])

    def _extract_preference_from_query(self, query: str | None) -> str | None:
        if not query:
            return None
        pattern = re.search(r"\b(i like|i prefer|my preference is)\b(.+)", query, re.IGNORECASE)
        if not pattern:
            return None
        return query.strip()

    def _enrich_prices_with_currency(
        self,
        payload: dict[str, Any] | None,
        *,
        home_currency: str,
        destination_currency: str,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return payload

        recommendations = payload.get("recommendations")
        if isinstance(recommendations, list):
            for rec in recommendations:
                if not isinstance(rec, dict):
                    continue
                amount = self._safe_amount(rec.get("price"))
                if amount is None:
                    continue

                comparison = self.currency_service.compare_home_and_destination(
                    amount=amount,
                    source_currency=BASE_PRICE_CURRENCY,
                    home_currency=home_currency,
                    destination_currency=destination_currency,
                )
                rec["price"] = comparison.get("amount_in_destination")
                rec["price_currency"] = comparison.get("destination_currency")
                rec["price_home"] = comparison.get("amount_in_home")
                rec["home_currency"] = comparison.get("home_currency")

        payload["destination_currency"] = destination_currency
        payload["home_currency"] = home_currency
        payload["base_price_currency"] = BASE_PRICE_CURRENCY
        return payload

    def _resolve_active_trip(self, db: Session, *, user_id: int, trip_id: int | None) -> Trip | None:
        active_trip = None
        if trip_id is not None:
            try:
                active_trip = (
                    db.query(Trip)
                    .filter(Trip.id == int(trip_id), Trip.user_id == int(user_id))
                    .first()
                )
            except Exception:
                active_trip = None

        if active_trip is None:
            active_trip = (
                db.query(Trip)
                .filter(Trip.user_id == int(user_id))
                .order_by(Trip.id.desc())
                .first()
            )
        return active_trip

    async def handle_chat(
        self,
        *,
        db: Session,
        user_id: int,
        request: ChatRequestDTO,
        home_currency: str,
    ) -> dict[str, Any]:
        if request.query is None and request.image_path is None:
            raise ValueError("Provide `query` or `image_path`.")

        session = None
        if request.new_chat or request.chat_session_id is not None:
            if request.new_chat:
                session = self.chat_memory.create_session(db, user_id=user_id, title=request.title or "New chat")
            else:
                session = self.chat_memory.get_or_create_session(
                    db, user_id=user_id, chat_session_id=request.chat_session_id
                )

        if request.image_path:
            if session is None:
                session = self.chat_memory.get_or_create_session(
                    db,
                    user_id=user_id,
                    chat_session_id=request.chat_session_id,
                    title=request.title or f"Image chat: {request.city}",
                )

            image_hash = hashlib.sha1(request.image_path.encode("utf-8", errors="ignore")).hexdigest()
            cache_key = f"image:{user_id}:{image_hash}"
            home_currency_norm = self.currency_detector.detect_home_currency(home_currency)
            destination_currency_norm = (
                request.destination_currency
                or self.currency_detector.detect_destination_currency(
                    request.city,
                    fallback=BASE_PRICE_CURRENCY,
                )
            )
            return await ImagePipelineService().process_image(
                image_path=request.image_path,
                city=request.city,
                home_currency=home_currency_norm,
                destination_currency=destination_currency_norm,
                user_id_int=user_id,
                session=session,
                db=db,
                cache=self.cache,
                cache_key=cache_key,
                chat_memory=self.chat_memory,
                vector_memory=self.vector_memory,
            )

        if session is None:
            session = self.chat_memory.get_or_create_session(
                db, user_id=user_id, chat_session_id=request.chat_session_id, title=request.title or "Chat"
            )

        user_query = request.query or ""
        self.chat_memory.append_message(db, session_id=session.id, role="user", content=user_query)
        self.vector_memory.add_text(
            user_id=user_id,
            session_id=session.id,
            role="user",
            text=user_query,
        )

        preference_signal = self._extract_preference_from_query(user_query)
        if preference_signal:
            self.vector_memory.add_preference(user_id=user_id, preference_text=preference_signal, source="chat")

        active_trip = self._resolve_active_trip(db, user_id=user_id, trip_id=request.trip_id)

        context_service = ContextService()
        if active_trip is not None:
            context = context_service.build_context(active_trip)
            self.vector_memory.add_trip_snapshot(
                user_id=user_id,
                trip_id=int(active_trip.id),
                origin=active_trip.origin,
                destination=active_trip.destination,
                status=active_trip.status,
            )
        else:
            context = context_service.build_query_context(query=user_query, city=request.city)

        memory_docs = self.vector_memory.query_similar(
            user_id=user_id,
            query_text=user_query or context.get("text", ""),
            k=8,
            memory_types=["chat", "preference", "trip", "viewed_place"],
        )
        user_preferences = self._derive_user_preferences(memory_docs)

        resolved_mode = request.mode
        if request.is_user_at_airport and request.flight_delayed:
            resolved_mode = "delay_mode"
        elif self._is_nearby_query(user_query):
            resolved_mode = "in_destination"

        target_destination = request.city or context.get("destination")
        if active_trip is not None:
            nearby_query = self._is_nearby_query(user_query)
            if nearby_query and request.mode != "in_destination":
                target_destination = active_trip.origin or request.city or active_trip.destination
            elif resolved_mode in ("pre_trip_plan", "delay_mode"):
                target_destination = active_trip.origin or request.city or active_trip.destination
            else:
                target_destination = request.city or active_trip.destination

        recommendation_payload = self.recommendation_service.recommend(
            context=context,
            memory_docs=memory_docs,
            mode=resolved_mode,
            origin=active_trip.origin if active_trip is not None else None,
            destination=target_destination,
            days=request.days,
            budget=request.budget,
            traveler_type=request.traveler_type,
            user_lat=request.user_lat,
            user_lon=request.user_lon,
            image_context=user_query,
            user_preferences=user_preferences,
        )

        home_currency_norm = self.currency_detector.detect_home_currency(home_currency)
        currency_anchor_city = (
            active_trip.origin if (active_trip is not None and resolved_mode in ("pre_trip_plan", "delay_mode")) else target_destination
        )
        destination_currency_norm = (
            request.destination_currency
            or self.currency_detector.detect_destination_currency(
                currency_anchor_city,
                fallback=BASE_PRICE_CURRENCY,
            )
        )
        recommendation_payload = self._enrich_prices_with_currency(
            recommendation_payload,
            home_currency=home_currency_norm,
            destination_currency=destination_currency_norm,
        ) or {}

        recommendation_payload["trip_id"] = int(active_trip.id) if active_trip is not None else None
        recommendation_payload["trip_origin"] = active_trip.origin if active_trip is not None else None
        recommendation_payload["trip_destination"] = active_trip.destination if active_trip is not None else None
        recommendation_payload["currency_anchor_city"] = currency_anchor_city

        recommendations = recommendation_payload.get("recommendations", [])
        disruption = (
            DisruptionAgent().predict_delay(active_trip, context)
            if active_trip is not None
            else {"delay_probability": 0.0, "risk_level": "low", "reason": "No active trip."}
        )

        if active_trip is not None:
            self.autopilot.trigger_trip_check(trip_id=int(active_trip.id), user_id=user_id)

        response = self.chatbot.chat(
            user_id=user_id,
            query=user_query,
            context=context,
            recommendations=recommendations,
            disruption=disruption,
            session_id=session.id,
            db=db,
            memory="\n".join([d.get("document", "") for d in memory_docs if d.get("document")]),
        )

        self.vector_memory.add_text(
            user_id=user_id,
            session_id=session.id,
            role="assistant",
            text=response,
        )

        explanation_parts = []
        if recommendations:
            top = recommendations[0]
            explanation_parts.append(top.get("why") or f"Top recommendation is {top.get('name')}")
        if disruption.get("reason"):
            explanation_parts.append(str(disruption.get("reason")))

        price_comparison = [
            {
                "name": rec.get("name"),
                "destination_price": rec.get("price"),
                "destination_currency": rec.get("price_currency"),
                "home_price": rec.get("price_home"),
                "home_currency": rec.get("home_currency"),
            }
            for rec in recommendations[:3]
        ]

        chat_data = {
            "response": response,
            "recommendations": recommendations,
            "plans": recommendation_payload.get("plans", []),
            "mode": recommendation_payload.get("mode", request.mode),
            "alternate_flight_message": recommendation_payload.get("alternate_flight_message"),
            "home_currency": recommendation_payload.get("home_currency", home_currency),
            "destination_currency": recommendation_payload.get("destination_currency"),
            "currency_anchor_city": recommendation_payload.get("currency_anchor_city"),
            "explanation": " ".join([part for part in explanation_parts if part]).strip() or None,
            "price_comparison": price_comparison,
            "context_awareness": {
                "memory_hits": len(memory_docs),
                "risk_level": disruption.get("risk_level"),
                "trip_id": recommendation_payload.get("trip_id"),
            },
        }

        response_payload = {
            "chat_data": chat_data,
            "map_data": {"routes": []},
            "response": response,
            "recommendations": recommendations,
            "plans": recommendation_payload.get("plans", []),
            "mode": recommendation_payload.get("mode", request.mode),
            "alternate_flight_message": recommendation_payload.get("alternate_flight_message"),
            "home_currency": recommendation_payload.get("home_currency", home_currency),
            "destination_currency": recommendation_payload.get("destination_currency"),
            "currency_anchor_city": recommendation_payload.get("currency_anchor_city"),
            "trip_id": recommendation_payload.get("trip_id"),
            "chat_session_id": session.id,
        }

        return response_payload
