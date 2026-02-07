"""Grammar review API endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services.grammar import GrammarService
from app.services.achievement_service import AchievementService
from sqlalchemy.orm import Session


router = APIRouter(prefix="/grammar", tags=["grammar"])


# ─────────────────────────────────────────────────────────────────
# Request/Response Schemas
# ─────────────────────────────────────────────────────────────────

class GrammarConceptCreate(BaseModel):
    """Request to create a grammar concept."""
    name: str = Field(..., min_length=1, max_length=255)
    level: str = Field(..., pattern=r"^(A1|A2|B1|B2|C1|C2)$")
    category: str | None = None
    description: str | None = None
    examples: str | None = None
    difficulty_order: int = 0


class GrammarConceptRead(BaseModel):
    """Response for a grammar concept."""
    id: int
    name: str
    level: str
    category: str | None
    description: str | None
    examples: str | None
    difficulty_order: int

    class Config:
        from_attributes = True


class GrammarProgressRead(BaseModel):
    """Response for user grammar progress."""
    concept_id: int
    concept_name: str
    concept_level: str
    score: float
    reps: int
    state: str
    state_label: str
    notes: str | None
    last_review: str | None
    next_review: str | None


class GrammarReviewRequest(BaseModel):
    """Request to record a grammar review."""
    concept_id: int
    score: float = Field(..., ge=0, le=10)
    notes: str | None = None


class GrammarSummaryResponse(BaseModel):
    """Summary of grammar progress."""
    total_concepts: int
    started: int
    due_today: int
    new_available: int
    state_counts: dict[str, int]
    level_counts: dict[str, int]


class DueConceptRead(BaseModel):
    """A concept due for review."""
    id: int
    name: str
    level: str
    category: str | None
    description: str | None
    current_score: float | None
    current_state: str
    reps: int


class BulkImportRequest(BaseModel):
    """Request to bulk import grammar concepts."""
    concepts: list[GrammarConceptCreate]


class AchievementRead(BaseModel):
    """Achievement with unlock status."""
    id: int
    key: str
    name: str
    description: str | None
    icon_url: str | None
    xp_reward: int
    tier: str
    category: str | None
    is_unlocked: bool
    unlocked_at: str | None
    progress: int


class StreakInfoRead(BaseModel):
    """Grammar streak information."""
    current_streak: int
    longest_streak: int
    last_review_date: str | None
    is_active_today: bool


class ConceptGraphNode(BaseModel):
    """Node in the concept dependency graph."""
    id: int
    name: str
    level: str
    category: str | None
    description: str | None
    visualization_type: str | None
    prerequisites: list[int]
    is_locked: bool
    state: str
    score: float
    reps: int


class ConceptGraphEdge(BaseModel):
    """Edge in the concept dependency graph."""
    source: int
    target: int


class ConceptGraphResponse(BaseModel):
    """Complete concept dependency graph."""
    nodes: list[ConceptGraphNode]
    edges: list[ConceptGraphEdge]
    levels: dict[str, list[int]]


class ChapterConceptRead(BaseModel):
    """Grammar concept for a chapter."""
    id: int
    name: str
    level: str
    category: str | None
    description: str | None
    visualization_type: str | None
    state: str
    score: float
    reps: int
    is_due: bool


# ─────────────────────────────────────────────────────────────────
# Dependency
# ─────────────────────────────────────────────────────────────────

def get_grammar_service(db: Session = Depends(get_db)) -> GrammarService:
    return GrammarService(db)


def get_achievement_service(db: Session = Depends(get_db)) -> AchievementService:
    return AchievementService(db)


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/concepts", response_model=list[GrammarConceptRead])
def list_concepts(
    level: str | None = Query(None, pattern=r"^(A1|A2|B1|B2|C1|C2)$"),
    category: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: GrammarService = Depends(get_grammar_service),
) -> list[GrammarConceptRead]:
    """List all grammar concepts."""
    concepts = service.list_concepts(level=level, category=category, limit=limit, offset=offset)
    return [GrammarConceptRead.model_validate(c) for c in concepts]


@router.post("/concepts", response_model=GrammarConceptRead, status_code=status.HTTP_201_CREATED)
def create_concept(
    payload: GrammarConceptCreate,
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> GrammarConceptRead:
    """Create a new grammar concept."""
    concept = service.create_concept(
        name=payload.name,
        level=payload.level,
        category=payload.category,
        description=payload.description,
        examples=payload.examples,
        difficulty_order=payload.difficulty_order,
    )
    return GrammarConceptRead.model_validate(concept)


@router.post("/concepts/import", status_code=status.HTTP_201_CREATED)
def bulk_import_concepts(
    payload: BulkImportRequest,
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    """Bulk import grammar concepts."""
    count = service.bulk_create_concepts([c.model_dump() for c in payload.concepts])
    return {"imported": count}


@router.get("/summary", response_model=GrammarSummaryResponse)
def get_summary(
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> GrammarSummaryResponse:
    """Get grammar progress summary for dashboard."""
    summary = service.get_summary(user=current_user)
    return GrammarSummaryResponse(**summary)


@router.get("/due", response_model=list[DueConceptRead])
def get_due_concepts(
    level: str | None = Query(None, pattern=r"^(A1|A2|B1|B2|C1|C2)$"),
    limit: int = Query(5, ge=1, le=20),
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> list[DueConceptRead]:
    """Get grammar concepts due for review."""
    due = service.get_due_concepts(user=current_user, limit=limit, level=level)
    result = []
    for concept, progress in due:
        result.append(DueConceptRead(
            id=concept.id,
            name=concept.name,
            level=concept.level,
            category=concept.category,
            description=concept.description,
            current_score=progress.score if progress else None,
            current_state=progress.state if progress else "neu",
            reps=progress.reps if progress else 0,
        ))
    return result


@router.get("/progress", response_model=list[GrammarProgressRead])
def get_user_progress(
    level: str | None = Query(None, pattern=r"^(A1|A2|B1|B2|C1|C2)$"),
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> list[GrammarProgressRead]:
    """Get user's grammar progress."""
    progress_list = service.get_user_progress(user=current_user, level=level)
    result = []
    for progress in progress_list:
        concept = progress.concept
        result.append(GrammarProgressRead(
            concept_id=progress.concept_id,
            concept_name=concept.name if concept else "",
            concept_level=concept.level if concept else "",
            score=progress.score,
            reps=progress.reps,
            state=progress.state,
            state_label=progress.state_label,
            notes=progress.notes,
            last_review=progress.last_review.isoformat() if progress.last_review else None,
            next_review=progress.next_review.isoformat() if progress.next_review else None,
        ))
    return result


