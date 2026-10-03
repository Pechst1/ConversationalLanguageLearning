"""La Relecture (WP-121 B.3): the learner's second answer to their own Papier's question.

One row per closed ``revue_sessions`` row (unique ``session_id``): a Papier is re-asked
at most once. ``answer_fr`` is what the learner said today (typed, or the transcript
when spoken: ``mode``); ``evidence`` keeps the phase-2 rubric's reading of both answers,
the underlined spans and Romy's one line, so the pair shows again exactly as it did.
``app/services/revue/relecture.py`` is the only writer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

RELECTURE_MODES: tuple[str, ...] = ("text", "voice")


class RevueRelecture(Base):
    __tablename__ = "revue_relectures"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("revue_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    answer_fr: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="text")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)

    __table_args__ = (Index("ix_revue_relectures_user_asked", "user_id", "asked_at"),)
