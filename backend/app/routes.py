from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.auth.auth_service import create_access_token, decode_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt

from app.models.user import User, UserCredential
from app.models.trip import Trip

from app.schemas.user_schema import UserCreate, UserResponse
from app.schemas.trip_schema import TripCreate, TripResponse

from app.services.context_service import ContextService
from app.services.recommendation_service import RecommendationService
from app.services.currency_service import CurrencyService
from app.services.routing_service import RoutingService
from app.services.cache_service import CacheService
from app.services.chat_memory_service import ChatMemoryService
from app.services.vector_memory_service import VectorMemoryService
from app.services.image_pipeline_service import ImagePipelineService

from app.agents.chatbot_agent import ChatbotAgent
from app.agents.vision_agent import VisionAgent
from app.agents.vision_classifier import VisionClassifier
from app.agents.place_agent import PlaceAgent
from app.agents.price_agent import PriceAgent
from app.agents.deal_agent import DealAgent
from app.agents.disruption_agent import DisruptionAgent

from app.graph.agent_graph import build_graph

from jose import jwt
import os
import asyncio

router = APIRouter()
security = HTTPBearer()


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

    # If a password is provided, store a bcrypt hash in a dedicated credentials table.
    # This keeps the existing `users` schema compatible with earlier deployments.
    if user.password:
        password_hash = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        cred = UserCredential(user_id=new_user.id, password_hash=password_hash)
        db.add(cred)
        db.commit()

    return new_user

@router.post("/login")
def login(email: str, password: str | None = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    credential = db.query(UserCredential).filter(UserCredential.user_id == user.id).first()

    # Secure path: password is provided and we verify against stored bcrypt hash.
    if password is not None:
        if not credential:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        ok = bcrypt.checkpw(password.encode("utf-8"), credential.password_hash.encode("utf-8"))
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid credentials")

    # Backward-compatible legacy path:
    # - If no password is supplied and no credential exists (older accounts), allow token issuance.
    # - If a credential exists but password is missing, require password (prevents insecure logins).
    else:
        if credential:
            raise HTTPException(status_code=401, detail="Password required")

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

    result = graph.invoke({
        # Keep `trip` JSON-serializable for API responses.
        "trip": {
            "id": str(trip.id),
            "user_id": str(trip.user_id),
            "origin": trip.origin,
            "destination": trip.destination,
            "status": trip.status,
        },
        "user_id": user_id,
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
    home_currency: str = Header(default="INR", alias="X-Home-Currency"),
    destination_currency: str | None = None,
    chat_session_id: int | None = None,
    new_chat: bool = False,
    title: str | None = None,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    chatbot = ChatbotAgent()
    cache = CacheService()
    chat_memory = ChatMemoryService()
    vector_memory = VectorMemoryService()

    if query is None and image_path is None:
        raise HTTPException(status_code=400, detail="Provide `query` or `image_path`.")

    user_id_int = int(user_id)
    session = None
    if new_chat or chat_session_id is not None:
        # Fetch existing or create new based on `new_chat`
        if new_chat:
            session = chat_memory.create_session(db, user_id=user_id_int, title=title or "New chat")
        else:
            try:
                session = chat_memory.get_or_create_session(
                    db, user_id=user_id_int, chat_session_id=chat_session_id
                )
            except ValueError:
                raise HTTPException(status_code=404, detail="Chat session not found")

    # 🖼️ IMAGE FLOW
    if image_path:
        # If session wasn't created for this request yet, create one (we don't change response shape).
        if session is None:
            session = chat_memory.get_or_create_session(
                db,
                user_id=user_id_int,
                chat_session_id=chat_session_id,
                title=title or f"Image chat: {city}",
            )

        cache_key = f"image:{image_path}"
        image_service = ImagePipelineService()
        return await image_service.process_image(
            image_path=image_path,
            city=city,
            home_currency=home_currency,
            destination_currency=destination_currency,
            user_id_int=user_id_int,
            session=session,
            db=db,
            cache=cache,
            cache_key=cache_key,
            chat_memory=chat_memory,
            vector_memory=vector_memory,
        )

    # 💬 NORMAL CHAT
    # 💬 NORMAL CHAT
    if session is None:
        session = chat_memory.get_or_create_session(
            db, user_id=user_id_int, chat_session_id=chat_session_id, title=title or "Chat"
        )

    # Store user message
    chat_memory.append_message(db, session_id=session.id, role="user", content=query)
    vector_memory.add_text(
        user_id=user_id_int,
        session_id=session.id,
        role="user",
        text=query,
    )

    latest_trip = (
        db.query(Trip)
        .filter(Trip.user_id == user_id_int)
        .order_by(Trip.id.desc())
        .first()
    )

    context = None
    recommendations = None
    disruption = None

    if latest_trip is not None:
        context_service = ContextService()
        context = context_service.build_context(latest_trip)
        recommendations = RecommendationService().recommend(context)
        disruption = DisruptionAgent().predict_delay(latest_trip, context)

    response = chatbot.chat(
        user_id=user_id_int,
        query=query,
        context=context,
        recommendations=recommendations,
        disruption=disruption,
        session_id=session.id,
        db=db,
    )

    vector_memory.add_text(
        user_id=user_id_int,
        session_id=session.id,
        role="assistant",
        text=response,
    )

    return {
        "chat_data": {"response": response},
        "map_data": {"routes": []},
        "response": response,
        "chat_session_id": session.id,
    }