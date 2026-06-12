"""Atelier grammar practice API."""
from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.core.security import InvalidTokenError, decode_token
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.grammar import GrammarConcept
from app.db.models.mission import RealWorldMission
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.schemas import TokenPayload
from app.schemas.atelier import (
    AtelierActiveSessionResponse,
    AtelierAttemptRequest,
    AtelierAttemptResponse,
    AtelierCompleteResponse,
    AtelierConceptRead,
    AtelierErrataAttemptRequest,
    AtelierErrataAttemptResponse,
    AtelierErrataReviewRequest,
    AtelierErrataReviewResponse,
    AtelierErrataTaskResponse,
    AtelierSessionStartRequest,
    AtelierSessionStartResponse,
    AtelierTodayResponse,
)
from app.services.atelier import (
    AtelierCorrectionService,
    AtelierExerciseGenerationError,
    AtelierExerciseGenerator,
    AtelierScheduler,
    AtelierSRSService,
    ConceptSelection,
    inject_vocabulary_context,
    run_atelier_ai_review,
    select_atelier_vocabulary,
    serialize_concept,
    serialize_erratum_record,
    session_vocabulary_context,
)
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import ErrorMemoryService
from app.services.serial import SerialThreadService

router = APIRouter(prefix="/atelier", tags=["atelier"])
atelier_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)
ATELIER_DEMO_EMAIL = "atelier-demo@local.test"


def _atelier_day_progress(db: Session, user: User, *, errata_due: int) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    start = datetime.combine(today, time.min, tzinfo=timezone.utc)
    vocabulary_due = (
        db.query(func.count(UserVocabularyProgress.id))
        .filter(UserVocabularyProgress.user_id == user.id)
        .filter(
            or_(
                UserVocabularyProgress.due_date.is_(None),
                UserVocabularyProgress.due_date <= today,
                UserVocabularyProgress.due_at <= start,
                UserVocabularyProgress.next_review_date <= start,
            )
        )
        .scalar()
        or 0
    )
    mission_done = (
        db.query(RealWorldMission.id)
        .filter(RealWorldMission.user_id == user.id, RealWorldMission.status == "completed")
        .filter(RealWorldMission.completed_at >= start)
        .first()
        is not None
    )
    feuilleton_done = (
        db.query(GraphicNovelScene.id)
        .filter(GraphicNovelScene.user_id == user.id, GraphicNovelScene.status == "completed")
        .filter(GraphicNovelScene.completed_at >= start)
        .first()
        is not None
    )
    return {
        "errataDue": int(errata_due),
        "vocabularyDue": int(vocabulary_due),
        "missionDone": mission_done,
        "feuilletonDone": feuilleton_done,
    }


