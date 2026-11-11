"""Package V stage 5: appeals (see app/db/models/verdict_appeal.py).

Revision ID: d7f9b1c3e5a6
Revises: c5e7a9b1d3f4
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d7f9b1c3e5a6"
down_revision = "c5e7a9b1d3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verdict_appeals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("item", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("verdict_before", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reason_language", sa.String(8), nullable=True),
        sa.Column("ruling", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("memo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_verdict_appeals_user_id", "verdict_appeals", ["user_id"])
    op.create_index("ix_verdict_appeals_subject", "verdict_appeals", ["subject_type", "subject_id"])
    op.create_index("ix_verdict_appeals_user_day", "verdict_appeals", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_verdict_appeals_user_day", table_name="verdict_appeals")
    op.drop_index("ix_verdict_appeals_subject", table_name="verdict_appeals")
    op.drop_index("ix_verdict_appeals_user_id", table_name="verdict_appeals")
    op.drop_table("verdict_appeals")
