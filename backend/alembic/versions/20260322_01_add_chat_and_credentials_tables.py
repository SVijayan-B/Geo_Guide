"""add chat sessions/messages and user credentials tables

Revision ID: 20260322_01
Revises: 20260321_02
Create Date: 2026-03-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260322_01"
down_revision = "20260321_02"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if not _table_exists("user_credentials"):
        op.create_table(
            "user_credentials",
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if not _table_exists("chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_chat_sessions_id"), "chat_sessions", ["id"], unique=False)
        op.create_index(op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False)

    if not _table_exists("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)
        op.create_index(op.f("ix_chat_messages_session_id"), "chat_messages", ["session_id"], unique=False)


def downgrade() -> None:
    if _table_exists("chat_messages"):
        op.drop_index(op.f("ix_chat_messages_session_id"), table_name="chat_messages")
        op.drop_index(op.f("ix_chat_messages_id"), table_name="chat_messages")
        op.drop_table("chat_messages")

    if _table_exists("chat_sessions"):
        op.drop_index(op.f("ix_chat_sessions_user_id"), table_name="chat_sessions")
        op.drop_index(op.f("ix_chat_sessions_id"), table_name="chat_sessions")
        op.drop_table("chat_sessions")

    if _table_exists("user_credentials"):
        op.drop_table("user_credentials")
