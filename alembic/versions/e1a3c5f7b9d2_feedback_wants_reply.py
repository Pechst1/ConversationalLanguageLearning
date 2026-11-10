"""S4 stage 4: a feedback report records whether the learner wants a reply.

Revision ID: e1a3c5f7b9d2
Revises: d8f0a2c4e6b1
Create Date: 2026-11-10
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e1a3c5f7b9d2"
down_revision = "d8f0a2c4e6b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing reports never offered the choice: they read as «no reply asked».
    op.add_column(
        "user_feedback_reports",
        sa.Column("wants_reply", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_feedback_reports", "wants_reply")
