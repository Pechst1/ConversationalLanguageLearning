"""Pydantic schemas for Story RPG feature."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Story Schemas
# ============================================================================

class StoryRead(BaseModel):
    """Schema for story list and detail views."""
    id: str
    title: str
    subtitle: str | None = None
    source_book: str | None = None
    source_author: str | None = None
    target_levels: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int = 60
    cover_image_url: str | None = None
    is_unlocked: bool = True
    
    class Config:
        from_attributes = True


class StoryProgressRead(BaseModel):
    """Schema for user's story progress."""
    story_id: str
    current_chapter_id: str | None = None
    current_chapter_title: str | None = None
    current_scene_id: str | None = None
    completion_percentage: int = 0
    status: str = "in_progress"
    story_flags: dict[str, Any] = Field(default_factory=dict)
    philosophical_learnings: list[str] = Field(default_factory=list)
    book_quotes_unlocked: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    last_played_at: datetime | None = None
    
    class Config:
        from_attributes = True


class StoryWithProgressRead(StoryRead):
    """Story with optional progress information."""
    progress: StoryProgressRead | None = None


# ============================================================================
# Scene Schemas
# ============================================================================

class ObjectiveRead(BaseModel):
    """Schema for scene objectives."""
    id: str
    description: str
    type: str = "task"  # "talk_to", "convince", "survive", "choose"
    optional: bool = False
    completed: bool = False


class ChoiceOptionRead(BaseModel):
    """Schema for player choice options."""
    id: str
    text: str
    
    
class SceneRead(BaseModel):
    """Schema for scene rendering."""
    id: str
    chapter_id: str
    location: str | None = None
    atmosphere: str | None = None
    narration: str  # Level-appropriate narration
    objectives: list[ObjectiveRead] = Field(default_factory=list)
    npcs_present: list["NPCInSceneRead"] = Field(default_factory=list)
    interaction_type: str = "free_input"  # "free_input", "choice", "drawing"
    choices: list[ChoiceOptionRead] = Field(default_factory=list)
    estimated_duration_minutes: int = 10
    
    class Config:
        from_attributes = True


class ChapterRead(BaseModel):
    """Schema for chapter information."""
    id: str
    story_id: str
    order_index: int
    title: str
    target_level: str | None = None
    
    class Config:
        from_attributes = True


# ============================================================================
# NPC Schemas
# ============================================================================

class NPCRead(BaseModel):
    """Schema for basic NPC information."""
    id: str
    name: str
    display_name: str | None = None
    role: str | None = None
    avatar_url: str | None = None
    
    class Config:
        from_attributes = True


class NPCInSceneRead(NPCRead):
    """NPC with relationship context for scene display."""
    relationship_level: int = 1
    trust: int = 0
    mood: str = "neutral"


class NPCDetailRead(NPCRead):
    """Full NPC details including personality."""
    backstory: str | None = None
    appearance_description: str | None = None
    personality: dict[str, Any] = Field(default_factory=dict)
    speech_pattern: dict[str, Any] = Field(default_factory=dict)


class NPCRelationshipRead(BaseModel):
    """Schema for NPC relationship status."""
    npc_id: str
    npc_name: str
    npc_avatar_url: str | None = None
    level: int = 1
    trust: int = 0
    mood: str = "neutral"
    total_interactions: int = 0
    positive_interactions: int = 0
    negative_interactions: int = 0
    first_interaction_at: datetime | None = None
    last_interaction_at: datetime | None = None
    
    class Config:
        from_attributes = True


class NPCMemoryRead(BaseModel):
    """Schema for NPC memory items."""
    id: str
    memory_type: str
    content: str
    sentiment: str = "neutral"
    scene_id: str | None = None
    player_quote: str | None = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Input Schemas
# ============================================================================

class StoryStartRequest(BaseModel):
    """Request to start or resume a story."""
    pass  # No additional params needed


class StoryInputRequest(BaseModel):
    """Request for player input in a story."""
    content: str  # The player's text input
    target_npc_id: str | None = None  # If multiple NPCs, who is addressed?
    conversation_history: list[dict] | None = None  # Optional client-side history
    choice_id: str | None = None  # ID of the selected choice (if explicit choice)
    is_voice: bool = False


class ChoiceRequest(BaseModel):
    """Request to make a choice in a scene."""
    choice_id: str


# ============================================================================
# Response Schemas
# ============================================================================

