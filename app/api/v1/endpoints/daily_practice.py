"""Daily Practice API endpoints - unified SRS for all learning types."""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services.unified_srs import (
    DailyPracticeSession,
    DailyPracticeSummary,
    DueLearningItem,
    InterleavingMode,
    ItemType,
    UnifiedSRSService,
)


router = APIRouter(prefix="/daily-practice", tags=["daily-practice"])


# ─────────────────────────────────────────────────────────────────
# Request/Response Schemas
# ─────────────────────────────────────────────────────────────────

class TypeSummary(BaseModel):
    """Summary for a single item type."""
    due: int
    new: int
    minutes: int


class PracticeSummaryResponse(BaseModel):
    """Today's practice overview."""
    total_due: int
    total_new: int
    estimated_minutes: int
    by_type: dict[str, TypeSummary]


class QueueItemResponse(BaseModel):
    """Single item in practice queue."""
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


class PracticeQueueResponse(BaseModel):
    """Full practice queue with summary."""
    summary: PracticeSummaryResponse
    queue: list[QueueItemResponse]
    interleaving_mode: str
    time_budget_minutes: int | None


class QueueSettingsRequest(BaseModel):
    """User settings for queue generation."""
    time_budget_minutes: int | None = None  # None = unlimited
    new_vocab_limit: int = 10
    new_grammar_limit: int = 5
    interleaving_mode: str = "random"  # random, blocks, priority


class CompleteItemRequest(BaseModel):
    """Record completion of a practice item."""
    rating: int = Field(..., ge=1, le=4, description="1=Again, 2=Hard, 3=Good, 4=Easy")
    response_time_ms: int | None = None


class CompleteItemResponse(BaseModel):
    """Result of completing an item."""
    success: bool
    next_review_days: int | None = None
    message: str = ""


# ─────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────

def get_srs_service(db: Session = Depends(get_db)) -> UnifiedSRSService:
    return UnifiedSRSService(db)


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=PracticeSummaryResponse)
async def get_practice_summary(
    srs_service: UnifiedSRSService = Depends(get_srs_service),
    current_user: User = Depends(get_current_user),
) -> PracticeSummaryResponse:
    """Get today's practice overview - total due items and time estimate."""
    summary = srs_service.get_due_summary(current_user.id)
    
    return PracticeSummaryResponse(
        total_due=summary.total_due,
        total_new=summary.total_new,
        estimated_minutes=summary.estimated_minutes,
        by_type={
            k: TypeSummary(**v) for k, v in summary.by_type.items()
        }
    )


@router.post("/queue", response_model=PracticeQueueResponse)
async def get_practice_queue(
    settings: QueueSettingsRequest | None = None,
    srs_service: UnifiedSRSService = Depends(get_srs_service),
    current_user: User = Depends(get_current_user),
) -> PracticeQueueResponse:
    """Get prioritized practice queue with optional settings."""
    settings = settings or QueueSettingsRequest()
    
    # Parse interleaving mode
    try:
        mode = InterleavingMode(settings.interleaving_mode)
    except ValueError:
        mode = InterleavingMode.RANDOM
    
    session = srs_service.get_daily_practice_queue(
        user_id=current_user.id,
        time_budget_minutes=settings.time_budget_minutes,
        new_vocab_limit=settings.new_vocab_limit,
        new_grammar_limit=settings.new_grammar_limit,
        interleaving_mode=mode,
    )
    
    return PracticeQueueResponse(
        summary=PracticeSummaryResponse(
            total_due=session.summary.total_due,
            total_new=session.summary.total_new,
            estimated_minutes=session.summary.estimated_minutes,
            by_type={k: TypeSummary(**v) for k, v in session.summary.by_type.items()}
        ),
        queue=[
            QueueItemResponse(
                id=item.id,
                item_type=item.item_type.value,
                priority_score=item.priority_score,
                display_title=item.display_title,
                display_subtitle=item.display_subtitle,
                level=item.level,
                due_since_days=item.due_since_days,
                estimated_seconds=item.estimated_seconds,
                original_id=str(item.original_id) if item.original_id else None,
                metadata=item.metadata
            )
            for item in session.queue
        ],
        interleaving_mode=session.interleaving_mode.value,
        time_budget_minutes=session.time_budget_minutes
    )


