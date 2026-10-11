"""WP-115a «Les mots qui reviennent»: what a review was, where a word was met, the caps.

Additive only:

* ``review_logs.source`` / ``format`` / ``direction`` — so retention can be read per
  kind of answer (recognition, production, …) and per place (day, drill, story);
* ``user_vocabulary_progress.context`` — the sentence, speaker, scene, panel and line
  audio key where the word was met;
* ``users.max_reviews_per_day`` — the learner's Anki-like cap on word reviews
  (default 200).

Revision ID: f7b9d1e3a5c7
Revises: e6a8c0d2f4b6
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f7b9d1e3a5c7"
down_revision = "e6a8c0d2f4b6"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table: str, column: str) -> bool:
    if _offline_mode():
        return False
    return column in {row["name"] for row in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for name, column in (
        ("source", sa.Column("source", sa.String(length=24), nullable=True)),
        ("format", sa.Column("format", sa.String(length=24), nullable=True)),
        ("direction", sa.Column("direction", sa.String(length=16), nullable=True)),
    ):
        if not _has_column("review_logs", name):
            op.add_column("review_logs", column)
    op.create_index("ix_review_logs_source", "review_logs", ["source"], if_not_exists=True)
    if not _has_column("user_vocabulary_progress", "context"):
        op.add_column("user_vocabulary_progress", sa.Column("context", postgresql.JSONB(), nullable=True))
    if not _has_column("users", "max_reviews_per_day"):
        op.add_column(
            "users",
            sa.Column("max_reviews_per_day", sa.Integer(), nullable=False, server_default="200"),
        )


def downgrade() -> None:
    if _has_column("users", "max_reviews_per_day"):
        op.drop_column("users", "max_reviews_per_day")
    if _has_column("user_vocabulary_progress", "context"):
        op.drop_column("user_vocabulary_progress", "context")
    op.drop_index("ix_review_logs_source", table_name="review_logs", if_exists=True)
    for name in ("direction", "format", "source"):
        if _has_column("review_logs", name):
            op.drop_column("review_logs", name)
