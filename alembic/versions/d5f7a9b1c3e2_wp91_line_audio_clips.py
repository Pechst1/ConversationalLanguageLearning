"""Add the line_audio_clips cache (WP-91 «Les voix»).

Additive only: one new table, no column on any existing one. With
``ATELIER_EPISODE_AUDIO_ENABLED`` off nothing writes to it, and a deploy that
runs this migration and then rolls the code back leaves an empty, inert table.

Revision ID: d5f7a9b1c3e2
Revises: c4e6a8b0d2f1
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d5f7a9b1c3e2"
down_revision = "c4e6a8b0d2f1"
branch_labels = None
depends_on = None

TABLE = "line_audio_clips"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clip_id", sa.String(length=80), nullable=False),
        sa.Column("voice", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("character_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("text_fr", sa.Text(), nullable=False, server_default=""),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "content_type", sa.String(length=40), nullable=False, server_default="audio/mpeg"
        ),
        sa.Column("audio", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "clip_id", "model", name="uq_line_audio_clip_owner"),
    )
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
    op.create_index("ix_line_audio_clips_clip_model", TABLE, ["clip_id", "model"])


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    op.drop_index("ix_line_audio_clips_clip_model", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_table(TABLE)
