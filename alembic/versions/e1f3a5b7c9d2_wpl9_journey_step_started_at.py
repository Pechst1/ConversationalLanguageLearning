"""WP-L9: each daily-journey step records when it started (additive).

`daily_journey_steps.started_at` — set when a step becomes the learner's
current step. Nullable, no backfill: a step completed before this column
existed has no honest start time, and the daily rollup's session lengths come
from the event ledger anyway (`measure_journey_duration`).

The rhythm (WP-L6) needs no column: it is `users.daily_goal_minutes`
(5 / 10 / 20 / 30), read through `app.services.journey_rhythm`.

Revision ID: e1f3a5b7c9d2
Revises: c4d6e8f0a2b3
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e1f3a5b7c9d2"
down_revision = "c4d6e8f0a2b3"
branch_labels = None
depends_on = None

TABLE = "daily_journey_steps"
COLUMN = "started_at"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column() -> bool:
    if _offline_mode():
        return False
    columns = sa.inspect(op.get_bind()).get_columns(TABLE)
    return any(column["name"] == COLUMN for column in columns)


def upgrade() -> None:
    if _has_column():
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    if _has_column():
        op.drop_column(TABLE, COLUMN)