class ConsequenceRead(BaseModel):
    """Schema for consequences of player actions."""
    type: str  # "relationship_change", "set_flag", "add_memory", "unlock_info", "trigger_achievement"
    target: str  # NPC id, flag name, etc.
    value: Any = None
    description: str | None = None  # Human-readable description


class NPCResponseRead(BaseModel):
    """Schema for NPC response to player input."""
    npc_id: str
    npc_name: str
    content: str  # The NPC's response text
    emotion: str | None = None
    voice_url: str | None = None  # For TTS
    relationship_delta: int = 0
    new_relationship_level: int = 1
    new_mood: str | None = None
    memory_added: str | None = None
    infobox: "InfoboxRead | None" = None


class InfoboxRead(BaseModel):
    """Schema for educational infobox content."""
    title: str
    content: str
    type: str = "grammar"  # "grammar", "culture", "vocabulary", "story"
    grammar_note: str | None = None
    book_quote: str | None = None


class StoryInputResponse(BaseModel):
    """Full response to player input in a story."""
    npc_response: NPCResponseRead | None = None
    consequences: list[ConsequenceRead] = Field(default_factory=list)
    xp_earned: int = 0
    xp_breakdown: list[dict] = Field(default_factory=list)  # XP breakdown for display
    scene_transition: "SceneTransitionRead | None" = None
    achievements_unlocked: list[str] = Field(default_factory=list)
    errors_detected: list[dict] = Field(default_factory=list)
    updated_flags: list[str] = Field(default_factory=list)


class SceneTransitionRead(BaseModel):
    """Schema for scene transition information."""
    next_scene_id: str
    transition_narration: str | None = None
    chapter_change: bool = False
    new_chapter_title: str | None = None


class StoryStartResponse(BaseModel):
    """Response when starting a story."""
    progress: StoryProgressRead
    scene: SceneRead
    chapter: ChapterRead


# ============================================================================
# Goal Checking Schemas (merged from worktree)
# ============================================================================

class GoalCheckRequest(BaseModel):
    """Request to check narrative goal completion."""
    session_id: str  # UUID as string


class GoalCheckResponse(BaseModel):
    """Response for narrative goal check."""
    goals_completed: list[str] = Field(default_factory=list)
    goals_remaining: list[str] = Field(default_factory=list)
    completion_rate: float = 0.0


class ChapterCompletionRequest(BaseModel):
    """Request to complete a chapter."""
    session_id: str  # UUID as string
    goals_completed: list[str] = Field(default_factory=list)


class ChapterCompletionResponse(BaseModel):
    """Response for chapter completion."""
    xp_earned: int
    achievements_unlocked: list[dict] = Field(default_factory=list)
    next_chapter_id: str | None = None
    next_chapter: ChapterRead | None = None
    story_completed: bool = False
    is_perfect: bool = False


class NarrativeChoiceRequest(BaseModel):
    """Request to make a narrative branching choice."""
    choice_id: str


class NarrativeChoiceResponse(BaseModel):
    """Response for narrative choice."""
    next_chapter_id: str
    next_chapter: ChapterRead | None = None
    choice_recorded: str


# ============================================================================
# Chapter Progress Schemas (merged from worktree)
# ============================================================================

class ChapterWithStatusRead(BaseModel):
    """Chapter with user completion status for chapter timeline."""
    id: str
    story_id: str
    order_index: int
    title: str
    target_level: str | None = None
    is_locked: bool = False
    is_completed: bool = False
    was_perfect: bool = False
    completion_xp: int = 75
    perfect_completion_xp: int = 150

    class Config:
        from_attributes = True


class StoryDetailResponse(BaseModel):
    """Complete story information with chapters and progress."""
    story: StoryRead
    chapters: list[ChapterWithStatusRead] = Field(default_factory=list)
    user_progress: StoryProgressRead | None = None


class NarrativeGoalRead(BaseModel):
    """Schema for narrative goal display."""
    goal_id: str
    description: str
    required_words: list[str] = Field(default_factory=list)
    min_required: int = 1
    is_completed: bool = False


class ChapterSessionResponse(BaseModel):
    """Response for starting a chapter session."""
    chapter: ChapterRead
    narrative_goals: list[NarrativeGoalRead] = Field(default_factory=list)
    vocabulary_words: list[dict] = Field(default_factory=list)
    session_id: str


# Update forward references
SceneRead.model_rebuild()
StoryInputResponse.model_rebuild()
NPCResponseRead.model_rebuild()
ChapterCompletionResponse.model_rebuild()
NarrativeChoiceResponse.model_rebuild()
