"""WP-119 phase 1: La Revue de Romy — one learner's Revue (plan + append-only state).

Revision ID: c3e5a7b9d1f2
Revises: a8c0e2f4b6d8
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c3e5a7b9d1f2"
down_revision = "a8c0e2f4b6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week", sa.String(8), nullable=False),
        sa.Column("dossier_id", sa.String(120), nullable=False),
        sa.Column("plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_revue_sessions_user_id", "revue_sessions", ["user_id"])
    op.create_index("ix_revue_sessions_user_week", "revue_sessions", ["user_id", "week"])
    # One active Revue per learner per ISO week (the service checks it first too).
    op.create_index(
        "uq_revue_sessions_one_active_per_week",
        "revue_sessions",
        ["user_id", "week"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_revue_sessions_one_active_per_week", table_name="revue_sessions")
    op.drop_index("ix_revue_sessions_user_week", table_name="revue_sessions")
    op.drop_index("ix_revue_sessions_user_id", table_name="revue_sessions")
    op.drop_table("revue_sessions")
