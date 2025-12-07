"""Pydantic models for learner progress endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    """Payload for submitting a review."""

    word_id: int = Field(..., ge=1)
    rating: int = Field(..., ge=0, le=3, description="FSRS rating from 0 (Again) to 3 (Easy)")
    response_time_ms: int | None = Field(None, ge=0)


class ReviewResponse(BaseModel):
    """Response after scheduling a review."""

    word_id: int
    state: str
    stability: float
    difficulty: float
    scheduled_days: int
    next_review: datetime


class ProgressDetail(BaseModel):
    """Detailed view of a learner's progress for a word."""

    word_id: int
    state: str
    stability: float | None
    difficulty: float | None
    scheduled_days: int | None
    next_review: datetime | None
    last_review: datetime | None
    reps: int
    lapses: int
    correct_count: int
    incorrect_count: int
    hint_count: int
    proficiency_score: int
    reviews_logged: int


class QueueWord(BaseModel):
    """Vocabulary entry returned in the review queue."""

    word_id: int
    word: str
    language: str
    english_translation: str | None = None
    german_translation: str | None = None
    french_translation: str | None = None
    part_of_speech: str | None = None
    difficulty_level: int | None = None
    state: str
    next_review: datetime | None = None
    scheduled_days: int | None = None
    is_new: bool
    scheduler: str | None = None


class AnkiWordProgressRead(BaseModel):
    """Overview entry for an imported Anki card and its progress."""

    word_id: int
    word: str
    language: str
    direction: str | None = None
    french_translation: str | None = None
    german_translation: str | None = None
    deck_name: str | None = None
    difficulty_level: int | None = None
    english_translation: str | None = None
    learning_stage: str
    state: str
    progress_difficulty: float | None = None
    ease_factor: float | None = None
    interval_days: int | None = None
    due_at: datetime | None = None
    next_review: datetime | None = None
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0
    proficiency_score: int = 0
    scheduler: str | None = None


class AnkiStageSlice(BaseModel):
    """Slice element for chart visualisation."""

    stage: str
    value: int


class AnkiDirectionSummary(BaseModel):
    """Per-direction breakdown for Anki progress."""

    direction: str
    total: int
    due_today: int
    stage_counts: dict[str, int]


class AnkiProgressSummary(BaseModel):
    """Aggregate Anki progress metrics."""

    total_cards: int
    due_today: int
    stage_totals: dict[str, int]
    chart: list[AnkiStageSlice]
    directions: dict[str, AnkiDirectionSummary]