@router.get("/by-level")
def get_concepts_by_level(
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, list[dict]]:
    """Get all concepts grouped by level with user progress."""
    return service.get_concepts_by_level(user=current_user)


@router.post("/review", response_model=GrammarProgressRead)
def record_review(
    payload: GrammarReviewRequest,
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> GrammarProgressRead:
    """Record a grammar concept review with 0-10 score."""
    concept = service.get_concept(payload.concept_id)
    if not concept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept {payload.concept_id} not found",
        )

    progress = service.record_review(
        user=current_user,
        concept_id=payload.concept_id,
        score=payload.score,
        notes=payload.notes,
    )

    return GrammarProgressRead(
        concept_id=progress.concept_id,
        concept_name=concept.name,
        concept_level=concept.level,
        score=progress.score,
        reps=progress.reps,
        state=progress.state,
        state_label=progress.state_label,
        notes=progress.notes,
        last_review=progress.last_review.isoformat() if progress.last_review else None,
        next_review=progress.next_review.isoformat() if progress.next_review else None,
    )


# ─────────────────────────────────────────────────────────────────
# Achievement & Streak Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/achievements", response_model=list[AchievementRead])
def get_achievements(
    category: str | None = Query(None),
    achievement_service: AchievementService = Depends(get_achievement_service),
    current_user: User = Depends(get_current_user),
) -> list[AchievementRead]:
    """Get all grammar achievements with user unlock status."""
    achievements = achievement_service.get_user_achievements(
        current_user, category=category or "grammar"
    )
    return [AchievementRead(**a) for a in achievements]


