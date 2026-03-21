import asyncio
from typing import Optional, Any, Dict

from sqlalchemy.orm import Session

from app.agents.vision_agent import VisionAgent
from app.agents.vision_classifier import VisionClassifier
from app.agents.place_agent import PlaceAgent
from app.agents.price_agent import PriceAgent
from app.agents.deal_agent import DealAgent
from app.services.currency_service import CurrencyService
from app.services.recommendation_service import RecommendationService
from app.services.routing_service import RoutingService
from app.services.currency_detection_service import CurrencyDetectionService
from app.services.cache_service import CacheService
from app.services.chat_memory_service import ChatMemoryService
from app.services.vector_memory_service import VectorMemoryService


class ImagePipelineService:
    async def process_image(
        self,
        *,
        image_path: str,
        city: str,
        home_currency: str,
        destination_currency: Optional[str],
        user_id_int: int,
        session: Any,
        db: Session,
        cache: CacheService,
        cache_key: str,
        chat_memory: ChatMemoryService,
        vector_memory: VectorMemoryService,
    ) -> Dict[str, Any]:
        cached = cache.get(cache_key)
        if cached:
            # Persist cached output into chat history/vector store (best-effort).
            chat_memory.append_message(db, session_id=session.id, role="assistant", content=str(cached))
            vector_memory.add_text(
                user_id=user_id_int,
                session_id=session.id,
                role="assistant",
                text=str(cached),
            )

            map_data = {"routes": cached.get("routes", [])}
            chat_data = {k: v for k, v in cached.items() if k != "routes"}
            return {"chat_data": chat_data, "map_data": map_data, "chat_session_id": session.id, **cached}

        vision = VisionAgent()
        classifier = VisionClassifier()
        vision_output = vision.analyze_image(image_path)
        category = classifier.classify(vision_output)

        currency = CurrencyService()
        currency_detector = CurrencyDetectionService()

        if category == "place":
            place_agent = PlaceAgent()
            explanation = place_agent.explain_place(vision_output["description"])

            response_data = {
                "type": "place",
                "vision": vision_output,
                "explanation": explanation,
            }
            cache.set(cache_key, response_data)

        else:
            price_agent = PriceAgent()
            deal_agent = DealAgent()
            recommendation_service = RecommendationService()
            routing_service = RoutingService()

            price_info = price_agent.estimate_price(vision_output["description"], city=city)
            target_price = price_info["estimated_price"]

            estimate_currency = "INR"
            if isinstance(price_info.get("price_range"), dict):
                estimate_currency = price_info["price_range"].get("currency") or "INR"

            home_currency_norm = currency_detector.detect_home_currency(home_currency)
            dest_currency = (
                destination_currency
                if destination_currency
                else currency_detector.detect_destination_currency(city, fallback=estimate_currency)
            )

            destination_amount = target_price
            if dest_currency and estimate_currency and dest_currency.upper() != estimate_currency.upper():
                converted_dest = currency.convert(
                    amount=target_price,
                    from_currency=estimate_currency,
                    to_currency=dest_currency,
                )
                if converted_dest is not None:
                    destination_amount = converted_dest

            home_amount = currency.convert(
                amount=destination_amount,
                from_currency=dest_currency,
                to_currency=home_currency_norm,
            )

            comparison = f"{destination_amount} {dest_currency} ≈ {home_amount} {home_currency_norm}"

            context = {
                "text": f"Looking for {price_info['product']} in {city}",
                "embedding": [0] * 384,
            }

            recommendations = recommendation_service.recommend(
                context,
                target_price=destination_amount,
            )

            deals = deal_agent.find_best_deals(
                city,
                price_info["product"],
                destination_amount,
            )

            tasks = [
                routing_service.get_route(city, deal["place"]) for deal in deals[:3]
            ]
            route_results = await asyncio.gather(*tasks, return_exceptions=True)

            routes = []
            for deal, route in zip(deals[:3], route_results):
                if isinstance(route, Exception):
                    continue
                routes.append({"to": deal["place"], "route": route})

            response_data = {
                "type": "object",
                "detected": vision_output,
                "product": price_info["product"],
                "price": {
                    "estimated_local": f"{destination_amount} {dest_currency}",
                    "converted": f"{home_amount} {home_currency_norm}",
                    "home_currency": home_currency_norm,
                    "destination_currency": dest_currency,
                    "comparison": comparison,
                },
                "best_places": recommendations[:3],
                "cheaper_options": deals,
                "routes": routes,
            }

            cache.set(cache_key, response_data)

        chat_memory.append_message(
            db,
            session_id=session.id,
            role="assistant",
            content=str(response_data),
        )
        vector_memory.add_text(
            user_id=user_id_int,
            session_id=session.id,
            role="assistant",
            text=str(response_data),
        )

        map_data = {"routes": response_data.get("routes", [])}
        chat_data = {k: v for k, v in response_data.items() if k != "routes"}
        return {"chat_data": chat_data, "map_data": map_data, "chat_session_id": session.id, **response_data}

