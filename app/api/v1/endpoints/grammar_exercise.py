"""Grammar exercise API endpoints with 3×3 structure."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services.grammar import GrammarService
from app.services.grammar_exercise import GrammarExerciseService
from sqlalchemy.orm import Session


router = APIRouter(prefix="/grammar/exercise", tags=["grammar-exercise"])


# ─────────────────────────────────────────────────────────────────
# Request/Response Schemas
# ─────────────────────────────────────────────────────────────────

class GenerateExerciseRequest(BaseModel):
    """Request to generate exercises for a concept."""
    concept_id: int


class GenerateExerciseResponse(BaseModel):
    """Response with generated exercises (3×3 structure) and concept explanation."""
    concept_id: int
    concept_name: str
    level: str
    exercises: list[dict[str, Any]]  # Block structure
    flat_exercises: list[dict[str, Any]]  # Flattened for frontend
    explanation: dict[str, Any] | None = None  # Concept info box content


class CheckAnswersRequest(BaseModel):
    """Request to check user answers."""
    concept_id: int
    exercises: list[dict[str, Any]]
    answers: list[str]


class CheckAnswersResponse(BaseModel):
    """Response with correction results."""
    results: list[dict[str, Any]]  # Block structure
    flat_results: list[dict[str, Any]]  # Flattened for frontend
    total_score: float
    correct_count: int
    total_count: int
    overall_feedback: str
    focus_areas: list[str] = []


# ─────────────────────────────────────────────────────────────────
# Dependencies
# ─────────────────────────────────────────────────────────────────

def get_grammar_service(db: Session = Depends(get_db)) -> GrammarService:
    return GrammarService(db)


def get_exercise_service() -> GrammarExerciseService:
    return GrammarExerciseService()


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateExerciseResponse)
async def generate_exercises(
    payload: GenerateExerciseRequest,
    grammar_service: GrammarService = Depends(get_grammar_service),
    exercise_service: GrammarExerciseService = Depends(get_exercise_service),
    current_user: User = Depends(get_current_user),
) -> GenerateExerciseResponse:
    """Generate 3×3 grammar exercises for a concept using LLM.
    
    Also generates a concept explanation for the info box.
    """
    concept = grammar_service.get_concept(payload.concept_id)
    if not concept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept {payload.concept_id} not found",
        )
    
    # Generate exercises and explanation in parallel
    import asyncio
    exercise_result, explanation_result = await asyncio.gather(
        exercise_service.generate_exercises(concept),
        exercise_service.generate_concept_explanation(concept),
    )
    
    return GenerateExerciseResponse(
        concept_id=exercise_result.get("concept_id", payload.concept_id),
        concept_name=exercise_result.get("concept_name", concept.name),
        level=exercise_result.get("level", concept.level),
        exercises=exercise_result.get("exercises", []),
        flat_exercises=exercise_result.get("flat_exercises", []),
        explanation=explanation_result,
    )


@router.post("/check", response_model=CheckAnswersResponse)
async def check_answers(
    payload: CheckAnswersRequest,
    grammar_service: GrammarService = Depends(get_grammar_service),
    exercise_service: GrammarExerciseService = Depends(get_exercise_service),
    current_user: User = Depends(get_current_user),
) -> CheckAnswersResponse:
    """Check user answers with strict criteria."""
    concept = grammar_service.get_concept(payload.concept_id)
    if not concept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept {payload.concept_id} not found",
        )
    
    if len(payload.answers) != len(payload.exercises):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Answer count ({len(payload.answers)}) must match exercise count ({len(payload.exercises)})",
        )
    
    result = await exercise_service.check_answers(
        concept,
        payload.exercises,
        payload.answers,
    )
    
    return CheckAnswersResponse(
        results=result.get("results", []),
        flat_results=result.get("flat_results", []),
        total_score=result.get("total_score", 0),
        correct_count=result.get("correct_count", 0),
        total_count=result.get("total_count", len(payload.exercises)),
        overall_feedback=result.get("overall_feedback", ""),
        focus_areas=result.get("focus_areas", []),
    )
