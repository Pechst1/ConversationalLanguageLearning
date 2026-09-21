"""Add Courrier correspondence columns (WP-64).

Additive only: six nullable columns on `real_world_missions` plus two composite
indexes. Nothing is backfilled. A null `correspondent_id` means "written before
the Courrier kept threads", which is what every existing row is, and inventing an
identity for those rows would fabricate a correspondence history nobody had.

A deploy that runs this and then rolls the code back leaves six always-null
columns and two unused indexes behind, all inert.

Revision ID: a1c4e7b90d33
Revises: 3759e1c7098c
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a1c4e7b90d33"
down_revision = "3759e1c7098c"
branch_labels = None
depends_on = None

TABLE = "real_world_missions"

COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("correspondent_id", sa.String(length=80)),
    ("chain_id", sa.String(length=80)),
    ("chain_index", sa.Integer()),
    ("chain_total", sa.Integer()),
    ("expires_at", sa.DateTime(timezone=True)),
    ("outcome", sa.String(length=20)),
)

INDEXES: tuple[tuple[str, list[str]], ...] = (
    ("ix_real_world_missions_correspondent_id", ["correspondent_id"]),
    ("ix_real_world_missions_chain_id", ["chain_id"]),
    ("ix_real_world_missions_correspondent", ["user_id", "correspondent_id"]),
    ("ix_real_world_missions_expiry", ["user_id", "expires_at"]),
)


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    for name, column_type in COLUMNS:
        if not _has_column(TABLE, name):
            op.add_column(TABLE, sa.Column(name, column_type, nullable=True))
    for index_name, columns in INDEXES:
        if not _has_index(TABLE, index_name):
            op.create_index(index_name, TABLE, columns)


def downgrade() -> None:
    for index_name, _ in reversed(INDEXES):
        if _has_index(TABLE, index_name):
            op.drop_index(index_name, table_name=TABLE)
    for name, _ in reversed(COLUMNS):
        if _has_column(TABLE, name):
            op.drop_column(TABLE, name)
