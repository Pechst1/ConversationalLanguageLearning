"""Vocabulary browsing endpoints."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
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
    DailyWordSlateResponse,
    VocabularyBiographyEvent,
    VocabularyBiographyExample,
    VocabularyBiographyOrigin,
    VocabularyBiographyProgress,
    VocabularyBiographyResponse,
    VocabularyBiographyRevisit,
    VocabularyListResponse,
    VocabularyWordRead,
)
from app.services.conjugation import ConjugationService
from app.services.core_lexicon import CORE_DECK
from app.services.daily_words import DailyWordSlateService
from app.services.glosses import gloss_payload, normalize_language
from app.services.progress import ProgressService
from app.services.vocabulary import VocabularyNotFoundError, VocabularyService
from app.services.vocabulary_coverage import VocabularyCoverageService
from app.services.vocabulary_pace import new_words_left_today, vocabulary_pace_allowance
from app.utils.cache import build_cache_key, cache_backend

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


# ---------------------------------------------------------------------------
# «Vérification du lexique» (2026-10-03): skip the words a learner already knows.
# Declared first: a later ``/{word_id}`` route would otherwise capture «band-check».
# ---------------------------------------------------------------------------


class BandCheckItem(BaseModel):
    id: str
    fr: str
    options: list[str]


class BandCheckSubBand(BaseModel):
    sub_band: str
    words: int
    credited: bool
    #: WP-127: ``sampled`` (a pass on this band) or ``inferred`` (from a pass above).
    credit_kind: str | None = None
    #: WP-127: the latest check of this band did not pass (ladder only).
    missed: bool = False


class BandCheckLadder(BaseModel):
    """WP-127: the top-down check — where it stands and what to check next."""

    policy_version: str
    #: open / paused (this visit's checks are spent) / done / none
    status: str
    next: str | None = None
    resume_band: str | None = None
    visit_checks_used: int
    visit_checks_left: int
    max_checks_per_visit: int
    items_per_check: int
    pass_correct: int
    #: Highest first.
    bands: list[BandCheckSubBand]


class BandCheckStart(BaseModel):
    sub_band: str
    items: list[BandCheckItem]
    pass_share: float
    #: WP-127: correct answers a pass needs (a documented candidate).
    pass_correct: int | None = None
    #: WP-127: this check's persistent identity; send it back with the answers.
    attempt_id: str | None = None
    policy_version: str | None = None


class BandCheckSubmit(BaseModel):
    #: item id → the chosen option's index, or null for «je ne sais pas».
    answers: dict[str, int | None] = Field(default_factory=dict)
    #: WP-127: the ``attempt_id`` the check was opened with (older clients omit it).
    attempt_id: str | None = Field(default=None, max_length=64)


class BandCheckResult(BaseModel):
    sub_band: str
    correct: int
    total: int
    passed: bool
    credited_words: int
    missed: list[str]
    #: WP-127: words on the check and answered right.
    credited_sampled: int = 0
    #: WP-127: words credited by inference — the pass's unsampled words and lower bands.
    credited_inferred: int = 0
    inferred_bands: list[str] = Field(default_factory=list)
    pass_correct: int | None = None
    attempt_id: str | None = None
    policy_version: str | None = None
    #: A replayed submit: the stored result, nothing credited twice.
    replayed: bool = False
    #: The ladder after this check: the next band down, or why there is none.
    next: str | None = None
    ladder_status: str | None = None
    resume_band: str | None = None


@router.get("/band-check", response_model=list[BandCheckSubBand])
def list_band_checks(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> list[dict[str, Any]]:
    """The sub-bands below the learner's level whose words a short check can credit."""

    from app.services import band_check

    return band_check.checkable(db, current_user)


