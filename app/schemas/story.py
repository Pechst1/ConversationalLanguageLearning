"""Pydantic models for story workflows."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Base models for stories and chapters
# ============================================================================


class StoryBase(BaseModel):
    """Base story information."""

    id: int
    story_key: str
    title: str
    description: str | None = None
    difficulty_level: str | None = None
    estimated_duration_minutes: int | None = None
    theme_tags: list[str] = Field(default_factory=list)
    vocabulary_theme: str | None = None
    cover_image_url: str | None = None
    author: str | None = None
    total_chapters: int = 0
    is_published: bool = False


class ChapterBase(BaseModel):
    """Base chapter information."""

    id: int
    chapter_key: str
    sequence_order: int
    title: str
    synopsis: str | None = None
    opening_narrative: str | None = None
    min_turns: int = 3
    max_turns: int = 10
    narrative_goals: list[dict[str, Any]] = Field(default_factory=list)
    completion_criteria: dict[str, Any] | None = None
    branching_choices: list[dict[str, Any]] | None = None
    completion_xp: int = 75
    perfect_completion_xp: int = 150


# ============================================================================
# Progress models
# ============================================================================


class UserStoryProgressBase(BaseModel):
    """User progress through a story."""

    id: UUID
    user_id: UUID
    story_id: int
    current_chapter_id: int | None = None
    status: str = "in_progress"
    chapters_completed: list[dict[str, Any]] = Field(default_factory=list)
    total_chapters_completed: int = 0
    completion_percentage: float = 0.0
    total_xp_earned: int = 0
    total_time_spent_minutes: int = 0
    vocabulary_mastered_count: int = 0
    perfect_chapters_count: int = 0
    narrative_choices: dict[str, str] = Field(default_factory=dict)
    started_at: datetime
    last_accessed_at: datetime
    completed_at: datetime | None = None


# ============================================================================
# API Response models
# ============================================================================


class StoryProgressSummary(BaseModel):
    """Summary of user progress on a story."""

    is_started: bool
    is_completed: bool
    completion_percentage: float
    current_chapter_number: int | None = None
    current_chapter_title: str | None = None
    chapters_completed: int
    total_xp_earned: int


class StoryListItem(BaseModel):
    """Story information for library listing."""

    story: StoryBase
    user_progress: StoryProgressSummary | None = None


class ChapterWithStatus(BaseModel):
    """Chapter with user completion status."""

    chapter: ChapterBase
    is_locked: bool
    is_completed: bool
    was_perfect: bool


class StoryDetailResponse(BaseModel):
    """Complete story information with chapters."""

    story: StoryBase
    chapters: list[ChapterWithStatus]
    user_progress: UserStoryProgressBase | None = None


class UserStoryProgressResponse(BaseModel):
    """User story progress with current chapter details."""

    progress: UserStoryProgressBase
    current_chapter: ChapterBase | None = None


# ============================================================================
# API Request models
# ============================================================================


class ChapterSessionRequest(BaseModel):
    """Request to start a chapter session."""

    planned_duration_minutes: int = Field(15, ge=5, le=180)
    difficulty_preference: str | None = None


class ChapterCompletionRequest(BaseModel):
    """Request to mark chapter as complete."""

    session_id: UUID
    goals_completed: list[str] = Field(
        default_factory=list,
        description="List of goal_ids that were completed",
    )


class ChapterCompletionResponse(BaseModel):
    """Response from completing a chapter."""

    xp_earned: int
    achievements_unlocked: list[dict[str, Any]] = Field(default_factory=list)
    next_chapter_id: int | None = None
    next_chapter: ChapterBase | None = None
    story_completed: bool
    is_perfect: bool


class NarrativeChoiceRequest(BaseModel):
    """Request to record a narrative choice."""

    choice_id: str = Field(..., description="Choice ID from branching_choices")


class NextChapterResponse(BaseModel):
    """Response after making a narrative choice."""

    next_chapter: ChapterBase
    choice_recorded: str


# ============================================================================
# Session integration
# ============================================================================


class StorySessionStartRequest(BaseModel):
    """Request to start a story-based learning session."""

    story_id: int
    chapter_id: int
    planned_duration_minutes: int = Field(15, ge=5, le=180)
    difficulty_preference: str | None = None


class StorySessionStartResponse(BaseModel):
    """Response when starting a story session."""

    session_id: UUID
    chapter: ChapterBase
    opening_message: str
    suggested_vocabulary: list[dict[str, Any]]
    narrative_goals: list[dict[str, Any]]


class GoalCheckRequest(BaseModel):
    """Request to check narrative goal completion."""

    session_id: UUID


class GoalCheckResponse(BaseModel):
    """Response from checking narrative goals."""

    goals_completed: list[str] = Field(
        default_factory=list,
        description="List of goal_ids that have been completed",
    )
    goals_remaining: list[str] = Field(
        default_factory=list,
        description="List of goal_ids that remain to be completed",
    )
    completion_rate: float = Field(
        ...,
        description="Percentage of goals completed (0.0 to 1.0)",
    )
