"""Merge the password-reset outbox head into the Revue heads (2026-10-06, WP-135).

The 09-30 production hardening (b9d1f3a5c7e0, password_reset_deliveries) was
written on a tree that never saw the WP-119–122 heads merged in b1d3f5a7c9e2.
Both only add tables, so the merge carries no schema change.

Revision ID: d2f4a6c8e0b1
Revises: b1d3f5a7c9e2, b9d1f3a5c7e0
Create Date: 2026-10-06
"""

from __future__ import annotations

revision = "d2f4a6c8e0b1"
down_revision = ("b1d3f5a7c9e2", "b9d1f3a5c7e0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