@router.get("/band-check/ladder", response_model=BandCheckLadder)
def band_check_ladder(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """WP-127: the top-down check — the next band to check, or why there is none."""

    from app.services import band_check

    return band_check.ladder(db, current_user)


@router.get("/band-check/{sub_band}", response_model=BandCheckStart)
def start_band_check(
    sub_band: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """This attempt's check for one sub-band: meaning choices, no answer key."""

    from app.services import band_check

    allowed = {row["sub_band"] for row in band_check.checkable(db, current_user)}
    if sub_band not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No check for this level.")
    try:
        return band_check.start(db, current_user, sub_band)
    except band_check.VisitFull:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_full") from None


@router.post("/band-check/{sub_band}", response_model=BandCheckResult)
def submit_band_check(
    sub_band: str,
    payload: BandCheckSubmit,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """Grade the check; a pass credits the band (sampled) and the bands below (inferred)."""

    from app.services import band_check

    allowed = {row["sub_band"] for row in band_check.checkable(db, current_user)}
    if sub_band not in allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No check for this level.")
    try:
        result = band_check.submit(db, current_user, sub_band, payload.answers, attempt=payload.attempt_id)
    except band_check.VisitFull:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="visit_full") from None
    except band_check.StaleAttempt:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale_attempt") from None
    db.commit()
    return result



def _core_sub_band(word: VocabularyWord) -> str:
    """The sub-band tag of a core-list row («A1.1»), else its band."""

    tags = [str(tag) for tag in (word.topic_tags or [])]
    return next((tag for tag in tags if len(tag) == 4 and tag[2] == "."), next(
        (tag for tag in tags if len(tag) == 2 and tag[:1] in "ABC"), ""))

def optional_viewer(
    token: str | None = Depends(deps.optional_oauth2_scheme),
    db: Session = Depends(deps.get_db),
) -> User | None:
    """The signed-in learner when there is one; these routes stay public.

    Browsing the registre never required a session, so the payload builders had
    no learner to resolve a gloss for and shipped the raw columns instead. The
    reader is optional here: signed in, the Cahier gets glosses in the learner's
    own language; anonymous, it falls back to the shared default.
    """
    if not token:
        return None
    try:
        return deps.get_current_user_or_demo(token=token, db=db)
    except HTTPException:
        return None


def _viewer_language(viewer: User | None) -> str:
    return normalize_language(getattr(viewer, "native_language", None))


def _word_payload(word: Any, viewer_language: str) -> dict[str, Any]:
    """A vocabulary row plus the gloss the learner should actually read."""
    payload = VocabularyWordRead.model_validate(word).model_dump(mode="json")
    payload.update(gloss_payload(word, viewer_language))
    return payload


@router.get("/", response_model=VocabularyListResponse)
def list_vocabulary(
    language: str | None = Query(default=None, max_length=10, description="Language code to filter by"),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(deps.get_db),
    viewer: User | None = Depends(optional_viewer),
) -> VocabularyListResponse:
    """Return vocabulary items with optional pagination."""

    viewer_language = _viewer_language(viewer)
    # The gloss depends on who is reading, so it has to be part of the cache
    # key — otherwise the first reader's language is served to everyone.
    cache_key = build_cache_key(
        language=language,
        search=(search or "").strip().lower(),
        limit=limit,
        offset=offset,
        gloss=viewer_language,
    )
    cached = cache_backend.get("vocabulary:list", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    items = service.list_words(language=language, search=search, limit=limit, offset=offset)
    total = service.count_words(language=language, search=search)
    payload = {
        "total": total,
        "items": [_word_payload(item, viewer_language) for item in items],
    }
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
        return value.replace(tzinfo=UTC)
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


# The deck prints these four French labels over ratings 0..3; the word's own
# thread must name the same buttons rather than the raw number.
_RATING_LABELS = {0: "Encore", 1: "Dur", 2: "Bien", 3: "Facile"}


def _origin_for_word(word: Any) -> VocabularyBiographyOrigin:
    label = word.deck_name or ("French 5000" if word.is_anki_card else "Le lexique")
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
        return "new", "Nouveau", "Pas encore révisé par vous."

    state = str(progress.state or "new").lower()
    phase = str(progress.phase or "").lower()
    aware_due_at = _as_aware_datetime(due_at)
    is_due = aware_due_at is not None and aware_due_at <= now

    if is_due and (progress.reps or 0) > 0:
        return "due", "À revoir", "Prêt pour une reprise."
    if (progress.lapses or 0) >= 3 or (retrievability is not None and retrievability < 0.45):
        return "fraying", "Mémoire qui s’effrite", "Plusieurs oublis, ou un rappel estimé faible."
    if (
        phase in {"learn", "learning", "relearn", "relearning"}
        or state in {"learning", "relearning"}
        or (progress.lapses or 0) > 0
        or (retrievability is not None and retrievability < 0.72)
    ):
        return "tender", "Mémoire fragile", "Utile, mais encore facile à perdre."
    if state == "mastered" or (progress.proficiency_score or 0) >= 90:
        return "holding", "Tient", "Ce fil tient bien pour l’instant."
    if state == "new" and (progress.reps or 0) == 0:
        return "new", "Nouveau", "Pas encore révisé."
    return "forming", "En formation", "Le fil se dessine."


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
                # WP-78: a word kept from the story shows the sentence it was
                # kept with, and its meaning in the learner's language.
                source="story" if interaction.interaction_type == "kept_from_story" else "conversation",
                occurred_at=interaction.created_at,
            )
        )
        seen_sentences.add(sentence.strip().lower())
        if len(examples) >= 4:
            break
    return examples


#: WP-93: how many of the learner's latest story pages «revu dans» looks at.
#: Bounded: a season of daily pages, read newest first, filtered in Python
#: (the lemma lists are JSON, and SQLite has no portable containment test).
REVISIT_SCENE_LIMIT = 120
REVISIT_MAX = 12
_ARTICLES = ("le ", "la ", "les ", "l'", "un ", "une ", "des ", "du ", "de la ", "de l'")


def _lemma_keys(value: Any) -> set[str]:
    """A word's folded forms: as written, and without its article."""

    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or "")).casefold().replace("’", "'")
    text = " ".join("".join(c for c in text if not unicodedata.combining(c)).split())
    keys = {text} if text else set()
    for article in _ARTICLES:
        if text.startswith(article) and len(text) > len(article):
            keys.add(text[len(article):].strip())
    return keys


