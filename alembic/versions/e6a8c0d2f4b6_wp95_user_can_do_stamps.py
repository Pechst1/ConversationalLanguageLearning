"""Add user_can_do_stamps (WP-95 «Le Carnet»).

Additive only: one new table. A stamp is written the first time story evidence
shows a can-do (an engine scene's objective met, a passed épreuve, or an
authored scenario mapped to a can-do) and is never removed.

Revision ID: e6a8c0d2f4b6
Revises: d5f7a9b1c3e2
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e6a8c0d2f4b6"
down_revision = "d5f7a9b1c3e2"
branch_labels = None
depends_on = None

TABLE = "user_can_do_stamps"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("can_do_id", sa.String(length=60), nullable=False),
        sa.Column("band", sa.String(length=10), nullable=False),
        sa.Column("stamped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "journey_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("daily_journeys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("scene_id", sa.String(length=120), nullable=True),
        sa.Column("scene_title_fr", sa.String(length=200), nullable=True),
        sa.Column("character_id", sa.String(length=80), nullable=True),
        sa.Column("quote_fr", sa.String(length=160), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="scene"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "can_do_id", name="uq_user_can_do_stamps_user_can_do"),
    )
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_table(TABLE)
