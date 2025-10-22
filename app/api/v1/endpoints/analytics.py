"""Analytics endpoints for learner dashboards."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api import deps
from app.db.models.user import User
from app.schemas import (
    AnalyticsStatisticsResponse,
    AnalyticsSummary,
    ErrorPatternsResponse,
    StreakInfo,
    VocabularyHeatmapResponse,
)
from app.services.analytics import AnalyticsService


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def read_analytics_summary(
    *,
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
) -> AnalyticsSummary:
    """Return top-line learner metrics."""

    return service.get_user_summary(user=current_user)


@router.get("/statistics", response_model=AnalyticsStatisticsResponse)
def read_statistics(
    *,
    days: int = Query(30, ge=7, le=180),
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
) -> AnalyticsStatisticsResponse:
    """Return rolling analytics windows for charts."""

    return service.get_statistics(user=current_user, days=days)


@router.get("/streak", response_model=StreakInfo)
def read_streak(
    *,
    window_days: int = Query(90, ge=7, le=365),
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
) -> StreakInfo:
    """Return streak counts and calendar data."""

    return service.get_streak_info(user=current_user, window_days=window_days)


@router.get("/vocabulary", response_model=VocabularyHeatmapResponse)
def read_vocabulary_heatmap(
    *,
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
) -> VocabularyHeatmapResponse:
    """Return vocabulary mastery counts by state."""

    return service.get_vocabulary_heatmap(user=current_user)


@router.get("/errors", response_model=ErrorPatternsResponse)
def read_error_patterns(
    *,
    limit: int = Query(10, ge=1, le=25),
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
) -> ErrorPatternsResponse:
    """Return the most common learner errors."""

    return service.get_error_patterns(user=current_user, limit=limit)
