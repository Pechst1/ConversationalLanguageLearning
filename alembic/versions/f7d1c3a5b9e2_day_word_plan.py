"""The day's word plan (#396).

``vocabulary_drill_batch.plan``: the day's words as picked at the first read of
the day (the reviews the day deck holds, the new-word dose, the dealt deck's
size), so Home, the scene's hand-on, the review and the Done screen count one
deck. Only adds a nullable column.

Revision ID: f7d1c3a5b9e2
Revises: cff949e9612d
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f7d1c3a5b9e2"
down_revision = "cff949e9612d"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_plan() -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return "plan" in {column["name"] for column in inspector.get_columns("vocabulary_drill_batch")}


def upgrade() -> None:
    if not _has_plan():
        json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
        op.add_column("vocabulary_drill_batch", sa.Column("plan", json_type, nullable=True))


def downgrade() -> None:
    if _offline_mode() or _has_plan():
        op.drop_column("vocabulary_drill_batch", "plan")
