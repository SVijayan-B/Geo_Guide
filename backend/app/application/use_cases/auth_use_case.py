from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth.auth_service import create_access_token, create_refresh_token, decode_token
from app.models.auth import RefreshToken


class AuthUseCase:
    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()

    def issue_tokens(self, *, user_id: int) -> dict:
        access_token = create_access_token({"user_id": str(user_id)})
        refresh_payload = create_refresh_token({"user_id": str(user_id)})
        return {
            "access_token": access_token,
            "refresh_token": refresh_payload["token"],
            "refresh_token_id": refresh_payload["jti"],
            "refresh_expires_at": refresh_payload["expires_at"],
            "token_type": "bearer",
        }

    def persist_refresh_token(self, db: Session, *, user_id: int, token_id: str, refresh_token: str, expires_at: datetime) -> None:
        record = RefreshToken(
            user_id=user_id,
            token_id=token_id,
            token_hash=self._hash_token(refresh_token),
            expires_at=expires_at,
        )
        db.add(record)
        db.commit()

    def login_tokens(self, db: Session, *, user_id: int) -> dict:
        issued = self.issue_tokens(user_id=user_id)
        self.persist_refresh_token(
            db,
            user_id=user_id,
            token_id=issued["refresh_token_id"],
            refresh_token=issued["refresh_token"],
            expires_at=issued["refresh_expires_at"],
        )
        return {
            "access_token": issued["access_token"],
            "refresh_token": issued["refresh_token"],
            "token_type": issued["token_type"],
        }

    def rotate_refresh_token(self, db: Session, *, refresh_token: str) -> dict:
        payload = decode_token(refresh_token, expected_type="refresh")
        token_id = payload.get("jti")
        user_id = int(payload["user_id"])

        record = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_id == token_id, RefreshToken.user_id == user_id)
            .first()
        )
        if not record:
            raise ValueError("Refresh token not found")

        if record.revoked_at is not None:
            raise ValueError("Refresh token already revoked")

        expires_at = record.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise ValueError("Refresh token expired")

        if record.token_hash != self._hash_token(refresh_token):
            raise ValueError("Refresh token mismatch")

        record.revoked_at = datetime.now(timezone.utc)
        db.add(record)
        db.commit()

        issued = self.issue_tokens(user_id=user_id)
        self.persist_refresh_token(
            db,
            user_id=user_id,
            token_id=issued["refresh_token_id"],
            refresh_token=issued["refresh_token"],
            expires_at=issued["refresh_expires_at"],
        )
        return {
            "access_token": issued["access_token"],
            "refresh_token": issued["refresh_token"],
            "token_type": issued["token_type"],
        }
