"""Endpoints for learner vocabulary progress."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.schemas import ProgressDetail, QueueWord, ReviewRequest, ReviewResponse
from app.services.progress import ProgressService


router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/queue", response_model=list[QueueWord])
def get_review_queue(
    *,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of queue entries to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QueueWord]:
    """Return a mix of due and new words for the authenticated learner."""

    service = ProgressService(db)
    queue_items = service.get_learning_queue(user=current_user, limit=limit)
    response: list[QueueWord] = []
    for item in queue_items:
        progress = item.progress
        response.append(
            QueueWord(
                word_id=item.word.id,
                word=item.word.word,
                language=item.word.language,
                english_translation=item.word.english_translation,
                part_of_speech=item.word.part_of_speech,
                difficulty_level=item.word.difficulty_level,
                state=progress.state if progress else "new",
                next_review=progress.next_review_date if progress else None,
                scheduled_days=progress.scheduled_days if progress else None,
                is_new=item.is_new or progress is None,
            )
        )
    return response


@router.get("/{word_id}", response_model=ProgressDetail)
def get_progress_detail(
    *,
    word_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProgressDetail:
    """Return the learner's scheduling stats for a vocabulary item."""

    service = ProgressService(db)
    word = db.get(VocabularyWord, word_id)
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary word not found")

    progress = service.get_progress(user_id=current_user.id, word_id=word_id)
    summary = service.progress_summary(user_id=current_user.id, word_id=word_id)

    return ProgressDetail(
        word_id=word_id,
        state=progress.state if progress else "new",
        stability=progress.stability if progress else None,
        difficulty=progress.difficulty if progress else None,
        scheduled_days=progress.scheduled_days if progress else None,
        next_review=progress.next_review_date if progress else None,
        last_review=progress.last_review_date if progress else None,
        reps=summary.get("reps", 0),
        lapses=summary.get("lapses", 0),
        correct_count=summary.get("correct_count", 0),
        incorrect_count=summary.get("incorrect_count", 0),
        hint_count=progress.hint_count if progress else 0,
        proficiency_score=progress.proficiency_score if progress else 0,
        reviews_logged=summary.get("reviews_logged", 0),
    )


@router.post("/review", response_model=ReviewResponse)
def submit_review(
    *,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewResponse:
    """Register a learner review and return the next scheduled review time."""

    word = db.get(VocabularyWord, payload.word_id)
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary word not found")

    service = ProgressService(db)
    progress, review_log, outcome = service.record_review(
        user=current_user,
        word=word,
        rating=payload.rating,
    )
    if payload.response_time_ms is not None:
        review_log.response_time_ms = payload.response_time_ms

    db.commit()
    db.refresh(progress)

    return ReviewResponse(
        word_id=word.id,
        state=progress.state,
        stability=progress.stability or 0.0,
        difficulty=progress.difficulty or 0.0,
        scheduled_days=progress.scheduled_days or 0,
        next_review=outcome.next_review,
    )
