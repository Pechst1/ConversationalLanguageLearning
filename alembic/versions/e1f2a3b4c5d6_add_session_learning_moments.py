"""Add session learning moments for inline conversation drills.

Revision ID: e1f2a3b4c5d6
Revises: grammar_enhancements
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "grammar_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    op.create_table(
        "session_learning_moments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "anchor_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("source_deck_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("prompt_payload", json_type, nullable=True),
        sa.Column("result_payload", json_type, nullable=True),
        sa.Column("score_0_10", sa.Float(), nullable=True),
        sa.Column("srs_credit_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_session_learning_moments_session_id",
        "session_learning_moments",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        "ix_session_learning_moments_user_id",
        "session_learning_moments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_session_learning_moments_anchor_message_id",
        "session_learning_moments",
        ["anchor_message_id"],
        unique=False,
    )
    op.create_index(
        "ix_session_learning_moments_kind",
        "session_learning_moments",
        ["kind"],
        unique=False,
    )
    op.create_index(
        "ix_session_learning_moments_status",
        "session_learning_moments",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_session_learning_moments_status", table_name="session_learning_moments")
    op.drop_index("ix_session_learning_moments_kind", table_name="session_learning_moments")
    op.drop_index(
        "ix_session_learning_moments_anchor_message_id",
        table_name="session_learning_moments",
    )
    op.drop_index("ix_session_learning_moments_user_id", table_name="session_learning_moments")
    op.drop_index("ix_session_learning_moments_session_id", table_name="session_learning_moments")
    op.drop_table("session_learning_moments")
