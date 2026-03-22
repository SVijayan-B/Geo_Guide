from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.dto.travel import RefreshTokenRequestDTO
from app.application.use_cases.auth_use_case import AuthUseCase
from app.application.use_cases.autopilot_use_case import AutopilotUseCase
from app.auth.auth_service import decode_token
from app.db.database import get_db

router = APIRouter(prefix="", tags=["platform"])
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        return int(payload["user_id"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


@router.post("/auth/refresh")
def refresh_access_token(payload: RefreshTokenRequestDTO, db: Session = Depends(get_db)):
    use_case = AuthUseCase()
    try:
        return use_case.rotate_refresh_token(db, refresh_token=payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/autopilot/status/{trip_id}")
def get_autopilot_status(
    trip_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status = AutopilotUseCase().get_status(db, trip_id=trip_id, user_id=user_id)
    return status.model_dump()


@router.post("/autopilot/trigger/{trip_id}")
def trigger_autopilot(
    trip_id: int,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = db
    AutopilotUseCase().trigger_trip_check(trip_id=trip_id, user_id=user_id)
    return {"ok": True, "trip_id": trip_id, "status": "queued"}
