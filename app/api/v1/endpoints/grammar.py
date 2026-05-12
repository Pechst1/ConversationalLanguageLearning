"""Grammar review API endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.security import InvalidTokenError, decode_token
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization, UserGrammarProgress
from app.db.models.user import User
from app.schemas import TokenPayload
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import serialize_error_memory
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.grammar import GrammarService
from app.services.achievement_service import AchievementService


router = APIRouter(prefix="/grammar", tags=["grammar"])
grammar_notebook_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)
GRAMMAR_NOTEBOOK_DEMO_EMAIL = "atelier-demo@local.test"


# ─────────────────────────────────────────────────────────────────
# Request/Response Schemas
# ─────────────────────────────────────────────────────────────────

class GrammarConceptCreate(BaseModel):
    """Request to create a grammar concept."""
    external_id: str | None = None
    language: str = "fr"
    name: str = Field(..., min_length=1, max_length=255)
    level: str = Field(..., pattern=r"^(A1|A2|B1|B2|C1|C2)$")
    category: str | None = None
    subskill: str | None = None
    description: str | None = None
    examples: str | None = None
    difficulty_order: int = 0
    core_rule: str | None = None
    main_traps: str | None = None
    anchor_examples: str | None = None
    exercise_tags: list[str] = Field(default_factory=list)
    is_foundation: bool = False
    active: bool = True


class GrammarConceptRead(BaseModel):
    """Response for a grammar concept."""
    id: int
    external_id: str | None
    language: str
    name: str
    level: str
    category: str | None
    subskill: str | None
    description: str | None
    examples: str | None
    difficulty_order: int
    core_rule: str | None
    main_traps: str | None
    anchor_examples: str | None
    exercise_tags: list[str]
    is_foundation: bool
    active: bool

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


class GrammarNotebookProgressRead(BaseModel):
    """Personal progress payload for the grammar notebook."""
    score: float
    reps: int
    state: str
    state_label: str
    notes: str | None
    last_review: str | None
    next_review: str | None


class GrammarNotebookItemRead(BaseModel):
    """Concept list item for the personal grammar notebook."""
    id: int
    external_id: str | None
    language: str
    name: str
    display_title: str
    localized_title: str | None = None
    localized_category: str | None = None
    localized_subskill: str | None = None
    level: str
    category: str | None
    subskill: str | None
    catalog_version: str | None = None
    source_refs: dict[str, Any] = Field(default_factory=dict)
    is_foundation: bool
    active: bool
    mastery: float
    state: str
    state_label: str
    next_review: str | None
    due_errata_count: int
    recent_errata_count: int
    motif: dict[str, Any] = Field(default_factory=dict)
    blueprint_status: str | None = None
    blueprint_quality: dict[str, Any] = Field(default_factory=dict)


class GrammarNotebookDetailRead(GrammarNotebookItemRead):
    """Full notebook detail for one grammar concept."""
    core_rule: str | None
    main_traps: list[str] = Field(default_factory=list)
    anchor_examples: list[str] = Field(default_factory=list)
    exercise_tags: list[str] = Field(default_factory=list)
    description: str | None
    examples: str | None
    atelier_blueprint: dict[str, Any] = Field(default_factory=dict)
    progress: GrammarNotebookProgressRead | None = None
    due_errata: list[dict[str, Any]] = Field(default_factory=list)
    recent_errata: list[dict[str, Any]] = Field(default_factory=list)
    personal_notes: str | None = None


class GrammarNotebookNotesRequest(BaseModel):
    """Personal note update for one grammar concept."""
    notes: str = ""


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


def get_grammar_notebook_user(
    token: str | None = Depends(grammar_notebook_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve a signed-in user, or use the local Atelier demo user for notebook review."""
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise InvalidTokenError("Token must be an access token")
            token_data = TokenPayload.model_validate(payload)
            user = db.get(User, UUID(str(token_data.sub)))
            if user:
                return user
        except (InvalidTokenError, ValidationError, ValueError, KeyError):
            pass

    if not settings.AUTO_CREATE_USERS_ON_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Grammar notebook requires authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == GRAMMAR_NOTEBOOK_DEMO_EMAIL).first()
    if user:
        return user

    user = User(
        email=GRAMMAR_NOTEBOOK_DEMO_EMAIL,
        hashed_password="atelier-demo",
        full_name="Atelier Demo",
        native_language="en",
        target_language="fr",
        proficiency_level="intermediate",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"\s*[;|]\s*", value) if item.strip()]


def _progress_payload(progress: UserGrammarProgress | None) -> GrammarNotebookProgressRead | None:
    if not progress:
        return None
    return GrammarNotebookProgressRead(
        score=progress.score,
        reps=progress.reps,
        state=progress.state,
        state_label=progress.state_label,
        notes=progress.notes,
        last_review=_iso(progress.last_review),
        next_review=_iso(progress.next_review),
    )