def _story_revisits(db: Session, *, user: User, word: Any) -> list[VocabularyBiographyRevisit]:
    """WP-93 «revu dans l'épisode du 12»: the story pages that brought this word back."""

    from app.services.living_story import ENGINE_VERSION_PREFIX

    wanted = _lemma_keys(getattr(word, "word", None)) | _lemma_keys(
        getattr(word, "normalized_word", None)
    )
    if not wanted:
        return []
    try:
        rows = (
            db.query(GraphicNovelScene)
            .filter(
                GraphicNovelScene.user_id == user.id,
                GraphicNovelScene.prompt_version.like(f"{ENGINE_VERSION_PREFIX}%"),
            )
            .order_by(GraphicNovelScene.created_at.desc())
            .limit(REVISIT_SCENE_LIMIT)
            .all()
        )
    except Exception:  # noqa: BLE001 - a biography never fails for its story line
        return []
    hits = []
    for scene in rows:
        payload = scene.script_payload if isinstance(scene.script_payload, dict) else {}
        lemmas = [
            *(payload.get("recycled_lemmas") or []),
            *(payload.get("placed_lemmas") or []),
        ]
        if any(_lemma_keys(lemma) & wanted for lemma in lemmas if isinstance(lemma, str)):
            hits.append(scene)
            if len(hits) >= REVISIT_MAX:
                break
    # The page's day is the learner's local day of the journey it was written for.
    local_days: dict[str, str] = {}
    journey_ids = []
    for scene in hits:
        source = scene.source_snapshot if isinstance(scene.source_snapshot, dict) else {}
        try:
            journey_ids.append(UUID(str(source.get("journey_id"))))
        except (TypeError, ValueError):
            continue
    if journey_ids:
        from app.db.models.daily_journey import DailyJourney

        try:
            for journey_id, local_date in (
                db.query(DailyJourney.id, DailyJourney.local_date)
                .filter(DailyJourney.id.in_(journey_ids), DailyJourney.user_id == user.id)
                .all()
            ):
                local_days[str(journey_id)] = local_date.isoformat()
        except Exception:  # noqa: BLE001 - fall back to the page's own date
            local_days = {}
    revisits: list[VocabularyBiographyRevisit] = []
    for scene in hits:
        source = scene.source_snapshot if isinstance(scene.source_snapshot, dict) else {}
        created = _as_aware_datetime(scene.created_at)
        day = local_days.get(str(source.get("journey_id") or "")) or (
            created.date().isoformat() if created else ""
        )
        revisits.append(
            VocabularyBiographyRevisit(
                date=day,
                scene_title_fr=str(scene.title or ""),
                scene_id=str(scene.id),
            )
        )
    return revisits


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
        "target_new": "Introduit en conversation",
        "target_review": "Revenu en conversation",
        "learner_use": "Employé en conversation",
        "learner_skip": "Esquivé en conversation",
    }
    for interaction in interactions:
        label = interaction_labels.get(interaction.interaction_type, "Passage en conversation")
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
                label=erratum.display_label or "Erratum lié",
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
                label=f"Mission : {mission.title}",
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
                label=f"Feuilleton : {scene.title}",
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
                label="Ancre de l’Atelier",
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


