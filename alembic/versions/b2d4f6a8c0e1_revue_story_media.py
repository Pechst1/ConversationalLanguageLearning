"""«Papier · photos»: revue_story_media — a story's Commons photos and extra illustrations.

Only adds a table (the story's first picture stays in revue_story_pictures).

Revision ID: b2d4f6a8c0e1
Revises: d7f9b1c3e5a6
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b2d4f6a8c0e1"
down_revision = "d7f9b1c3e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_story_media",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dossier_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("licence", sa.String(80), nullable=True),
        sa.Column("licence_url", sa.Text(), nullable=True),
        sa.Column("author", sa.String(300), nullable=True),
        sa.Column("credit_fr", sa.String(400), nullable=False),
        sa.Column("caption_fr", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(200), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column("model", sa.String(80), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dossier_id", "kind", "position", name="uq_revue_story_media_slot"),
    )
    op.create_index("ix_revue_story_media_dossier_id", "revue_story_media", ["dossier_id"])


def downgrade() -> None:
    op.drop_index("ix_revue_story_media_dossier_id", table_name="revue_story_media")
    op.drop_table("revue_story_media")
