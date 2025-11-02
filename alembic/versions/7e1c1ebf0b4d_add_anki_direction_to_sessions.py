"""add anki_direction to learning_sessions

Revision ID: 7e1c1ebf0b4d
Revises: 4f0d5a5f2dc0
Create Date: 2025-11-01 16:30:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7e1c1ebf0b4d"
down_revision = "4f0d5a5f2dc0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_sessions", sa.Column("anki_direction", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("learning_sessions", "anki_direction")
