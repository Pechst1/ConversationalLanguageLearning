"""The story picture of one Papier story (WP-119 §8.4).

One row per dossier, shared by every learner and final: the picture is painted once, at
intake, by ``app/services/revue/plates.py:paint_story`` (the only writer) and never
repainted. ``flagged`` keeps what the cheap post-check (a flag band, ``plates.looks_wrong``)
said about it; it is a note for the owner, not a reason to paint again.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class RevueStoryPicture(Base):
    __tablename__ = "revue_story_pictures"

    dossier_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    #: The place the picture shows (the dossier's site, ``places[0]``).
    place_id: Mapped[str] = mapped_column(String(120), nullable=False)
    picture_url: Mapped[str] = mapped_column(Text, nullable=False)
    #: The desk's caption printed under it (``visual.caption_fr``, as painted).
    caption_fr: Mapped[str] = mapped_column(Text, nullable=False)
    #: The full prompt, so the owner can read what was asked.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``plates.STORY_PROMPT_VERSION`` of the template.
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    painted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
