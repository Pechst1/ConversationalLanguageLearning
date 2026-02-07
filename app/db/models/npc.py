"""NPC and relationship models for the RPG feature."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class NPC(Base):
    """Represents a non-player character with personality and speech patterns."""

    __tablename__ = "npcs"

    id = Column(String(50), primary_key=True)  # e.g., "petit_prince"
    story_id = Column(String(50), ForeignKey("stories.id", ondelete="CASCADE"), index=True)  # Optional, for story-specific NPCs
    
    # Basic identity
    name = Column(String(100), nullable=False)
    display_name = Column(String(100))  # e.g., "Das Kind" before introduction
    role = Column(String(255))  # e.g., "Der kleine Prinz"
    backstory = Column(Text)
    
    # Visual
    avatar_url = Column(String(500))
    appearance_description = Column(Text)
    
    # Personality configuration
    personality = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {
    #   core_traits: ["curious", "persistent"],
    #   patience: 0.8,
    #   formality: 0.3,
    #   humor: 0.5,
    #   openness: 0.9
    # }
    
    # Speech patterns for LLM prompts
    speech_pattern = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {
    #   base_complexity: "A1",
    #   adapt_to_player: true,
    #   uses_slang: false,
    #   speaking_speed: "slow",
    #   example_quotes: ["S'il te plaît...", "Tu viens d'où?"],
    #   quirks: ["Never answers before his request is fulfilled"]
    # }
    
    # Voice synthesis configuration
    voice_config = Column(JSONB().with_variant(JSON(), "sqlite"))
    # Structure: {speed: 0.8, tone: "curious, gentle", pronunciation: "clear"}
    
    # Information tiers (what secrets they reveal at different relationship levels)
    information_tiers = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {3: ["mentions_asteroid"], 5: ["tells_about_rose"], 7: ["shares_regret"]}
    
    # Relationship behavior
    relationship_config = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {
    #   initial_level: 1,
    #   max_level: 10,
    #   likes_when: ["player_asks_questions", "player_uses_polite_register"],
    #   dislikes_when: ["player_is_dismissive", "player_rushes"]
    # }
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    story = relationship("Story")


class NPCRelationship(Base):
    """Tracks the relationship between a user and an NPC."""

    __tablename__ = "npc_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    npc_id = Column(String(50), ForeignKey("npcs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationship state
    level = Column(Integer, default=1)  # 0-10
    trust = Column(Integer, default=0)  # -5 to +5
    mood = Column(String(50), default="neutral")  # "neutral", "happy", "suspicious", "sad", "angry"
    
    # Tracking
    total_interactions = Column(Integer, default=0)
    positive_interactions = Column(Integer, default=0)
    negative_interactions = Column(Integer, default=0)
    
    # Special flags
    has_shared_secret = Column(Integer, default=0)  # Which tier of secrets shared
    is_ally = Column(Integer, default=0)  # Boolean workaround for SQLite
    is_rival = Column(Integer, default=0)
    
    # Timestamps
    first_interaction_at = Column(DateTime(timezone=True), server_default=func.now())
    last_interaction_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="npc_relationships")
    npc = relationship("NPC")
    
    # Unique constraint: one relationship per user per NPC
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
    
    def update_level(self, delta: int) -> None:
        """Update relationship level, clamping to valid range."""
        self.level = max(0, min(10, self.level + delta))
        self.last_interaction_at = datetime.utcnow()
        self.total_interactions += 1
        if delta > 0:
            self.positive_interactions += 1
        elif delta < 0:
            self.negative_interactions += 1
    
    def update_trust(self, delta: int) -> None:
        """Update trust level, clamping to valid range."""
        self.trust = max(-5, min(5, self.trust + delta))


class NPCMemory(Base):
    """Episodic memory of NPC interactions with a user."""

    __tablename__ = "npc_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    npc_id = Column(String(50), ForeignKey("npcs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Memory content
    memory_type = Column(String(50), nullable=False)  # "fact", "interaction", "milestone", "notable_quote"
    content = Column(Text, nullable=False)
    
    # Context
    scene_id = Column(String(50))  # Which scene this memory is from
    sentiment = Column(String(20), default="neutral")  # "positive", "neutral", "negative"
    importance = Column(Integer, default=5)  # 1-10, for memory prioritization
    
    # For notable quotes
    player_quote = Column(Text)  # What the player said that was memorable
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", backref="npc_memories")
    npc = relationship("NPC")
