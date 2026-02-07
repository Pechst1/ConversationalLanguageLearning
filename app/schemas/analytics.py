"""Pydantic models for analytics endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

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
    last_session_at: Optional[datetime] = None


class AnalyticsStatisticsResponse(BaseModel):
    """Rolling analytics metrics."""

    accuracy: List[MetricPoint] = Field(default_factory=list)
    xp_earned: List[MetricPoint] = Field(default_factory=list)
    minutes_practiced: List[MetricPoint] = Field(default_factory=list)
    reviews_completed: List[MetricPoint] = Field(default_factory=list)


class StreakCalendarDay(BaseModel):
    """Calendar entry for streak visualisation."""

    date: date
    completed: int


class StreakInfo(BaseModel):
    """Current and longest streak data."""

    current_streak: int
    longest_streak: int
    calendar: List[StreakCalendarDay] = Field(default_factory=list)


class VocabularyHeatmapEntry(BaseModel):
    """Vocabulary mastery bin."""

    state: str
    count: int


class VocabularyHeatmapResponse(BaseModel):
    """Heatmap payload summarising vocabulary states."""

    total: int
    states: List[VocabularyHeatmapEntry] = Field(default_factory=list)


class ErrorPattern(BaseModel):
    """Common learner error grouping."""

    error_type: str
    count: int
    severity: Optional[str] = None
    example: Optional[str] = None


class ErrorPatternsResponse(BaseModel):
    """Collection of frequent learner errors."""

    total: int
    items: List[ErrorPattern] = Field(default_factory=list)


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
    categories: List[ErrorCategoryCount] = Field(default_factory=list)


class ErrorDetailItem(BaseModel):
    """Detailed information about a tracked error."""

    id: int
    pattern: str
    explanation: Optional[str] = None
    category: str
    occurrences: int
    lapses: int
    learning_stage: str
    next_review: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    example_sentence: Optional[str] = None


class ErrorListResponse(BaseModel):
    """List of detailed error items."""

    total: int
    items: List[ErrorDetailItem] = Field(default_factory=list)


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

