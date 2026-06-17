"""Add serial UX and Feuilleton audio fields.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
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
    _add_column_once(
        "users",
        sa.Column("serial_edition_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    _add_column_once(
        "users",
        sa.Column("serial_onboarding_seen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _add_column_once(
        "graphic_novel_panels",
        sa.Column("audio_payload", json_type, nullable=False, server_default=sa.text("'{}'")),
    )
    if not _offline_mode():
        for table_name, column_name in (
            ("users", "serial_edition_notifications"),
            ("users", "serial_onboarding_seen"),
            ("graphic_novel_panels", "audio_payload"),
        ):
            if _has_column(table_name, column_name):
                op.alter_column(table_name, column_name, server_default=None)


def downgrade() -> None:
    for table_name, column_name in (
        ("graphic_novel_panels", "audio_payload"),
        ("users", "serial_onboarding_seen"),
        ("users", "serial_edition_notifications"),
    ):
        if _offline_mode() or _has_column(table_name, column_name):
            op.drop_column(table_name, column_name)
