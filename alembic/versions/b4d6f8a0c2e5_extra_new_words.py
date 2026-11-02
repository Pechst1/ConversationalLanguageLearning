"""Extra new words today (owner request, 2 Nov 2026).

``vocabulary_drill_batch.extra_new_words``: the new words the learner asked for
today on top of their daily number («Noch 5 neue Wörter»). The day's batch row
is per learner and day, so the count starts at zero every day. Only adds a
column with a default.

Revision ID: b4d6f8a0c2e5
Revises: a9c4e6f8b0d2
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b4d6f8a0c2e5"
down_revision = "a9c4e6f8b0d2"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column() -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return "extra_new_words" in {column["name"] for column in inspector.get_columns("vocabulary_drill_batch")}


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            "vocabulary_drill_batch",
            sa.Column("extra_new_words", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if _offline_mode() or _has_column():
        op.drop_column("vocabulary_drill_batch", "extra_new_words")
