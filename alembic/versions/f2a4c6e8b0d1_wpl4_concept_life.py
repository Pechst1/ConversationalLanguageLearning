"""WP-L4: a grammar concept's life on the learner's progress row (additive).

Five nullable timestamps on `user_grammar_progress`, read and written by
`app.services.concept_life`:

* `introduced_at` — the learner met the unit (the journey's Règle, or its first
  evidence on any surface);
* `free_use_first_at` / `free_use_last_at` — the first and latest correct,
  unassisted free use in a reply;
* `spaced_success_at` — the latest correct spaced item at least 14 days after
  the introduction;
* `held_at` — when the unit was first held («Tenue»: free use on two days at
  least 7 days apart plus one such spaced item).

No backfill: nothing before this migration recorded free use separately, so a
learner's existing concepts start their «Tenue» from their next evidence.

Revision ID: f2a4c6e8b0d1
Revises: e1f3a5b7c9d2
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f2a4c6e8b0d1"
down_revision = "e1f3a5b7c9d2"
branch_labels = None
depends_on = None

TABLE = "user_grammar_progress"
COLUMNS = (
    "introduced_at",
    "free_use_first_at",
    "free_use_last_at",
    "spaced_success_at",
    "held_at",
)


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _existing() -> set[str]:
    if _offline_mode():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    existing = _existing()
    for name in COLUMNS:
        if name not in existing:
            op.add_column(TABLE, sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = _existing()
    for name in reversed(COLUMNS):
        if name in existing or _offline_mode():
            op.drop_column(TABLE, name)
