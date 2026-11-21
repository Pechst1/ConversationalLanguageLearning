"""Red-thread design, slice 5: the pool of shared pages.

``story_pool_pages``: one row per page written for a contract day in the shared
mode, read by every learner whose day gives the writer the same input. Only adds
a table; nothing reads or writes it while ``STORY_SHARED_PAGES`` is off.

Revision ID: c5e7a9b1d3f6
Revises: b4d6f8a0c2e5
Create Date: 2026-11-10
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c5e7a9b1d3f6"
down_revision = "b4d6f8a0c2e5"
branch_labels = None
depends_on = None

TABLE = "story_pool_pages"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table() -> bool:
    if _offline_mode():
        return False
    return TABLE in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _has_table():
        return
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("season_id", sa.String(40), nullable=False),
        sa.Column("day_key", sa.String(160), nullable=False),
        sa.Column("band", sa.String(8), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("frame_hash", sa.String(64), nullable=False),
        sa.Column("draft", json_type, nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("served", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_reason", sa.String(200), nullable=True),
    )
    op.create_index("ix_story_pool_pages_frame", TABLE, ["season_id", "day_key", "frame_hash"])


def downgrade() -> None:
    if _offline_mode() or _has_table():
        op.drop_index("ix_story_pool_pages_frame", table_name=TABLE)
        op.drop_table(TABLE)
