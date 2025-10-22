"""Analytics snapshot model."""
import uuid
from datetime import date

from sqlalchemy import Column, Date, Float, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class AnalyticsSnapshot(Base):
    """Daily analytics snapshot for longitudinal tracking."""

    __tablename__ = "analytics_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_date = Column(Date, nullable=False, index=True)

    total_words_seen = Column(Integer, default=0)
    words_learning = Column(Integer, default=0)
    words_mastered = Column(Integer, default=0)
    new_words_today = Column(Integer, default=0)
    reviews_completed = Column(Integer, default=0)

    average_accuracy = Column(Float)
    average_response_time_ms = Column(Integer)
    streak_length = Column(Integer)

    created_at = Column(Date, server_default=func.current_date())

    def mark_snapshot(self, snapshot_day: date) -> None:
        """Update the snapshot date."""

        self.snapshot_date = snapshot_day