def get_atelier_user(
    token: str | None = Depends(atelier_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the signed-in user, or use a local demo user for standalone Atelier design work."""
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise InvalidTokenError("Token must be an access token")
            token_data = TokenPayload.model_validate(payload)
            user = db.get(User, UUID(str(token_data.sub)))
            if user and user.is_active and int(token_data.av or 0) == int(user.auth_version or 0):
                return user
        except (InvalidTokenError, ValidationError, ValueError, KeyError):
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Atelier token is no longer valid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.AUTO_CREATE_USERS_ON_LOGIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Atelier requires authentication",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == ATELIER_DEMO_EMAIL).first()
    if user:
        return user

    user = User(
        email=ATELIER_DEMO_EMAIL,
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


def _concept_read(
    selection: ConceptSelection,
    due_errata_by_concept: dict[int, list[dict[str, Any]]] | None = None,
    asset_service: AtelierAssetService | None = None,
) -> AtelierConceptRead:
    data = serialize_concept(selection.concept)
    data["role"] = selection.role
    data["mastery"] = selection.progress.score if selection.progress else 0
    data["next_review"] = (
        selection.progress.next_review.isoformat()
        if selection.progress and selection.progress.next_review
        else None
    )
    data["due_errata"] = (due_errata_by_concept or {}).get(selection.concept.id, [])
    if asset_service:
        data["atelier_blueprint"] = asset_service.approved_blueprint_payload(selection.concept)
    return AtelierConceptRead(**data)


def _session_or_404(db: Session, session_id: UUID, user: User) -> AtelierSession:
    session = (
        db.query(AtelierSession)
        .filter(AtelierSession.id == session_id, AtelierSession.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier session not found")
    return session


def _attempt_or_404(db: Session, attempt_id: UUID, user: User) -> AtelierAttempt:
    attempt = db.query(AtelierAttempt).filter(AtelierAttempt.id == attempt_id, AtelierAttempt.user_id == user.id).first()
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier attempt not found")
    return attempt


def _attempt_response(attempt: AtelierAttempt) -> AtelierAttemptResponse:
    correction = attempt.correction_payload or {}
    ai_review = correction.get("ai_review") if isinstance(correction, dict) else {}
    return AtelierAttemptResponse(
        attempt_id=attempt.id,
        verdict=attempt.verdict,
        score_0_4=attempt.score_0_4,
        correction=correction,
        ai_review=ai_review if isinstance(ai_review, dict) else {},
    )


def _errata_by_concept(due_errata: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in due_errata:
        concept_id = item.get("concept_id")
        if concept_id is None:
            continue
        grouped.setdefault(int(concept_id), []).append(item)
    return grouped


def _session_selections(db: Session, user: User, session: AtelierSession) -> list[ConceptSelection]:
    concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
    if not concept_ids:
        return []
    concepts = db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all()
    by_id = {concept.id: concept for concept in concepts}
    scheduler = AtelierScheduler(db)
    selections: list[ConceptSelection] = []
    for index, concept_id in enumerate(concept_ids):
        concept = by_id.get(concept_id)
        if not concept:
            continue
        selections.append(
            ConceptSelection(
                concept=concept,
                role="fragile" if index < 2 else "contrast",
                progress=scheduler._progress_for(user, concept.id),
            )
        )
    return selections


def _session_attempts(db: Session, session: AtelierSession) -> list[AtelierAttempt]:
    return list(
        db.query(AtelierAttempt)
        .filter(AtelierAttempt.atelier_session_id == session.id)
        .order_by(AtelierAttempt.created_at.asc(), AtelierAttempt.id.asc())
        .all()
    )


def _submitted_key(attempt: AtelierAttempt) -> str:
    mode = attempt.mode
    concept_id: str | int = attempt.concept_id or "session"
    if attempt.round == "transform":
        mode = "transform"
    elif attempt.round in {"sentence", "speak", "conversation", "produce"}:
        mode = attempt.round
    if attempt.round == "produce":
        concept_id = "session"
    return f"{attempt.round}:{mode}:{concept_id}"


def _attempt_read(attempt: AtelierAttempt) -> dict[str, Any]:
    correction = attempt.correction_payload or {}
    return {
        "attempt_id": str(attempt.id),
        "session_id": str(attempt.atelier_session_id),
        "concept_id": attempt.concept_id,
        "round": attempt.round,
        "mode": attempt.mode,
        "exercise_id": attempt.exercise_id,
        "prompt_payload": attempt.prompt_payload or {},
        "answer_payload": attempt.answer_payload or {},
        "correction": correction,
        "ai_review": correction.get("ai_review") if isinstance(correction, dict) else {},
        "verdict": attempt.verdict,
        "score_0_4": attempt.score_0_4,
        "submitted_key": _submitted_key(attempt),
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }


def _current_position(session: AtelierSession, attempts: list[AtelierAttempt]) -> dict[str, Any]:
    submitted = {_submitted_key(attempt): True for attempt in attempts}
    concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
    for concept_index, concept_id in enumerate(concept_ids):
        for mode in ("fill", "word_bank", "classify"):
            if not submitted.get(f"recognize:{mode}:{concept_id}"):
                return {"round": "recognize", "mode": mode, "concept_id": concept_id, "concept_index": concept_index}
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(f"transform:transform:{concept_id}"):
            return {"round": "transform", "mode": "transform", "concept_id": concept_id, "concept_index": concept_index}
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(f"sentence:sentence:{concept_id}"):
            return {"round": "sentence", "mode": "sentence", "concept_id": concept_id, "concept_index": concept_index}
    if not submitted.get("produce:produce:session"):
        return {"round": "produce", "mode": "produce", "concept_id": None, "concept_index": 0}
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(f"speak:speak:{concept_id}"):
            return {"round": "speak", "mode": "speak", "concept_id": concept_id, "concept_index": concept_index}
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(f"conversation:conversation:{concept_id}"):
            return {"round": "conversation", "mode": "conversation", "concept_id": concept_id, "concept_index": concept_index}
    return {"round": "complete", "mode": "complete", "concept_id": None, "concept_index": 0}


def _session_response(db: Session, user: User, session: AtelierSession) -> AtelierSessionStartResponse:
    scheduler = AtelierScheduler(db)
    generator = AtelierExerciseGenerator(db)
    asset_service = AtelierAssetService(db)
    selections = _session_selections(db, user, session)
    due_errata = scheduler.due_errata(user)
    due_by_concept = _errata_by_concept(due_errata)
    exercise_sets: list[dict[str, Any]] = []
    target_vocabulary = session_vocabulary_context(session)
    for concept_index, selection in enumerate(selections):
        try:
            exercise_set = generator.get_or_create(selection.concept, user=user)
        except AtelierExerciseGenerationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        payload = inject_vocabulary_context(
            exercise_set.payload,
            target_vocabulary,
            concept_index=concept_index,
        )
        exercise_sets.append(
            {
                "id": str(exercise_set.id),
                "concept_id": selection.concept.id,
                "generator_version": exercise_set.generator_version,
                "source": exercise_set.source,
                "payload": payload,
            }
        )
    attempts = _session_attempts(db, session)
    return AtelierSessionStartResponse(
        session_id=session.id,
        status=session.status,
        concepts=[_concept_read(selection, due_by_concept, asset_service) for selection in selections],
        quote=session.quote_payload or scheduler.quote_for_today(),
        exercise_sets=exercise_sets,
        attempts=[_attempt_read(attempt) for attempt in attempts],
        submitted_map={_submitted_key(attempt): True for attempt in attempts},
        current_position=_current_position(session, attempts),
        due_errata=due_errata,
        target_vocabulary_ids=[int(item["word_id"]) for item in target_vocabulary if item.get("word_id")],
        target_vocabulary=target_vocabulary,
        recap=session.recap_payload or {},
    )


@router.get("/today", response_model=AtelierTodayResponse)
async def get_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierTodayResponse:
    scheduler = AtelierScheduler(db)
    selections = scheduler.select_today(current_user)
    asset_service = AtelierAssetService(db)
    due_errata = scheduler.due_errata(current_user)
    due_by_concept = _errata_by_concept(due_errata)
    summary = scheduler.summary(current_user)
    summary["due_errata"] = len(due_errata)
    serial_episode = await SerialThreadService(db).today(current_user) if settings.SERIAL_WORLD_ENABLED else None
    progress = _atelier_day_progress(db, current_user, errata_due=len(due_errata))
    return AtelierTodayResponse(
        concepts=[_concept_read(selection, due_by_concept, asset_service) for selection in selections],
        quote=scheduler.quote_for_today(),
        summary=summary,
        atlas=scheduler.atlas(current_user),
        due_errata=due_errata,
        progress=progress,
        serial_episode=serial_episode,
        serial=serial_episode,
    )


@router.post("/sessions", response_model=AtelierSessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    payload: AtelierSessionStartRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierSessionStartResponse:
    scheduler = AtelierScheduler(db)
    scheduler.ensure_catalog()

    if payload and payload.concept_ids:
        concepts = (
            db.query(GrammarConcept)
            .filter(GrammarConcept.id.in_(payload.concept_ids), GrammarConcept.active.is_(True))
            .all()
        )
        concepts_by_id = {concept.id: concept for concept in concepts}
        selections = [
            ConceptSelection(concept=concepts_by_id[concept_id], role="fragile" if index < 2 else "contrast")
            for index, concept_id in enumerate(payload.concept_ids[:3])
            if concept_id in concepts_by_id
        ]
    elif payload and payload.preferred_concept_id:
        concept = (
            db.query(GrammarConcept)
            .filter(GrammarConcept.id == payload.preferred_concept_id, GrammarConcept.active.is_(True))
            .first()
        )
        if not concept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook concept is not available")
        selections = [ConceptSelection(concept=concept, role="fragile")]
        seen_ids = {concept.id}
        for selection in scheduler.select_today(current_user):
            if selection.concept.id in seen_ids:
                continue
            role = "fragile" if len(selections) < 2 else "contrast"
            selections.append(ConceptSelection(concept=selection.concept, role=role))
            seen_ids.add(selection.concept.id)
            if len(selections) >= 3:
                break
        if len(selections) < 3:
            fallback_concepts = (
                db.query(GrammarConcept)
                .filter(
                    GrammarConcept.language == concept.language,
                    GrammarConcept.active.is_(True),
                    ~GrammarConcept.id.in_(seen_ids),
                )
                .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
                .limit(3 - len(selections))
                .all()
            )
            for fallback in fallback_concepts:
                role = "fragile" if len(selections) < 2 else "contrast"
                selections.append(ConceptSelection(concept=fallback, role=role))
    else:
        selections = scheduler.select_today(current_user)

    if not selections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Atelier concepts are available")

    target_vocabulary = select_atelier_vocabulary(
        db,
        user=current_user,
        preferred_word_ids=(payload.preferred_vocabulary_ids if payload else None),
        limit=3,
    )
    quote = {
        **scheduler.quote_for_today(),
        "target_vocabulary_ids": [int(item["word_id"]) for item in target_vocabulary if item.get("word_id")],
        "target_vocabulary": target_vocabulary,
    }
    session = AtelierSession(
        user_id=current_user.id,
        selected_concept_ids=[selection.concept.id for selection in selections],
        quote_payload=quote,
        status="in_progress",
        recap_payload={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_response(db, current_user, session)


@router.get("/sessions/active", response_model=AtelierActiveSessionResponse)
def get_active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierActiveSessionResponse:
    session = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == current_user.id, AtelierSession.status == "in_progress")
        .order_by(AtelierSession.created_at.desc())
        .first()
    )
    if not session:
        return AtelierActiveSessionResponse(session=None)
    return AtelierActiveSessionResponse(session=_session_response(db, current_user, session))


@router.get("/sessions/{session_id}", response_model=AtelierSessionStartResponse)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierSessionStartResponse:
    session = _session_or_404(db, session_id, current_user)
    return _session_response(db, current_user, session)


@router.post("/sessions/{session_id}/attempts", response_model=AtelierAttemptResponse)
def submit_attempt(
    session_id: UUID,
    payload: AtelierAttemptRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierAttemptResponse:
    session = _session_or_404(db, session_id, current_user)
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Atelier session is already completed")

    concept = None
    if payload.concept_id is not None:
        if payload.concept_id not in (session.selected_concept_ids or []):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Concept is not part of this session")
        concept = db.get(GrammarConcept, payload.concept_id)
        if not concept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar concept not found")
    elif payload.round != "produce":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Concept is required for this attempt")

    duplicate_query = db.query(AtelierAttempt).filter(
        AtelierAttempt.atelier_session_id == session.id,
        AtelierAttempt.round == payload.round,
        AtelierAttempt.mode == payload.mode,
        AtelierAttempt.exercise_id == payload.exercise_id,
    )
    if payload.concept_id is None:
        duplicate_query = duplicate_query.filter(AtelierAttempt.concept_id.is_(None))
    else:
        duplicate_query = duplicate_query.filter(AtelierAttempt.concept_id == payload.concept_id)
    existing = duplicate_query.order_by(AtelierAttempt.created_at.desc()).first()
    if existing and not payload.resubmit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Atelier drill has already been submitted. Pass resubmit=true to replace it intentionally.",
        )

    correction_service = AtelierCorrectionService(db)
    attempt = correction_service.submit_attempt(
        session=session,
        user=current_user,
        concept=concept,
        round_name=payload.round,
        mode=payload.mode,
        exercise_id=payload.exercise_id,
        answer_payload=payload.answer_payload,
    )
    if correction_service.should_auto_start_ai_review(attempt):
        background_tasks.add_task(run_atelier_ai_review, attempt.id)
    return _attempt_response(attempt)


@router.get("/attempts/{attempt_id}", response_model=AtelierAttemptResponse)
def get_attempt(
    attempt_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierAttemptResponse:
    return _attempt_response(_attempt_or_404(db, attempt_id, current_user))


@router.post("/attempts/{attempt_id}/ai-review", response_model=AtelierAttemptResponse)
def request_attempt_ai_review(
    attempt_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierAttemptResponse:
    attempt = _attempt_or_404(db, attempt_id, current_user)
    review = AtelierCorrectionService.ai_review_from_correction(attempt.correction_payload)
    if review.get("status") == "not_applicable":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI review is not available for this attempt")
    correction_service = AtelierCorrectionService(db)
    attempt, should_enqueue = correction_service.mark_ai_review_pending(attempt, auto_started=False)
    if should_enqueue:
        background_tasks.add_task(run_atelier_ai_review, attempt.id)
    return _attempt_response(attempt)


@router.post("/sessions/{session_id}/complete", response_model=AtelierCompleteResponse)
def complete_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierCompleteResponse:
    session = _session_or_404(db, session_id, current_user)
    if session.status == "completed":
        return AtelierCompleteResponse(session_id=session.id, recap=session.recap_payload or {})
    recap = AtelierSRSService(db).complete_session(session=session, user=current_user)
    return AtelierCompleteResponse(session_id=session.id, recap=recap)


@router.post("/errata/{error_id}/review", response_model=AtelierErrataReviewResponse)
def review_erratum(
    error_id: UUID,
    payload: AtelierErrataReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierErrataReviewResponse:
    error = db.query(UserError).filter(UserError.id == error_id, UserError.user_id == current_user.id).first()
    if not error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier erratum not found")

    error = ErrorMemoryService(db).review_error(
        user=current_user,
        error_id=error_id,
        rating=payload.rating,
        repaired=payload.repaired,
    )
    if not error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier erratum not found")
    db.commit()
    db.refresh(error)
    return AtelierErrataReviewResponse(erratum=serialize_erratum_record(error))


@router.get("/errata/{error_id}/task", response_model=AtelierErrataTaskResponse)
def get_erratum_review_task(
    error_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierErrataTaskResponse:
    task = ErrorMemoryService(db).build_review_task(user=current_user, error_id=error_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier erratum not found")
    return AtelierErrataTaskResponse(task=task)


@router.post("/errata/{error_id}/attempt", response_model=AtelierErrataAttemptResponse)
def submit_erratum_review_attempt(
    error_id: UUID,
    payload: AtelierErrataAttemptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierErrataAttemptResponse:
    result = ErrorMemoryService(db).submit_review_attempt(
        user=current_user,
        error_id=error_id,
        answer_text=payload.answer_text,
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier erratum not found")
    db.commit()
    return AtelierErrataAttemptResponse(**result)
