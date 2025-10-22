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
]
