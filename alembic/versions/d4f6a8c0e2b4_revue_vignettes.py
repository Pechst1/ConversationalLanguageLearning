"""WP-120 phase B: the vignette — shared pictograms and each learner's minted stamps.

Revision ID: d4f6a8c0e2b4
Revises: c3e5a7b9d1f2
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d4f6a8c0e2b4"
down_revision = "c3e5a7b9d1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_pictograms",
        sa.Column("dossier_id", sa.String(120), primary_key=True),
        sa.Column("object_fr", sa.String(200), nullable=False),
        sa.Column("svg", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "revue_vignettes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("revue_sessions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("dossier_id", sa.String(120), nullable=False),
        sa.Column("ring", sa.String(16), nullable=False),
        sa.Column("kept_contribution", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("week", sa.String(8), nullable=False),
        sa.Column("place_label_fr", sa.String(200), nullable=False, server_default=""),
        sa.Column("minted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_revue_vignettes_user_id", "revue_vignettes", ["user_id"])
    op.create_index("ix_revue_vignettes_user_minted", "revue_vignettes", ["user_id", "minted_at"])


def downgrade() -> None:
    op.drop_index("ix_revue_vignettes_user_minted", table_name="revue_vignettes")
    op.drop_index("ix_revue_vignettes_user_id", table_name="revue_vignettes")
    op.drop_table("revue_vignettes")
    op.drop_table("revue_pictograms")
