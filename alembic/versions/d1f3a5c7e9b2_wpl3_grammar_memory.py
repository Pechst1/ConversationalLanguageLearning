"""Grammar concepts get the vocabulary's FSRS-style memory (WP-L3).

Adds ``stability``, ``difficulty`` and ``lapses`` to ``user_grammar_progress``
and seeds them from the SM-2-era columns. The formula is the one in
``app.core.srs.memory.seed_from_legacy`` (a test pins that both agree):

* ``reps = 0``  → ``stability = 0, difficulty = 5, lapses = 0`` (no memory yet);
* ``stability`` = the interval the last review granted, ``next_review −
  last_review`` in days (at least 1) — at retention 0.9 an FSRS interval *is*
  the stability. When that pair is missing: the historic seed interval for the
  score (≥ 9 → 30, ≥ 7 → 14, ≥ 5 → 7, ≥ 3 → 3, else 1). Capped at 365;
* ``difficulty = clamp(5 + (5 − score) · 0.6, 1, 10)`` (score 10 → 2, 5 → 5,
  0 → 8);
* ``lapses = 1`` if the last score failed (< 5), else 0 — SM-2 never stored a
  lapse count.

``score``, ``state``, ``last_review`` and ``next_review`` are not touched, so no
concept is re-dated by the migration. Purely additive; the downgrade drops the
three columns.

Revision ID: d1f3a5c7e9b2
Revises: c4d6e8f0a2b3
"""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "d1f3a5c7e9b2"
down_revision = "c4d6e8f0a2b3"
branch_labels = None
depends_on = None

TABLE = "user_grammar_progress"
COLUMNS = ("stability", "difficulty", "lapses")
LEGACY_SEED_DAYS = ((9.0, 30), (7.0, 14), (5.0, 7), (3.0, 3))


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _columns() -> set[str]:
    if _offline_mode():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def _as_datetime(value) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def seed(score, reps, last_review, next_review) -> tuple[float, float, int]:
    """(stability, difficulty, lapses) for one SM-2-era row."""

    reps = int(reps or 0)
    score = max(0.0, min(10.0, float(score or 0.0)))
    if reps <= 0:
        return 0.0, 5.0, 0
    last, nxt = _as_datetime(last_review), _as_datetime(next_review)
    if last is not None and nxt is not None:
        stability = max(1.0, (nxt - last).total_seconds() / 86400.0)
    else:
        stability = 1.0
        for threshold, days in LEGACY_SEED_DAYS:
            if score >= threshold:
                stability = float(days)
                break
    stability = min(365.0, stability)
    difficulty = min(10.0, max(1.0, 5.0 + (5.0 - score) * 0.6))
    return round(stability, 4), round(difficulty, 4), 1 if score < 5.0 else 0


def _backfill() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, score, reps, last_review, next_review FROM user_grammar_progress "
            "WHERE reps > 0"
        )
    ).fetchall()
    update = sa.text(
        "UPDATE user_grammar_progress SET stability = :stability, difficulty = :difficulty, lapses = :lapses "
        "WHERE id = :id"
    )
    for row_id, score, reps, last_review, next_review in rows:
        stability, difficulty, lapses = seed(score, reps, last_review, next_review)
        bind.execute(
            update,
            {"id": row_id, "stability": stability, "difficulty": difficulty, "lapses": lapses},
        )


def upgrade() -> None:
    existing = _columns()
    if "stability" not in existing:
        op.add_column(
            TABLE, sa.Column("stability", sa.Float(), nullable=False, server_default="0")
        )
    if "difficulty" not in existing:
        op.add_column(
            TABLE, sa.Column("difficulty", sa.Float(), nullable=False, server_default="5")
        )
    if "lapses" not in existing:
        op.add_column(TABLE, sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"))
    if not _offline_mode():
        _backfill()


def downgrade() -> None:
    existing = _columns() if not _offline_mode() else set(COLUMNS)
    with op.batch_alter_table(TABLE) as batch:
        for column in COLUMNS:
            if column in existing:
                batch.drop_column(column)
