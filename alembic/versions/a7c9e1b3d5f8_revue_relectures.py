"""WP-121 B: La Relecture — one second answer per closed Papier.

Revision ID: a7c9e1b3d5f8
Revises: d4f6a8c0e2b4
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a7c9e1b3d5f8"
down_revision = "d4f6a8c0e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_relectures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("revue_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("answer_fr", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False, server_default="text"),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_revue_relectures_user_id", "revue_relectures", ["user_id"])
    op.create_index("ix_revue_relectures_user_asked", "revue_relectures", ["user_id", "asked_at"])


def downgrade() -> None:
    op.drop_index("ix_revue_relectures_user_asked", table_name="revue_relectures")
    op.drop_index("ix_revue_relectures_user_id", table_name="revue_relectures")
    op.drop_table("revue_relectures")
