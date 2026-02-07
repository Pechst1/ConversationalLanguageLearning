"""Story and narrative content models for the RPG feature."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Story(Base):
    """Represents an interactive story adapted from literature."""

    __tablename__ = "stories"

    id = Column(String(50), primary_key=True)  # e.g., "petit_prince"
    title = Column(String(255), nullable=False)
    subtitle = Column(String(255))
    
    # Source information
    source_book = Column(String(255))  # e.g., "Le Petit Prince"
    source_author = Column(String(255))  # e.g., "Antoine de Saint-Exupéry"
    gutenberg_id = Column(String(20))  # Optional Gutenberg reference
    
    # Target audience
    target_levels = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)  # ["A1", "A2"]
    themes = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)  # ["loneliness", "love"]
    
    # Learning objectives
    learning_objectives = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {grammar: [...], vocabulary: [...], functions: [...]}
    
    # Metadata
    estimated_duration_minutes = Column(Integer, default=60)
    cover_image_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    chapters = relationship("Chapter", back_populates="story", cascade="all, delete-orphan", order_by="Chapter.order_index")


class Chapter(Base):
    """A chapter within a story, containing multiple scenes."""

    __tablename__ = "chapters"

    id = Column(String(50), primary_key=True)  # e.g., "chapter1_arrival"
    story_id = Column(String(50), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    order_index = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    target_level = Column(String(10))  # e.g., "A1", "A2", "B1"
    
    # Learning focus for this chapter
    learning_focus = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {grammar: [...], vocabulary: [...], functions: [...]}

    # Specific grammar concepts to practice in this chapter (links to GrammarConcept IDs)
    grammar_focus = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [concept_id1, concept_id2] - IDs from grammar_concepts table
    
    # Optional cliffhanger at chapter end
    cliffhanger = Column(JSONB().with_variant(JSON(), "sqlite"))
    # Structure: {text: "...", hook: "...", next_chapter_teaser: "..."}
    
    # Unlock conditions
    unlock_conditions = Column(JSONB().with_variant(JSON(), "sqlite"))
    # Structure: {requires_chapter: "...", requires_level: "...", requires_flag: "..."}

    # Narrative goals for chapter completion (merged from worktree)
    narrative_goals = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{goal_id: "...", description: "...", required_words: ["word1", "word2"], min_required: 2}]

    # Completion criteria
    completion_criteria = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {min_goals: 2, min_vocabulary: 5}

    # Branching choices at chapter end
    branching_choices = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{choice_id: "...", text: "...", next_chapter_id: "..."}]

    # Default next chapter for linear progression
    default_next_chapter_id = Column(String(50), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True)

    # XP rewards
    completion_xp = Column(Integer, default=75)
    perfect_completion_xp = Column(Integer, default=150)

    # Vocabulary theme for SRS integration
    vocabulary_theme = Column(String(100))  # e.g., "cafe,food,ordering"

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    story = relationship("Story", back_populates="chapters")
    scenes = relationship("Scene", back_populates="chapter", cascade="all, delete-orphan", order_by="Scene.order_index")


class Scene(Base):
    """An interactive scene within a chapter."""

    __tablename__ = "scenes"

    id = Column(String(50), primary_key=True)  # e.g., "scene_platform"
    chapter_id = Column(String(50), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    
    order_index = Column(Integer, nullable=False)
    
    # Scene setting
    location = Column(String(255))
    description = Column(Text)
    atmosphere = Column(String(100))  # e.g., "mysterious", "warm", "tense"
    
    # Level-adaptive narration
    narration_variants = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {A1: "...", A2: "...", B1: "..."}
    
    # Scene objectives
    objectives = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{id: "...", description: "...", type: "talk_to|convince|survive", optional: bool}]
    
    # NPCs present in this scene
    npcs_present = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: ["petit_prince", "narrator"]
    
    # Consequence triggers and effects
    consequences = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{trigger: {...}, effects: [...]}]
    
    # Scene transition rules
    transition_rules = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{condition: {...}, next_scene: "...", narration: "..."}]
    
    # Interaction configuration (choices, prompts, etc.)
    player_interaction = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {type: "free_input"|"choice", prompt: ..., options: [...]}
    
    # Estimated duration
    estimated_duration_minutes = Column(Integer, default=10)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    chapter = relationship("Chapter", back_populates="scenes")


class StoryProgress(Base):
    """Tracks a user's progress and state within a story."""

    __tablename__ = "story_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    story_id = Column(String(50), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Current position
    current_chapter_id = Column(String(50))
    current_scene_id = Column(String(50))
    
    # Story flags set by consequences
    story_flags = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {discovered_secret: true, bribed_waiter: true}
    
    # Player choices for branching
    player_choices = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{scene_id: "...", choice_id: "...", timestamp: "..."}]
    
    # Philosophical learnings (from Petit Prince)
    philosophical_learnings = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: ["heart_sees_clearly", "time_invested_matters"]
    
    # Book quotes unlocked
    book_quotes_unlocked = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: ["on_ne_voit_bien", "c_est_le_temps_perdu"]
    
    # Completion tracking
    chapters_completed = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    completion_percentage = Column(Integer, default=0)

    # Detailed chapter completion tracking (merged from worktree)
    chapters_completed_details = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [{chapter_id: "...", completed_at: "...", xp_earned: 75, was_perfect: true, goals_completed: [...]}]

    # Narrative choices made during branching
    narrative_choices = Column(JSONB().with_variant(JSON(), "sqlite"), default=dict)
    # Structure: {chapter_choice_id: selected_choice_id}

    # XP tracking
    total_xp_earned = Column(Integer, default=0)
    perfect_chapters_count = Column(Integer, default=0)

    # Status
    status = Column(String(20), default="in_progress")  # "in_progress", "completed", "abandoned"
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_played_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", backref="story_progress")
    story = relationship("Story")
    
    # Unique constraint: one progress per user per story
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
