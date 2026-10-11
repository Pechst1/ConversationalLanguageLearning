"""Le Correcteur (WP-122 §4): one row per proofreading attempt.

``draft`` holds the whole draft as the service built it, including the private key
(the seeded spans, the unseeded base text and the fact checks' verdicts); the
learner's client only ever sees the public view (``revue/correcteur.public_view``).
``result`` is the graded marks, written once by ``POST …/marks`` (null until then).
``app/services/revue/correcteur.py`` is the only writer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class RevueCorrection(Base):
    __tablename__ = "revue_corrections"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dossier_id: Mapped[str] = mapped_column(String(120), nullable=False)
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (Index("ix_revue_corrections_user_created", "user_id", "created_at"),)