@router.get("/streak", response_model=StreakInfoRead)
def get_streak_info(
    achievement_service: AchievementService = Depends(get_achievement_service),
    current_user: User = Depends(get_current_user),
) -> StreakInfoRead:
    """Get user's current grammar streak information."""
    streak_info = achievement_service.get_grammar_streak_info(current_user)
    return StreakInfoRead(**streak_info)


@router.post("/review-with-achievements")
def record_review_with_achievements(
    payload: GrammarReviewRequest,
    db: Session = Depends(get_db),
    service: GrammarService = Depends(get_grammar_service),
    achievement_service: AchievementService = Depends(get_achievement_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Record a grammar review and check for achievement unlocks.

    Returns the review result plus any newly unlocked achievements.
    """
    concept = service.get_concept(payload.concept_id)
    if not concept:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concept {payload.concept_id} not found",
        )

    # Record the review
    progress = service.record_review(
        user=current_user,
        concept_id=payload.concept_id,
        score=payload.score,
        notes=payload.notes,
    )

    # Update streak
    streak_result = achievement_service.update_grammar_streak(current_user)

    # Check for achievement unlocks
    unlocked = achievement_service.check_and_unlock_achievements(
        current_user, score=payload.score, concept=concept
    )

    return {
        "progress": GrammarProgressRead(
            concept_id=progress.concept_id,
            concept_name=concept.name,
            concept_level=concept.level,
            score=progress.score,
            reps=progress.reps,
            state=progress.state,
            state_label=progress.state_label,
            notes=progress.notes,
            last_review=progress.last_review.isoformat() if progress.last_review else None,
            next_review=progress.next_review.isoformat() if progress.next_review else None,
        ),
        "streak": streak_result,
        "achievements_unlocked": [
            {
                "id": a.id,
                "key": a.achievement_key,
                "name": a.name,
                "description": a.description,
                "xp_reward": a.xp_reward,
                "tier": a.tier,
            }
            for a in unlocked
        ],
    }


# ─────────────────────────────────────────────────────────────────
# Concept Graph Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/graph", response_model=ConceptGraphResponse)
def get_concept_graph(
    level: str | None = Query(None, pattern=r"^(A1|A2|B1|B2|C1|C2)$"),
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> ConceptGraphResponse:
    """Get the concept dependency graph for visualization."""
    graph = service.get_concept_graph(user=current_user, level=level)
    return ConceptGraphResponse(
        nodes=[ConceptGraphNode(**n) for n in graph["nodes"]],
        edges=[ConceptGraphEdge(**e) for e in graph["edges"]],
        levels=graph["levels"],
    )


# ─────────────────────────────────────────────────────────────────
# Story-Grammar Integration Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/for-chapter/{chapter_id}", response_model=list[ChapterConceptRead])
def get_concepts_for_chapter(
    chapter_id: str,
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> list[ChapterConceptRead]:
    """Get grammar concepts associated with a story chapter."""
    concepts = service.get_concepts_for_chapter(chapter_id=chapter_id, user=current_user)
    return [ChapterConceptRead(**c) for c in concepts]


@router.get("/for-errors", response_model=list[dict])
def get_concepts_for_errors(
    limit: int = Query(5, ge=1, le=10),
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Get grammar concepts to review based on user's error patterns.
    
    This creates the Error→Grammar synergy by recommending which grammar
    topics to study based on recurring mistakes.
    """
    results = service.get_concepts_for_user_errors(user=current_user, limit=limit)
    
    response = []
    for concept, error_patterns in results:
        response.append({
            "concept": GrammarConceptRead.model_validate(concept),
            "error_patterns": error_patterns,
            "error_count": len(error_patterns),
        })
    
    return response


@router.post("/mark-practiced-in-context")
def mark_practiced_in_context(
    concept_ids: list[int],
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark grammar concepts as practiced in story context."""
    service.mark_concepts_practiced_in_context(user=current_user, concept_ids=concept_ids)
    return {"marked": len(concept_ids)}
