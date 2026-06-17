"""Add user-owned guided reading library.

Revision ID: b2c3d4e5f6a7
Revises: aa1b2c3d4e5f
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b2c3d4e5f6a7"
down_revision = "aa1b2c3d4e5f"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode():
        return False
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("user_books"):
        op.create_table(
            "user_books",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("author", sa.String(length=255), nullable=True),
            sa.Column("source_filename", sa.String(length=255), nullable=True),
            sa.Column("source_type", sa.String(length=20), nullable=False),
            sa.Column("source_hash", sa.String(length=64), nullable=False),
            sa.Column("target_level", sa.String(length=10), nullable=False, server_default="A2"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
            sa.Column("status_message", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_episodes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("current_episode_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_episode_indices", json_type, nullable=False),
            sa.Column("estimated_total_words", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("task_id", sa.String(length=64), nullable=True),
            sa.Column("extra_metadata", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id"),
            sa.UniqueConstraint("user_id", "source_hash", name="uq_user_books_owner_source_hash"),
        )
    _create_index_once("ix_user_books_user_id", "user_books", ["user_id"])
    _create_index_once("ix_user_books_status", "user_books", ["status"])
    _create_index_once("ix_user_books_task_id", "user_books", ["task_id"])
    _create_index_once("ix_user_books_user_status", "user_books", ["user_id", "status"])

    if not _has_table("book_episodes"):
        op.create_table(
            "book_episodes",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_book_id", uuid_type, nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("passage_text", sa.Text(), nullable=False),
            sa.Column("est_reading_minutes", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("cefr_level", sa.String(length=10), nullable=False, server_default="A2"),
            sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("vocab_seed", json_type, nullable=False),
            sa.Column("grammar_seed", json_type, nullable=False),
            sa.Column("exercise_payload", json_type, nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_book_id"], ["user_books.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_book_id", "order_index", name="uq_book_episodes_book_order"),
        )
    _create_index_once("ix_book_episodes_user_book_id", "book_episodes", ["user_book_id"])
    _create_index_once("ix_book_episodes_status", "book_episodes", ["status"])
    _create_index_once("ix_book_episodes_book_status", "book_episodes", ["user_book_id", "status"])


def downgrade() -> None:
    for index_name in (
        "ix_book_episodes_book_status",
        "ix_book_episodes_status",
        "ix_book_episodes_user_book_id",
    ):
        if _has_index("book_episodes", index_name):
            op.drop_index(index_name, table_name="book_episodes")
    if _has_table("book_episodes"):
        op.drop_table("book_episodes")

    for index_name in (
        "ix_user_books_user_status",
        "ix_user_books_task_id",
        "ix_user_books_status",
        "ix_user_books_user_id",
    ):
        if _has_index("user_books", index_name):
            op.drop_index(index_name, table_name="user_books")
    if _has_table("user_books"):
        op.drop_table("user_books")
