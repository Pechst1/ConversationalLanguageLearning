"""Add the learner address preference to users.

Additive only: one nullable column with a server default, so every existing row
reads back "neutral" without a data migration and without touching any other
column, streak, level or session.

Revision ID: a3b4c5d6e7f8
Revises: e2f3a4b5c6d7
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if _has_column("users", "address_preference"):
        return
    op.add_column(
        "users",
        sa.Column(
            "address_preference",
            sa.String(length=20),
            nullable=True,
            server_default="neutral",
        ),
    )


def downgrade() -> None:
    if not _has_column("users", "address_preference"):
        return
    op.drop_column("users", "address_preference")
