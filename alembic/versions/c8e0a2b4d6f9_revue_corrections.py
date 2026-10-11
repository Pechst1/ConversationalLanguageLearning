"""WP-122 part B «Le Correcteur»: one row per proofreading attempt.

``revue_corrections``: the draft (with its private key: the seeded spans) and, once the
learner says «Bon à tirer», the graded result. Chained on d4f6a8c0e2b4 alongside the
other WP-119/122 leads' revisions; the heads are merged at integration.

Revision ID: c8e0a2b4d6f9
Revises: d4f6a8c0e2b4
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c8e0a2b4d6f9"
down_revision = "d4f6a8c0e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dossier_id", sa.String(120), nullable=False),
        sa.Column("draft", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_revue_corrections_user_id", "revue_corrections", ["user_id"])
    op.create_index("ix_revue_corrections_user_created", "revue_corrections", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_revue_corrections_user_created", table_name="revue_corrections")
    op.drop_index("ix_revue_corrections_user_id", table_name="revue_corrections")
    op.drop_table("revue_corrections")
