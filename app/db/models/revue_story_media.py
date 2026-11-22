"""The other pictures of one Papier story («Papier · photos», 2026-11-20).

The story's first picture stays in ``revue_story_pictures`` (WP-119 §8.4). This table holds what
the gallery shows after it, one row per picture, shared by every learner and final:

* ``kind="photo"``: a real photo from Wikimedia Commons found for one of the story's subjects
  (``app/services/revue/photos.py``, the only writer of those rows). The image is hot-linked
  (``image_url`` is the Commons thumbnail; no bytes are copied), with its licence, author and the
  French credit line the gallery prints under it.
* ``kind="illustration"``: another painted shot of the same story (the place wide, the thing
  close), when ``REVUE_PICTURES_PER_STORY`` is 2 or 3 (``plates.paint_story_shot``), painted once,
  never repainted, priced like the first picture.

``position`` orders the rows of one kind within a story (photos 1…N in subject order;
illustrations 2…3, the first being ``revue_story_pictures``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class RevueStoryMedia(Base):
    __tablename__ = "revue_story_media"
    __table_args__ = (UniqueConstraint("dossier_id", "kind", "position", name="uq_revue_story_media_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dossier_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    #: ``photo`` (Wikimedia Commons) or ``illustration`` (painted, like the story's first picture).
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The picture's URL: the Commons thumbnail (hot-linked) or the stored painting.
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: A photo's file page on Commons (the source link).
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: «CC BY-SA 4.0», «CC0», «Domaine public»; ``None`` for an illustration (it is ours).
    licence: Mapped[str | None] = mapped_column(String(80), nullable=True)
    licence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: What the gallery prints under it: «Photo · {author} · {licence} · Wikimedia Commons», or
    #: «Illustration · Le Papier».
    credit_fr: Mapped[str] = mapped_column(String(400), nullable=False)
    #: A French caption stated from the dossier's own facts (a photo of a named place), else none.
    caption_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What the photo was searched for (a place, the story's object) or the shot an illustration is.
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: An illustration's full prompt and template version (``None`` for a photo).
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
