"""Add CEFR progress estimate fields.

Revision ID: b0c1d2e3f4a5
Revises: a0b1c2d3e4f5
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b0c1d2e3f4a5"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return True
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_once(table_name: str, column: sa.Column) -> None:
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    _add_column_once("users", sa.Column("cefr_estimate", sa.String(length=10), nullable=True, server_default="A1.1"))
    _add_column_once("users", sa.Column("cefr_target_level", sa.String(length=10), nullable=True, server_default="A1.2"))
    _add_column_once("users", sa.Column("cefr_estimate_payload", json_type, nullable=True, server_default=sa.text("'{}'")))
    if _has_table("users") and not _offline_mode():
        for column_name in ("cefr_estimate", "cefr_target_level", "cefr_estimate_payload"):
            if _has_column("users", column_name):
                op.alter_column("users", column_name, server_default=None)

    if not _has_table("user_cefr_progress_history"):
        op.create_table(
            "user_cefr_progress_history",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("estimate_level", sa.String(length=10), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=False, server_default="recompute"),
            sa.Column("signal_snapshot", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("payload", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_user_cefr_progress_history_user_id", "user_cefr_progress_history", ["user_id"])
        op.create_index("ix_user_cefr_progress_history_estimate_level", "user_cefr_progress_history", ["estimate_level"])
        op.create_index("ix_user_cefr_history_user_created", "user_cefr_progress_history", ["user_id", "created_at"])


def downgrade() -> None:
    if _offline_mode() or _has_table("user_cefr_progress_history"):
        op.drop_index("ix_user_cefr_history_user_created", table_name="user_cefr_progress_history")
        op.drop_index("ix_user_cefr_progress_history_estimate_level", table_name="user_cefr_progress_history")
        op.drop_index("ix_user_cefr_progress_history_user_id", table_name="user_cefr_progress_history")
        op.drop_table("user_cefr_progress_history")
    for column_name in ("cefr_estimate_payload", "cefr_target_level", "cefr_estimate"):
        if _offline_mode() or _has_column("users", column_name):
            op.drop_column("users", column_name)
