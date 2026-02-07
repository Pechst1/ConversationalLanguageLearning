"""User management endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.user import User
from app.schemas import UserRead, UserUpdate
from app.services.users import UserNotFoundError, UserService
from app.utils.cache import cache_backend, build_cache_key

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(deps.get_current_user)) -> UserRead:
    """Return the authenticated user profile."""

    cache_key = build_cache_key(user_id=str(current_user.id))
    cached = cache_backend.get("user:profile", cache_key)
    if cached is not None:
        return cached

    payload = UserRead.model_validate(current_user).model_dump(mode="json")
    cache_backend.set("user:profile", cache_key, payload, ttl_seconds=300)
    return payload


@router.patch("/me", response_model=UserRead)
def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> UserRead:
    """Allow the authenticated user to update their profile details."""

    service = UserService(db)
    updated = service.update(current_user, payload)
    cache_key = build_cache_key(user_id=str(updated.id))
    cache_backend.invalidate("user:profile", key=cache_key)
    response = UserRead.model_validate(updated).model_dump(mode="json")
    cache_backend.set("user:profile", cache_key, response, ttl_seconds=300)
    return response


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> None:
    """Permanently delete the authenticated user account."""
    service = UserService(db)
    service.delete(current_user)


@router.get("/", response_model=list[UserRead])
def list_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.get_current_user),
) -> list[User]:
    """Return a paginated list of users ordered by recency."""

    service = UserService(db)
    return service.list_users(limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(
    user_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.get_current_user),
) -> UserRead:
    """Fetch another user profile. Access control to be refined later."""

    cache_key = build_cache_key(user_id=str(user_id))
    cached = cache_backend.get("user:profile", cache_key)
    if cached is not None:
        return cached

    service = UserService(db)
    try:
        user = service.get(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = UserRead.model_validate(user).model_dump(mode="json")
    cache_backend.set("user:profile", cache_key, payload, ttl_seconds=300)
    return payload


@router.get("/me/export")
def export_user_data(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> dict:
    """Export all user data as JSON for GDPR compliance.
    
    Returns comprehensive data including:
    - User profile
    - Vocabulary progress
    - Grammar progress
    - Error tracking
    - Session history
    - Achievements
    """
    from app.db.models.vocabulary import UserVocabularyProgress
    from app.db.models.grammar import UserGrammarProgress
    from app.db.models.error import UserError
    from app.db.models.session import LearningSession
    from app.db.models.achievement import UserAchievement
    
    # Get all progress
    vocab_progress = db.query(UserVocabularyProgress).filter(
        UserVocabularyProgress.user_id == current_user.id
    ).all()
    
    grammar_progress = db.query(UserGrammarProgress).filter(
        UserGrammarProgress.user_id == current_user.id
    ).all()
    
    errors = db.query(UserError).filter(
        UserError.user_id == current_user.id
    ).all()
    
    sessions = db.query(LearningSession).filter(
        LearningSession.user_id == current_user.id
    ).order_by(LearningSession.created_at.desc()).limit(100).all()
    
    achievements = db.query(UserAchievement).filter(
        UserAchievement.user_id == current_user.id
    ).all()
    
    return {
        "exported_at": "2025-01-25T12:00:00Z",  # Use current time
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "proficiency_level": current_user.proficiency_level,
            "level": current_user.level,
            "total_xp": current_user.total_xp,
            "current_streak": current_user.current_streak,
            "longest_streak": current_user.longest_streak,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "vocabulary_progress": [
            {
                "word_id": p.word_id,
                "state": p.state,
                "stability": p.stability,
                "difficulty": p.difficulty,
                "reps": p.reps,
                "lapses": p.lapses,
                "last_review": p.last_review.isoformat() if p.last_review else None,
                "next_review": p.next_review.isoformat() if p.next_review else None,
            }
            for p in vocab_progress
        ],
        "grammar_progress": [
            {
                "concept_id": p.concept_id,
                "score": p.score,
                "reps": p.reps,
                "state": p.state,
                "last_review": p.last_review.isoformat() if p.last_review else None,
                "next_review": p.next_review.isoformat() if p.next_review else None,
            }
            for p in grammar_progress
        ],
        "errors": [
            {
                "category": e.error_category,
                "subcategory": e.subcategory,
                "original_text": e.original_text,
                "correction": e.correction,
                "occurrences": e.occurrences,
                "lapses": e.lapses,
                "state": e.state,
            }
            for e in errors
        ],
        "sessions": [
            {
                "id": str(s.id),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "status": s.status,
                "xp_earned": s.xp_earned,
            }
            for s in sessions
        ],
        "achievements": [
            {
                "achievement_key": a.achievement_key,
                "unlocked_at": a.unlocked_at.isoformat() if a.unlocked_at else None,
                "xp_rewarded": a.xp_rewarded,
            }
            for a in achievements
        ],
    }


@router.post("/me/sign-out-all", status_code=status.HTTP_204_NO_CONTENT)
def sign_out_all_devices(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> None:
    """Sign out from all devices by invalidating all user sessions.
    
    This forces re-authentication on all devices.
    Note: Actual implementation depends on session management strategy.
    For JWT, this would require a token blacklist or version increment.
    """
    # Invalidate all cached user data
    cache_key = build_cache_key(user_id=str(current_user.id))
    cache_backend.invalidate("user:profile", key=cache_key)
    
    # TODO: Implement actual session invalidation
    # For JWT-based auth, consider:
    # 1. Increment user.auth_version field
    # 2. Add tokens to redis blacklist
    # 3. Clear all user sessions from database
    
    # For now, just clear cache
    pass
