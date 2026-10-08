"""Durable encrypted password reset email delivery.

Revision ID: b9d1f3a5c7e0
Revises: a8c0e2f4b6d8
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "b9d1f3a5c7e0"
down_revision = "a8c0e2f4b6d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    for column in ("user_id", "status", "next_attempt_at"):
        op.create_index(f"ix_password_reset_deliveries_{column}", "password_reset_deliveries", [column])


def downgrade() -> None:
    op.drop_table("password_reset_deliveries")
