"""WP-115e: what the scheduler predicted, and how long it had been.

Additive only: ``review_logs.predicted_r`` (recall probability at the review) and
``review_logs.elapsed_days_exact`` (days since the previous review), so retention can
be measured against the prediction (calibration) and by lag (the forgetting curve).

Revision ID: a8c0e2f4b6d8
Revises: f7b9d1e3a5c7
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a8c0e2f4b6d8"
down_revision = "f7b9d1e3a5c7"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table: str, column: str) -> bool:
    if _offline_mode():
        return False
    return column in {row["name"] for row in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for name in ("predicted_r", "elapsed_days_exact"):
        if not _has_column("review_logs", name):
            op.add_column("review_logs", sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in ("elapsed_days_exact", "predicted_r"):
        if _has_column("review_logs", name):
            op.drop_column("review_logs", name)