def _progress_state(progress: UserGrammarProgress | None) -> tuple[float, str, str, str | None]:
    if not progress:
        return 0.0, "neu", "Neu", None
    return progress.score, progress.state, progress.state_label, _iso(progress.next_review)


def _notebook_item_payload(
    concept: GrammarConcept,
    progress: UserGrammarProgress | None,
    blueprint: dict[str, Any],
    due_count: int,
    recent_count: int,
    localization: GrammarConceptLocalization | None = None,
) -> dict[str, Any]:
    mastery, state, state_label, next_review = _progress_state(progress)
    localized_title = localization.title if localization else None
    return {
        "id": concept.id,
        "external_id": concept.external_id,
        "language": concept.language,
        "name": concept.name,
        "display_title": localized_title or blueprint.get("display_title") or concept.name,
        "localized_title": localized_title,
        "localized_category": localization.category_label if localization else None,
        "localized_subskill": localization.subskill_label if localization else None,
        "level": concept.level,
        "category": concept.category,
        "subskill": concept.subskill,
        "catalog_version": concept.catalog_version,
        "source_refs": concept.source_refs or {},
        "is_foundation": concept.is_foundation,
        "active": concept.active,
        "mastery": mastery,
        "state": state,
        "state_label": state_label,
        "next_review": next_review,
        "due_errata_count": due_count,
        "recent_errata_count": recent_count,
        "motif": blueprint.get("visual_motif") or {},
        "blueprint_status": blueprint.get("blueprint_status") or "approved",
        "blueprint_quality": blueprint.get("blueprint_quality") or {},
    }


def _matches_notebook_query(concept: GrammarConcept, blueprint: dict[str, Any], q: str | None) -> bool:
    if not q:
        return True
    needle = q.strip().casefold()
    if not needle:
        return True
    pedagogy = blueprint.get("pedagogy") or {}
    haystack = " ".join(
        str(part or "")
        for part in (
            concept.name,
            concept.category,
            concept.subskill,
            concept.external_id,
            concept.core_rule,
            blueprint.get("display_title"),
            pedagogy.get("core_rule"),
            pedagogy.get("pattern"),
            " ".join(pedagogy.get("main_traps") or []),
        )
    ).casefold()
    return needle in haystack


def _concept_errata(
    db: Session,
    user: User,
    concept_id: int,
    limit_recent: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = datetime.now(timezone.utc)
    base = (
        db.query(UserError)
        .filter(
            UserError.user_id == user.id,
            UserError.concept_id == concept_id,
            UserError.state != "mastered",
        )
    )
    due_rows = (
        base.filter(or_(UserError.next_review_date.is_(None), UserError.next_review_date <= now))
        .order_by(
            UserError.lapses.desc(),
            UserError.occurrences.desc(),
            UserError.next_review_date.asc().nullsfirst(),
            UserError.updated_at.desc().nullslast(),
        )
        .limit(limit_recent)
        .all()
    )
    due_ids = [row.id for row in due_rows]
    recent_query = base
    if due_ids:
        recent_query = recent_query.filter(UserError.id.notin_(due_ids))
    recent_rows = (
        recent_query.order_by(UserError.updated_at.desc().nullslast(), UserError.created_at.desc())
        .limit(limit_recent)
        .all()
    )
    return [serialize_error_memory(row) for row in due_rows], [serialize_error_memory(row) for row in recent_rows]


def _notebook_detail_payload(
    db: Session,
    user: User,
    concept: GrammarConcept,
    progress: UserGrammarProgress | None,
    asset_service: AtelierAssetService,
    localization: GrammarConceptLocalization | None = None,
) -> GrammarNotebookDetailRead:
    blueprint = asset_service.approved_blueprint_payload(concept)
    due_errata, recent_errata = _concept_errata(db, user, concept.id)
    item = _notebook_item_payload(concept, progress, blueprint, len(due_errata), len(recent_errata), localization)
    return GrammarNotebookDetailRead(
        **item,
        core_rule=concept.core_rule,
        main_traps=_split_list(concept.main_traps),
        anchor_examples=_split_list(concept.anchor_examples),
        exercise_tags=list(concept.exercise_tags or []),
        description=concept.description,
        examples=concept.examples,
        atelier_blueprint=blueprint,
        progress=_progress_payload(progress),
        due_errata=due_errata,
        recent_errata=recent_errata,
        personal_notes=progress.notes if progress else None,
    )


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/notebook", response_model=list[GrammarNotebookItemRead])
def get_grammar_notebook(
    level: str | None = Query(None, pattern=r"^(A1|A2|B1|B2|C1|C2)$"),
    category: str | None = None,
    q: str | None = Query(None, max_length=120),
    locale: str = Query("en", min_length=2, max_length=10),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_grammar_notebook_user),
) -> list[GrammarNotebookItemRead]:
    """List concepts for the personal grammar notebook."""
    FrenchCoreGrammarCatalog(db).ensure_catalog(archive_legacy=True)
    query = db.query(GrammarConcept).filter(GrammarConcept.active.is_(True))
    if level:
        query = query.filter(GrammarConcept.level == level)
    if category:
        query = query.filter(GrammarConcept.category == category)
    ordered_query = query.order_by(GrammarConcept.level, GrammarConcept.difficulty_order, GrammarConcept.id)
    if not q:
        ordered_query = ordered_query.offset(offset).limit(limit)
    concepts = ordered_query.all()
    concept_ids = [concept.id for concept in concepts]
    if not concept_ids:
        return []

    progress_rows = (
        db.query(UserGrammarProgress)
        .filter(
            UserGrammarProgress.user_id == current_user.id,
            UserGrammarProgress.concept_id.in_(concept_ids),
        )
        .all()
    )
    progress_by_concept = {progress.concept_id: progress for progress in progress_rows}
    localization_by_concept: dict[int, GrammarConceptLocalization] = {}
    if locale.lower() != "en":
        localization_rows = (
            db.query(GrammarConceptLocalization)
            .filter(
                GrammarConceptLocalization.concept_id.in_(concept_ids),
                GrammarConceptLocalization.locale == locale.lower(),
            )
            .all()
        )
        localization_by_concept = {row.concept_id: row for row in localization_rows}

    now = datetime.now(timezone.utc)
    due_counts = dict(
        db.query(UserError.concept_id, func.count(UserError.id))
        .filter(
            UserError.user_id == current_user.id,
            UserError.concept_id.in_(concept_ids),
            UserError.state != "mastered",
            or_(UserError.next_review_date.is_(None), UserError.next_review_date <= now),
        )
        .group_by(UserError.concept_id)
        .all()
    )
    recent_counts = dict(
        db.query(UserError.concept_id, func.count(UserError.id))
        .filter(
            UserError.user_id == current_user.id,
            UserError.concept_id.in_(concept_ids),
            UserError.state != "mastered",
            UserError.next_review_date > now,
        )
        .group_by(UserError.concept_id)
        .all()
    )

    asset_service = AtelierAssetService(db)
    rows: list[GrammarNotebookItemRead] = []
    for concept in concepts:
        blueprint = asset_service.approved_blueprint_payload(concept)
        if not _matches_notebook_query(concept, blueprint, q):
            continue
        rows.append(
            GrammarNotebookItemRead(
                **_notebook_item_payload(
                    concept,
                    progress_by_concept.get(concept.id),
                    blueprint,
                    int(due_counts.get(concept.id, 0)),
                    int(recent_counts.get(concept.id, 0)),
                    localization_by_concept.get(concept.id),
                )
            )
        )
    if q:
        return rows[offset : offset + limit]
    return rows


