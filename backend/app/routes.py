from __future__ import annotations

from typing import Any

import bcrypt
from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.dto.travel import ChatRequestDTO
from app.application.use_cases.auth_use_case import AuthUseCase
from app.application.use_cases.chat_use_case import ChatUseCase
from app.auth.auth_service import decode_token
from app.db.database import get_db
from app.graph.agent_graph import build_graph
from app.models.chat import ChatMessage, ChatSession
from app.models.trip import Trip
from app.models.user import User, UserCredential
from app.schemas.trip_schema import TripCreate, TripResponse
from app.schemas.user_schema import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.services.chat_memory_service import ChatMemoryService
from app.services.context_service import ContextService
from app.services.vector_memory_service import VectorMemoryService

router = APIRouter()
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        return int(payload["user_id"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/create-user", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(name=user.name, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if user.password:
        password_hash = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.add(UserCredential(user_id=new_user.id, password_hash=password_hash))
        db.commit()

    return new_user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest | None = Body(default=None),
    email: str | None = None,
    password: str | None = None,
    db: Session = Depends(get_db),
):
    # Backward compatibility: allow query-parameter auth while supporting JSON body.
    resolved_email = payload.email if payload else email
    resolved_password = payload.password if payload else password

    if not resolved_email:
        raise HTTPException(status_code=422, detail="Email is required")

    user = db.query(User).filter(User.email == resolved_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    credential = db.query(UserCredential).filter(UserCredential.user_id == user.id).first()

    if resolved_password is not None:
        if not credential:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        ok = bcrypt.checkpw(resolved_password.encode("utf-8"), credential.password_hash.encode("utf-8"))
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    else:
        # Legacy path is allowed only if user has no password record.
        if credential:
            raise HTTPException(status_code=401, detail="Password required")

    token_pair = AuthUseCase().login_tokens(db, user_id=int(user.id))
    return token_pair


@router.post("/create-trip", response_model=TripResponse)
def create_trip(
    trip: TripCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    new_trip = Trip(user_id=user_id, origin=trip.origin, destination=trip.destination)
    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)

    VectorMemoryService().add_trip_snapshot(
        user_id=user_id,
        trip_id=int(new_trip.id),
        origin=new_trip.origin,
        destination=new_trip.destination,
        status=new_trip.status,
    )

    return {
        "id": str(new_trip.id),
        "user_id": str(new_trip.user_id),
        "origin": new_trip.origin,
        "destination": new_trip.destination,
        "status": new_trip.status,
    }


@router.get("/trip-context/{trip_id}")
def get_trip_context(
    trip_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return ContextService().build_context(trip)


@router.get("/recommend/{trip_id}")
async def recommend_places(
    trip_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.user_id == user_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip_payload = {
        "id": int(trip.id),
        "user_id": int(trip.user_id),
        "origin": trip.origin,
        "destination": trip.destination,
        "status": trip.status,
    }

    graph = build_graph()
    result = graph.invoke(
        {
            "input": {
                "trip": trip_payload,
                "user_id": int(user_id),
                "query": f"Plan travel for {trip.origin} to {trip.destination}",
                "city": trip.destination,
                "mode": "pre_trip_plan",
                "days": 3,
                "traveler_type": "foodie",
            },
            "context": {},
            "memory": {},
            "disruption": {},
            "recommendation": {},
            "decision": {},
            "output": {},
        }
    )

    output = result.get("output", {})
    return {
        **result,
        "chat_data": output.get("chat_data", {}),
        "map_data": output.get("map_data", {"routes": []}),
    }


@router.post("/chat")
async def chat_with_ai(
    query: str | None = None,
    image_path: str | None = None,
    city: str = "Chennai",
    home_currency: str = Header(default="INR", alias="X-Home-Currency"),
    destination_currency: str | None = None,
    chat_session_id: int | None = None,
    new_chat: bool = False,
    title: str | None = None,
    mode: str = "pre_trip_plan",
    days: int = 3,
    traveler_type: str = "foodie",
    budget: float | None = None,
    user_lat: float | None = None,
    user_lon: float | None = None,
    cuisine: str | None = None,
    is_user_at_airport: bool = False,
    flight_delayed: bool = False,
    trip_id: int | None = None,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request = ChatRequestDTO(
        query=query,
        image_path=image_path,
        city=city,
        destination_currency=destination_currency,
        trip_id=trip_id,
        chat_session_id=chat_session_id,
        new_chat=new_chat,
        title=title,
        mode=mode,
        days=days,
        traveler_type=traveler_type,
        budget=budget,
        user_lat=user_lat,
        user_lon=user_lon,
        cuisine=cuisine,
        is_user_at_airport=is_user_at_airport,
        flight_delayed=flight_delayed,
    )

    try:
        return await ChatUseCase().handle_chat(
            db=db,
            user_id=user_id,
            request=request,
            home_currency=home_currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/chat/sessions")
def list_chat_sessions(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }
        for session in sessions
    ]


@router.post("/chat/sessions")
def create_chat_session(
    title: str | None = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    session = ChatMemoryService().create_session(db, user_id=user_id, title=title or "New chat")
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.get("/chat/sessions/{session_id}/messages")
def list_chat_messages(
    session_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == int(session_id), ChatSession.user_id == int(user_id))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == int(session_id))
        .order_by(ChatMessage.created_at.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )

    return [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in messages
    ]
