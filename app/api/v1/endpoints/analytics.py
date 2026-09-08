"""Analytics endpoints for learner dashboards."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api import deps
from app.config import settings
from app.db.models.atelier import AtelierExerciseSet, AtelierGenerationEvent
from app.db.models.feedback import UserFeedbackReport
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.schemas import (
    AnalyticsStatisticsResponse,
    AnalyticsSummary,
    ErrorPatternsResponse,
    StreakInfo,
    VocabularyHeatmapResponse,
)
from app.schemas.analytics import ErrorSummary
from app.services.analytics import AnalyticsService
from app.services.pilot_events import PilotEventService
from app.services.serial_costs import SerialGenerationCostService

router = APIRouter(prefix="/analytics", tags=["analytics"])


class ClientErrorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    stack: str | None = Field(default=None, max_length=12000)
    route: str | None = Field(default=None, max_length=500)
    source: str = Field(default="web", max_length=40)


def _require_admin(user: User) -> None:
    if str(getattr(user, "role", "user") or "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges are required.",
        )


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


@router.get("/errors/summary", response_model=ErrorSummary)
def read_error_summary(
    *,
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
) -> ErrorSummary:
    """Return Anki-like summary of user errors for progress tracking."""

    return service.get_error_summary(user=current_user)


@router.get("/errors/list")
def read_error_list(
    *,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_user),
    service: AnalyticsService = Depends(deps.get_analytics_service),
):
    """Return detailed list of all tracked errors with SRS data."""
    return service.get_error_list(user=current_user, limit=limit)


@router.post("/client-error", status_code=status.HTTP_204_NO_CONTENT)
def record_client_error(
    payload: ClientErrorRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> None:
    """First-party crash intake for the web/native shell."""
    PilotEventService(db).record(
        "client_crash",
        user_id=current_user.id,
        entity_type="client",
        payload=payload.model_dump(),
    )
    db.commit()


@router.get("/pilot-daily")
def read_pilot_daily(
    *,
    day: date | None = Query(default=None),
    user_id: str | None = Query(default=None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> dict:
    """Return one learner-day ledger for pilot operations."""
    _require_admin(current_user)
    try:
        return PilotEventService(db).daily_rollup(day or date.today(), user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid user_id") from exc


@router.get("/pilot-ops")
def read_pilot_operations(
    *,
    weeks: int = Query(4, ge=1, le=26),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> dict:
    """Return the pilot's cost and generated-content health guardrails."""

    _require_admin(current_user)
    end_date = date.today() + timedelta(days=1)
    start_date = end_date - timedelta(weeks=weeks)
    cost_rows = SerialGenerationCostService(db).weekly_rollup(
        start_date=start_date,
        end_date=end_date,
    )
    guardrail = float(settings.PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD)
    unique_users = {str(row["user_id"]) for row in cost_rows}
    total_usd = round(sum(float(row.get("total_usd") or 0) for row in cost_rows), 4)
    over_guardrail = [
        row
        for row in cost_rows
        if float(row.get("total_usd") or 0) > guardrail
    ]
    feedback_by_category = {
        str(category): int(count)
        for category, count in db.query(
            UserFeedbackReport.category,
            func.count(UserFeedbackReport.id),
        )
        .group_by(UserFeedbackReport.category)
        .all()
    }
    retired_sets = (
        db.query(func.count(AtelierExerciseSet.id))
        .filter(AtelierExerciseSet.retired_at.isnot(None))
        .scalar()
        or 0
    )
    active_sets = (
        db.query(func.count(AtelierExerciseSet.id))
        .filter(AtelierExerciseSet.retired_at.is_(None))
        .scalar()
        or 0
    )
    quality_reports = (
        db.query(func.count(AtelierGenerationEvent.id))
        .filter(AtelierGenerationEvent.event_type == "user_report")
        .scalar()
        or 0
    )
    return {
        "window": {
            "weeks": weeks,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "costs": {
            "currency": "USD",
            "total_usd": total_usd,
            "tracked_learners": len(unique_users),
            "average_usd_per_tracked_learner": round(total_usd / len(unique_users), 4)
            if unique_users
            else 0.0,
            "weekly_guardrail_usd_per_learner": guardrail,
            "rows_over_guardrail": len(over_guardrail),
            "weekly_rows": cost_rows,
        },
        "content_health": {
            "active_exercise_sets": int(active_sets),
            "retired_exercise_sets": int(retired_sets),
            "atelier_quality_reports": int(quality_reports),
            "feedback_reports": int(sum(feedback_by_category.values())),
            "feedback_by_category": feedback_by_category,
        },
        "generation": {
            "serial_scenes": int(
                db.query(func.count(GraphicNovelScene.id))
                .filter(GraphicNovelScene.serial_thread_id.isnot(None))
                .scalar()
                or 0
            ),
        },
    }
