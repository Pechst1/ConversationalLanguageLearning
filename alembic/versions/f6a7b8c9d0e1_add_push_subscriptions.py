"""Add push notification subscriptions.

Revision ID: f6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2026-06-23
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f6a7b8c9d0e1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _dialect_name() -> str:
    return str(getattr(op.get_context().dialect, "name", ""))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode() or not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _has_unique(table_name: str, constraint_name: str) -> bool:
    if _offline_mode() or not _has_table(table_name):
        return False
    return constraint_name in {
        constraint["name"] for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
    }


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns)


def _create_unique_once(constraint_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode():
        op.create_unique_constraint(constraint_name, table_name, columns)
        return
    if _dialect_name() == "sqlite":
        return
    if _has_table(table_name) and not _has_unique(table_name, constraint_name):
        op.create_unique_constraint(constraint_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("push_subscriptions"):
        op.create_table(
            "push_subscriptions",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("keys", json_type, nullable=False),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "endpoint", name="uq_push_subscriptions_user_endpoint"),
        )
    else:
        _create_unique_once(
            "uq_push_subscriptions_user_endpoint",
            "push_subscriptions",
            ["user_id", "endpoint"],
        )

    _create_index_once("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
    _create_index_once("ix_push_subscriptions_created_at", "push_subscriptions", ["created_at"])


def downgrade() -> None:
    if _has_table("push_subscriptions"):
        op.drop_index("ix_push_subscriptions_created_at", table_name="push_subscriptions")
        op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
        op.drop_table("push_subscriptions")
