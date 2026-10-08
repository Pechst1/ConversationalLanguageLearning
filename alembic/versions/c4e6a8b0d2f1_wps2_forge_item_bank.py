"""WP-S2 (La Forge): served-item fingerprints and shared LLM pools by band (additive).

``atelier_served_items`` records every exercise sentence a learner was served
(its fingerprint), so the item bank never repeats a sentence within seven
days. ``atelier_exercise_sets.pool_band`` marks a vetted LLM set as a shared
pool entry for one learner band (A1, A2, …).

Revision ID: c4e6a8b0d2f1
Revises: c3e5a7b9d1f4
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c4e6a8b0d2f1"
down_revision = "c3e5a7b9d1f4"
branch_labels = None
depends_on = None

TABLE = "atelier_served_items"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(name: str) -> bool:
    if _offline_mode():
        return False
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "atelier_session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("atelier_sessions.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("fingerprint", sa.String(40), nullable=False),
            sa.Column("unit", sa.String(80), nullable=True),
            sa.Column("served_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_atelier_served_items_user_served", TABLE, ["user_id", "served_at"])
        op.create_index("ix_atelier_served_items_user_fingerprint", TABLE, ["user_id", "fingerprint"])
    if not _has_column("atelier_exercise_sets", "pool_band"):
        op.add_column("atelier_exercise_sets", sa.Column("pool_band", sa.String(10), nullable=True))


def downgrade() -> None:
    if _offline_mode() or _has_column("atelier_exercise_sets", "pool_band"):
        op.drop_column("atelier_exercise_sets", "pool_band")
    if _offline_mode() or _has_table(TABLE):
        op.drop_index("ix_atelier_served_items_user_fingerprint", table_name=TABLE)
        op.drop_index("ix_atelier_served_items_user_served", table_name=TABLE)
        op.drop_table(TABLE)
