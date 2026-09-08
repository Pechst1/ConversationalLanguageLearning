"""Add user daily word slates ("Les mots du jour").

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-18
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return inspector.has_table(table_name)


def upgrade() -> None:
    if not _offline_mode() and _has_table("user_daily_word_slates"):
        return
    op.create_table(
        "user_daily_word_slates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slate_date", sa.Date(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "slate_date", name="uq_user_daily_word_slate_day"),
    )
    op.create_index("ix_user_daily_word_slates_user_id", "user_daily_word_slates", ["user_id"])
    op.create_index("ix_user_daily_word_slates_slate_date", "user_daily_word_slates", ["slate_date"])


def downgrade() -> None:
    if not _offline_mode() and not _has_table("user_daily_word_slates"):
        return
    op.drop_index("ix_user_daily_word_slates_slate_date", table_name="user_daily_word_slates")
    op.drop_index("ix_user_daily_word_slates_user_id", table_name="user_daily_word_slates")
    op.drop_table("user_daily_word_slates")
