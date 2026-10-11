"""Add the rehearsals table (WP-31).

Additive only: one new table, no column on any existing one, and deliberately no
foreign key into the serial story — a rehearsal is the learner's real life, not
canon, and nothing about it may be reachable from the story tables.

A deploy that runs this and then rolls the code back leaves an unread table
behind, which is inert.

Revision ID: e48fd9624811
Revises: e419f24edcd7
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e48fd9624811"
down_revision = "e419f24edcd7"
branch_labels = None
depends_on = None

TABLE = "rehearsals"


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
        sa.Column("status", sa.String(length=16), nullable=False, server_default="declared"),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="rehearsal-v1"),
        sa.Column("declaration", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("brief", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("scene", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("turns", _json_type(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("debrief", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("rehearsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("debriefed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_rehearsals_user_id", TABLE, ["user_id"])
    op.create_index("ix_rehearsals_status", TABLE, ["status"])
    op.create_index("ix_rehearsals_outcome", TABLE, ["outcome"])
    op.create_index("ix_rehearsals_event_date", TABLE, ["event_date"])
    op.create_index("ix_rehearsals_user_status", TABLE, ["user_id", "status"])
    op.create_index("ix_rehearsals_user_created", TABLE, ["user_id", "created_at"])


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    op.drop_index("ix_rehearsals_user_created", table_name=TABLE)
    op.drop_index("ix_rehearsals_user_status", table_name=TABLE)
    op.drop_index("ix_rehearsals_event_date", table_name=TABLE)
    op.drop_index("ix_rehearsals_outcome", table_name=TABLE)
    op.drop_index("ix_rehearsals_status", table_name=TABLE)
    op.drop_index("ix_rehearsals_user_id", table_name=TABLE)
    op.drop_table(TABLE)
