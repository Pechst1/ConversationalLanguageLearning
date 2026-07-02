"""In-app feedback collection endpoints."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.feedback import UserFeedbackReport
from app.db.models.user import User
from app.schemas.feedback import FeedbackCategory, FeedbackReportCreate, FeedbackReportRead

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _require_admin(user: User) -> None:
    if str(getattr(user, "role", "user") or "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges are required.",
        )


@router.post("/reports", response_model=FeedbackReportRead, status_code=status.HTTP_201_CREATED)
def create_feedback_report(
    payload: FeedbackReportCreate,
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> UserFeedbackReport:
    """Store a lightweight report from the global pilot feedback widget."""

    report = UserFeedbackReport(
        user_id=current_user.id,
        category=payload.category,
        message=payload.message,
        route=payload.route,
        url=payload.url,
        screen=payload.screen,
        viewport=payload.viewport,
        user_agent=payload.user_agent,
        context_payload=payload.context_payload,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports", response_model=list[FeedbackReportRead])
def list_feedback_reports(
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    category: Annotated[FeedbackCategory | None, Query()] = None,
    route: Annotated[str | None, Query(max_length=240)] = None,
) -> list[UserFeedbackReport]:
    """List feedback reports for admin triage."""

    _require_admin(current_user)

    stmt = select(UserFeedbackReport).order_by(UserFeedbackReport.created_at.desc())
    if category is not None:
        stmt = stmt.where(UserFeedbackReport.category == category)
    if route:
        stmt = stmt.where(UserFeedbackReport.route == route.strip())
    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


__all__ = ["router"]
