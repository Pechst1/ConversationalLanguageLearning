"""Vocabulary browsing endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.session import WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VerbConjugation, VocabularyWord
from app.schemas.progress import VocabularyDueContextResponse
from app.schemas.vocabulary import (
    ConjugationReviewRequest,
    ConjugationReviewResponse,
    VocabularyBiographyEvent,
    VocabularyBiographyExample,
    VocabularyBiographyOrigin,
    VocabularyBiographyProgress,
    VocabularyBiographyResponse,
    VocabularyListResponse,
    VocabularyWordRead,
)
from app.services.conjugation import ConjugationService
from app.services.progress import ProgressService
from app.services.vocabulary import VocabularyNotFoundError, VocabularyService
from app.services.vocabulary_coverage import VocabularyCoverageService
from app.utils.cache import cache_backend, build_cache_key

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/", response_model=VocabularyListResponse)
def list_vocabulary(
    language: str | None = Query(default=None, max_length=10, description="Language code to filter by"),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(deps.get_db),
) -> VocabularyListResponse:
    """Return vocabulary items with optional pagination."""

    cache_key = build_cache_key(language=language, search=(search or "").strip().lower(), limit=limit, offset=offset)
    cached = cache_backend.get("vocabulary:list", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    items = service.list_words(language=language, search=search, limit=limit, offset=offset)
    total = service.count_words(language=language, search=search)
    response = VocabularyListResponse(total=total, items=items)
    payload = response.model_dump(mode="json")
    cache_backend.set("vocabulary:list", cache_key, payload, ttl_seconds=3600)
    return payload


def _split_csv_values(raw_values: list[str] | None) -> list[str]:
    values: list[str] = []
    for raw in raw_values or []:
        values.extend(item.strip() for item in raw.split(",") if item.strip())
    return values


def _split_csv_ints(raw_values: list[str] | None) -> list[int]:
    values: list[int] = []
    for item in _split_csv_values(raw_values):
        try:
            values.append(int(item))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="linked_word_ids must be integers",
            ) from exc
    return values


def _compact_text(value: Any, *, max_length: int = 180) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3].rstrip()}..."


def _as_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _contains_word_id(raw_values: Any, word_id: int) -> bool:
    values = raw_values if isinstance(raw_values, list) else [raw_values]
    for value in values or []:
        try:
            if int(value) == word_id:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _payload_has_word_id(payload: Any, word_id: int, *, depth: int = 5) -> bool:
    if depth <= 0:
        return False
    if isinstance(payload, (int, str)):
        return _contains_word_id(payload, word_id)
    if isinstance(payload, dict):
        for key in ("word_id", "linked_word_id", "target_word_id"):
            if _contains_word_id(payload.get(key), word_id):
                return True
        return any(_payload_has_word_id(value, word_id, depth=depth - 1) for value in payload.values())
    if isinstance(payload, list):
        return any(_payload_has_word_id(item, word_id, depth=depth - 1) for item in payload)
    return False


def _timeline_event(
    *,
    event_id: str,
    event_type: str,
    label: str,
    source_type: str,
    description: Any = None,
    occurred_at: datetime | None = None,
    source_id: Any = None,
    metadata: dict[str, Any] | None = None,
) -> VocabularyBiographyEvent:
    return VocabularyBiographyEvent(
        id=event_id,
        event_type=event_type,
        label=label,
        description=_compact_text(description),
        occurred_at=occurred_at,
        source_type=source_type,
        source_id=str(source_id) if source_id else None,
        metadata=metadata or {},
    )


def _dedupe_events(events: list[VocabularyBiographyEvent]) -> list[VocabularyBiographyEvent]:
    seen: set[str] = set()
    deduped: list[VocabularyBiographyEvent] = []
    for event in events:
        if event.id in seen:
            continue
        seen.add(event.id)
        deduped.append(event)
    return deduped


def _origin_for_word(word: Any) -> VocabularyBiographyOrigin:
    label = word.deck_name or ("French 5000" if word.is_anki_card else "Vocabulary bank")
    source_type = "anki_deck" if word.is_anki_card else ("deck" if word.deck_name else "lexicon")
    return VocabularyBiographyOrigin(
        label=label,
        source_type=source_type,
        deck_name=word.deck_name,
        imported=bool(word.is_anki_card),
        frequency_rank=word.frequency_rank,
        created_at=word.created_at,
    )


def _fragility_for_progress(
    progress: UserVocabularyProgress | None,
    *,
    due_at: datetime | None,
    retrievability: float | None,
    now: datetime,
) -> tuple[str, str, str | None]:
    if progress is None:
        return "new", "New thread", "No personal reviews yet."

    state = str(progress.state or "new").lower()
    phase = str(progress.phase or "").lower()
    aware_due_at = _as_aware_datetime(due_at)
    is_due = aware_due_at is not None and aware_due_at <= now

    if is_due and (progress.reps or 0) > 0:
        return "due", "Due now", "Ready for another touch."
    if (progress.lapses or 0) >= 3 or (retrievability is not None and retrievability < 0.45):
        return "fraying", "Fraying memory", "Several misses or low recall estimate."
    if (
        phase in {"learn", "learning", "relearn", "relearning"}
        or state in {"learning", "relearning"}
        or (progress.lapses or 0) > 0
        or (retrievability is not None and retrievability < 0.72)
    ):
        return "tender", "Tender memory", "Useful, but still easy to lose."
    if state == "mastered" or (progress.proficiency_score or 0) >= 90:
        return "holding", "Holding", "This thread is currently strong."
    if state == "new" and (progress.reps or 0) == 0:
        return "new", "New thread", "Not reviewed yet."
    return "forming", "Forming", "The thread is taking shape."


def _progress_payload(
    *,
    word: Any,
    progress: UserVocabularyProgress | None,
    service: ProgressService,
    now: datetime,
) -> VocabularyBiographyProgress:
    due_at = service._progress_due_at(progress) if progress else None
    retrievability = service._fsrs_retrievability(progress, now=now) if progress else None
    level, label, reason = _fragility_for_progress(
        progress,
        due_at=due_at,
        retrievability=retrievability,
        now=now,
    )
    return VocabularyBiographyProgress(
        progress_id=str(progress.id) if progress and progress.id else None,
        scheduler=progress.scheduler if progress else ("anki" if word.is_anki_card else "fsrs"),
        state=progress.state if progress else "new",
        phase=progress.phase if progress else None,
        due_at=due_at,
        next_review=progress.next_review_date if progress else None,
        last_review=progress.last_review_date if progress else None,
        scheduled_days=progress.scheduled_days if progress else None,
        interval_days=progress.interval_days if progress else None,
        stability=progress.stability if progress else None,
        difficulty=progress.difficulty if progress else None,
        retrievability=retrievability,
        proficiency_score=progress.proficiency_score if progress else 0,
        reps=progress.reps if progress else 0,
        lapses=progress.lapses if progress else 0,
        times_seen=progress.times_seen if progress else 0,
        times_used_correctly=progress.times_used_correctly if progress else 0,
        times_used_incorrectly=progress.times_used_incorrectly if progress else 0,
        fragility_level=level,
        fragility_label=label,
        fragility_reason=reason,
    )


def _example_payloads(db: Session, *, user: User, word: Any) -> list[VocabularyBiographyExample]:
    examples: list[VocabularyBiographyExample] = []
    seen_sentences: set[str] = set()
    if word.example_sentence:
        examples.append(
            VocabularyBiographyExample(
                sentence=word.example_sentence,
                translation=word.example_translation or word.english_translation or word.german_translation,
                source="dictionary",
                occurred_at=word.created_at,
            )
        )
        seen_sentences.add(word.example_sentence.strip().lower())

    interactions = (
        db.query(WordInteraction)
        .filter(WordInteraction.user_id == user.id, WordInteraction.word_id == word.id)
        .order_by(WordInteraction.created_at.desc())
        .limit(6)
        .all()
    )
    for interaction in interactions:
        sentence = _compact_text(interaction.context_sentence or interaction.user_response, max_length=220)
        if not sentence or sentence.strip().lower() in seen_sentences:
            continue
        examples.append(
            VocabularyBiographyExample(
                sentence=sentence,
                translation=interaction.correction,
                source="conversation",
                occurred_at=interaction.created_at,
            )
        )
        seen_sentences.add(sentence.strip().lower())
        if len(examples) >= 4:
            break
    return examples


def _context_timeline_events(db: Session, *, user: User, word_id: int) -> list[VocabularyBiographyEvent]:
    events: list[VocabularyBiographyEvent] = []

    interactions = (
        db.query(WordInteraction)
        .filter(WordInteraction.user_id == user.id, WordInteraction.word_id == word_id)
        .order_by(WordInteraction.created_at.desc())
        .limit(8)
        .all()
    )
    interaction_labels = {
        "target_new": "Introduced in conversation",
        "target_review": "Returned in conversation",
        "learner_use": "Used in conversation",
        "learner_skip": "Skipped in conversation",
    }
    for interaction in interactions:
        label = interaction_labels.get(interaction.interaction_type, "Conversation touch")
        events.append(
            _timeline_event(
                event_id=f"interaction:{interaction.id}",
                event_type="conversation",
                label=label,
                description=interaction.user_response or interaction.context_sentence or interaction.error_description,
                occurred_at=interaction.created_at,
                source_type="conversation",
                source_id=interaction.message_id or interaction.session_id,
                metadata={
                    "interaction_type": interaction.interaction_type,
                    "was_suggested": bool(interaction.was_suggested),
                    "error_type": interaction.error_type,
                },
            )
        )

    errata = (
        db.query(UserError)
        .filter(UserError.user_id == user.id, UserError.linked_word_id == word_id)
        .order_by(UserError.created_at.desc())
        .limit(6)
        .all()
    )
    for erratum in errata:
        events.append(
            _timeline_event(
                event_id=f"erratum:{erratum.id}",
                event_type="erratum",
                label=erratum.display_label or "Linked erratum",
                description=erratum.why_wrong or erratum.repair_hint or erratum.context_snippet,
                occurred_at=erratum.created_at,
                source_type=erratum.source_type or "errata",
                source_id=erratum.id,
                metadata={
                    "review_mode": erratum.review_mode,
                    "task_error_type": erratum.task_error_type,
                    "state": erratum.state,
                    "lapses": erratum.lapses or 0,
                },
            )
        )

    missions = (
        db.query(RealWorldMission)
        .filter(RealWorldMission.user_id == user.id)
        .order_by(RealWorldMission.created_at.desc())
        .limit(10)
        .all()
    )
    for mission in missions:
        if not _contains_word_id(mission.target_vocabulary_ids, word_id):
            continue
        events.append(
            _timeline_event(
                event_id=f"mission:{mission.id}",
                event_type="mission",
                label=f"Mission target: {mission.title}",
                description=mission.brief,
                occurred_at=mission.completed_at or mission.started_at or mission.created_at,
                source_type="mission",
                source_id=mission.id,
                metadata={"status": mission.status, "mission_type": mission.mission_type},
            )
        )

    scenes = (
        db.query(GraphicNovelScene)
        .filter(GraphicNovelScene.user_id == user.id)
        .order_by(GraphicNovelScene.created_at.desc())
        .limit(10)
        .all()
    )
    for scene in scenes:
        if not _contains_word_id(scene.target_vocabulary_ids, word_id):
            continue
        events.append(
            _timeline_event(
                event_id=f"graphic-novel:{scene.id}",
                event_type="graphic_novel",
                label=f"Feuilleton thread: {scene.title}",
                description=scene.brief,
                occurred_at=scene.completed_at or scene.started_at or scene.created_at,
                source_type="graphic_novel",
                source_id=scene.id,
                metadata={"status": scene.status, "cadence": scene.cadence},
            )
        )

    atelier_sessions = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user.id)
        .order_by(AtelierSession.created_at.desc())
        .limit(10)
        .all()
    )
    for session in atelier_sessions:
        if not _payload_has_word_id(session.quote_payload or {}, word_id):
            continue
        events.append(
            _timeline_event(
                event_id=f"atelier-session:{session.id}",
                event_type="atelier",
                label="Atelier context anchor",
                description=(session.quote_payload or {}).get("brief") or (session.quote_payload or {}).get("title"),
                occurred_at=session.completed_at or session.started_at or session.created_at,
                source_type="atelier",
                source_id=session.id,
                metadata={"status": session.status},
            )
        )

    atelier_attempts = (
        db.query(AtelierAttempt)
        .filter(AtelierAttempt.user_id == user.id)
        .order_by(AtelierAttempt.created_at.desc())
        .limit(12)
        .all()
    )
    for attempt in atelier_attempts:
        if not (
            _payload_has_word_id(attempt.prompt_payload or {}, word_id)
            or _payload_has_word_id(attempt.correction_payload or {}, word_id)
        ):
            continue
        answer_text = (attempt.answer_payload or {}).get("text")
        events.append(
            _timeline_event(
                event_id=f"atelier-attempt:{attempt.id}",
                event_type="atelier_attempt",
                label=f"Atelier {attempt.round}",
                description=answer_text or (attempt.correction_payload or {}).get("feedback"),
                occurred_at=attempt.created_at,
                source_type="atelier",
                source_id=attempt.id,
                metadata={"round": attempt.round, "mode": attempt.mode, "verdict": attempt.verdict},
            )
        )

    return events


@router.get("/due-context", response_model=VocabularyDueContextResponse)
def get_vocabulary_due_context(
    *,
    limit: int = Query(12, ge=1, le=50),
    due_limit: int = Query(4, ge=0, le=50),
    fragile_limit: int = Query(4, ge=0, le=50),
    new_limit: int = Query(4, ge=0, le=50),
    topic_limit: int = Query(4, ge=0, le=50),
    linked_limit: int = Query(4, ge=0, le=50),
    direction: str | None = Query("fr_to_de", description="Optional card direction filter"),
    topic_tags: Annotated[list[str] | None, Query()] = None,
    linked_word_ids: Annotated[list[str] | None, Query()] = None,
    mission_id: UUID | None = Query(None),
    feuilleton_scene_id: UUID | None = Query(None),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> VocabularyDueContextResponse:
    """Return SRS and contextual vocabulary buckets for mobile practice surfaces."""

    if direction and direction not in {"fr_to_de", "de_to_fr"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction filter")

    resolved_topic_tags = _split_csv_values(topic_tags)
    resolved_linked_ids = _split_csv_ints(linked_word_ids)

    if mission_id:
        mission = (
            db.query(RealWorldMission)
            .filter(RealWorldMission.id == mission_id, RealWorldMission.user_id == current_user.id)
            .first()
        )
        if not mission:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
        resolved_linked_ids.extend(int(word_id) for word_id in (mission.target_vocabulary_ids or []) if word_id)
        snapshot = mission.source_snapshot or {}
        resolved_topic_tags.extend(str(tag) for tag in snapshot.get("topic_tags", []) if tag)

    if feuilleton_scene_id:
        scene = (
            db.query(GraphicNovelScene)
            .filter(GraphicNovelScene.id == feuilleton_scene_id, GraphicNovelScene.user_id == current_user.id)
            .first()
        )
        if not scene:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feuilleton scene not found")
        resolved_linked_ids.extend(int(word_id) for word_id in (scene.target_vocabulary_ids or []) if word_id)
        snapshot = scene.source_snapshot or {}
        resolved_topic_tags.extend(str(tag) for tag in snapshot.get("topic_tags", []) if tag)

    service = ProgressService(db)
    payload = service.get_vocabulary_due_context(
        user=current_user,
        limit=limit,
        due_limit=due_limit,
        fragile_limit=fragile_limit,
        new_limit=new_limit,
        topic_limit=topic_limit,
        linked_limit=linked_limit,
        direction=direction,
        topic_tags=resolved_topic_tags,
        linked_word_ids=resolved_linked_ids,
    )
    return VocabularyDueContextResponse(**payload)


@router.get("/coverage")
def get_vocabulary_coverage(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> dict[str, Any]:
    """Return the three-axis coverage map for the learner."""

    return VocabularyCoverageService(db).coverage(user=current_user)


@router.get("/conjugation/review")
def get_conjugation_review_queue(
    *,
    limit: int = Query(12, ge=1, le=50),
    cefr_band: str | None = Query(None, max_length=10),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> dict[str, Any]:
    """Return due/new irregular conjugation drill prompts."""

    service = ConjugationService(db)
    items = service.review_queue(user=current_user, limit=limit, cefr_band=cefr_band)
    if not items:
        if db.query(VerbConjugation.id).limit(1).first() is None:
            service.ensure_verb_rows_from_vocabulary()
        service.seed_essential_irregulars()
        db.commit()
        items = service.review_queue(user=current_user, limit=limit, cefr_band=cefr_band)
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "due": len([item for item in items if item.get("progress_id")]),
            "new": len([item for item in items if not item.get("progress_id")]),
        },
        "algorithm": "irregular_conjugation_fsrs_v1",
    }


@router.post("/conjugation/review", response_model=ConjugationReviewResponse)
def submit_conjugation_review(
    payload: ConjugationReviewRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> ConjugationReviewResponse:
    """Rate an irregular conjugation item."""

    try:
        progress = ConjugationService(db).review(
            user=current_user,
            lemma=payload.lemma,
            tense=payload.tense,
            rating=payload.rating,
            response_time_ms=payload.response_time_ms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ConjugationReviewResponse(
        lemma=progress.verb_lemma,
        tense=progress.tense,
        state=progress.state or "new",
        proficiency_score=progress.proficiency_score or 0,
        reps=progress.reps or 0,
        lapses=progress.lapses or 0,
        next_review=progress.next_review_date,
    )


@router.get("/lookup", response_model=VocabularyWordRead)
def lookup_vocabulary_word(
    word: str = Query(..., min_length=1, description="Surface form to look up"),
    language: str | None = Query(default=None, max_length=10),
    db: Session = Depends(deps.get_db),
) -> VocabularyWordRead:
    """Lookup a vocabulary word by its surface form."""

    cache_key = build_cache_key(word=word.strip().lower(), language=language)
    cached = cache_backend.get("vocabulary:lookup", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    try:
        vocab_word = service.lookup_word(term=word, language=language)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    payload = VocabularyWordRead.model_validate(vocab_word).model_dump(mode="json")
    cache_backend.set("vocabulary:lookup", cache_key, payload, ttl_seconds=600)
    return payload


@router.get("/{word_id}/biography", response_model=VocabularyBiographyResponse)
def get_vocabulary_word_biography(
    word_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> VocabularyBiographyResponse:
    """Return a concise, user-aware memory thread for a vocabulary word."""

    word = db.get(VocabularyWord, word_id)
    if not word:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vocabulary word not found")

    now = datetime.now(timezone.utc)
    progress_service = ProgressService(db)
    progress = progress_service.get_progress(user_id=current_user.id, word_id=word_id)
    origin = _origin_for_word(word)
    progress_state = _progress_payload(
        word=word,
        progress=progress,
        service=progress_service,
        now=now,
    )
    examples = _example_payloads(db, user=current_user, word=word)

    events: list[VocabularyBiographyEvent] = [
        _timeline_event(
            event_id=f"origin:{word.id}",
            event_type="origin",
            label=f"Entered from {origin.label}",
            description=(
                f"Frequency rank {word.frequency_rank}"
                if word.frequency_rank
                else word.definition or word.usage_notes
            ),
            occurred_at=word.created_at,
            source_type=origin.source_type,
            source_id=word.deck_name,
            metadata={"direction": word.direction, "imported": bool(word.is_anki_card)},
        )
    ]

    if progress:
        if progress.first_seen_date:
            events.append(
                _timeline_event(
                    event_id=f"progress:first-seen:{progress.id}",
                    event_type="first_seen",
                    label="First seen by you",
                    description=f"{progress.times_seen or 0} context touches recorded.",
                    occurred_at=progress.first_seen_date,
                    source_type="srs",
                    source_id=progress.id,
                )
            )
        if progress.last_review_date:
            events.append(
                _timeline_event(
                    event_id=f"progress:last-review:{progress.id}",
                    event_type="review",
                    label="Last reviewed",
                    description=f"{progress.reps or 0} reviews, {progress.lapses or 0} lapses.",
                    occurred_at=progress.last_review_date,
                    source_type="srs",
                    source_id=progress.id,
                    metadata={"state": progress.state, "phase": progress.phase},
                )
            )
        if progress_state.due_at:
            events.append(
                _timeline_event(
                    event_id=f"progress:due:{progress.id}",
                    event_type="schedule",
                    label="Next scheduled touch",
                    description=progress_state.fragility_reason,
                    occurred_at=progress_state.due_at,
                    source_type="srs",
                    source_id=progress.id,
                    metadata={"fragility_level": progress_state.fragility_level},
                )
            )
        review_logs = (
            db.query(ReviewLog)
            .filter(ReviewLog.progress_id == progress.id)
            .order_by(ReviewLog.review_date.desc())
            .limit(5)
            .all()
        )
        for log in review_logs:
            events.append(
                _timeline_event(
                    event_id=f"review-log:{log.id}",
                    event_type="review_log",
                    label=f"Review rating {log.rating}",
                    description=(
                        f"Schedule {log.schedule_before or 0} to {log.schedule_after or 0} days"
                        if log.schedule_after is not None
                        else log.state_transition
                    ),
                    occurred_at=log.review_date,
                    source_type=log.scheduler_type or "srs",
                    source_id=log.id,
                    metadata={
                        "state_transition": log.state_transition,
                        "response_time_ms": log.response_time_ms,
                    },
                )
            )

    context_events = _context_timeline_events(db, user=current_user, word_id=word_id)
    events.extend(context_events)
    deduped_timeline = _dedupe_events(events)
    origin_events = [event for event in deduped_timeline if event.event_type == "origin"]
    recent_events = [event for event in deduped_timeline if event.event_type != "origin"]
    recent_events.sort(
        key=lambda event: _as_aware_datetime(event.occurred_at)
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    timeline = origin_events + recent_events[:27]

    linked_errata_count = (
        db.query(UserError)
        .filter(UserError.user_id == current_user.id, UserError.linked_word_id == word_id)
        .count()
    )
    context_event_types = {
        "atelier",
        "atelier_attempt",
        "conversation",
        "erratum",
        "graphic_novel",
        "mission",
    }
    context_event_count = len([event for event in timeline if event.event_type in context_event_types])

    return VocabularyBiographyResponse(
        word=VocabularyWordRead.model_validate(word),
        origin=origin,
        progress=progress_state,
        examples=examples,
        linked_errata_count=linked_errata_count,
        context_event_count=context_event_count,
        timeline=timeline,
    )


@router.get("/{word_id}", response_model=VocabularyWordRead)
def get_vocabulary_word(word_id: int, db: Session = Depends(deps.get_db)) -> VocabularyWordRead:
    """Retrieve a vocabulary word by identifier."""

    cache_key = build_cache_key(word_id=word_id)
    cached = cache_backend.get("vocabulary:item", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    try:
        word = service.get_word(word_id)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = VocabularyWordRead.model_validate(word).model_dump(mode="json")
    cache_backend.set("vocabulary:item", cache_key, payload, ttl_seconds=3600)
    return payload
