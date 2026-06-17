"""Add serial episode brief payload.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    if not _has_column("serial_episodes", "brief_payload"):
        op.add_column(
            "serial_episodes",
            sa.Column("brief_payload", json_type, nullable=False, server_default=sa.text("'{}'")),
        )
        op.alter_column("serial_episodes", "brief_payload", server_default=None)


def downgrade() -> None:
    if _offline_mode() or _has_column("serial_episodes", "brief_payload"):
        op.drop_column("serial_episodes", "brief_payload")
