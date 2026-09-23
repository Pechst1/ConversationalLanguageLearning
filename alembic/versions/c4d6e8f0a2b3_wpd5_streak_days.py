"""The streak as one row per learner-local day (WP-D5).

`streak_days` holds `practised` and `relache` days, so the calendar and
`users.grammar_streak_days` read the same writes. The backfill makes existing
learners' grids agree with the number they already see:

* the current chain is rebuilt from `grammar_last_review_date` back over
  `grammar_streak_days` practised days, with `streak_freeze_used_on` as the
  «jour de relâche» when it falls inside the chain;
* every finished daily journey (`completed` / `ended_early`, both of which
  moved the streak since decision D-0) adds its own day.

Revision ID: c4d6e8f0a2b3
Revises: b8e0f2a4c6d8
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision = "c4d6e8f0a2b3"
down_revision = "b8e0f2a4c6d8"
branch_labels = None
depends_on = None

TABLE = "streak_days"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(name: str) -> bool:
    if _offline_mode():
        return False
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _as_date(value) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _backfill() -> None:
    bind = op.get_bind()
    rows: dict[tuple[str, date], str] = {}

    users = bind.execute(
        sa.text(
            "SELECT id, grammar_streak_days, grammar_last_review_date, streak_freeze_used_on "
            "FROM users WHERE COALESCE(grammar_streak_days, 0) > 0 "
            "AND grammar_last_review_date IS NOT NULL"
        )
    ).fetchall()
    for user_id, days, last, used_on in users:
        last, used_on = _as_date(last), _as_date(used_on)
        day, counted = last, 0
        # A chain never spans more than its days plus one relâche per week.
        for _ in range(int(days) * 2 + 1):
            if counted >= int(days):
                break
            if used_on is not None and day == used_on:
                rows[(str(user_id), day)] = "relache"
            else:
                rows[(str(user_id), day)] = "practised"
                counted += 1
            day -= timedelta(days=1)

    journeys = bind.execute(
        sa.text(
            "SELECT DISTINCT user_id, local_date FROM daily_journeys "
            "WHERE status IN ('completed', 'ended_early')"
        )
    ).fetchall()
    for user_id, local_date in journeys:
        rows[(str(user_id), _as_date(local_date))] = "practised"

    if not rows:
        return
    table = sa.table(
        TABLE,
        sa.column("id", PG_UUID(as_uuid=True)),
        sa.column("user_id", PG_UUID(as_uuid=True)),
        sa.column("local_date", sa.Date()),
        sa.column("kind", sa.String()),
    )
    op.bulk_insert(
        table,
        [
            {"id": uuid.uuid4(), "user_id": uuid.UUID(user_id), "local_date": day, "kind": kind}
            for (user_id, day), kind in sorted(rows.items())
        ],
    )


def upgrade() -> None:
    if _has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "local_date", name="uq_streak_days_user_date"),
    )
    op.create_index("ix_streak_days_user_id", TABLE, ["user_id"])
    if not _offline_mode():
        _backfill()


def downgrade() -> None:
    if _has_table(TABLE):
        op.drop_index("ix_streak_days_user_id", table_name=TABLE)
        op.drop_table(TABLE)