@router.post("/complete/{item_type}/{item_id}", response_model=CompleteItemResponse)
async def complete_practice_item(
    item_type: str,
    item_id: str,
    request: CompleteItemRequest,
    srs_service: UnifiedSRSService = Depends(get_srs_service),
    current_user: User = Depends(get_current_user),
) -> CompleteItemResponse:
    """Record completion of a practice item.
    
    Routes to appropriate service based on item_type:
    - vocab: Updates UserVocabularyProgress
    - grammar: Updates UserGrammarProgress  
    - error: Updates UserError
    """
    try:
        parsed_type = ItemType(item_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item_type: {item_type}",
        ) from exc

    try:
        result = srs_service.complete_item(
            user_id=current_user.id,
            item_type=parsed_type,
            item_id=item_id,
            rating=request.rating,
            response_time_ms=request.response_time_ms,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return CompleteItemResponse(
        success=True,
        next_review_days=result.get("next_review_days"),
        message=result.get("message", f"Completed {item_type} item {item_id}"),
    )


# ─────────────────────────────────────────────────────────────────
# Brief Exercise Endpoints (for interactive daily practice)
# ─────────────────────────────────────────────────────────────────

class BriefExercise(BaseModel):
    """A single brief exercise item."""
    id: str
    type: str  # "fill_blank", "translation", "short_answer"
    difficulty: str  # "a", "b", "c"
    instruction: str
    prompt: str
    correct_answer: str
    hint: str | None = None


class BriefGrammarExercisesResponse(BaseModel):
    """Response with 3 brief grammar exercises."""
    concept_id: int
    concept_name: str
    level: str
    exercises: list[BriefExercise]


class ErrorExerciseResponse(BaseModel):
    """Response with an error correction exercise."""
    error_id: str
    exercise_type: str
    instruction: str
    prompt: str
    correct_answer: str
    explanation: str
    memory_tip: str | None = None
    original_text: str | None = None
    stored_correction: str | None = None


class CheckAnswerRequest(BaseModel):
    """Request to check a user's answer."""
    exercise_type: str
    prompt: str
    correct_answer: str
    user_answer: str
    concept_id: int | None = None


class CheckAnswerResponse(BaseModel):
    """Response with answer check result."""
    is_correct: bool
    feedback: str
    explanation: str = ""
    score: int = 0


def get_brief_exercise_service(db: Session = Depends(get_db)):
    """Dependency for brief exercise service."""
    from app.services.brief_exercise_service import BriefExerciseService
    return BriefExerciseService(db)


@router.post("/grammar/{concept_id}/exercises", response_model=BriefGrammarExercisesResponse)
async def generate_brief_grammar_exercises(
    concept_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BriefGrammarExercisesResponse:
    """Generate 3 brief grammar exercises for a concept.
    
    Used in Daily Practice when user clicks "Ich habe es wiederholt" on a grammar card.
    """
    from app.services.brief_exercise_service import BriefExerciseService
    
    service = BriefExerciseService(db)
    result = await service.generate_grammar_exercises(concept_id)
    
    if "error" in result and not result.get("exercises"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Failed to generate exercises")
        )
    
    return BriefGrammarExercisesResponse(
        concept_id=result.get("concept_id", concept_id),
        concept_name=result.get("concept_name", "Unknown"),
        level=result.get("level", "B1"),
        exercises=[
            BriefExercise(**ex) for ex in result.get("exercises", [])
        ]
    )


@router.post("/error/{error_id}/exercise", response_model=ErrorExerciseResponse)
async def generate_error_exercise(
    error_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ErrorExerciseResponse:
    """Generate a correction exercise based on user's past error.
    
    Used in Daily Practice for error (FEHLER) cards.
    """
    from uuid import UUID as UUIDType
    from app.services.brief_exercise_service import BriefExerciseService
    
    try:
        error_uuid = UUIDType(error_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid error ID format"
        )
    
    service = BriefExerciseService(db)
    result = await service.generate_error_exercise(error_uuid)
    
    if "error" in result and not result.get("exercise_type"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get("error", "Failed to generate exercise")
        )
    
    return ErrorExerciseResponse(
        error_id=result.get("error_id", error_id),
        exercise_type=result.get("exercise_type", "correction"),
        instruction=result.get("instruction", "Korrigiere den Fehler"),
        prompt=result.get("prompt", ""),
        correct_answer=result.get("correct_answer", ""),
        explanation=result.get("explanation", ""),
        memory_tip=result.get("memory_tip"),
        original_text=result.get("original_text"),
        stored_correction=result.get("stored_correction")
    )


@router.post("/check-answer", response_model=CheckAnswerResponse)
async def check_brief_answer(
    request: CheckAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckAnswerResponse:
    """Check user's answer for a brief exercise.
    
    Uses LLM for flexible validation (accepts minor typos/variations).
    """
    from app.services.brief_exercise_service import BriefExerciseService
    
    service = BriefExerciseService(db)
    result = await service.check_answer(
        exercise_type=request.exercise_type,
        prompt=request.prompt,
        correct_answer=request.correct_answer,
        user_answer=request.user_answer,
        user_id=current_user.id,
        concept_id=request.concept_id
    )
    
    return CheckAnswerResponse(
        is_correct=result.get("is_correct", False),
        feedback=result.get("feedback", ""),
        explanation=result.get("explanation", ""),
        score=result.get("score", 0)
    )


__all__ = ["router"]
