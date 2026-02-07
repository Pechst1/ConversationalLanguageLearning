"""Scenario state tracking models."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserScenarioState(Base):
    """Tracks a user's progress and state within a specific scenario."""

    __tablename__ = "user_scenario_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id = Column(String(50), nullable=False, index=True)
    
    # State Data
    state_data = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)  # Inventory, facts known, etc.
    current_goal_index = Column(Integer, default=0)
    status = Column(String(20), default="in_progress")  # "in_progress", "completed", "abandoned"
    
    last_interaction_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="scenario_states")
