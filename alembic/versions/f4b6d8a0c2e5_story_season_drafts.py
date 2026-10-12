"""WP-168 follow-up: the season writer runs in the background.

``story_season_drafts``: one row per (serial thread, season). The worker writes
the drafted season file there, and the rollover adopts it on the request path
without a model call. Only adds a table.

Revision ID: f4b6d8a0c2e5
Revises: e3a5c7f9b1d4
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f4b6d8a0c2e5"
down_revision = "e3a5c7f9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_season_drafts",
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("serial_threads.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("season", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="drafting"),
        sa.Column("season_file", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("story_season_drafts")
