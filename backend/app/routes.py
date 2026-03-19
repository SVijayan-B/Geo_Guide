from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db


from app.models.user import User
from app.models.trip import Trip


from app.schemas.user_schema import UserCreate, UserResponse
from app.schemas.trip_schema import TripCreate, TripResponse

from app.services.context_service import ContextService
from app.services.recommendation_service import RecommendationService

from app.agents.decision_agent import DecisionAgent
from app.agents.notification_agent import NotificationAgent
from app.agents.disruption_agent import DisruptionAgent

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}

@router.post("/create-trip", response_model=TripResponse)
def create_trip(trip: TripCreate, db: Session = Depends(get_db)):
    new_trip = Trip(
        user_id=trip.user_id,
        origin=trip.origin,
        destination=trip.destination
    )

    db.add(new_trip)
    db.commit()
    db.refresh(new_trip)

    return new_trip

@router.get("/trip-context/{trip_id}")
def get_trip_context(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()

    if not trip:
        return {"error": "Trip not found"}

    context_service = ContextService()
    context = context_service.build_context(trip)

    return context

@router.get("/recommend/{trip_id}")
def recommend_places(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()

    if not trip:
        return {"error": "Trip not found"}

    # 🧠 Context
    context_service = ContextService()
    context = context_service.build_context(trip)

    # ⚠️ Disruption (NEW)
    disruption_agent = DisruptionAgent()
    disruption = disruption_agent.predict_delay(trip, context)

    # 📊 Recommendations
    recommendation_service = RecommendationService()
    recommendations = recommendation_service.recommend(context)

    # 🤖 Decision (UPDATED)
    decision_agent = DecisionAgent()
    decision = decision_agent.make_decision(
        context["text"],
        recommendations,
        disruption   # 🔥 NEW INPUT
    )
    # 📢 Notification
    notification_agent = NotificationAgent()
    message = notification_agent.format_message(context, decision)

    return {
        "context": context["text"],
        "recommendations": recommendations,
        "decision": decision,
        "message": message
    }