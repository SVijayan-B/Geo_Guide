from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.agents.Booking_agent import BookingAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.disruption_agent import DisruptionAgent
from app.db.database import SessionLocal
from app.infrastructure.observability.metrics import mark_autopilot_remediation, mark_disruption_event
from app.infrastructure.tasks.celery_app import celery_app
from app.models.autopilot import AutopilotStatus
from app.models.trip import Trip
from app.services.context_service import ContextService

logger = logging.getLogger("aura.autopilot")


def _upsert_status(
    db: Session,
    *,
    trip: Trip,
    status: str,
    delay_probability: float | None = None,
    risk_level: str | None = None,
    recommendation: str | None = None,
    last_error: str | None = None,
) -> AutopilotStatus:
    current = db.query(AutopilotStatus).filter(AutopilotStatus.trip_id == trip.id).first()
    if current is None:
        current = AutopilotStatus(trip_id=trip.id, user_id=trip.user_id, status=status)

    current.status = status
    current.delay_probability = delay_probability
    current.risk_level = risk_level
    current.recommendation = recommendation
    current.last_error = last_error
    db.add(current)
    db.commit()
    db.refresh(current)
    return current


@celery_app.task(name="app.infrastructure.tasks.disruption_tasks.run_disruption_autopilot", bind=True, max_retries=3)
def run_disruption_autopilot(self, *, trip_id: int, user_id: int):
    db: Session = SessionLocal()
    try:
        trip = db.query(Trip).filter(Trip.id == int(trip_id), Trip.user_id == int(user_id)).first()
        if not trip:
            return {"status": "skipped", "reason": "trip not found"}

        context = ContextService().build_context(trip)
        disruption = DisruptionAgent().predict_delay(trip, context)
        delay_probability = float(disruption.get("delay_probability") or 0.0)
        risk_level = str(disruption.get("risk_level") or "low")

        mark_disruption_event("evaluated")

        decision = DecisionAgent().make_decision(
            context=context.get("text", ""),
            recommendations=[],
            disruption=disruption,
        )

        recommendation_text = str(decision.get("action") or "No action required")

        if decision.get("rebooking_required"):
            rebook = BookingAgent().handle_rebooking(trip, decision)
            recommendation_text = f"{recommendation_text} | Rebooking suggestion: {rebook}"
            mark_autopilot_remediation("rebooking_suggested")
            status = "remediation_suggested"
        else:
            mark_autopilot_remediation("no_action")
            status = "stable"

        status_row = _upsert_status(
            db,
            trip=trip,
            status=status,
            delay_probability=delay_probability,
            risk_level=risk_level,
            recommendation=recommendation_text,
        )
        return {
            "status": status_row.status,
            "trip_id": trip.id,
            "delay_probability": status_row.delay_probability,
            "risk_level": status_row.risk_level,
            "recommendation": status_row.recommendation,
        }
    except Exception as exc:
        logger.exception("autopilot run failed")
        trip = db.query(Trip).filter(Trip.id == int(trip_id)).first()
        if trip:
            _upsert_status(db, trip=trip, status="failed", last_error=str(exc))
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(name="app.infrastructure.tasks.disruption_tasks.scan_active_trips")
def scan_active_trips():
    db: Session = SessionLocal()
    queued = 0
    try:
        trips = db.query(Trip).filter(Trip.status.in_(["planned", "ongoing"])).all()
        for trip in trips:
            run_disruption_autopilot.delay(trip_id=int(trip.id), user_id=int(trip.user_id))
            queued += 1
        return {"queued": queued}
    finally:
        db.close()
