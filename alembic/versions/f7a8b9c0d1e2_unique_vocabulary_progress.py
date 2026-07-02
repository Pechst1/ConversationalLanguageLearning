"""Add unique vocabulary progress rows.

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-01
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


INDEX_NAME = "uq_user_vocabulary_progress_user_word"
TABLE_NAME = "user_vocabulary_progress"


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


def upgrade() -> None:
    if not _offline_mode() and _has_table(TABLE_NAME):
        op.execute(
            sa.text(
                """
                DELETE FROM user_vocabulary_progress
                WHERE id IN (
                    SELECT id
                    FROM (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (
                                PARTITION BY user_id, word_id
                                ORDER BY COALESCE(updated_at, created_at) DESC, created_at DESC, id DESC
                            ) AS duplicate_rank
                        FROM user_vocabulary_progress
                    ) ranked
                    WHERE duplicate_rank > 1
                )
                """
            )
        )

    if _offline_mode() or (_has_table(TABLE_NAME) and not _has_index(TABLE_NAME, INDEX_NAME)):
        op.create_index(INDEX_NAME, TABLE_NAME, ["user_id", "word_id"], unique=True)


def downgrade() -> None:
    if _offline_mode() or (_has_table(TABLE_NAME) and _has_index(TABLE_NAME, INDEX_NAME)):
        op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
