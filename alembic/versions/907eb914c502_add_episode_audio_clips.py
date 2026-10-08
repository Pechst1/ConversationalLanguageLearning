"""Add the episode_audio_clips cache (WP-32).

Additive only: one new table, no column on any existing one. The radio episode
is opt-in and its feature flag defaults to false, so a deploy that runs this
migration and then rolls the code back leaves an empty table behind, which is
inert.

Revision ID: 907eb914c502
Revises: e48fd9624811
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "907eb914c502"
down_revision = "e48fd9624811"
branch_labels = None
depends_on = None

TABLE = "episode_audio_clips"


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
            "scene_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graphic_novel_scenes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.String(length=32), nullable=False),
        sa.Column("line_key", sa.String(length=80), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("voice", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=60), nullable=False, server_default=""),
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
        sa.UniqueConstraint(
            "scene_id", "revision", "line_key", name="uq_episode_audio_clip_line"
        ),
    )
    op.create_index(f"ix_{TABLE}_scene_id", TABLE, ["scene_id"])
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
    op.create_index(
        "ix_episode_audio_clips_scene_revision", TABLE, ["scene_id", "revision", "ordinal"]
    )


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    op.drop_index("ix_episode_audio_clips_scene_revision", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_scene_id", table_name=TABLE)
    op.drop_table(TABLE)
