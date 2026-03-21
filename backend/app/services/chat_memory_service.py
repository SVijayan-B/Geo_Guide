from typing import Optional, List, Dict

from sqlalchemy.orm import Session

from app.models.chat import ChatSession, ChatMessage


class ChatMemoryService:
    def get_latest_session_for_user(self, db: Session, user_id: int) -> Optional[ChatSession]:
        return (
            db.query(ChatSession)
            .filter(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc())
            .first()
        )

    def get_session_for_user(
        self, db: Session, user_id: int, chat_session_id: int
    ) -> Optional[ChatSession]:
        return (
            db.query(ChatSession)
            .filter(ChatSession.id == chat_session_id, ChatSession.user_id == user_id)
            .first()
        )

    def create_session(self, db: Session, user_id: int, title: Optional[str] = None) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_or_create_session(
        self,
        db: Session,
        user_id: int,
        chat_session_id: Optional[int] = None,
        title: Optional[str] = None,
    ) -> ChatSession:
        if chat_session_id is not None:
            existing = self.get_session_for_user(db, user_id=user_id, chat_session_id=chat_session_id)
            if not existing:
                # Caller can translate this to 404 if desired.
                raise ValueError("Chat session not found for user")
            return existing

        # No explicit session requested: reuse latest if available, else create.
        latest = self.get_latest_session_for_user(db, user_id=user_id)
        if latest is not None:
            return latest

        return self.create_session(db, user_id=user_id, title=title)

    def append_message(self, db: Session, session_id: int, role: str, content: str) -> ChatMessage:
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return msg

    def get_recent_messages(self, db: Session, session_id: int, limit: int = 12) -> List[Dict[str, str]]:
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
        # reverse so order is oldest -> newest
        messages = list(reversed(messages))
        return [{"role": m.role, "content": m.content} for m in messages]

