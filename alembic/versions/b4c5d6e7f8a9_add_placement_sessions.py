"""Add the placement_sessions table (WP-25).

Additive only: one new table, no column on any existing one. A deploy that runs
this and then rolls the code back leaves an unread table behind, which is inert.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

TABLE = "placement_sessions"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


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
        sa.Column("status", sa.String(length=24), nullable=False, server_default="in_progress"),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="placement-v1"),
        sa.Column("current_band", sa.String(length=8), nullable=False, server_default="A1.2"),
        sa.Column("turns", _json_type(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("estimate", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("estimate_level", sa.String(length=8), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_placement_sessions_user_id", TABLE, ["user_id"])
    op.create_index("ix_placement_sessions_status", TABLE, ["status"])
    op.create_index("ix_placement_sessions_user_status", TABLE, ["user_id", "status"])
    op.create_index("ix_placement_sessions_user_created", TABLE, ["user_id", "created_at"])


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    op.drop_index("ix_placement_sessions_user_created", table_name=TABLE)
    op.drop_index("ix_placement_sessions_user_status", table_name=TABLE)
    op.drop_index("ix_placement_sessions_status", table_name=TABLE)
    op.drop_index("ix_placement_sessions_user_id", table_name=TABLE)
    op.drop_table(TABLE)
