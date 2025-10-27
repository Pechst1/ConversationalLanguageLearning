"""Achievement API endpoints for tracking learner progress."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.user import User
from app.schemas.achievement import (
    AchievementProgressResponse,
    AchievementRead,
    AchievementUnlockResponse,
)
from app.services.achievement import AchievementService

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("", response_model=list[AchievementRead])
def list_achievements(
    *,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.get_current_user),
) -> list[AchievementRead]:
    """Return all available achievement definitions."""

    service = AchievementService(db)
    achievements = service.list_all_achievements()
    return [
        AchievementRead(
            id=achievement.id,
            achievement_key=achievement.achievement_key,
            name=achievement.name,
            description=achievement.description,
            tier=achievement.tier,
            xp_reward=achievement.xp_reward,
            icon_url=achievement.icon_url,
        )
        for achievement in achievements
    ]


@router.get("/my", response_model=list[AchievementProgressResponse])
def get_my_achievements(
    *,
    include_locked: bool = Query(False, description="Include locked achievements"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> list[AchievementProgressResponse]:
    """Return the authenticated user's achievement progress."""

    service = AchievementService(db)
    progress = service.get_user_achievements(
        current_user.id, include_locked=include_locked
    )
    return [
        AchievementProgressResponse(
            achievement_id=item.achievement_id,
            achievement_key=item.achievement_key,
            name=item.name,
            description=item.description,
            tier=item.tier,
            xp_reward=item.xp_reward,
            icon_url=item.icon_url,
            current_progress=item.current_progress,
            target_progress=item.target_progress,
            completed=item.completed,
            unlocked_at=item.unlocked_at,
        )
        for item in progress
    ]


@router.post("/check", response_model=AchievementUnlockResponse)
def check_achievements(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> AchievementUnlockResponse:
    """Manually trigger achievement check for the authenticated user."""

    service = AchievementService(db)
    newly_unlocked = service.check_and_unlock(user=current_user)

    return AchievementUnlockResponse(
        newly_unlocked=[
            AchievementRead(
                id=achievement.id,
                achievement_key=achievement.achievement_key,
                name=achievement.name,
                description=achievement.description,
                tier=achievement.tier,
                xp_reward=achievement.xp_reward,
                icon_url=achievement.icon_url,
            )
            for achievement in newly_unlocked
        ],
        total_unlocked=len(newly_unlocked),
    )
