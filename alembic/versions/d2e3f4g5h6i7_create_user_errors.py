"""create user errors table

Revision ID: d2e3f4g5h6i7
Revises: c1d2e3f4g5h6
Create Date: 2025-12-09 11:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d2e3f4g5h6i7"
down_revision = "c1d2e3f4g5h6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_category", sa.String(length=50), nullable=False),
        sa.Column("error_pattern", sa.String(length=100), nullable=True),
        sa.Column("correction", sa.Text(), nullable=True),
        sa.Column("context_snippet", sa.Text(), nullable=True),
        sa.Column("stability", sa.Float(), nullable=True),
        sa.Column("difficulty", sa.Float(), nullable=True),
        sa.Column("elapsed_days", sa.Integer(), nullable=True),
        sa.Column("scheduled_days", sa.Integer(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("lapses", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=True),
        sa.Column("last_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_errors_next_review_date"), "user_errors", ["next_review_date"], unique=False)
    op.create_index(op.f("ix_user_errors_user_id"), "user_errors", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_errors_user_id"), table_name="user_errors")
    op.drop_index(op.f("ix_user_errors_next_review_date"), table_name="user_errors")
    op.drop_table("user_errors")
