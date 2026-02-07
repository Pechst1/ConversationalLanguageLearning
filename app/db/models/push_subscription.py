"""Push Notification Subscription model."""
import uuid
from sqlalchemy import Column, ForeignKey, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.db.base import Base

class PushSubscription(Base):
    """Stores Web Push API subscription details for a user."""
    __tablename__ = "push_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    endpoint = Column(Text, nullable=False)
    keys = Column(JSONB, nullable=False)  # Stores { p256dh: "...", auth: "..." }
    
    user_agent = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
