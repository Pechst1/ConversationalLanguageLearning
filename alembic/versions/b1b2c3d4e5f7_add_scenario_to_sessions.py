"""add scenario to sessions

Revision ID: b1b2c3d4e5f7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-21 16:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1b2c3d4e5f7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_sessions", sa.Column("scenario", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("learning_sessions", "scenario")
