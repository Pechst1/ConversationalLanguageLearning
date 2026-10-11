"""WP-119 phase 4: revue_places — one painted plate per new place, shared and kept forever.

Revision ID: e5a7c9b1d3f6
Revises: d4f6a8c0e2b4
"""
import sqlalchemy as sa

from alembic import op

revision = "e5a7c9b1d3f6"
down_revision = "d4f6a8c0e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_places",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("name_fr", sa.String(200), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("plate_url", sa.Text(), nullable=False),
        sa.Column("painted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("prompt_version", sa.String(40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("revue_places")
