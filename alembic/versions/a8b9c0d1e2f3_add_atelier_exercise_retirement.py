"""Add lifecycle fields for Atelier exercise quality retirement.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "atelier_exercise_sets",
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "atelier_exercise_sets",
        sa.Column("retirement_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_atelier_exercise_sets_retired_at",
        "atelier_exercise_sets",
        ["retired_at"],
    )
    op.drop_index("ix_atelier_exercise_sets_lookup", table_name="atelier_exercise_sets")
    op.create_index(
        "ix_atelier_exercise_sets_lookup",
        "atelier_exercise_sets",
        ["concept_id", "generator_version", "retired_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_atelier_exercise_sets_lookup", table_name="atelier_exercise_sets")
    op.create_index(
        "ix_atelier_exercise_sets_lookup",
        "atelier_exercise_sets",
        ["concept_id", "generator_version", "created_at"],
    )
    op.drop_index("ix_atelier_exercise_sets_retired_at", table_name="atelier_exercise_sets")
    op.drop_column("atelier_exercise_sets", "retirement_reason")
    op.drop_column("atelier_exercise_sets", "retired_at")
