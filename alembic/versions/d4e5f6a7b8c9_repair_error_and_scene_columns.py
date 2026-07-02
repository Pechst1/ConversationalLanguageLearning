"""Repair missing error-memory and scene columns.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
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
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_once(table_name: str, column: sa.Column) -> None:
    if _has_table(table_name) and not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _has_table(table_name) and _has_column(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    _add_column_once("user_errors", sa.Column("subcategory", sa.String(length=50), nullable=True))
    _add_column_once("user_errors", sa.Column("original_text", sa.Text(), nullable=True))
    _add_column_once(
        "user_errors",
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    if _has_column("user_errors", "occurrences"):
        op.execute("UPDATE user_errors SET occurrences = 1 WHERE occurrences IS NULL")
        if not _offline_mode():
            op.alter_column("user_errors", "occurrences", server_default=None)

    _add_column_once(
        "scenes",
        sa.Column("player_interaction", json_type, nullable=False, server_default=sa.text("'{}'")),
    )
    if _has_column("scenes", "player_interaction") and not _offline_mode():
        op.alter_column("scenes", "player_interaction", server_default=None)


def downgrade() -> None:
    _drop_column_if_exists("scenes", "player_interaction")
    _drop_column_if_exists("user_errors", "occurrences")
    _drop_column_if_exists("user_errors", "original_text")
    _drop_column_if_exists("user_errors", "subcategory")
