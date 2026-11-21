"""S6 stage 2: a flag for walk and test accounts.

``users.is_synthetic``: true for an account that is not a learner (a walk account,
the owner's test accounts). The cohort view leaves these out by default. Every
existing row starts false; which accounts to mark is the owner's call
(``scripts/mark_synthetic_accounts.py``). Only adds a column.

Revision ID: d6f8a0b2c4e7
Revises: c5e7a9b1d3f6
Create Date: 2026-11-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d6f8a0b2c4e7"
down_revision = "c5e7a9b1d3f6"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column() -> bool:
    if _offline_mode():
        return False
    return "is_synthetic" in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}


def upgrade() -> None:
    if _has_column():
        return
    op.add_column(
        "users",
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    if _offline_mode() or _has_column():
        op.drop_column("users", "is_synthetic")
