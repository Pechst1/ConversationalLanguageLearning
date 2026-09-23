"""WP-L7: one checkpoint («épreuve») row per learner and sub-band (additive).

``user_level_checkpoints`` records when a band's coverage was met (``ready``),
the épreuve's result (``passed`` / ``failed`` with a ``retry_after`` a week
later) and bands credited without an épreuve (``credited``: the level each
learner was shown before the coverage rule shipped, so nobody's level drops on
release day — written lazily by ``CEFRProgressService`` on the first recompute).

Revision ID: b7d9f1a3c5e8
Revises: f2a4c6e8b0d1
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b7d9f1a3c5e8"
down_revision = "f2a4c6e8b0d1"
branch_labels = None
depends_on = None

TABLE = "user_level_checkpoints"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table() -> bool:
    if _offline_mode():
        return False
    return TABLE in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table():
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
        sa.Column("band", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ready"),
        sa.Column("source", sa.String(40), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "band", name="uq_user_level_checkpoints_user_band"),
    )
    op.create_index("ix_user_level_checkpoints_user_id", TABLE, ["user_id"])


def downgrade() -> None:
    if _has_table():
        op.drop_index("ix_user_level_checkpoints_user_id", table_name=TABLE)
        op.drop_table(TABLE)
