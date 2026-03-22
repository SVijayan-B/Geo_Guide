"""remove digital twin tables

Revision ID: 20260321_02
Revises: 20260321_01
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_02"
down_revision = "20260321_01"
branch_labels = None
depends_on = None


def _drop_if_exists(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name in inspector.get_table_names():
        op.drop_table(table_name)


def upgrade() -> None:
    # Roll back the digital twin feature tables.
    _drop_if_exists("digital_twin_events")
    _drop_if_exists("digital_twin_profiles")


def downgrade() -> None:
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
