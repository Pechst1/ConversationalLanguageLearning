"""Pydantic models for analytics endpoints."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class MetricPoint(BaseModel):
    """Time series datapoint."""

    date: date
    value: float


class AnalyticsSummary(BaseModel):
    """Headline learner statistics."""

    sessions_completed: int
    total_minutes: int
    average_minutes: float
    xp_earned: int
    accuracy_rate: float | None = Field(default=None)
    current_streak: int
    longest_streak: int
    words_learning: int
    words_mastered: int
    reviews_due_today: int
    reviews_due_week: int
    last_session_at: datetime | None = None


class AnalyticsStatisticsResponse(BaseModel):
    """Rolling analytics metrics."""

    accuracy: list[MetricPoint] = Field(default_factory=list)
    xp_earned: list[MetricPoint] = Field(default_factory=list)
    minutes_practiced: list[MetricPoint] = Field(default_factory=list)
    reviews_completed: list[MetricPoint] = Field(default_factory=list)


class StreakCalendarDay(BaseModel):
    """One learner-local day of «Vos sceaux» (WP-D5)."""

    date: date
    #: ``completed | relache | missed | today | future``.
    state: str = "missed"
    #: 1 on a completed day (kept for older readers of this endpoint).
    completed: int = 0
    is_today: bool = False
    #: The day's journey was *completed* (an early stop presses no seal).
    sealed: bool = False
    edition_no: int | None = None
    seal_variant: str | None = None


class StreakInfo(BaseModel):
    """The streak number and its calendar, read from the same rows (WP-D5)."""

    current_streak: int
    longest_streak: int
    today_done: bool = False
    freeze_available: bool = False
    today: date | None = None
    timezone: str | None = None
    calendar: list[StreakCalendarDay] = Field(default_factory=list)


class VocabularyHeatmapEntry(BaseModel):
    """Vocabulary mastery bin."""

    state: str
    count: int


class VocabularyHeatmapResponse(BaseModel):
    """Heatmap payload summarising vocabulary states."""

    total: int
    states: list[VocabularyHeatmapEntry] = Field(default_factory=list)


class ErrorPattern(BaseModel):
    """Common learner error grouping."""

    error_type: str
    count: int
    severity: str | None = None
    example: str | None = None


class ErrorPatternsResponse(BaseModel):
    """Collection of frequent learner errors."""

    total: int
    items: list[ErrorPattern] = Field(default_factory=list)


class ErrorCategoryCount(BaseModel):
    """Error count by category."""

    category: str
    count: int


class ErrorStageCounts(BaseModel):
    """Error counts by SRS stage."""

    new: int = 0
    learning: int = 0
    review: int = 0
    relearning: int = 0
    mastered: int = 0


class ErrorSummary(BaseModel):
    """Anki-like summary for error tracking."""

    total_errors: int
    due_today: int
    stage_counts: ErrorStageCounts
    categories: list[ErrorCategoryCount] = Field(default_factory=list)


class ErrorDetailItem(BaseModel):
    """Detailed information about a tracked error."""

    id: int
    pattern: str
    explanation: str | None = None
    category: str
    occurrences: int
    lapses: int
    learning_stage: str
    next_review: datetime | None = None
    last_seen: datetime | None = None
    example_sentence: str | None = None


class ErrorListResponse(BaseModel):
    """List of detailed error items."""

    total: int
    items: list[ErrorDetailItem] = Field(default_factory=list)


__all__ = [
    "MetricPoint",
    "AnalyticsSummary",
    "AnalyticsStatisticsResponse",
    "StreakInfo",
    "StreakCalendarDay",
    "VocabularyHeatmapResponse",
    "VocabularyHeatmapEntry",
    "ErrorPatternsResponse",
    "ErrorPattern",
    "ErrorCategoryCount",
    "ErrorStageCounts",
    "ErrorSummary",
    "ErrorDetailItem",
    "ErrorListResponse",
]

