"""Merge the WP-30 journal and WP-32 episode-audio branches.

Both packages were written against the same head (``e48fd9624811``, WP-31's
rehearsals) by concurrent leases, so each added a sibling revision rather than a
chain. Neither touches the other's table — ``journal_entries`` and
``episode_audio_clips`` are independent additive tables — so there is nothing to
reconcile and this revision has no operations of its own. It exists so that
``alembic upgrade head`` has one head to reach.

Revision ID: 79e0beb6c84b
Revises: c7d8e9f0a1b2, 907eb914c502
"""
from __future__ import annotations

revision = "79e0beb6c84b"
down_revision = ("c7d8e9f0a1b2", "907eb914c502")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do: a merge point, not a change."""


def downgrade() -> None:
    """Nothing to undo: splitting the branches again needs no schema change."""
