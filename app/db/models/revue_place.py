"""A place La Revue painted a plate for (WP-119 §8.1, phase 4 «Les planches»).

One row per place id, shared by every learner and kept forever: a plate is painted once
(``app/services/revue/plates.py:paint`` is the only writer) and a later season day can
reuse "the vineyard the Revue painted in week 40". Known season places never get a row;
they keep ``SEASON_ONE_LOCATIONS``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class RevuePlace(Base):
    __tablename__ = "revue_places"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name_fr: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The normalised brief the plate was painted from (name + three landmarks + light).
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    plate_url: Mapped[str] = mapped_column(Text, nullable=False)
    painted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    #: ``plates.PROMPT_VERSION`` of the template the plate was painted with.
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
