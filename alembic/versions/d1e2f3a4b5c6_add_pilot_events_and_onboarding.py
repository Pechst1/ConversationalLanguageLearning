"""Add the pilot event ledger and onboarding preferences.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("learning_motivation", sa.String(length=80), nullable=True, server_default=""),
    )
    op.add_column(
        "users",
        sa.Column("speaking_comfort", sa.String(length=20), nullable=True, server_default="warming_up"),
    )
    op.create_table(
        "pilot_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=48), nullable=True),
        sa.Column("entity_id", sa.String(length=180), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pilot_events_user_id", "pilot_events", ["user_id"])
    op.create_index("ix_pilot_events_event_type", "pilot_events", ["event_type"])
    op.create_index("ix_pilot_events_user_occurred", "pilot_events", ["user_id", "occurred_at"])
    op.create_index("ix_pilot_events_type_occurred", "pilot_events", ["event_type", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_pilot_events_type_occurred", table_name="pilot_events")
    op.drop_index("ix_pilot_events_user_occurred", table_name="pilot_events")
    op.drop_index("ix_pilot_events_event_type", table_name="pilot_events")
    op.drop_index("ix_pilot_events_user_id", table_name="pilot_events")
    op.drop_table("pilot_events")
    op.drop_column("users", "speaking_comfort")
    op.drop_column("users", "learning_motivation")
