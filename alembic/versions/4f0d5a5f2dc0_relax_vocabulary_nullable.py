"""relax vocabulary column constraints for Anki imports

Revision ID: 4f0d5a5f2dc0
Revises: 04a21e9bbef5
Create Date: 2025-11-01 15:05:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4f0d5a5f2dc0"
down_revision = "04a21e9bbef5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("vocabulary_words") as batch:
        batch.alter_column(
            "frequency_rank",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch.alter_column(
            "english_translation",
            existing_type=sa.Text(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("vocabulary_words") as batch:
        batch.alter_column(
            "english_translation",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch.alter_column(
            "frequency_rank",
            existing_type=sa.Integer(),
            nullable=False,
        )
