"""Add Atelier reward collectibles.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _has_unique(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return constraint_name in {
        constraint["name"] for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
    }


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("atelier_collectibles"):
        op.create_table(
            "atelier_collectibles",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("minted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("source_kind", sa.String(length=40), nullable=False),
            sa.Column("source_ref", sa.String(length=180), nullable=False),
            sa.Column("metadata", json_type, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("composed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("composed_into_id", uuid_type, nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["composed_into_id"], ["atelier_collectibles.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "source_kind", "source_ref", "kind", name="uq_atelier_collectibles_source"),
        )
        if not _offline_mode():
            op.alter_column("atelier_collectibles", "metadata", server_default=None)
            op.alter_column("atelier_collectibles", "composed", server_default=None)
    elif not _has_unique("atelier_collectibles", "uq_atelier_collectibles_source"):
        op.create_unique_constraint(
            "uq_atelier_collectibles_source",
            "atelier_collectibles",
            ["user_id", "source_kind", "source_ref", "kind"],
        )

    _create_index_once("ix_atelier_collectibles_user_id", "atelier_collectibles", ["user_id"])
    _create_index_once("ix_atelier_collectibles_composed_into_id", "atelier_collectibles", ["composed_into_id"])
    _create_index_once(
        "ix_atelier_collectibles_user_kind_composed",
        "atelier_collectibles",
        ["user_id", "kind", "composed"],
    )


def downgrade() -> None:
    for index_name in (
        "ix_atelier_collectibles_user_kind_composed",
        "ix_atelier_collectibles_composed_into_id",
        "ix_atelier_collectibles_user_id",
    ):
        if _has_index("atelier_collectibles", index_name):
            op.drop_index(index_name, table_name="atelier_collectibles")
    if _has_table("atelier_collectibles"):
        op.drop_table("atelier_collectibles")
