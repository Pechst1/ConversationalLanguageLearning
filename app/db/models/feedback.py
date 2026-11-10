"""Pilot feedback report models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class UserFeedbackReport(Base):
    """Small, route-aware feedback report submitted from the global pilot widget."""

    __tablename__ = "user_feedback_reports"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    route: Mapped[str] = mapped_column(String(240), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    screen: Mapped[str | None] = mapped_column(String(120), nullable=True)
    viewport = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    # S4 stage 4: the learner asked to be answered (at the account's address).
    # Stored only; nothing sends a reply yet.
    wants_reply: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User")

    __table_args__ = (
        Index("ix_user_feedback_reports_user_id", "user_id"),
        Index("ix_user_feedback_reports_category", "category"),
        Index("ix_user_feedback_reports_route", "route"),
        Index("ix_user_feedback_reports_created_at", "created_at"),
    )


__all__ = ["UserFeedbackReport"]
