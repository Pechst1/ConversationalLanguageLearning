"""Package O-1: the gold ledger (l'or), in shadow.

``atelier_gold_ledger``: one row per movement of l'or (an answer's feuilles, a
milestone, a bonus), unique per learner and source key, so the same evidence
can never mint twice. ``atelier_gold_balance``: the livret, a cache of the
settled ledger. Only adds two tables; nothing reads them on a learner's screen
yet (``ATELIER_GOLD_MODE=shadow``).

Revision ID: a9c4e6f8b0d2
Revises: f7d1c3a5b9e2
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a9c4e6f8b0d2"
down_revision = "f7d1c3a5b9e2"
branch_labels = None
depends_on = None

LEDGER = "atelier_gold_ledger"
BALANCE = "atelier_gold_balance"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(name: str) -> bool:
    if _offline_mode():
        return False
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    if not _has_table(LEDGER):
        op.create_table(
            LEDGER,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("entry_kind", sa.String(16), nullable=False),
            sa.Column("state", sa.String(16), nullable=False),
            sa.Column("source_kind", sa.String(32), nullable=False),
            sa.Column("source_key", sa.String(255), nullable=False),
            sa.Column("target", json_type, nullable=True),
            sa.Column("evidence", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("breakdown", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("rule_version", sa.String(16), nullable=False),
            sa.Column("local_date", sa.Date(), nullable=False),
            sa.Column("week_id", sa.String(10), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("void_reason", sa.String(32), nullable=True),
            sa.UniqueConstraint("user_id", "source_key", name="uq_atelier_gold_ledger_source"),
        )
        op.create_index("ix_atelier_gold_ledger_user_id", LEDGER, ["user_id"])
        op.create_index("ix_atelier_gold_ledger_user_day", LEDGER, ["user_id", "local_date"])
        op.create_index("ix_atelier_gold_ledger_user_week_state", LEDGER, ["user_id", "week_id", "state"])
    if not _has_table(BALANCE):
        op.create_table(
            BALANCE,
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("earned_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("spent_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    if _offline_mode() or _has_table(BALANCE):
        op.drop_table(BALANCE)
    if _offline_mode() or _has_table(LEDGER):
        op.drop_index("ix_atelier_gold_ledger_user_week_state", table_name=LEDGER)
        op.drop_index("ix_atelier_gold_ledger_user_day", table_name=LEDGER)
        op.drop_index("ix_atelier_gold_ledger_user_id", table_name=LEDGER)
        op.drop_table(LEDGER)
