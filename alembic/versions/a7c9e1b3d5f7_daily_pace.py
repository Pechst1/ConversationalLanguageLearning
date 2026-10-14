"""Round 3: the learner's pace for the daily session (Ruhig / Normal / Schnell).

``users.daily_pace``: the pace the learner picked on the Tempo sheet. It sets
the day's new words, the grammar rules a week and the La Forge séance length
(``app.services.daily_session.PACES``). Empty means the learner never picked
one: their stored ``new_words_per_day`` and rhythm keep working as before.
Only adds a nullable column.

Revision ID: a7c9e1b3d5f7
Revises: f1b3d5e7a9c2
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a7c9e1b3d5f7"
down_revision = "f1b3d5e7a9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("daily_pace", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "daily_pace")
