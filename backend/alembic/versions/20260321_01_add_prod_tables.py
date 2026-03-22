"""add production support tables

Revision ID: 20260321_01
Revises:
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_refresh_tokens_id"), "refresh_tokens", ["id"], unique=False)
    op.create_index(op.f("ix_refresh_tokens_token_id"), "refresh_tokens", ["token_id"], unique=True)
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "digital_twin_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("traits", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_digital_twin_profiles_id"), "digital_twin_profiles", ["id"], unique=False)
    op.create_index(op.f("ix_digital_twin_profiles_user_id"), "digital_twin_profiles", ["user_id"], unique=True)

    op.create_table(
        "digital_twin_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_digital_twin_events_id"), "digital_twin_events", ["id"], unique=False)
    op.create_index(op.f("ix_digital_twin_events_user_id"), "digital_twin_events", ["user_id"], unique=False)

    op.create_table(
        "autopilot_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("delay_probability", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(), nullable=True),
        sa.Column("recommendation", sa.String(), nullable=True),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_autopilot_status_id"), "autopilot_status", ["id"], unique=False)
    op.create_index(op.f("ix_autopilot_status_trip_id"), "autopilot_status", ["trip_id"], unique=False)
    op.create_index(op.f("ix_autopilot_status_user_id"), "autopilot_status", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_autopilot_status_user_id"), table_name="autopilot_status")
    op.drop_index(op.f("ix_autopilot_status_trip_id"), table_name="autopilot_status")
    op.drop_index(op.f("ix_autopilot_status_id"), table_name="autopilot_status")
    op.drop_table("autopilot_status")

    op.drop_index(op.f("ix_digital_twin_events_user_id"), table_name="digital_twin_events")
    op.drop_index(op.f("ix_digital_twin_events_id"), table_name="digital_twin_events")
    op.drop_table("digital_twin_events")

    op.drop_index(op.f("ix_digital_twin_profiles_user_id"), table_name="digital_twin_profiles")
    op.drop_index(op.f("ix_digital_twin_profiles_id"), table_name="digital_twin_profiles")
    op.drop_table("digital_twin_profiles")

    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_token_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
