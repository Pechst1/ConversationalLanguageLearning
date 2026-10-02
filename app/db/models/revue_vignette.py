"""The Revue's vignette (WP-120 §4): the shared pictogram and each learner's minted stamp.

``revue_pictograms`` holds one validated SVG per dossier, drawn once by the model in
the house grammar (``app/services/revue/pictogram.py``) and shared by every learner
who reads that story; an authored topic fallback is stored the same way when the model
fails twice, so a story never costs a second round. ``revue_vignettes`` is what one
learner brought back from one closed Papier: the ring (what they made), whether their
part was kept in the dispatch, the week and the place. One per session (unique), so
minting is idempotent. ``app/services/revue/vignette.py`` is the only writer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

VIGNETTE_RINGS: tuple[str, ...] = ("headline", "question", "report")


class RevuePictogram(Base):
    __tablename__ = "revue_pictograms"

    dossier_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    object_fr: Mapped[str] = mapped_column(String(200), nullable=False)
    svg: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``PROMPT_VERSION`` of the drawing, or ``fallback-v1:<topic>`` for an authored fallback.
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RevueVignette(Base):
    __tablename__ = "revue_vignettes"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("revue_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    dossier_id: Mapped[str] = mapped_column(String(120), nullable=False)
    #: ``headline`` (ink) · ``question`` (blue) · ``report`` (red): what the learner made.
    ring: Mapped[str] = mapped_column(String(16), nullable=False)
    kept_contribution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: ISO week, ``"2026-W40"``.
    week: Mapped[str] = mapped_column(String(8), nullable=False)
    place_label_fr: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    minted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (Index("ix_revue_vignettes_user_minted", "user_id", "minted_at"),)
