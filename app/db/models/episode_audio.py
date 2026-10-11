"""WP-32 — the synthesized radio episode, cached per scene revision.

One row is one spoken line: the narrator's sentence or one character's line,
with the voice it was spoken in and the bytes the provider returned.

Why a table rather than a JSON blob on the panel (which is what
``GraphicNovelPanel.audio_payload`` does for the serial Feuilleton): the radio
episode is played **line by line**, the learner may replay one line, and a
failed line must be re-synthesizable without paying for the whole episode
again. A per-line row is also what makes the cache honest — a partially
synthesized episode is visibly partial instead of a blob that looks complete.

Three properties the columns exist to keep:

* **Cached per scene revision.** ``revision`` is a digest of the exact text,
  voices and TTS model that produced the audio (see
  :func:`app.services.episode_audio.scene_revision`). A regenerated scene, one
  corrected line, or a changed model all yield a new revision, so nothing ever
  plays audio that no longer matches the words on screen. Old rows stay
  addressable and are simply never asked for again.
* **Idempotent.** ``(scene_id, revision, line_key)`` is unique: a replayed
  request finds the row and makes no paid call. This is the only thing standing
  between the daily journey and paying for the same episode twice a day.
* **Owned.** ``user_id`` is denormalised from the scene so a clip can be
  authorised without a join, and so a deleted learner takes their audio with
  them.

The bytes live in the column. They are small (a few tens of kB per line at
``tts-1``'s mp3), they are worthless without the scene they belong to, and an
object store would need a second lifecycle to delete them when the scene goes.
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


class EpisodeAudioClip(Base):
    """One synthesized line of one revision of one story-engine scene."""

    __tablename__ = "episode_audio_clips"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scene_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("graphic_novel_scenes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Digest of the text + voices + model this audio was made from.
    revision: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Stable identity of the line inside the scene; the frontend derives the
    #: same key from the published episode, so a manifest needs no index maths.
    line_key: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Playback order within the episode.
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    #: ``narrator`` for narration, otherwise the dialogue line's character id.
    character_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    voice: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    #: The exact French that was spoken. Kept so a cache row can be verified
    #: against the scene without re-deriving it, and so the verify stage can
    #: reveal precisely what was heard.
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
        UniqueConstraint(
            "scene_id", "revision", "line_key", name="uq_episode_audio_clip_line"
        ),
        Index("ix_episode_audio_clips_scene_revision", "scene_id", "revision", "ordinal"),
    )


__all__ = ["EpisodeAudioClip"]
