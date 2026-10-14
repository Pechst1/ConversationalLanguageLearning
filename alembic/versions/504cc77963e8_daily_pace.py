"""Round 3: the learner's pace for the daily session (Ruhig / Normal / Schnell).

``users.daily_pace``: the pace the learner picked on the Tempo sheet. It sets
the day's new words, the grammar rules a week and the La Forge séance length
(``app.services.daily_session.PACES``). Empty means the learner never picked
one: their stored ``new_words_per_day`` and rhythm keep working as before.
Only adds a nullable column.

#136 first shipped this as ``a7c9e1b3d5f7``, the same id #137 gave
``revue_story_pictures``, so a database stamped ``a7c9e1b3d5f7`` holds one
of the two. Production ran #137's; a database that ran #136's has the column
and lacks the table. Both steps here therefore run only when needed.

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
    inspector = sa.inspect(op.get_bind())
    if "daily_pace" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("daily_pace", sa.String(16), nullable=True))
    if not inspector.has_table("revue_story_pictures"):
        # The copy of a7c9e1b3d5f7_revue_story_pictures for a database that ran #136's a7c9e1b3d5f7.
        op.create_table(
            "revue_story_pictures",
            sa.Column("dossier_id", sa.String(120), primary_key=True),
            sa.Column("place_id", sa.String(120), nullable=False),
            sa.Column("picture_url", sa.Text(), nullable=False),
            sa.Column("caption_fr", sa.Text(), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("prompt_version", sa.String(40), nullable=False),
            sa.Column("model", sa.String(80), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column("flagged", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("painted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_column("users", "daily_pace")
