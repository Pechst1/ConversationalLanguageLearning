"""WP-91 «Les voix» — one spoken line of a daily journey, cached per voice and text.

Why not :class:`~app.db.models.episode_audio.EpisodeAudioClip`: that cache is
keyed by a story-engine *scene revision* (``scene_id`` is required), while a
voice in the journey speaks lines that belong to no scene — the character's
reply in the respond step, the ending's line, an authored scene's panel, a
listening item. What those lines share is only *who says what*, so this cache
is keyed by exactly that:

* ``clip_id`` is ``"{voice}-{digest}"`` where the digest is over the voice and
  the normalised text (:func:`app.services.line_audio.clip_id_for`). The same
  line in the same voice is the same clip id on every day and for every
  learner, and it is what the listening items' ``audio_url`` carries.
* ``(user_id, clip_id, model)`` is unique: a replay finds the row and makes no
  paid call. A second learner asking for a line someone already paid for gets a
  copy of those bytes, also without a call (and without a cost row).
* ``user_id`` owns the row: ``GET /daily-journeys/line-audio/{clip_id}`` serves
  only the caller's own clips, and a deleted learner takes theirs with them.

The bytes live in the column, as for the radio episode: a line is a few tens of
kB of mp3 and worthless without the day it was spoken in.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class LineAudioClip(Base):
    """One synthesized line, in one voice, for one learner."""

    __tablename__ = "line_audio_clips"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: ``"{voice}-{digest}"``, stable across days and learners for one line.
    clip_id: Mapped[str] = mapped_column(String(80), nullable=False)
    voice: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    #: The speaker the line was resolved to (``narrator`` for narration), or ``""``.
    character_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    #: Exactly what was spoken.
    text_fr: Mapped[str] = mapped_column(Text, nullable=False, default="")
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(
        String(40), nullable=False, default="audio/mpeg"
    )
    audio: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "clip_id", "model", name="uq_line_audio_clip_owner"),
        Index("ix_line_audio_clips_clip_model", "clip_id", "model"),
    )


__all__ = ["LineAudioClip"]
