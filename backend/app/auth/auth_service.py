from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = _utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": _utcnow(), "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> dict[str, Any]:
    to_encode = data.copy()
    expire = _utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    token_id = str(uuid.uuid4())
    to_encode.update({"exp": expire, "iat": _utcnow(), "type": "refresh", "jti": token_id})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "jti": token_id, "expires_at": expire}


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    token_type = payload.get("type")

    # Backward compatibility: older access tokens did not include a "type" claim.
    if expected_type and token_type and token_type != expected_type:
        raise JWTError("Invalid token type")
    if expected_type and not token_type and expected_type != "access":
        raise JWTError("Invalid token type")

    return payload
