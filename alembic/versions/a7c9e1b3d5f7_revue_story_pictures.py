"""WP-119 §8.4: revue_story_pictures — one painted picture per Papier story, final.

Only adds a table.

Revision ID: a7c9e1b3d5f7
Revises: f1b3d5e7a9c2
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a7c9e1b3d5f7"
down_revision = "f1b3d5e7a9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_story_pictures",
        sa.Column("dossier_id", sa.String(120), primary_key=True),
        sa.Column("place_id", sa.String(120), nullable=False),
        sa.Column("picture_url", sa.Text(), nullable=False),
        sa.Column("caption_fr", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("painted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("revue_story_pictures")
