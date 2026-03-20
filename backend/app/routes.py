from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.auth.auth_service import create_access_token, decode_token
from fastapi import Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.user import User
from app.models.trip import Trip

from app.schemas.user_schema import UserCreate, UserResponse
from app.schemas.trip_schema import TripCreate, TripResponse

from app.services.context_service import ContextService
from app.services.recommendation_service import RecommendationService
from app.services.currency_service import CurrencyService
from app.services.routing_service import RoutingService
from app.services.cache_service import CacheService

from app.agents.chatbot_agent import ChatbotAgent
from app.agents.vision_agent import VisionAgent
from app.agents.vision_classifier import VisionClassifier
from app.agents.place_agent import PlaceAgent
from app.agents.price_agent import PriceAgent
from app.agents.deal_agent import DealAgent

from app.graph.agent_graph import build_graph

from jose import jwt
import os
import asyncio

router = APIRouter()
security = HTTPBearer()
SECRET_KEY = "supersecret"
ALGORITHM = "HS256"


# ------------------------
# AUTH HELPER
# ------------------------
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        token = credentials.credentials  # 🔥 auto extracts Bearer token
        payload = decode_token(token)

        return payload["user_id"]

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
# ------------------------
# HEALTH CHECK
# ------------------------
@router.get("/health")
def health_check():
    return {"status": "ok"}


# ------------------------
# CREATE USER
# ------------------------
@router.post("/create-user", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user = User(name=user.name, email=user.email)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

@router.post("/login")
def login(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token({
        "user_id": str(user.id)
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }

# ------------------------
# CREATE TRIP (SECURED 🔥)
# ------------------------
@router.post("/create-trip", response_model=TripResponse)
def create_trip(
    trip: TripCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    new_trip = Trip(
        user_id=user_id,  # 🔥 from token
        origin=trip.origin,
        destination=trip.destination
    )

    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)

    return {
        "id": str(new_trip.id),
        "user_id": str(new_trip.user_id),
        "origin": new_trip.origin,
        "destination": new_trip.destination,
        "status": new_trip.status
    }


# ------------------------
# GET CONTEXT (SECURED)
# ------------------------
@router.get("/trip-context/{trip_id}")
def get_trip_context(
    trip_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == user_id
    ).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    context_service = ContextService()
    return context_service.build_context(trip)


# ------------------------
# MAIN AI PIPELINE (LangGraph)
# ------------------------
@router.get("/recommend/{trip_id}")
async def recommend_places(
    trip_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user)
):
    trip = db.query(Trip).filter(
        Trip.id == trip_id,
        Trip.user_id == user_id
    ).first()

    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    graph = build_graph()

    # 🔥 FIX: pass full object (no dict issues)
    result = graph.invoke({
        "trip": trip
    })

    return result


# ------------------------
# CHAT + IMAGE (MULTIMODAL AI 🔥)
# ------------------------
@router.post("/chat")
async def chat_with_ai(
    query: str = None,
    image_path: str = None,
    city: str = "Chennai",
    user_id: str = Depends(get_current_user)
):
    chatbot = ChatbotAgent()
    cache = CacheService()

    # 🖼️ IMAGE FLOW
    if image_path:
        cache_key = f"image:{image_path}"
        cached = cache.get(cache_key)

        if cached:
            return cached

        vision = VisionAgent()
        classifier = VisionClassifier()
        place_agent = PlaceAgent()
        price_agent = PriceAgent()
        deal_agent = DealAgent()
        currency = CurrencyService()
        recommendation_service = RecommendationService()
        routing_service = RoutingService()

        vision_output = vision.analyze_image(image_path)
        category = classifier.classify(vision_output)

        # 🏛️ PLACE
        if category == "place":
            explanation = place_agent.explain_place(
                vision_output["description"]
            )

            response_data = {
                "type": "place",
                "vision": vision_output,
                "explanation": explanation
            }

            cache.set(cache_key, response_data)
            return response_data

        # 🛒 OBJECT
        price_info = price_agent.estimate_price(
            vision_output["description"]
        )

        target_price = price_info["estimated_price"]

        converted_price = currency.convert(
            amount=target_price,
            from_currency="INR",
            to_currency="USD"
        )

        context = {
            "text": f"Looking for {price_info['product']} in {city}",
            "embedding": [0] * 384
        }

        recommendations = recommendation_service.recommend(
            context,
            target_price=target_price
        )

        deals = deal_agent.find_best_deals(
            city,
            price_info["product"],
            target_price
        )

        # 🗺️ ASYNC ROUTING
        tasks = [
            routing_service.get_route(city, deal["place"])
            for deal in deals[:3]
        ]

        route_results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

        routes = []

        for deal, route in zip(deals[:3], route_results):
            if isinstance(route, Exception):
                continue

            routes.append({
                "to": deal["place"],
                "route": route
            })

        response_data = {
            "type": "object",
            "detected": vision_output,
            "product": price_info["product"],
            "price": {
                "estimated_local": f"{target_price} INR",
                "converted": f"{converted_price} USD"
            },
            "best_places": recommendations[:3],
            "cheaper_options": deals,
            "routes": routes
        }

        cache.set(cache_key, response_data)
        return response_data

    # 💬 NORMAL CHAT
    response = chatbot.chat(
        user_id=user_id,
        query=query
    )

    return {"response": response}