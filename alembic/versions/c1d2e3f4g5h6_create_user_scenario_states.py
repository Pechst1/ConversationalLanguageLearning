"""create user scenario states

Revision ID: c1d2e3f4g5h6
Revises: b1b2c3d4e5f7
Create Date: 2025-12-09 11:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c1d2e3f4g5h6"
down_revision = "b1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_scenario_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scenario_id", sa.String(length=50), nullable=False),
        sa.Column("state_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("current_goal_index", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_scenario_states_user_id"), "user_scenario_states", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_scenario_states_scenario_id"), "user_scenario_states", ["scenario_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_scenario_states_scenario_id"), table_name="user_scenario_states")
    op.drop_index(op.f("ix_user_scenario_states_user_id"), table_name="user_scenario_states")
    op.drop_table("user_scenario_states")
