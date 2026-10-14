"""Round 3: the learner's pace for the daily session (Ruhig / Normal / Schnell).

``users.daily_pace``: the pace the learner picked on the Tempo sheet. It sets
the day's new words, the grammar rules a week and the La Forge séance length
(``app.services.daily_session.PACES``). Empty means the learner never picked
one: their stored ``new_words_per_day`` and rhythm keep working as before.
Only adds a nullable column.

Revision ID: 504cc77963e8
Revises: a7c9e1b3d5f7
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "504cc77963e8"
down_revision = "a7c9e1b3d5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("daily_pace", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "daily_pace")
