"""E1: money held for a paid call before the provider is asked.

``spend_reservations``: one row per paid request, written under a lock before
the provider is called and closed when the work ends. The daily caps count
open rows as already spent, so requests that start together can no longer all
pass the same check. Only adds a table.

Revision ID: f1b3d5e7a9c2
Revises: e3a5c7f9b1d4
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f1b3d5e7a9c2"
down_revision = "e3a5c7f9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spend_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_key", sa.String(120), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("upper_bound_usd", sa.Float(), nullable=False),
        sa.Column("actual_usd", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="reserved"),
        sa.Column("service_day", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("request_key", name="uq_spend_reservations_request_key"),
    )
    op.create_index("ix_spend_reservations_user_id", "spend_reservations", ["user_id"])
    op.create_index("ix_spend_reservations_day_status", "spend_reservations", ["service_day", "status"])


def downgrade() -> None:
    op.drop_index("ix_spend_reservations_day_status", table_name="spend_reservations")
    op.drop_index("ix_spend_reservations_user_id", table_name="spend_reservations")
    op.drop_table("spend_reservations")
