"""WP-154: the word drill's dealt batch survives a reload.

``vocabulary_drill_batch``: one row per learner per app day — the deck as it was
dealt (word ids per bucket, in order, each with the time it was dealt), the
latest deal's new-word allowance and how many new words it served, and how
many of its cards were answered as of the last read. A reload the same day
serves the rest of that deck instead of dealing new words into the freed «new»
slots. Only adds a table.

Revision ID: e3a5c7f9b1d4
Revises: d2f4a6c8e0b1
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e3a5c7f9b1d4"
down_revision = "d2f4a6c8e0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_drill_batch",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("new_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_dealt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cursor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "day", name="uq_vocabulary_drill_batch_user_day"),
    )


def downgrade() -> None:
    op.drop_table("vocabulary_drill_batch")
