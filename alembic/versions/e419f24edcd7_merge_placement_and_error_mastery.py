"""Merge the placement-sessions and user-error-mastery branches.

Revision ID: e419f24edcd7
Revises: b8e8c24ffddf, b5c6d7e8f9a0
Create Date: 2026-09-10

Both WP-24 and WP-25 branched off a3b4c5d6e7f8 concurrently; this
merge revision restores a single head. No schema change.
"""

revision = "e419f24edcd7"
down_revision = ("b8e8c24ffddf", "b5c6d7e8f9a0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
