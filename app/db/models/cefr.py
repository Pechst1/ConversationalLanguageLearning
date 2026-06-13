"""Persisted CEFR estimate history."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class UserCEFRProgressHistory(Base):
    """Point-in-time CEFR estimate snapshots for smoothing and forecasting."""

    __tablename__ = "user_cefr_progress_history"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    estimate_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="recompute", nullable=False)
    signal_snapshot = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_user_cefr_history_user_created", "user_id", "created_at"),
    )


__all__ = ["UserCEFRProgressHistory"]
