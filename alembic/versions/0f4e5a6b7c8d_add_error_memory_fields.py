"""Add source-aware error memory fields.

Revision ID: 0f4e5a6b7c8d
Revises: f3a4b5c6d7e8
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0f4e5a6b7c8d"
down_revision = "f3a4b5c6d7e8"
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
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode():
        return False
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    _add_column_once("user_errors", sa.Column("source_type", sa.String(length=40), nullable=True))
    _add_column_once("user_errors", sa.Column("review_mode", sa.String(length=40), nullable=True))
    _add_column_once("user_errors", sa.Column("memory_key", sa.String(length=180), nullable=True))
    _add_column_once("user_errors", sa.Column("linked_word_id", sa.Integer(), nullable=True))
    _add_column_once("user_errors", sa.Column("error_metadata", sa.JSON(), nullable=True))

    _create_index_once("ix_user_errors_source_type", "user_errors", ["source_type"])
    _create_index_once("ix_user_errors_review_mode", "user_errors", ["review_mode"])
    _create_index_once("ix_user_errors_memory_key", "user_errors", ["memory_key"])
    _create_index_once("ix_user_errors_linked_word_id", "user_errors", ["linked_word_id"])
    _create_index_once("ix_user_errors_user_memory", "user_errors", ["user_id", "memory_key"])

    fks = set()
    if not _offline_mode():
        inspector = sa.inspect(op.get_bind())
        fks = {fk["name"] for fk in inspector.get_foreign_keys("user_errors")}
    if _offline_mode() or "fk_user_errors_linked_word_id_vocabulary_words" not in fks:
        op.create_foreign_key(
            "fk_user_errors_linked_word_id_vocabulary_words",
            "user_errors",
            "vocabulary_words",
            ["linked_word_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    fks = set()
    if not _offline_mode():
        inspector = sa.inspect(op.get_bind())
        fks = {fk["name"] for fk in inspector.get_foreign_keys("user_errors")}
    if _offline_mode() or "fk_user_errors_linked_word_id_vocabulary_words" in fks:
        op.drop_constraint("fk_user_errors_linked_word_id_vocabulary_words", "user_errors", type_="foreignkey")
    for index_name in (
        "ix_user_errors_user_memory",
        "ix_user_errors_linked_word_id",
        "ix_user_errors_memory_key",
        "ix_user_errors_review_mode",
        "ix_user_errors_source_type",
    ):
        op.drop_index(index_name, table_name="user_errors", if_exists=True)
    for column_name in ("error_metadata", "linked_word_id", "memory_key", "review_mode", "source_type"):
        if _has_column("user_errors", column_name):
            op.drop_column("user_errors", column_name)