def _drill_deck(
    db: Session,
    service: ProgressService,
    user: User,
    *,
    drill: str,
    context_kwargs: dict[str, Any],
    new_limit: int,
    reserved_new: set[int],
    new_room: int | None,
) -> dict[str, Any]:
    """WP-154: the word drill's deck, kept for the learner's app day.

    ``session``: what is left of today's batch, in the order it was dealt; a new
    batch only when that one is answered (or on a new day). ``more``: the
    «Encore N mots» continuation, appended to the batch, never a word already in
    it. See :mod:`app.services.drill_batch`.
    """

    from app.services import drill_batch
    from app.services.streak import local_today

    now = datetime.now(UTC)
    day = local_today(user, now)
    batch = drill_batch.load_batch(db, user, day)
    if drill == drill_batch.DRILL_SESSION and batch is not None:
        items = list(batch.items or [])
        remaining = drill_batch.remaining_items(db, user, items, reserved_new=reserved_new)
        if remaining:
            batch.cursor = len(items) - len(remaining)
            db.commit()
            payload = service.vocabulary_due_context_from_batch(user=user, items=remaining, now=now)
            payload["new_words_left_today"] = drill_batch.resumed_new_words_left(
                new_room, batch, len(payload["new_words"])
            )
            return payload

    exclude = set(reserved_new)
    if drill == drill_batch.DRILL_MORE and batch is not None:
        # Nothing the batch already dealt as new is dealt again.
        exclude |= {int(item["word_id"]) for item in batch.items or [] if item.get("list") == "new_words"}
    payload = service.get_vocabulary_due_context(**{**context_kwargs, "exclude_new_word_ids": exclude, "now": now})
    served_new = len(payload.get("new_words") or [])
    dealt = drill_batch.items_from_payload(payload, now)
    if drill == drill_batch.DRILL_MORE and batch is not None:
        items = drill_batch.merge_items(db, user, list(batch.items or []), dealt)
        drill_batch.save_batch(db, user, day, items, new_limit=new_limit, new_dealt=served_new, batch=batch)
        db.commit()
        remaining = drill_batch.remaining_items(db, user, items, reserved_new=reserved_new)
        payload = service.vocabulary_due_context_from_batch(user=user, items=remaining, now=now)
        payload["new_words_left_today"] = drill_batch.resumed_new_words_left(
            new_room, batch, len(payload["new_words"])
        )
        return payload

    drill_batch.save_batch(db, user, day, dealt, new_limit=new_limit, new_dealt=served_new, batch=batch)
    db.commit()
    payload["new_words_left_today"] = new_words_left_today(new_room, new_limit, served_new)
    return payload


