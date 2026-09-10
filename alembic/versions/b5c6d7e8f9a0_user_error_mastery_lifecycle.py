"""WP-24: give a UserError a way out — mastery columns and state normalisation.

Adds the four columns the lifecycle needs and folds the legacy state vocabulary
("new"/"learning"/"review"/"relearning") onto the three states the loop has.
Existing rows keep their schedule: nothing is re-dated, only re-labelled.

Revision ID: b5c6d7e8f9a0
Revises: a3b4c5d6e7f8
Create Date: 2026-09-10
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

_COLUMNS = (
    ("mastery_streak", sa.Column("mastery_streak", sa.Integer(), nullable=True, server_default="0")),
    ("mastered_at", sa.Column("mastered_at", sa.DateTime(timezone=True), nullable=True)),
    ("last_correct_date", sa.Column("last_correct_date", sa.DateTime(timezone=True), nullable=True)),
    ("ease_factor", sa.Column("ease_factor", sa.Float(), nullable=True, server_default="2.5")),
)


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
    if not _offline_mode() and not sa.inspect(op.get_bind()).has_table("user_errors"):
        return
    for name, column in _COLUMNS:
        if not _has_column("user_errors", name):
            op.add_column("user_errors", column)

    # Legacy vocabulary → lifecycle vocabulary. "review" becomes "repairing"
    # rather than "mastered": a row that was merely scheduled forward has not
    # demonstrated the three spaced repairs mastery requires, and claiming it
    # had would retire errata the learner never fixed.
    op.execute(
        sa.text(
            "UPDATE user_errors SET state = 'open' "
            "WHERE state IS NULL OR state IN ('new', 'learning')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE user_errors SET state = 'repairing' "
            "WHERE state IN ('relearning', 'review')"
        )
    )
    op.execute(sa.text("UPDATE user_errors SET mastery_streak = 0 WHERE mastery_streak IS NULL"))
    op.execute(sa.text("UPDATE user_errors SET ease_factor = 2.5 WHERE ease_factor IS NULL"))


def downgrade() -> None:
    if not _offline_mode() and not sa.inspect(op.get_bind()).has_table("user_errors"):
        return
    op.execute(sa.text("UPDATE user_errors SET state = 'new' WHERE state = 'open'"))
    op.execute(sa.text("UPDATE user_errors SET state = 'relearning' WHERE state = 'repairing'"))
    op.execute(sa.text("UPDATE user_errors SET state = 'review' WHERE state = 'mastered'"))
    for name, _column in _COLUMNS:
        if _has_column("user_errors", name):
            op.drop_column("user_errors", name)
