"""Pydantic models for session workflows."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """Payload for starting a learning session."""

    planned_duration_minutes: int = Field(..., ge=5, le=180)
    topic: str | None = Field(None, max_length=255)
    conversation_style: str = Field(
        "tutor",
        description="High-level conversation style such as tutor, casual, exam-prep",
    )
    difficulty_preference: str | None = Field(
        None, description="Optional learner difficulty preference"
    )
    generate_greeting: bool = Field(
        True, description="Whether to immediately create an assistant greeting"
    )
    anki_direction: Literal["fr_to_de", "de_to_fr", "both"] | None = Field(
        None,
        description="Preferred Anki card direction for the session",
    )
    scenario: str | None = Field(
        None,
        description="Roleplay scenario context (e.g. 'Bakery', 'Train Station')",
    )
    story_id: int | None = Field(
        None,
        description="Story ID for story-based sessions",
    )
    story_chapter_id: int | None = Field(
        None,
        description="Story chapter ID for story-based sessions",
    )


class SessionMessageRequest(BaseModel):
    """Payload for sending a learner message within a session."""

    content: str = Field(..., min_length=1)
    suggested_word_ids: list[int] | None = Field(
        default=None,
        description="Identifiers of suggested words the learner actually attempted to use",
    )


class SessionStatusUpdate(BaseModel):
    """Update the status of a session."""

    status: Literal["in_progress", "paused", "completed", "abandoned"]


class DetectedErrorRead(BaseModel):
    """Serialized error feedback for API consumers."""

    code: str
    message: str
    span: str
    suggestion: str | None = None
    category: str
    severity: str
    confidence: float


class ErrorFeedback(BaseModel):
    """Aggregate feedback for a learner message."""

    summary: str
    errors: list[DetectedErrorRead]
    review_vocabulary: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TargetWordRead(BaseModel):
    """Metadata about a vocabulary item targeted in a turn."""

    word_id: int
    word: str
    translation: str | None = None
    is_new: bool
    familiarity: Literal["new", "learning", "familiar"] | None = None
    hint_sentence: str | None = None
    hint_translation: str | None = None


class SessionMessageRead(BaseModel):
    """Response model for persisted conversation messages."""

    id: UUID
    sender: Literal["user", "assistant"]
    content: str
    sequence_number: int
    created_at: datetime
    xp_earned: int = 0
    target_words: list[int] = Field(default_factory=list)
    words_used: list[int] = Field(default_factory=list)
    suggested_words_used: list[int] = Field(default_factory=list)
    error_feedback: ErrorFeedback | None = None
    target_details: list[TargetWordRead] = Field(default_factory=list)


class SessionOverview(BaseModel):
    """High-level view of a session."""

    id: UUID
    status: str
    topic: str | None = None
    conversation_style: str | None = None
    anki_direction: str | None = None
    planned_duration_minutes: int
    xp_earned: int
    words_practiced: int
    accuracy_rate: float | None
    started_at: datetime
    completed_at: datetime | None = None


class AssistantTurnRead(BaseModel):
    """Assistant message accompanied by vocabulary plan."""

    message: SessionMessageRead
    targets: list[TargetWordRead] = Field(default_factory=list)


class SessionTurnWordFeedback(BaseModel):
    """Detailed learner feedback for a targeted vocabulary item."""

    word_id: int
    word: str
    translation: str | None = None
    is_new: bool
    was_used: bool
    rating: int | None
    had_error: bool
    error: DetectedErrorRead | None = None


class SessionStartResponse(BaseModel):
    """Response returned when a new session is created."""

    session: SessionOverview
    assistant_turn: AssistantTurnRead | None = None


class SessionTurnResponse(BaseModel):
    """Response returned after a learner message is processed."""

    session: SessionOverview
    user_message: SessionMessageRead
    assistant_turn: AssistantTurnRead
    xp_awarded: int
    error_feedback: ErrorFeedback
    word_feedback: list[SessionTurnWordFeedback]


class PracticeIssue(BaseModel):
    word: str
    translation: str | None = None
    category: str | None = None
    issue: str | None = None
    correction: str | None = None
    sentence: str | None = None


class SessionSummaryResponse(BaseModel):
    """Aggregate statistics for a session."""

    xp_earned: int
    words_practiced: int
    accuracy_rate: float
    new_words_introduced: int
    words_reviewed: int
    correct_responses: int
    incorrect_responses: int
    status: str
    success_examples: list[dict[str, Any]] = Field(default_factory=list)
    error_examples: list[dict[str, Any]] = Field(default_factory=list)
    flashcard_words: list[TargetWordRead] = Field(default_factory=list)
    practice_items: list[PracticeIssue] = Field(default_factory=list)


class SessionMessageListResponse(BaseModel):
    """Paginated collection of session messages."""

    items: list[SessionMessageRead]
    total: int


class WordExposureRequest(BaseModel):
    """Payload for tracking hint/translation interactions."""

    word_id: int
    exposure_type: Literal["hint", "translation", "flag"]
