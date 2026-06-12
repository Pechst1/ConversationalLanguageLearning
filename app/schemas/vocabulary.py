"""Pydantic schemas for vocabulary endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class VocabularyWordRead(BaseModel):
    """Representation of a vocabulary word."""

    id: int
    language: str = Field(max_length=10)
    word: str
    normalized_word: str
    part_of_speech: Optional[str] = None
    gender: Optional[str] = None
    frequency_rank: Optional[int] = None
    english_translation: Optional[str] = None
    definition: Optional[str] = None
    example_sentence: Optional[str] = None
    example_translation: Optional[str] = None
    usage_notes: Optional[str] = None
    difficulty_level: Optional[int] = None
    german_translation: Optional[str] = None
    french_translation: Optional[str] = None
    topic_tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class VocabularyListResponse(BaseModel):
    """Paginated vocabulary response payload."""

    total: int
    items: list[VocabularyWordRead]


class VocabularyBiographyOrigin(BaseModel):
    """Where a word first enters the learner-facing system."""

    label: str
    source_type: str = "deck"
    deck_name: str | None = None
    imported: bool = False
    frequency_rank: int | None = None
    created_at: datetime | None = None


class VocabularyBiographyProgress(BaseModel):
    """Human-readable SRS state for a word biography."""

    progress_id: str | None = None
    scheduler: str | None = None
    state: str = "new"
    phase: str | None = None
    due_at: datetime | None = None
    next_review: datetime | None = None
    last_review: datetime | None = None
    scheduled_days: int | None = None
    interval_days: int | None = None
    stability: float | None = None
    difficulty: float | None = None
    retrievability: float | None = None
    proficiency_score: int = 0
    reps: int = 0
    lapses: int = 0
    times_seen: int = 0
    times_used_correctly: int = 0
    times_used_incorrectly: int = 0
    fragility_level: str = "new"
    fragility_label: str = "New thread"
    fragility_reason: str | None = None


class VocabularyBiographyExample(BaseModel):
    """One remembered or dictionary-backed example for a vocabulary word."""

    sentence: str
    translation: str | None = None
    source: str = "dictionary"
    occurred_at: datetime | None = None


class VocabularyBiographyEvent(BaseModel):
    """One entry in the word's memory thread."""

    id: str
    event_type: str
    label: str
    description: str | None = None
    occurred_at: datetime | None = None
    source_type: str
    source_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VocabularyBiographyResponse(BaseModel):
    """A compact, resilient biography for a vocabulary word."""

    word: VocabularyWordRead
    origin: VocabularyBiographyOrigin
    progress: VocabularyBiographyProgress
    examples: list[VocabularyBiographyExample] = Field(default_factory=list)
    linked_errata_count: int = 0
    context_event_count: int = 0
    timeline: list[VocabularyBiographyEvent] = Field(default_factory=list)
