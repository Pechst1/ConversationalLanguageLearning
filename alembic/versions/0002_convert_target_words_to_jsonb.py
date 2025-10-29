"""Convert conversation target_words to JSONB.

Revision ID: 0002_convert_target_words_to_jsonb
Revises: 0001_initial_schema
Create Date: 2024-01-02 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_convert_target_words_to_jsonb"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("target_words_temp", JSONB(), nullable=True),
    )
    op.execute(
        """
        UPDATE conversation_messages
        SET target_words_temp = to_jsonb(target_words)
        WHERE target_words IS NOT NULL
        """
    )
    op.drop_column("conversation_messages", "target_words")
    op.alter_column(
        "conversation_messages",
        "target_words_temp",
        new_column_name="target_words",
        existing_type=JSONB(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("target_words_temp", sa.ARRAY(sa.Integer()), nullable=True),
    )
    op.execute(
        """
        UPDATE conversation_messages
        SET target_words_temp = ARRAY(
            SELECT jsonb_array_elements_text(target_words)::integer
        )
        WHERE target_words IS NOT NULL
        """
    )
    op.drop_column("conversation_messages", "target_words")
    op.alter_column(
        "conversation_messages",
        "target_words_temp",
        new_column_name="target_words",
        existing_type=sa.ARRAY(sa.Integer()),
        existing_nullable=True,
    )
