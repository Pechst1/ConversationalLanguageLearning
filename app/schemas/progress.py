"""Pydantic models for learner progress endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

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


class UnifiedQueueItem(BaseModel):
    """Cross-mode learning item returned by the unified SRS queue."""

    id: str
    item_type: str
    priority_score: float
    display_title: str
    display_subtitle: str
    level: str
    due_since_days: int
    estimated_seconds: int
    original_id: str | int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedQueueTypeSummary(BaseModel):
    """Due-count summary for one SRS item type."""

    due: int
    new: int = 0
    minutes: int


class UnifiedQueueSummary(BaseModel):
    """Unified workload summary across vocabulary, grammar, and errata."""

    total_due: int
    total_new: int = 0
    estimated_minutes: int
    by_type: dict[str, UnifiedQueueTypeSummary]


class UnifiedQueueResponse(BaseModel):
    """Unified SRS queue response."""

    summary: UnifiedQueueSummary
    queue: list[UnifiedQueueItem]
    interleaving_mode: str
    time_budget_minutes: int | None = None


class CEFRProgressResponse(BaseModel):
    """Visible CEFR estimate, threshold breakdown, and forecast."""

    version: str
    estimate: str
    computed_estimate: str | None = None
    target: str
    next_level: str | None = None
    daily_minutes: int | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, dict[str, float]] = Field(default_factory=dict)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    forecast: dict[str, Any] | None = None
    today_delta: dict[str, Any] = Field(default_factory=dict)
    generated_at: str | None = None


class VocabularyRecommendationTranslations(BaseModel):
    """Translation hints for a recommended vocabulary item."""

    de: str | None = None
    en: str | None = None
    fr: str | None = None


class VocabularyRecommendationItem(BaseModel):
    """Vocabulary card selected for today's SRS work."""

    bucket: str
    word_id: int
    progress_id: str | None = None
    word: str
    language: str
    direction: str | None = None
    scheduler: str | None = None
    state: str
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
    lapses: int = 0
    priority_score: float
    is_new: bool = False
    deck_name: str | None = None
    translations: VocabularyRecommendationTranslations
    example_sentence: str | None = None
    example_translation: str | None = None


class VocabularyRecommendationSummary(BaseModel):
    """Counts for each recommendation bucket."""

    due: int
    fragile: int
    new: int
    total: int


class VocabularyRecommendationResponse(BaseModel):
    """Ranked vocabulary recommendations for the daily learning loop."""

    summary: VocabularyRecommendationSummary
    items: list[VocabularyRecommendationItem]
    algorithm: str = "fsrs_retrievability_v1"


class VocabularyDueContextSummary(BaseModel):
    """Selected counts for a contextual vocabulary review bundle."""

    due: int
    fragile: int
    new: int
    topic_compatible: int
    linked: int
    total: int


class VocabularyDueContextResponse(BaseModel):
    """Bucketed due-context vocabulary for mobile practice surfaces."""

    summary: VocabularyDueContextSummary
    due_words: list[VocabularyRecommendationItem]
    fragile_words: list[VocabularyRecommendationItem]
    new_words: list[VocabularyRecommendationItem]
    topic_compatible_words: list[VocabularyRecommendationItem]
    linked_words: list[VocabularyRecommendationItem]
    algorithm: str = "fsrs_retrievability_v1"


class VocabularyMasteryMapCell(BaseModel):
    """One tiny cell in the French 5000 mastery map."""

    word_id: int
    word: str
    frequency_rank: int | None = None
    mastery_state: str
    proficiency_score: int = 0
    is_due: bool = False
    lapses: int = 0


class VocabularyMasteryMapSummary(BaseModel):
    """Aggregate counts for the French 5000 mastery map."""

    total: int
    new: int
    due: int
    fragile: int
    building: int
    solid: int
    mastered: int


class VocabularyMasteryMapResponse(BaseModel):
    """Typographic map of the imported French 5000 deck."""

    summary: VocabularyMasteryMapSummary
    cells: list[VocabularyMasteryMapCell]
    deck_label: str = "French 5000"


class WeeklyDossierStats(BaseModel):
    """Deterministic weekly learning stats for the editorial progress mirror."""

    repairs_filed: int = 0
    vocabulary_reviews: int = 0
    words_seen: int = 0
    words_produced: int = 0
    missions_completed: int = 0
    feuilleton_scenes_completed: int = 0


class WeeklyDossierThread(BaseModel):
    """One highlighted strength, fragile item, or suggested next action."""

    title: str
    subtitle: str | None = None
    tone: str = "neutral"
    count: int = 0


class WeeklyDossierResponse(BaseModel):
    """Editorial weekly digest generated from local learning telemetry."""

    period_start: datetime
    period_end: datetime
    headline: str
    stats: WeeklyDossierStats
    strengths: list[WeeklyDossierThread]
    fragile_threads: list[WeeklyDossierThread]
    next_actions: list[WeeklyDossierThread]


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
