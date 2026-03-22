from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.orm import Session

from app.agents.deal_agent import DealAgent
from app.agents.place_agent import PlaceAgent
from app.agents.price_agent import PriceAgent
from app.agents.vision_agent import VisionAgent
from app.agents.vision_classifier import VisionClassifier
from app.services.cache_service import CacheService
from app.services.chat_memory_service import ChatMemoryService
from app.services.currency_detection_service import CurrencyDetectionService
from app.services.currency_service import CurrencyService
from app.services.recommendation_service import RecommendationService
from app.services.routing_service import RoutingService
from app.services.vector_memory_service import VectorMemoryService


class ImagePipelineService:
    async def process_image(
        self,
        *,
        image_path: str,
        city: str,
        home_currency: str,
        destination_currency: str | None,
        user_id_int: int,
        session: Any,
        db: Session,
        cache: CacheService,
        cache_key: str,
        chat_memory: ChatMemoryService,
        vector_memory: VectorMemoryService,
    ) -> dict[str, Any]:
        cached = cache.get(cache_key)
        if cached:
            chat_memory.append_message(db, session_id=session.id, role="assistant", content=str(cached))
            vector_memory.add_text(user_id=user_id_int, session_id=session.id, role="assistant", text=str(cached))
            return {
                "chat_data": cached.get("chat_data", {}),
                "map_data": cached.get("map_data", {"routes": []}),
                "chat_session_id": session.id,
                **cached,
            }

        vision_output = VisionAgent().analyze_image(image_path)
        category = VisionClassifier().classify(vision_output)

        currency_service = CurrencyService()
        currency_detector = CurrencyDetectionService()
        recommendation_service = RecommendationService()
        routing_service = RoutingService()

        home_currency_norm = currency_detector.detect_home_currency(home_currency)
        destination_currency_norm = destination_currency or currency_detector.detect_destination_currency(city, fallback="INR")

        if category == "place":
            place_info = PlaceAgent().explain_place(vision_output.get("description", ""))

            recommendation_payload = recommendation_service.recommend(
                mode="in_destination",
                destination=city,
                days=1,
                traveler_type="explorer",
                image_context=vision_output.get("description"),
            )

            place_name = (vision_output.get("objects") or [city])[0]
            vector_memory.add_viewed_place(
                user_id=user_id_int,
                place_name=str(place_name),
                city=city,
                details=place_info.get("summary") if isinstance(place_info, dict) else str(place_info),
            )

            chat_data = {
                "type": "place",
                "vision": vision_output,
                "explanation": place_info.get("summary") if isinstance(place_info, dict) else str(place_info),
                "facts": place_info.get("facts", []) if isinstance(place_info, dict) else [],
                "recommendations": recommendation_payload.get("recommendations", []),
                "context_awareness": {"city": city, "memory_written": True},
            }
            map_data = {"routes": []}

        else:
            price_info = PriceAgent().estimate_price(vision_output.get("description", ""), city=city)
            product = price_info.get("product", "item")
            price_range = price_info.get("price_range") or {}
            estimated_price = float(price_info.get("estimated_price") or 0)
            source_currency = price_range.get("currency") or "INR"

            comparison = currency_service.compare_home_and_destination(
                amount=estimated_price,
                source_currency=source_currency,
                home_currency=home_currency_norm,
                destination_currency=destination_currency_norm,
            )
            target_destination_amount = comparison.get("amount_in_destination") or estimated_price

            recommendation_payload = recommendation_service.recommend(
                mode="in_destination",
                destination=city,
                days=1,
                budget=float(target_destination_amount),
                traveler_type="value_seeker",
                image_context=f"Affordable alternatives for {product}",
            )

            deals = DealAgent().find_best_deals(city, product, float(target_destination_amount))
            route_jobs = [routing_service.get_route(city, f"{deal.get('place')}, {city}") for deal in deals[:3]]
            route_results = await asyncio.gather(*route_jobs, return_exceptions=True)

            routes = []
            for deal, route in zip(deals[:3], route_results):
                if isinstance(route, Exception):
                    continue
                routes.append({"to": deal.get("place"), "route": route})

            vector_memory.add_preference(
                user_id=user_id_int,
                preference_text=f"User looked at {product} in {city} with destination budget {target_destination_amount}",
                source="image",
            )

            chat_data = {
                "type": "object",
                "vision": vision_output,
                "product": product,
                "price": {
                    "estimated_source": f"{estimated_price:.2f} {source_currency}",
                    "estimated_destination": f"{comparison.get('amount_in_destination')} {comparison.get('destination_currency')}",
                    "estimated_home": (
                        f"{comparison.get('amount_in_home')} {comparison.get('home_currency')}"
                        if comparison.get("amount_in_home") is not None
                        else None
                    ),
                    "comparison": comparison,
                    "normalization_source": price_info.get("source"),
                },
                "recommendations": recommendation_payload.get("recommendations", []),
                "cheaper_options": deals,
                "context_awareness": {"city": city, "memory_written": True},
            }
            map_data = {"routes": routes}

        response_data = {
            "chat_data": chat_data,
            "map_data": map_data,
            "type": chat_data.get("type"),
        }
        cache.set(cache_key, response_data)

        chat_memory.append_message(db, session_id=session.id, role="assistant", content=str(response_data))
        vector_memory.add_text(user_id=user_id_int, session_id=session.id, role="assistant", text=str(response_data))

        return {
            **response_data,
            "chat_session_id": session.id,
        }