@router.get("/due-context", response_model=VocabularyDueContextResponse)
def get_vocabulary_due_context(
    *,
    limit: int = Query(12, ge=1, le=50),
    due_limit: int = Query(4, ge=0, le=50),
    fragile_limit: int = Query(4, ge=0, le=50),
    new_limit: int = Query(4, ge=0, le=50),
    topic_limit: int = Query(4, ge=0, le=50),
    linked_limit: int = Query(4, ge=0, le=50),
    direction: str | None = Query(None, description="Optional card direction filter; defaults to the learner's stored direction"),
    topic_tags: Annotated[list[str] | None, Query()] = None,
    linked_word_ids: Annotated[list[str] | None, Query()] = None,
    mission_id: UUID | None = Query(None),
    feuilleton_scene_id: UUID | None = Query(None),
    drill: str | None = Query(
        None,
        pattern="^(session|more)$",
        description=(
            "WP-154: the word drill's own deck. `session` serves the rest of the batch dealt "
            "today (a new one once it is answered); `more` appends the «Encore N mots» continuation."
        ),
    ),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> VocabularyDueContextResponse:
    """Return SRS and contextual vocabulary buckets for mobile practice surfaces."""

    card_directions = {"fr_to_de", "de_to_fr"}
    if direction and direction not in card_directions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid direction filter")
    if direction is None:
        # Fall back to the learner's stored direction; non-German pairs have no
        # Anki-style card direction yet, so they simply skip the filter.
        stored = getattr(current_user, "default_vocab_direction", None)
        direction = stored if stored in card_directions else None

    resolved_topic_tags = _split_csv_values(topic_tags)
    resolved_linked_ids = _split_csv_ints(linked_word_ids)
    episodic_anchor: dict[str, Any] | None = None

    # Normal review should still carry the active episode into the deck. Explicit
    # mission/scene filters below remain authoritative when a surface supplies one.
    if not mission_id and not feuilleton_scene_id:
        from app.db.models.serial import SerialThread
        from app.services.serial import SerialThreadService

        thread = (
            db.query(SerialThread)
            .filter(SerialThread.user_id == current_user.id, SerialThread.status == "active")
            .order_by(SerialThread.updated_at.desc())
            .first()
        )
        if thread:
            serial_service = SerialThreadService(db)
            episode = serial_service.current_episode(thread)
            if episode and episode.mission:
                resolved_linked_ids.extend(
                    int(word_id) for word_id in (episode.mission.target_vocabulary_ids or []) if word_id
                )
                snapshot = episode.mission.source_snapshot or {}
                resolved_topic_tags.extend(str(tag) for tag in snapshot.get("topic_tags", []) if tag)
            elif episode and episode.scene:
                resolved_linked_ids.extend(
                    int(word_id) for word_id in (episode.scene.target_vocabulary_ids or []) if word_id
                )
                snapshot = episode.scene.source_snapshot or {}
                resolved_topic_tags.extend(str(tag) for tag in snapshot.get("topic_tags", []) if tag)

            cast = serial_service.cast_payload(thread)
            required_cast = [
                str(value)
                for value in ((episode.brief_payload or {}).get("required_cast") or [])
                if str(value).strip()
            ] if episode else []
            cast_by_id = {str(member.get("id")): member for member in cast}
            member = next(
                (cast_by_id[member_id] for member_id in required_cast if member_id in cast_by_id),
                cast[0] if cast else None,
            )
            if member:
                episodic_anchor = {
                    "character_name": member.get("name"),
                    "portrait_url": member.get("model_sheet_url"),
                    "accent_colour": member.get("accent_colour"),
                    "source": "active_episode",
                }

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
        if mission.serial_thread_id:
            from app.db.models.serial import SerialThread
            from app.services.serial import SerialThreadService

            thread = db.get(SerialThread, mission.serial_thread_id)
            cast = SerialThreadService(db).cast_payload(thread) if thread else []
            member = cast[0] if cast else None
            if member:
                episodic_anchor = {
                    "character_name": member.get("name"),
                    "portrait_url": member.get("model_sheet_url"),
                    "source": "mission",
                }

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
        if scene.serial_thread_id:
            from app.db.models.serial import SerialThread
            from app.services.serial import SerialThreadService

            thread = db.get(SerialThread, scene.serial_thread_id)
            cast = SerialThreadService(db).cast_payload(thread) if thread else []
            member = cast[0] if cast else None
            if member:
                episodic_anchor = {
                    "character_name": member.get("name"),
                    "portrait_url": member.get("model_sheet_url"),
                    "source": "feuilleton",
                }

    # WP-L6: the word drill introduces only what the learner's vocabulary
    # pace leaves after today's journey (one intake pool), and never a word
    # the journey has reserved. WP-131: the room is kept, so the deck can say
    # what the day's allowance still holds after it.
    new_limit, reserved_new, new_room = vocabulary_pace_allowance(db, current_user, new_limit)
    # WP-115a: the learner's «Maximum reviews/day» — due words first, then fragile.
    try:
        from app.services.vocabulary_pace import reviews_left_today

        reviews_left = reviews_left_today(db, current_user)
    except Exception:  # noqa: BLE001 - a cap that cannot be read never costs the deck
        reviews_left = None
    if reviews_left is not None:
        due_limit = min(due_limit, reviews_left)
        fragile_limit = min(fragile_limit, max(0, reviews_left - due_limit))

    service = ProgressService(db)
    context_kwargs: dict[str, Any] = {
        "user": current_user,
        "limit": limit,
        "due_limit": due_limit,
        "fragile_limit": fragile_limit,
        "new_limit": new_limit,
        "exclude_new_word_ids": reserved_new,
        "topic_limit": topic_limit,
        "linked_limit": linked_limit,
        "direction": direction,
        "topic_tags": resolved_topic_tags,
        "linked_word_ids": resolved_linked_ids,
    }
    if drill and getattr(current_user, "id", None):
        payload = _drill_deck(
            db,
            service,
            current_user,
            drill=drill,
            context_kwargs=context_kwargs,
            new_limit=new_limit,
            reserved_new=set(reserved_new or ()),
            new_room=new_room,
        )
    else:
        payload = service.get_vocabulary_due_context(**context_kwargs)
        payload["new_words_left_today"] = new_words_left_today(
            new_room, new_limit, len(payload.get("new_words") or [])
        )
    if episodic_anchor:
        anchor_word_ids = {int(word_id) for word_id in resolved_linked_ids}
        for bucket_name in (
            "due_words",
            "fragile_words",
            "new_words",
            "topic_compatible_words",
            "linked_words",
        ):
            payload[bucket_name] = [
                {
                    **item,
                    **(
                        {"episodic_anchor": episodic_anchor}
                        if bucket_name == "linked_words" or int(item.get("word_id") or 0) in anchor_word_ids
                        else {}
                    ),
                }
                for item in payload.get(bucket_name) or []
            ]
    return VocabularyDueContextResponse(**payload)


@router.get("/words-of-the-day", response_model=DailyWordSlateResponse)
def get_words_of_the_day(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user_or_demo),
) -> DailyWordSlateResponse:
    """Return today's coordinated word slate, selecting it on first call."""

    service = DailyWordSlateService(db)
    payload = service.get_or_create(user=current_user)
    db.commit()
    return DailyWordSlateResponse(**_with_word_grammar(db, payload))


