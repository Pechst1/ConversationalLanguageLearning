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
    op.alter_column(
        "conversation_messages",
        "target_words",
        type_=JSONB(),
        nullable=True,
        postgresql_using="to_jsonb(target_words)",
    )


def downgrade() -> None:
    op.alter_column(
        "conversation_messages",
        "target_words",
        type_=sa.ARRAY(sa.Integer()),
        nullable=True,
        postgresql_using=(
            "CASE WHEN target_words IS NULL THEN NULL ELSE "
            "(SELECT array_agg((elem)::integer) "
            "FROM jsonb_array_elements_text(target_words) AS elem) END"
        ),
    )
