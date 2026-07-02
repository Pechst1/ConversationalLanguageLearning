"""Add user feedback report table.

Revision ID: f5a6b7c8d9e0
Revises: f4e5d6c7b8a9
Create Date: 2026-06-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f5a6b7c8d9e0"
down_revision = "f4e5d6c7b8a9"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode() or not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("user_feedback_reports"):
        op.create_table(
            "user_feedback_reports",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("route", sa.String(length=240), nullable=False),
            sa.Column("url", sa.Text(), nullable=True),
            sa.Column("screen", sa.String(length=120), nullable=True),
            sa.Column("viewport", json_type, nullable=False),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("context_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_once("ix_user_feedback_reports_user_id", "user_feedback_reports", ["user_id"])
    _create_index_once("ix_user_feedback_reports_category", "user_feedback_reports", ["category"])
    _create_index_once("ix_user_feedback_reports_route", "user_feedback_reports", ["route"])
    _create_index_once("ix_user_feedback_reports_created_at", "user_feedback_reports", ["created_at"])


def downgrade() -> None:
    if _has_table("user_feedback_reports"):
        op.drop_index("ix_user_feedback_reports_created_at", table_name="user_feedback_reports")
        op.drop_index("ix_user_feedback_reports_route", table_name="user_feedback_reports")
        op.drop_index("ix_user_feedback_reports_category", table_name="user_feedback_reports")
        op.drop_index("ix_user_feedback_reports_user_id", table_name="user_feedback_reports")
        op.drop_table("user_feedback_reports")