def _with_word_grammar(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach each slate word's stored gender and part of speech (WP-D6).

    The slate is persisted once per day, so these are read from the catalogue
    on every request instead of being frozen into it: a gender backfill shows
    up the same day. A word the catalogue has no gender for keeps ``None``.
    """

    entries = [entry for entry in payload.get("words") or [] if isinstance(entry, dict)]
    ids: set[int] = set()
    for entry in entries:
        try:
            ids.add(int(entry.get("word_id") or 0))
        except (TypeError, ValueError):
            continue
    ids.discard(0)
    if not ids:
        return payload
    rows = (
        db.query(
            VocabularyWord.id,
            VocabularyWord.word,
            VocabularyWord.language,
            VocabularyWord.part_of_speech,
            VocabularyWord.gender,
        )
        .filter(VocabularyWord.id.in_(ids))
        .all()
    )
    from app.services.lexicon_grammar import word_grammar

    # WP-84: the core lexicon fills what the card lacks, so every noun shows le / la.
    grammar = {int(row.id): word_grammar(row) for row in rows}
    words = []
    for entry in payload.get("words") or []:
        if isinstance(entry, dict):
            try:
                pos, gender = grammar.get(int(entry.get("word_id") or 0), (None, None))
            except (TypeError, ValueError):
                pos, gender = None, None
            entry = {**entry, "part_of_speech": pos, "gender": gender}
        words.append(entry)
    return {**payload, "words": words}


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
            person=payload.person,
            answer_text=payload.answer_text,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    verdict = getattr(progress, "last_verdict", None)
    note = None
    if verdict is not None:
        from app.services.answer_acceptance import feedback_note
        from app.services.chrome_language import user_chrome_language

        note = feedback_note(verdict, str(user_chrome_language(current_user)))
    return ConjugationReviewResponse(
        lemma=progress.verb_lemma,
        tense=progress.tense,
        state=progress.state or "new",
        proficiency_score=progress.proficiency_score or 0,
        reps=progress.reps or 0,
        lapses=progress.lapses or 0,
        next_review=progress.next_review_date,
        correct=verdict.correct if verdict is not None else None,
        expected=verdict.expected if verdict is not None else None,
        note_native=note,
    )


class KeepWordRequest(BaseModel):
    """WP-78 «Garder»: a word tapped in the story, and the sentence it was in."""

    term: str = Field(..., min_length=1, max_length=80)
    sentence: str = Field(..., min_length=1, max_length=2000)
    surface: str | None = Field(default=None, max_length=80)
    journey_id: UUID | None = None
    #: WP-115a — where the word was met, so its reviews can bring the scene back.
    speaker_id: str | None = Field(default=None, max_length=80)
    panel_id: str | None = Field(default=None, max_length=80)
    #: The line's audio key (``{panel_id}:l{index}``).
    line_key: str | None = Field(default=None, max_length=120)


#: What the sheet says when a word cannot be kept. French: this is chrome.
_KEEP_REFUSAL_FR = {
    "empty_term": "Ce mot ne peut pas être gardé.",
    "no_sentence": "Ce mot ne peut être gardé qu'avec sa phrase.",
    "not_in_lexicon": "Ce mot n'est pas encore dans le lexique.",
    "no_gloss_in_learner_language": "Pas encore de traduction dans votre langue pour ce mot.",
}


@router.post("/keep")
def keep_vocabulary_word(
    payload: KeepWordRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, Any]:
    """WP-78 — keep a tapped word in the learner's Lexique, with its sentence.

    Learner-scoped by construction (``app/services/kept_words.py``): the shared
    catalogue row is never written. Idempotent for the same word and sentence.
    """

    from app.services.kept_words import KeepRefused, keep_word

    try:
        kept = keep_word(
            db,
            user=current_user,
            term=payload.term,
            sentence=payload.sentence,
            surface=payload.surface,
            journey_id=payload.journey_id,
            met={
                "speaker_id": payload.speaker_id,
                "panel_id": payload.panel_id,
                "line_key": payload.line_key,
            },
        )
    except KeepRefused as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": exc.reason,
                "message": _KEEP_REFUSAL_FR.get(exc.reason, _KEEP_REFUSAL_FR["empty_term"]),
            },
        ) from exc
    db.commit()
    return kept.as_public()


@router.get("/lookup", response_model=VocabularyWordRead)
def lookup_vocabulary_word(
    word: str = Query(..., min_length=1, description="Surface form to look up"),
    language: str | None = Query(default=None, max_length=10),
    db: Session = Depends(deps.get_db),
    viewer: User | None = Depends(optional_viewer),
) -> VocabularyWordRead:
    """Lookup a vocabulary word by its surface form."""

    viewer_language = _viewer_language(viewer)
    cache_key = build_cache_key(word=word.strip().lower(), language=language, gloss=viewer_language)
    cached = cache_backend.get("vocabulary:lookup", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    try:
        vocab_word = service.lookup_word(term=word, language=language)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    payload = _word_payload(vocab_word, viewer_language)
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

    now = datetime.now(UTC)
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
            label=f"Entré par {origin.label}",
            description=(
                # The core list's rank is a learning order, not a frequency.
                f"Lexique de base · {_core_sub_band(word)}"
                if word.deck_name == CORE_DECK
                else f"Rang de fréquence {word.frequency_rank}"
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
                    label="Première rencontre",
                    description=f"{progress.times_seen or 0} passages en contexte.",
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
                    label="Dernière révision",
                    description=f"{progress.reps or 0} révisions, {progress.lapses or 0} oublis.",
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
                    label="Prochaine reprise",
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
                    label=f"Noté : {_RATING_LABELS.get(int(log.rating or 0), 'classé')}",
                    description=(
                        f"Échéance {log.schedule_before or 0} → {log.schedule_after or 0} jours"
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
        or datetime.min.replace(tzinfo=UTC),
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
        # `_word_payload` attaches the gloss resolved for this learner; the bare
        # model_validate left `translation` empty and the sheet fell back to
        # reading the German column first for everyone.
        word=VocabularyWordRead.model_validate(
            _word_payload(word, _viewer_language(current_user))
        ),
        origin=origin,
        progress=progress_state,
        examples=examples,
        linked_errata_count=linked_errata_count,
        context_event_count=context_event_count,
        timeline=timeline,
        revisited_in=_story_revisits(db, user=current_user, word=word),
    )


@router.get("/{word_id}", response_model=VocabularyWordRead)
def get_vocabulary_word(
    word_id: int,
    db: Session = Depends(deps.get_db),
    viewer: User | None = Depends(optional_viewer),
) -> VocabularyWordRead:
    """Retrieve a vocabulary word by identifier."""

    viewer_language = _viewer_language(viewer)
    cache_key = build_cache_key(word_id=word_id, gloss=viewer_language)
    cached = cache_backend.get("vocabulary:item", cache_key)
    if cached is not None:
        return cached

    service = VocabularyService(db)
    try:
        word = service.get_word(word_id)
    except VocabularyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = _word_payload(word, viewer_language)
    cache_backend.set("vocabulary:item", cache_key, payload, ttl_seconds=3600)
    return payload