@router.get("/notebook/{concept_id}", response_model=GrammarNotebookDetailRead)
def get_grammar_notebook_concept(
    concept_id: int,
    locale: str = Query("en", min_length=2, max_length=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_grammar_notebook_user),
) -> GrammarNotebookDetailRead:
    """Get one concept as a personal grammar notebook page."""
    FrenchCoreGrammarCatalog(db).ensure_catalog(archive_legacy=True)
    concept = db.get(GrammarConcept, concept_id)
    if not concept or not concept.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Concept {concept_id} not found")
    localization = None
    if locale.lower() != "en":
        localization = (
            db.query(GrammarConceptLocalization)
            .filter(
                GrammarConceptLocalization.concept_id == concept.id,
                GrammarConceptLocalization.locale == locale.lower(),
            )
            .first()
        )
    progress = (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == current_user.id, UserGrammarProgress.concept_id == concept.id)
        .first()
    )
    return _notebook_detail_payload(db, current_user, concept, progress, AtelierAssetService(db), localization)


@router.patch("/notebook/{concept_id}/notes", response_model=GrammarNotebookDetailRead)
def update_grammar_notebook_notes(
    concept_id: int,
    payload: GrammarNotebookNotesRequest,
    db: Session = Depends(get_db),
    service: GrammarService = Depends(get_grammar_service),
    current_user: User = Depends(get_grammar_notebook_user),
) -> GrammarNotebookDetailRead:
    """Update personal notes without recording a review."""
    concept = db.get(GrammarConcept, concept_id)
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Concept {concept_id} not found")

    progress = service.get_or_create_progress(user_id=current_user.id, concept_id=concept_id)
    progress.notes = payload.notes.strip() or None
    db.add(progress)
    db.commit()
    db.refresh(progress)
    return _notebook_detail_payload(db, current_user, concept, progress, AtelierAssetService(db))

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
        external_id=payload.external_id,
        language=payload.language,
        name=payload.name,
        level=payload.level,
        category=payload.category,
        subskill=payload.subskill,
        description=payload.description,
        examples=payload.examples,
        difficulty_order=payload.difficulty_order,
        core_rule=payload.core_rule,
        main_traps=payload.main_traps,
        anchor_examples=payload.anchor_examples,
        exercise_tags=payload.exercise_tags,
        is_foundation=payload.is_foundation,
        active=payload.active,
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
