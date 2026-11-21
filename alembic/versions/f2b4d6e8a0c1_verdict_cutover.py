"""Package V stage 1: record when the verdict stack went live.

Rows stored before this moment keep what they counted for (VERDICT_LEGACY_ROWS=as_counted),
so the deploy moves no level, gold or token. The row is written here, at upgrade time.

Revision ID: f2b4d6e8a0c1
Revises: e1a3c5f7b9d2
Create Date: 2026-11-10
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f2b4d6e8a0c1"
down_revision = "e1a3c5f7b9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verdict_cutover",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("note", sa.String(200), nullable=False, server_default=""),
    )
    op.execute(
        sa.text(
            "INSERT INTO verdict_cutover (id, at, note) "
            "VALUES (1, CURRENT_TIMESTAMP, 'verdict stack (package V stage 1)')"
        )
    )


def downgrade() -> None:
    op.drop_table("verdict_cutover")
