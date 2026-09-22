"""A learner's timezone and the streak's «jour de relâche» (WP-80).

Additive only. `users` gains:

* `timezone` — the learner's IANA zone, set from the client. Every "today" the
  streak and the scheduled pushes use is a day in this zone. Existing rows get
  the server default `Europe/Paris`, which is what the morning push already
  assumed for everybody.
* `streak_freezes` — banked «jours de relâche» (0 or 1), earned per full
  seven-day week of the practice streak.
* `streak_freeze_used_on` — the local day the last freeze covered, so the
  number the learner sees stays explainable.

Nothing is backfilled: no learner is handed a freeze they did not earn.

Revision ID: b8e0f2a4c6d8
Revises: 2face6b8f71e
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b8e0f2a4c6d8"
down_revision = "2face6b8f71e"
branch_labels = None
depends_on = None

COLUMN_NAMES: tuple[str, ...] = ("timezone", "streak_freezes", "streak_freeze_used_on")


def _columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("timezone", sa.String(length=64), nullable=True, server_default="Europe/Paris"),
        sa.Column("streak_freezes", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("streak_freeze_used_on", sa.Date(), nullable=True),
    )


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    for column in _columns():
        if not _has_column("users", column.name):
            op.add_column("users", column)


def downgrade() -> None:
    for name in reversed(COLUMN_NAMES):
        if _has_column("users", name):
            op.drop_column("users", name)
