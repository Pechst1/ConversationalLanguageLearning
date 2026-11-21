"""Package V stage 3: the settlement job's log (see app/db/models/verdict_settlement.py).

Revision ID: b4d6f8a0c2e3
Revises: a3c5e7f9b1d2
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b4d6f8a0c2e3"
down_revision = "a3c5e7f9b1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verdict_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="auto"),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_verdict_settlements_user_id", "verdict_settlements", ["user_id"])
    op.create_index("ix_verdict_settlements_subject", "verdict_settlements", ["subject_type", "subject_id", "created_at"])
    op.create_index("ix_verdict_settlements_user_day", "verdict_settlements", ["user_id", "created_at"])
    op.create_index("ix_verdict_settlements_due", "verdict_settlements", ["state", "next_at"])


def downgrade() -> None:
    op.drop_index("ix_verdict_settlements_due", table_name="verdict_settlements")
    op.drop_index("ix_verdict_settlements_user_day", table_name="verdict_settlements")
    op.drop_index("ix_verdict_settlements_subject", table_name="verdict_settlements")
    op.drop_index("ix_verdict_settlements_user_id", table_name="verdict_settlements")
    op.drop_table("verdict_settlements")
