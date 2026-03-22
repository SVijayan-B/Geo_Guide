from __future__ import annotations

import logging
import os

import redis
from sqlalchemy.orm import Session

from app.application.dto.travel import AutopilotStatusDTO
from app.infrastructure.tasks.disruption_tasks import run_disruption_autopilot
from app.models.autopilot import AutopilotStatus

logger = logging.getLogger("aura.autopilot.usecase")


class AutopilotUseCase:
    def _is_enabled(self) -> bool:
        return os.getenv("AUTOPILOT_ASYNC_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}

    def _broker_available(self) -> bool:
        broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0").strip()
        if not broker_url.startswith(("redis://", "rediss://")):
            return True
        try:
            client = redis.from_url(
                broker_url,
                socket_connect_timeout=0.25,
                socket_timeout=0.25,
            )
            client.ping()
            return True
        except Exception:
            return False

    def trigger_trip_check(self, *, trip_id: int, user_id: int) -> None:
        if not self._is_enabled():
            logger.info("autopilot enqueue skipped because AUTOPILOT_ASYNC_ENABLED is disabled")
            return

        if not self._broker_available():
            logger.warning("autopilot enqueue skipped because Celery broker is unavailable")
            return

        try:
            run_disruption_autopilot.apply_async(
                kwargs={"trip_id": int(trip_id), "user_id": int(user_id)},
                retry=False,
                ignore_result=True,
            )
        except Exception as exc:
            logger.warning("failed to enqueue disruption autopilot task: %s", str(exc))

    def get_status(self, db: Session, *, trip_id: int, user_id: int) -> AutopilotStatusDTO:
        row = (
            db.query(AutopilotStatus)
            .filter(AutopilotStatus.trip_id == int(trip_id), AutopilotStatus.user_id == int(user_id))
            .first()
        )
        if not row:
            return AutopilotStatusDTO(
                trip_id=int(trip_id),
                user_id=int(user_id),
                status="not_started",
                delay_probability=None,
                risk_level=None,
                recommendation=None,
                last_error=None,
                updated_at=None,
            )

        return AutopilotStatusDTO(
            trip_id=int(row.trip_id),
            user_id=int(row.user_id),
            status=row.status,
            delay_probability=row.delay_probability,
            risk_level=row.risk_level,
            recommendation=row.recommendation,
            last_error=row.last_error,
            updated_at=row.updated_at,
        )
