"""Atelier grammar practice API."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from time import perf_counter
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, harden_demo_user_password
from app.config import settings
from app.core.offload import off_event_loop
from app.core.security import (
    InvalidTokenError,
    decode_token,
    get_unusable_password_hash,
)
from app.db.models.atelier import (
    AtelierAttempt,
    AtelierExerciseSet,
    AtelierGenerationEvent,
    AtelierSession,
)
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization, UserGrammarProgress
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.schemas import TokenPayload
from app.schemas.atelier import (
    AtelierActiveSessionResponse,
    AtelierAlmanacResponse,
    AtelierAttemptRepairRequest,
    AtelierAttemptRequest,
    AtelierAttemptResponse,
    AtelierCompleteResponse,
    AtelierConceptRead,
    AtelierErrataAttemptRequest,
    AtelierErrataAttemptResponse,
    AtelierErrataReviewRequest,
    AtelierErrataReviewResponse,
    AtelierErrataTaskResponse,
    AtelierExerciseReportRequest,
    AtelierExerciseReportResponse,
    AtelierSessionStartRequest,
    AtelierSessionStartResponse,
    AtelierTodayResponse,
    AtelierWorkshopComposeRequest,
    AtelierWorkshopComposeResponse,
)
from app.services.atelier import (
    ATELIER_GENERATOR_VERSION,
    ATELIER_ITEMS_PER_RECOGNIZE_MODE,
    ATELIER_TRANSFORM_ITEMS,
    FORGE_VERDICT_EVENT,
    AtelierCorrectionService,
    AtelierExerciseGenerationError,
    AtelierExerciseQualityService,
    AtelierScheduler,
    AtelierSRSService,
    ConceptSelection,
    estimate_session_minutes,
    forward_report_to_pool,
    fr_localizations_by_concept_id,
    inject_vocabulary_context,
    planned_session_drills,
    pregenerate_next_atelier_session,
    run_atelier_ai_review,
    select_atelier_vocabulary,
    serialize_concept,
    serialize_erratum_record,
    session_exercise_set,
    session_vocabulary_context,
)
from app.services.atelier_assets import AtelierAssetService
from app.services.atelier_rewards import AtelierRewardService, AtelierWorkshopShortfall
from app.services.book_library import BookLibraryService
from app.services.cefr_progress import CEFRProgressService
from app.services.error_memory import ErrorMemoryService
from app.services.forge import ForgeService, is_forge_session  # WP-S3 La Forge
from app.services.forge_picker import forge_plan  # WP-S4 one picker
from app.services.glosses import DEFAULT_GLOSS_LANGUAGE, normalize_language
from app.services.learner_copy import (
    LEARNER_COPY,
    learner_text,
    learner_text_for_english,
)
from app.services.pilot_events import PilotEventService
from app.services.progress import vocabulary_due_filter
from app.services.serial import SerialThreadService
from app.services.streak import settle_streak

router = APIRouter(prefix="/atelier", tags=["atelier"])
atelier_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)
ATELIER_DEMO_EMAIL = "atelier-demo@local.test"


def _serial_conversation_context(db: Session, user: User) -> dict[str, Any] | None:
    """Choose the current-beat cast member, falling back to the closest relationship."""
    thread = (
        db.query(SerialThread)
        .filter(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.updated_at.desc())
        .first()
    )
    if not thread:
        return None
    serial_service = SerialThreadService(db)
    episode = serial_service.current_episode(thread)
    brief = episode.brief_payload if episode and isinstance(episode.brief_payload, dict) else {}
    preferred_ids = [str(value) for value in brief.get("required_cast") or [] if str(value).strip()]
    mission = db.get(RealWorldMission, episode.mission_id) if episode and episode.mission_id else None
    mission_prompt = mission.prompt_payload if mission and isinstance(mission.prompt_payload, dict) else {}
    mission_character_id = str(mission_prompt.get("serial_character_id") or "").strip()
    if mission_character_id:
        preferred_ids.insert(0, mission_character_id)

    cast = serial_service.cast_payload(thread)
    if not cast:
        return None
    by_id = {str(member.get("id")): member for member in cast if member.get("id")}
    character = next((by_id.get(character_id) for character_id in preferred_ids if by_id.get(character_id)), None)
    if not character:
        character = max(
            cast,
            key=lambda member: int((member.get("relationship") or {}).get("closeness") or 0),
        )
    relationship = character.get("relationship") if isinstance(character.get("relationship"), dict) else {}
    register = str(relationship.get("register") or "vous").lower()
    messenger = mission_prompt.get("messenger") if isinstance(mission_prompt.get("messenger"), dict) else {}
    opener = str(
        messenger.get("opening_message")
        or mission_prompt.get("conversation_opening")
        or (
            "J'ai besoin de ton avis. Qu'est-ce que tu en penses ?"
            if register == "tu"
            else "J'ai besoin de votre avis. Qu'est-ce que vous en pensez ?"
        )
    ).strip()
    previous_hook = (episode.hook_from_previous or {}).get("text") if episode else ""
    scene_context = str(
        previous_hook
        or brief.get("hook_guidance")
        or brief.get("stage_summary")
        or "La conversation reprend dans le feuilleton du jour."
    ).strip()
    return {
        "thread_id": str(thread.id),
        "episode_index": episode.episode_index if episode else thread.current_episode_index,
        "scene_context": scene_context,
        "opener": opener,
        "character": {
            "id": character.get("id"),
            "name": character.get("name"),
            "role": character.get("role"),
            "register": register,
            "closeness": int(relationship.get("closeness") or 0),
        },
    }


def _fr_concept_title(
    concept: GrammarConcept,
    fr_localizations: dict[int, GrammarConceptLocalization] | None = None,
) -> str:
    """The publication title for a concept, falling back to the catalog name."""
    localization = (fr_localizations or {}).get(concept.id)
    return str((localization.title if localization else None) or concept.name or "")


def _with_fr_titles(
    payload: dict[str, Any],
    *,
    concept: GrammarConcept,
    fr_localizations: dict[int, GrammarConceptLocalization] | None,
) -> dict[str, Any]:
    """Give the exercise-set payload the same French titles as the concept list.

    Exercise sets are generated once and shared across learners, so the stored
    payload carries the English catalog name in `concept.title_fr` and in
    `rule_panel.title`. L'Épreuve reads both (the rule sheet's heading and the
    correction's rule line), so localize them on the way out instead of writing
    a learner's language into shared content.
    """
    localization = (fr_localizations or {}).get(concept.id)
    title_fr = _fr_concept_title(concept, fr_localizations)
    next_payload = dict(payload)
    payload_concept = next_payload.get("concept")
    if isinstance(payload_concept, dict):
        next_payload["concept"] = {
            **payload_concept,
            "title_fr": title_fr,
            "category_label_fr": str(
                (localization.category_label if localization else None) or concept.category or ""
            ),
        }
    rule_panel = next_payload.get("rule_panel")
    if isinstance(rule_panel, dict):
        next_payload["rule_panel"] = {**rule_panel, "title": title_fr}
    return next_payload


def _with_learner_instructions(payload: dict[str, Any], *, native_language: Any) -> dict[str, Any]:
    """Read every exercise instruction in the learner's own language (WP-67).

    Exercise sets are generated once and shared across learners, so an
    instruction cannot be written in one learner's language when it is stored —
    the same problem `_with_fr_titles` solves for the concept title, and the
    same answer: localize on the way out.

    Two sources, in order. An item written since WP-67 carries
    `instruction_key`, the `learner_copy` identifier that produced it. An item
    cached before it — the rows already sitting in `atelier_exercise_sets` —
    carries only the English sentence, which is looked up in the copy table's
    own English column. Anything else (a model-written instruction) is left
    exactly as it is: this function translates nothing, it only re-reads a row
    the copy table already holds.

    Nothing that is graded is touched. `expected_answer`, `correct_answer`,
    `labels` and the French prompts are data the corrector compares against, and
    moving them to a learner's language would mean marking a right answer wrong.
    """
    language = normalize_language(native_language)
    if language == DEFAULT_GLOSS_LANGUAGE:
        return payload

    def localize(node: Any) -> Any:
        if isinstance(node, list):
            return [localize(child) for child in node]
        if not isinstance(node, dict):
            return node
        next_node = {key: localize(value) for key, value in node.items()}
        instruction = next_node.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip():
            return next_node
        key = next_node.get("instruction_key")
        if isinstance(key, str) and key in LEARNER_COPY:
            next_node["instruction"] = learner_text(key, language)
        else:
            next_node["instruction"] = learner_text_for_english(instruction, language)
        return next_node

    return localize(payload)


def _with_serial_conversation(
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None,
    concept: GrammarConcept,
    fr_localizations: dict[int, GrammarConceptLocalization] | None = None,
) -> dict[str, Any]:
    if not context:
        return payload
    output_ladder = dict(payload.get("output_ladder") or {})
    conversation = dict(output_ladder.get("conversation") or {})
    items = [dict(item or {}) for item in conversation.get("items") or []]
    if not items:
        return payload
    character = context["character"]
    register = str(character.get("register") or "vous")
    items[0].update(
        {
            # The concept is quoted inside a French instruction, so quote the
            # French title -- the catalog name is an internal English label.
            # Keep the approved task's concrete situation and question. Cast
            # decoration must not replace the task after content validation.
            "prompt": items[0].get("prompt"),
            "character": character,
            "serial_context": {
                "thread_id": context["thread_id"],
                "episode_index": context["episode_index"],
                "scene_context": context["scene_context"],
                "opener": items[0].get("prompt"),
                "register": register,
            },
        }
    )
    conversation["items"] = items
    output_ladder["conversation"] = conversation
    return {**payload, "output_ladder": output_ladder}


def _atelier_library_episode(db: Session, user: User) -> dict[str, Any] | None:
    next_episode = BookLibraryService(db).next_ready_episode(user=user)
    if not next_episode:
        return None
    book, episode = next_episode
    completed = {int(value) for value in (book.completed_episode_indices or [])}
    return {
        "book_id": str(book.id),
        "episode_id": str(episode.id),
        "book_title": book.title,
        "author": book.author,
        "title": episode.title,
        "order_index": int(episode.order_index),
        "episode_index": int(episode.order_index),
        "episode_label": f"Episode {int(episode.order_index) + 1}",
        "total_episodes": int(book.total_episodes or 0),
        "est_reading_minutes": int(episode.est_reading_minutes or 1),
        "word_count": int(episode.word_count or 0),
        "cefr_level": episode.cefr_level,
        "progress": {
            "completed_episodes": len(completed),
            "completion_percentage": round((len(completed) / max(1, int(book.total_episodes or 0))) * 100),
        },
        "href": f"/notebook?mode=library&book={book.id}&episode={episode.order_index}",
    }


def _atelier_day_progress(
    db: Session,
    user: User,
    *,
    errata_due: int,
    library_episode: dict[str, Any] | None = None,
    concept_count: int = 0,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    today = now.date()
    start = datetime.combine(today, time.min, tzinfo=UTC)
    vocabulary_due = (
        db.query(func.count(UserVocabularyProgress.id))
        .filter(UserVocabularyProgress.user_id == user.id)
        .filter(vocabulary_due_filter(now))
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
    session_done = (
        db.query(AtelierSession.id)
        .filter(AtelierSession.user_id == user.id, AtelierSession.status == "completed")
        .filter(AtelierSession.completed_at >= start)
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
    # Speaking is the habit the app is named for, so the day plan has to carry it.
    # A finished voice call files exactly one `plan_completed` pilot event for an
    # audio_session, which is the honest "spoke today" signal (LearningSession
    # rows are shared with the legacy text flow and cannot be told apart).
    studio_done = (
        db.query(PilotEvent.id)
        .filter(
            PilotEvent.user_id == user.id,
            PilotEvent.event_type == "plan_completed",
            PilotEvent.entity_type == "audio_session",
            PilotEvent.occurred_at >= start,
        )
        .first()
        is not None
    )
    level = str(getattr(user, "proficiency_level", None) or "A2").upper()
    review_minutes = 4 if errata_due else 0
    vocabulary_minutes = 4 if vocabulary_due else 0
    # The session estimate is derived from the drills the session will really
    # contain, at this learner's own measured pace -- not from a level bucket.
    # A first session is one concept by construction (AtelierScheduler.
    # concept_limit), so it needs no special case here.
    session_minutes = estimate_session_minutes(db, user=user, concept_count=concept_count)
    mission_minutes = 5 if level in {"BEGINNER", "A1", "A2"} else 7
    feuilleton_minutes = 5 if level in {"BEGINNER", "A1", "A2"} else 6
    library_minutes = int((library_episode or {}).get("est_reading_minutes") or 4)
    studio_minutes = 5
    mission_suggested = today.weekday() in {0, 2, 4}
    # Written missions take Mon/Wed/Fri; the voice studio takes the days between,
    # so speaking is prescribed rather than merely available. Both stay optional
    # -- `suggested` only decides whether the day plan proposes it.
    studio_suggested = not mission_suggested
    nodes = []
    if vocabulary_due > 0:
        nodes.append(
            {
                "id": "vocabulary",
                "label": "Vocabulary",
                "estimatedMinutes": vocabulary_minutes,
                "done": False,
                "suggested": True,
            }
        )
    nodes.extend([
        {"id": "review", "label": "Repair", "estimatedMinutes": review_minutes, "done": errata_due == 0},
        {
            "id": "session",
            "label": "Session",
            "estimatedMinutes": session_minutes,
            "plannedDrills": planned_session_drills(concept_count),
            "done": session_done,
        },
        {
            "id": "mission",
            "label": "Act",
            "estimatedMinutes": mission_minutes,
            "done": mission_done,
            "suggested": mission_suggested,
        },
        {
            "id": "studio",
            "label": "Studio",
            "estimatedMinutes": studio_minutes,
            "done": studio_done,
            "suggested": studio_suggested,
        },
    ])
    if library_episode is not None:
        nodes.append(
            {
                "id": "library",
                "label": "Library",
                "estimatedMinutes": library_minutes,
                "done": False,
                "suggested": True,
            }
        )
    nodes.append({"id": "feuilleton", "label": "Feuilleton", "estimatedMinutes": feuilleton_minutes, "done": feuilleton_done})
    total_minutes = sum(int(node["estimatedMinutes"]) for node in nodes)
    done_minutes = sum(int(node["estimatedMinutes"]) for node in nodes if node.get("done"))
    return {
        "errataDue": int(errata_due),
        "vocabularyDue": int(vocabulary_due),
        "missionDone": mission_done,
        "missionSuggested": mission_suggested,
        "libraryDone": library_episode is None,
        "librarySuggested": library_episode is not None,
        "feuilletonDone": feuilleton_done,
        "studioDone": studio_done,
        "studioSuggested": studio_suggested,
        "sessionDone": session_done,
        "timeBudgetMinutes": int(
            15 if getattr(user, "daily_goal_minutes", None) is None else user.daily_goal_minutes
        ),
        "estimatedTotalMinutes": total_minutes,
        "estimatedRemainingMinutes": max(0, total_minutes - done_minutes),
        "nodes": nodes,
        "filed": mission_done and feuilleton_done and library_episode is None,
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
        return harden_demo_user_password(db, user)

    user = User(
        email=ATELIER_DEMO_EMAIL,
        hashed_password=get_unusable_password_hash(),
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
    fr_localizations: dict[int, GrammarConceptLocalization] | None = None,
) -> AtelierConceptRead:
    data = serialize_concept(
        selection.concept,
        fr_localization=(fr_localizations or {}).get(selection.concept.id),
    )
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


def _attempt_response(
    attempt: AtelierAttempt,
    *,
    minted_collectibles: list[dict[str, Any]] | None = None,
    forge: dict[str, Any] | None = None,
) -> AtelierAttemptResponse:
    correction = attempt.correction_payload or {}
    ai_review = correction.get("ai_review") if isinstance(correction, dict) else {}
    return AtelierAttemptResponse(
        attempt_id=attempt.id,
        verdict=attempt.verdict,
        score_0_4=attempt.score_0_4,
        correction=correction,
        ai_review=ai_review if isinstance(ai_review, dict) else {},
        minted_collectibles=minted_collectibles or [],
        forge=forge or {},
    )


ADAPTIVE_LOCK_CLEAN_RECOGNIZE_ITEMS = 3
ADAPTIVE_LOCK_CLEAN_TRANSFORM_ITEMS = 2


def _clean_rung_attempts(
    db: Session,
    *,
    session: AtelierSession,
    concept: GrammarConcept,
    round_name: str,
) -> list[AtelierAttempt] | None:
    """This concept's attempts on a rung, or None if any of them was not clean."""
    attempts = list(
        db.query(AtelierAttempt)
        .filter(
            AtelierAttempt.atelier_session_id == session.id,
            AtelierAttempt.concept_id == concept.id,
            AtelierAttempt.round == round_name,
        )
        .order_by(AtelierAttempt.created_at.asc(), AtelierAttempt.id.asc())
        .all()
    )
    if any(
        candidate.verdict != "correct"
        or float(candidate.score_0_4 or 0) < 4
        or (candidate.correction_payload or {}).get("errata")
        for candidate in attempts
    ):
        return None
    return attempts


def _maybe_apply_adaptive_lock(
    db: Session,
    *,
    session: AtelierSession,
    concept: GrammarConcept | None,
    attempt: AtelierAttempt,
) -> dict[str, Any] | None:
    """Retire the rungs a learner has already proved, mid-session.

    Recognition: three genuinely clean items retire the unused recognition modes.
    Transform: two clean rewrites retire the rest of the transform rung, which is
    the same evidence bar applied to production rather than recognition.

    Returns the updated lock only when it newly retires something, so the client
    can announce the skip; the lock itself is persisted on the session so a
    resumed session (`_submitted_map`) agrees with the client's ladder.
    """
    if not concept or attempt.round not in {"recognize", "transform"}:
        return None
    locks = _adaptive_locks(session)
    existing = dict(locks.get(str(concept.id)) or {})
    skipped_modes = list(existing.get("skipped_modes") or [])
    skipped_rounds = list(existing.get("skipped_rounds") or [])
    lock = dict(existing)
    retired_now = 0

    if attempt.round == "recognize" and not skipped_modes:
        clean = _clean_rung_attempts(db, session=session, concept=concept, round_name="recognize")
        if clean is not None and len(clean) >= ADAPTIVE_LOCK_CLEAN_RECOGNIZE_ITEMS:
            seen_modes = {candidate.mode for candidate in clean}
            earned = [mode for mode in ("fill", "classify", "word_bank") if mode not in seen_modes]
            if earned:
                lock["skipped_modes"] = earned
                lock["clean_recognize_items"] = len(clean)
                retired_now += len(earned) * ATELIER_ITEMS_PER_RECOGNIZE_MODE

    if attempt.round == "transform" and "transform" not in skipped_rounds:
        clean = _clean_rung_attempts(db, session=session, concept=concept, round_name="transform")
        # Nothing to retire once the learner has worked the whole rung anyway.
        if (
            clean is not None
            and ADAPTIVE_LOCK_CLEAN_TRANSFORM_ITEMS <= len(clean) < ATELIER_TRANSFORM_ITEMS
        ):
            lock["skipped_rounds"] = [*skipped_rounds, "transform"]
            lock["clean_transform_items"] = len(clean)
            retired_now += ATELIER_TRANSFORM_ITEMS - len(clean)

    if not retired_now:
        return None

    lock.update(
        {
            "concept_id": concept.id,
            "title": concept.name,
            # What this moment just retired (what the learner is told), versus the
            # concept's running total across both rungs (session accounting).
            "retired_now": retired_now,
            "retired_drills": int(existing.get("retired_drills") or 0) + retired_now,
            "earned_at": datetime.now(UTC).isoformat(),
        }
    )
    quote = dict(session.quote_payload or {})
    next_locks = dict(locks)
    next_locks[str(concept.id)] = lock
    quote["adaptive_locks"] = next_locks
    session.quote_payload = quote
    db.add(session)
    return lock


def _errata_by_concept(due_errata: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in due_errata:
        concept_id = item.get("concept_id")
        if concept_id is None:
            continue
        grouped.setdefault(int(concept_id), []).append(item)
    return grouped


def _concept_roles_payload(selections: list[ConceptSelection]) -> dict[str, str]:
    return {str(selection.concept.id): selection.role for selection in selections}


#: WP-S4: a séance set aside because the learner asked for another rule.
SESSION_PARKED = "parked"
#: A parked séance is offered back for this long, then left alone.
PARKED_RESUME_WINDOW = timedelta(hours=24)


def _session_answers_request(
    session: AtelierSession, *, preferred_id: int | None, concept_ids: list[int]
) -> bool:
    """Does the open séance already seat what this start asks for?

    A bare start resumes it. A start for a rule resumes it only when that rule
    leads it; explicit ``concept_ids`` only when they are the same list.
    """

    seated = [int(item) for item in (session.selected_concept_ids or [])]
    if concept_ids:
        return seated[: len(concept_ids[:3])] == [int(item) for item in concept_ids[:3]]
    if preferred_id:
        return bool(seated) and seated[0] == int(preferred_id)
    return True


def _park_session(db: Session, session: AtelierSession) -> None:
    session.status = SESSION_PARKED
    db.add(session)
    db.flush()


def _resumable_session(db: Session, user: User) -> AtelierSession | None:
    """A bare start first resumes a recently parked séance, then a prepared one."""

    parked = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user.id, AtelierSession.status == SESSION_PARKED)
        .order_by(AtelierSession.created_at.desc())
        .first()
    )
    if parked is not None:
        created = parked.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created is None or datetime.now(UTC) - created <= PARKED_RESUME_WINDOW:
            return parked
    return (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user.id, AtelierSession.status == "prepared")
        .order_by(AtelierSession.created_at.desc())
        .first()
    )


def _session_selections(db: Session, user: User, session: AtelierSession) -> list[ConceptSelection]:
    concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
    if not concept_ids:
        return []
    concepts = db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all()
    by_id = {concept.id: concept for concept in concepts}
    scheduler = AtelierScheduler(db)
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    stored_roles = quote.get("concept_roles") if isinstance(quote, dict) else None
    stored_roles = stored_roles if isinstance(stored_roles, dict) else {}
    selections: list[ConceptSelection] = []
    for index, concept_id in enumerate(concept_ids):
        concept = by_id.get(concept_id)
        if not concept:
            continue
        # Prefer the role recorded at session-creation time (e.g. "new" for a
        # cold-start pick); older sessions with no stored roles fall back to
        # the previous index-based fragile/contrast heuristic.
        role = stored_roles.get(str(concept_id)) or ("fragile" if index < 2 else "contrast")
        selections.append(
            ConceptSelection(
                concept=concept,
                role=role,
                progress=scheduler._progress_for(user, concept.id),
            )
        )
    return selections


def _session_concepts_in_order(db: Session, session: AtelierSession) -> list[GrammarConcept]:
    concept_ids = [int(item) for item in (session.selected_concept_ids or []) if item]
    if not concept_ids:
        return []
    concepts = db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all()
    by_id = {concept.id: concept for concept in concepts}
    return [by_id[concept_id] for concept_id in concept_ids if concept_id in by_id]


def _concept_focus_payload(
    concept: GrammarConcept,
    asset_service: AtelierAssetService,
    progress: UserGrammarProgress | None = None,
) -> dict[str, Any]:
    blueprint = asset_service.approved_blueprint_payload(concept) or {}
    label = str(
        blueprint.get("display_title")
        or blueprint.get("title")
        or concept.name
        or "Grammar focus"
    ).strip()
    payload: dict[str, Any] = {
        "id": concept.id,
        "external_id": concept.external_id,
        "label": label,
        "display_title": label,
        "name": concept.name,
        "level": concept.level,
        "category": concept.category,
        "subskill": concept.subskill,
    }
    if progress and progress.next_review:
        payload["next_review"] = progress.next_review.isoformat()
    return payload


def _recent_session_focus(
    db: Session,
    user: User,
    asset_service: AtelierAssetService,
    *,
    today_start: datetime,
) -> dict[str, Any] | None:
    session = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user.id, AtelierSession.status == "completed")
        .filter(AtelierSession.completed_at.isnot(None), AtelierSession.completed_at < today_start)
        .order_by(AtelierSession.completed_at.desc())
        .first()
    )
    if not session:
        return None

    concepts = _session_concepts_in_order(db, session)
    if not concepts:
        return None

    focus = _concept_focus_payload(concepts[0], asset_service)
    completed_at = session.completed_at or session.created_at
    return {
        "source": "last_completed_session",
        "session_id": str(session.id),
        "label": focus["label"],
        "display_title": focus["display_title"],
        "completed_at": completed_at.isoformat() if completed_at else None,
        "concepts": [_concept_focus_payload(concept, asset_service) for concept in concepts],
    }


def _next_scheduled_focus(
    db: Session,
    user: User,
    asset_service: AtelierAssetService,
    *,
    current_concept_ids: set[int],
) -> dict[str, Any] | None:
    now = datetime.now(UTC)
    query = (
        db.query(GrammarConcept, UserGrammarProgress)
        .join(UserGrammarProgress, UserGrammarProgress.concept_id == GrammarConcept.id)
        .filter(UserGrammarProgress.user_id == user.id)
        .filter(UserGrammarProgress.next_review.isnot(None), UserGrammarProgress.next_review > now)
        .filter(GrammarConcept.active.is_(True))
        .filter(GrammarConcept.external_id.isnot(None), GrammarConcept.external_id != "")
    )
    if current_concept_ids:
        query = query.filter(~GrammarConcept.id.in_(current_concept_ids))
    row = (
        query.order_by(
            UserGrammarProgress.next_review.asc(),
            GrammarConcept.difficulty_order.asc(),
            GrammarConcept.id.asc(),
        )
        .first()
    )
    if not row:
        return None

    concept, progress = row
    focus = _concept_focus_payload(concept, asset_service, progress)
    scheduled_at = progress.next_review.isoformat() if progress.next_review else None
    return {
        "source": "next_srs_review",
        "label": focus["label"],
        "display_title": focus["display_title"],
        "scheduled_at": scheduled_at,
        "concept": focus,
        "concepts": [focus],
    }


def _atelier_parcours_summary(
    db: Session,
    user: User,
    selections: list[ConceptSelection],
    asset_service: AtelierAssetService,
) -> dict[str, Any]:
    today = datetime.now(UTC).date()
    today_start = datetime.combine(today, time.min, tzinfo=UTC)
    current_concept_ids = {selection.concept.id for selection in selections}
    today_concepts = [
        _concept_focus_payload(selection.concept, asset_service, selection.progress)
        for selection in selections
    ]
    today_focus = {
        "source": "today_selection",
        "label": today_concepts[0]["label"] if today_concepts else None,
        "display_title": today_concepts[0]["display_title"] if today_concepts else None,
        "concepts": today_concepts,
    } if today_concepts else None
    return {
        "previous": _recent_session_focus(db, user, asset_service, today_start=today_start),
        "today": today_focus,
        "next": _next_scheduled_focus(
            db,
            user,
            asset_service,
            current_concept_ids=current_concept_ids,
        ),
    }


def _session_attempts(db: Session, session: AtelierSession) -> list[AtelierAttempt]:
    return list(
        db.query(AtelierAttempt)
        .filter(AtelierAttempt.atelier_session_id == session.id)
        .order_by(AtelierAttempt.created_at.asc(), AtelierAttempt.id.asc())
        .all()
    )


def _attempt_key(round_name: str, mode: str, concept_id: int | None, item_id: str | None = None) -> str:
    key_mode = mode
    key_concept: str | int = concept_id or "session"
    if round_name == "transform":
        key_mode = "transform"
    elif round_name in {"sentence", "speak", "conversation", "produce"}:
        key_mode = round_name
    if round_name == "produce":
        key_concept = "session"
    key = f"{round_name}:{key_mode}:{key_concept}"
    return f"{key}:{item_id}" if item_id else key


def _legacy_submitted_key(attempt: AtelierAttempt) -> str:
    return _attempt_key(attempt.round, attempt.mode, attempt.concept_id)


def _answer_item_ids(attempt: AtelierAttempt) -> list[str]:
    answers = (attempt.answer_payload or {}).get("answers")
    if not isinstance(answers, dict):
        return []
    return [str(item_id) for item_id, answer in answers.items() if str(item_id).strip() and answer is not None]


def _submitted_keys_for_attempt(attempt: AtelierAttempt) -> list[str]:
    legacy_key = _legacy_submitted_key(attempt)
    if attempt.round not in {"recognize", "transform"}:
        return [legacy_key]

    item_ids = _answer_item_ids(attempt)
    if not item_ids:
        return [legacy_key]

    keys = [_attempt_key(attempt.round, attempt.mode, attempt.concept_id, item_id) for item_id in item_ids]
    if len(item_ids) > 1:
        keys.append(legacy_key)
    return keys


def _submitted_key(attempt: AtelierAttempt) -> str:
    keys = _submitted_keys_for_attempt(attempt)
    legacy_key = _legacy_submitted_key(attempt)
    if legacy_key in keys and len(keys) > 1:
        return legacy_key
    return keys[0]


def _adaptive_locks(session: AtelierSession) -> dict[str, dict[str, Any]]:
    raw = (session.quote_payload or {}).get("adaptive_locks") or {}
    return raw if isinstance(raw, dict) else {}


def _submitted_map(
    attempts: list[AtelierAttempt],
    adaptive_locks: dict[str, dict[str, Any]] | None = None,
) -> dict[str, bool]:
    submitted: dict[str, bool] = {}
    for attempt in attempts:
        for key in _submitted_keys_for_attempt(attempt):
            submitted[key] = True
    for concept_id, lock in (adaptive_locks or {}).items():
        for mode in lock.get("skipped_modes") or []:
            submitted[_attempt_key("recognize", str(mode), int(concept_id))] = True
        # A retired rung counts as settled for resume and for progress, so the
        # learner is never walked back into work they earned their way out of.
        for round_name in lock.get("skipped_rounds") or []:
            submitted[_attempt_key(str(round_name), str(round_name), int(concept_id))] = True
    return submitted


def _attempt_read(attempt: AtelierAttempt) -> dict[str, Any]:
    correction = attempt.correction_payload or {}
    submitted_keys = _submitted_keys_for_attempt(attempt)
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
        "submitted_keys": submitted_keys,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }


def _payload_items(exercise_sets: list[dict[str, Any]], concept_id: int, round_name: str, mode: str) -> list[dict[str, Any]]:
    exercise_set = next((item for item in exercise_sets if item.get("concept_id") == concept_id), None)
    payload = exercise_set.get("payload") if exercise_set else {}
    if round_name == "recognize":
        return list((((payload or {}).get("recognize") or {}).get(mode) or {}).get("items") or [])
    if round_name == "transform":
        return list(((payload or {}).get("transform") or {}).get("items") or [])
    return []


def _current_position(session: AtelierSession, attempts: list[AtelierAttempt], exercise_sets: list[dict[str, Any]]) -> dict[str, Any]:
    submitted = _submitted_map(attempts, _adaptive_locks(session))
    concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
    for concept_index, concept_id in enumerate(concept_ids):
        for mode in ("fill", "classify", "word_bank"):
            legacy_key = _attempt_key("recognize", mode, concept_id)
            items = _payload_items(exercise_sets, concept_id, "recognize", mode)
            if not items and not submitted.get(legacy_key):
                return {"round": "recognize", "mode": mode, "concept_id": concept_id, "concept_index": concept_index}
            for item_index, item in enumerate(items):
                item_id = str(item.get("id") or item_index)
                if not (submitted.get(_attempt_key("recognize", mode, concept_id, item_id)) or submitted.get(legacy_key)):
                    return {
                        "round": "recognize",
                        "mode": mode,
                        "concept_id": concept_id,
                        "concept_index": concept_index,
                        "item_id": item_id,
                        "item_index": item_index,
                        "item_count": len(items),
                    }
    for concept_index, concept_id in enumerate(concept_ids):
        legacy_key = _attempt_key("transform", "transform", concept_id)
        items = _payload_items(exercise_sets, concept_id, "transform", "transform")
        if not items and not submitted.get(legacy_key):
            return {"round": "transform", "mode": "transform", "concept_id": concept_id, "concept_index": concept_index}
        for item_index, item in enumerate(items):
            item_id = str(item.get("id") or item_index)
            if not (submitted.get(_attempt_key("transform", "transform", concept_id, item_id)) or submitted.get(legacy_key)):
                return {
                    "round": "transform",
                    "mode": "transform",
                    "concept_id": concept_id,
                    "concept_index": concept_index,
                    "item_id": item_id,
                    "item_index": item_index,
                    "item_count": len(items),
                }
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(_attempt_key("sentence", "sentence", concept_id)):
            return {"round": "sentence", "mode": "sentence", "concept_id": concept_id, "concept_index": concept_index, "item_index": 0, "item_count": 1}
    if not submitted.get(_attempt_key("produce", "produce", None)):
        return {"round": "produce", "mode": "produce", "concept_id": None, "concept_index": 0}
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(_attempt_key("speak", "speak", concept_id)):
            return {"round": "speak", "mode": "speak", "concept_id": concept_id, "concept_index": concept_index, "item_index": 0, "item_count": 1}
    for concept_index, concept_id in enumerate(concept_ids):
        if not submitted.get(_attempt_key("conversation", "conversation", concept_id)):
            return {"round": "conversation", "mode": "conversation", "concept_id": concept_id, "concept_index": concept_index, "item_index": 0, "item_count": 1}
    return {"round": "complete", "mode": "complete", "concept_id": None, "concept_index": 0}


def _session_response(
    db: Session,
    user: User,
    session: AtelierSession,
    *,
    fast_path: bool = False,
    background_tasks: BackgroundTasks | None = None,
) -> AtelierSessionStartResponse:
    scheduler = AtelierScheduler(db)
    asset_service = AtelierAssetService(db)
    # WP-S3 La Forge: a fresh séance is composed by the forge (it may reseat
    # the concepts: at most one brand-new rule, today's contrast partner).
    forge_service = ForgeService(db)
    forge_service.ensure_attached(user=user, session=session)
    selections = _session_selections(db, user, session)
    due_errata = scheduler.due_errata(user)
    due_by_concept = _errata_by_concept(due_errata)
    exercise_sets: list[dict[str, Any]] = []
    target_vocabulary = session_vocabulary_context(session)
    serial_conversation = _serial_conversation_context(db, user)
    fr_localizations = fr_localizations_by_concept_id(db, (selection.concept.id for selection in selections))
    for concept_index, selection in enumerate(selections):
        try:
            exercise_set = session_exercise_set(
                db,
                user=user,
                session=session,
                concept=selection.concept,
                target_vocabulary=target_vocabulary,
                fast_path=fast_path,
                background_tasks=background_tasks,
            )
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
        payload = _with_serial_conversation(
            payload,
            context=serial_conversation,
            concept=selection.concept,
            fr_localizations=fr_localizations,
        )
        payload = _with_fr_titles(
            payload,
            concept=selection.concept,
            fr_localizations=fr_localizations,
        )
        payload = _with_learner_instructions(
            payload,
            native_language=getattr(user, "native_language", None),
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
        concepts=[
            _concept_read(selection, due_by_concept, asset_service, fr_localizations) for selection in selections
        ],
        quote=session.quote_payload or scheduler.quote_for_today(),
        exercise_sets=exercise_sets,
        attempts=[_attempt_read(attempt) for attempt in attempts],
        submitted_map=_submitted_map(attempts, _adaptive_locks(session)),
        current_position=_current_position(session, attempts, exercise_sets),
        due_errata=due_errata,
        target_vocabulary_ids=[int(item["word_id"]) for item in target_vocabulary if item.get("word_id")],
        target_vocabulary=target_vocabulary,
        recap=session.recap_payload or {},
        learning_moments={"adaptive_locks": _adaptive_locks(session)},
        forge=forge_service.view(user=user, session=session),  # WP-S3
    )


@router.get("/today", response_model=AtelierTodayResponse)
@off_event_loop
async def get_today(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierTodayResponse:
    if settings.ATELIER_BACKGROUND_PREGENERATION_ENABLED:
        has_open_session = (
            db.query(AtelierSession.id)
            .filter(
                AtelierSession.user_id == current_user.id,
                AtelierSession.status.in_(["prepared", "in_progress"]),
            )
            .first()
            is not None
        )
        if not has_open_session:
            background_tasks.add_task(pregenerate_next_atelier_session, current_user.id)
    # WP-80: an honest streak — a missed day reads 0, a banked «jour de
    # relâche» is spent and written down before anything prints the number.
    streak = settle_streak(db, current_user)
    db.commit()
    scheduler = AtelierScheduler(db)
    selections = scheduler.select_today(current_user)
    asset_service = AtelierAssetService(db)
    due_errata = scheduler.due_errata(current_user)
    due_by_concept = _errata_by_concept(due_errata)
    summary = scheduler.summary(current_user)
    summary["learning_motivation"] = str(getattr(current_user, "learning_motivation", "") or "")
    summary["speaking_comfort"] = str(getattr(current_user, "speaking_comfort", "warming_up") or "warming_up")
    summary["first_session"] = scheduler.is_first_session(current_user)
    summary["due_errata"] = len(due_errata)
    parcours = _atelier_parcours_summary(db, current_user, selections, asset_service)
    summary["parcours"] = parcours
    if parcours.get("previous"):
        summary["previous_focus"] = parcours["previous"]
    if parcours.get("today"):
        summary["today_focus"] = parcours["today"]
    if parcours.get("next"):
        summary["next_focus"] = parcours["next"]
        scheduled_at = str((parcours["next"] or {}).get("scheduled_at") or "")
        if scheduled_at.startswith((datetime.now(UTC).date() + timedelta(days=1)).isoformat()):
            summary["tomorrow_focus"] = parcours["next"]
    serial_episode = await SerialThreadService(db).today(current_user) if settings.SERIAL_WORLD_ENABLED else None
    library_episode = _atelier_library_episode(db, current_user)
    progress = _atelier_day_progress(
        db,
        current_user,
        errata_due=len(due_errata),
        library_episode=library_episode,
        concept_count=len(selections),
    )
    cefr = CEFRProgressService(db).current(current_user)
    fr_localizations = fr_localizations_by_concept_id(db, (selection.concept.id for selection in selections))
    return AtelierTodayResponse(
        concepts=[
            _concept_read(selection, due_by_concept, asset_service, fr_localizations) for selection in selections
        ],
        quote=scheduler.quote_for_today(),
        summary=summary,
        atlas=scheduler.atlas(current_user),
        due_errata=due_errata,
        progress=progress,
        cefr=cefr,
        onboarding={
            "serial_seen": bool(getattr(current_user, "serial_onboarding_seen", False)),
            "serial_edition_notifications": bool(getattr(current_user, "serial_edition_notifications", True)),
        },
        library_episode=library_episode,
        serial_episode=serial_episode,
        serial=serial_episode,
        phrase_of_day=AtelierSRSService(db).phrase_for_la_une(user=current_user),
        streak=streak.as_payload(),
    )


@router.get("/almanac", response_model=AtelierAlmanacResponse)
def get_almanac(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierAlmanacResponse:
    return AtelierAlmanacResponse(**AtelierRewardService(db).almanac(user_id=current_user.id))


@router.post("/workshop/compose", response_model=AtelierWorkshopComposeResponse, status_code=status.HTTP_201_CREATED)
def compose_workshop_plate(
    payload: AtelierWorkshopComposeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierWorkshopComposeResponse:
    try:
        result = AtelierRewardService(db).compose(user_id=current_user.id, target=payload.target)
    except AtelierWorkshopShortfall as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.payload) from exc
    return AtelierWorkshopComposeResponse(**result)


@router.post("/sessions", response_model=AtelierSessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    background_tasks: BackgroundTasks,
    payload: AtelierSessionStartRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierSessionStartResponse:
    scheduler = AtelierScheduler(db)
    scheduler.ensure_catalog()
    preferred_id = payload.preferred_concept_id if payload else None
    explicit_ids = list(payload.concept_ids or []) if payload else []

    active = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == current_user.id, AtelierSession.status == "in_progress")
        .order_by(AtelierSession.created_at.desc())
        .first()
    )
    if active and _session_answers_request(active, preferred_id=preferred_id, concept_ids=explicit_ids):
        # fast_path is a no-op once a concept's exercise set is already stored
        # (the common case); it only matters if this in-progress session was
        # flipped over from "prepared" before background pregeneration finished
        # writing every concept's exercise set, so a reload doesn't block here.
        return _session_response(db, current_user, active, fast_path=True, background_tasks=background_tasks)
    if active:
        # WP-S4: the learner asked for a different rule. The open séance is
        # parked (resumable later, never deleted) and the asked-for rule is
        # seated — an in-progress session no longer overrides the choice.
        _park_session(db, active)

    if not payload or not (payload.concept_ids or payload.preferred_concept_id or payload.preferred_vocabulary_ids):
        resumable = _resumable_session(db, current_user)
        if resumable is not None:
            resumable.status = "in_progress"
            db.add(resumable)
            db.commit()
            db.refresh(resumable)
            if settings.ATELIER_BACKGROUND_PREGENERATION_ENABLED:
                background_tasks.add_task(pregenerate_next_atelier_session, current_user.id)
            # A "prepared" row can exist before background pregeneration has
            # finished writing every concept's exercise set (it commits the
            # session row up front, then populates exercise sets one by one) --
            # without fast_path this would block on the same slow generation
            # chain HS-1 exists to avoid.
            return _session_response(db, current_user, resumable, fast_path=True, background_tasks=background_tasks)

    forge = None
    if explicit_ids:
        concepts = (
            db.query(GrammarConcept)
            .filter(GrammarConcept.id.in_(explicit_ids), GrammarConcept.active.is_(True))
            .all()
        )
        concepts_by_id = {concept.id: concept for concept in concepts}
        selections = [
            ConceptSelection(concept=concepts_by_id[concept_id], role="fragile" if index < 2 else "contrast")
            for index, concept_id in enumerate(explicit_ids[:3])
            if concept_id in concepts_by_id
        ]
    else:
        if preferred_id:
            concept = (
                db.query(GrammarConcept)
                .filter(GrammarConcept.id == preferred_id, GrammarConcept.active.is_(True))
                .first()
            )
            if not concept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notebook concept is not available")
        # WP-S4 — La Forge's one picker: the chosen rule (or today's) first,
        # then due rules and introduced contrast partners. No padding from
        # teaching order; a new rule only through the rhythm quota.
        forge = forge_plan(
            db,
            current_user,
            preferred_concept_id=preferred_id,
            budget_seconds=payload.budget_seconds if payload else None,
        )
        selections = scheduler.selections_for_plan(
            current_user, forge, limit=scheduler.concept_limit(current_user)
        )

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
        "concept_roles": _concept_roles_payload(selections),
        # WP-S3 La Forge: the Cahier's chosen rule is today's rule; an explicit
        # plan keeps every concept the learner picked.
        "forge_today_concept_id": payload.preferred_concept_id if payload else None,
        "forge_keep_concepts": bool(payload and payload.concept_ids),
    }
    if forge is not None:
        quote["forge"] = {
            **forge.as_payload(),
            "origin": (payload.origin if payload else None) or ("practice" if preferred_id else "after_day"),
            "journey_step_id": str(payload.journey_step_id) if payload and payload.journey_step_id else None,
        }
    session = AtelierSession(
        user_id=current_user.id,
        selected_concept_ids=[selection.concept.id for selection in selections],
        quote_payload=quote,
        status="in_progress",
        recap_payload={},
    )
    db.add(session)
    PilotEventService(db).record(
        "plan_started",
        user_id=current_user.id,
        entity_type="atelier_session",
        entity_id=session.id,
        payload={
            "concept_ids": list(session.selected_concept_ids or []),
            "adjusted": bool(payload and (payload.concept_ids or payload.preferred_concept_id)),
        },
    )
    if payload and (payload.concept_ids or payload.preferred_concept_id):
        PilotEventService(db).record(
            "plan_adjusted",
            user_id=current_user.id,
            entity_type="atelier_session",
            entity_id=session.id,
            payload={"concept_ids": list(session.selected_concept_ids or [])},
        )
    db.commit()
    db.refresh(session)
    response = _session_response(db, current_user, session, fast_path=True, background_tasks=background_tasks)
    if settings.ATELIER_BACKGROUND_PREGENERATION_ENABLED:
        background_tasks.add_task(pregenerate_next_atelier_session, current_user.id)
    return response


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
    started = perf_counter()
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

    retest_source: AtelierAttempt | None = None
    prompt_payload_override: dict[str, Any] | None = None
    if payload.retest_source_attempt_id:
        retest_source = _attempt_or_404(db, payload.retest_source_attempt_id, current_user)
        if retest_source.atelier_session_id != session.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The re-test belongs to a different session")
        retest = (retest_source.correction_payload or {}).get("retest") or {}
        if retest.get("status") != "queued":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This re-test is no longer available")
        if (payload.round, payload.mode, payload.concept_id) != (retest_source.round, retest_source.mode, retest_source.concept_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The re-test must keep its original exercise context")
        prompt_payload_override = dict(retest_source.prompt_payload or {})
    elif payload.round == "conversation" and concept:
        serial_context = _serial_conversation_context(db, current_user)
        if serial_context:
            exercise_set = session_exercise_set(
                db,
                user=current_user,
                session=session,
                concept=concept,
                target_vocabulary=session_vocabulary_context(session),
            )
            enriched = _with_serial_conversation(
                exercise_set.payload,
                context=serial_context,
                concept=concept,
            )
            ladder = ((enriched.get("output_ladder") or {}).get("conversation") or {})
            prompt_payload_override = {
                "round": "conversation",
                "mode": payload.mode,
                "rule_panel": enriched.get("rule_panel") or {},
                **ladder,
            }

    answer_payload = dict(payload.answer_payload or {})
    if payload.confidence:
        answer_payload["confidence"] = payload.confidence
    correction_service = AtelierCorrectionService(db)
    first_submission = existing is None
    attempt = correction_service.submit_attempt(
        session=session,
        user=current_user,
        concept=concept,
        round_name=payload.round,
        mode=payload.mode,
        exercise_id=payload.exercise_id,
        answer_payload=answer_payload,
        prompt_payload_override=prompt_payload_override,
        retest_of=retest_source.id if retest_source else None,
    )
    # WP-S1: the conversation rung's in-character reply follows the relecture
    # (AtelierCorrectionService._attach_world_reply), never this request.
    # WP-S3 La Forge: the staircase replaces the adaptive lock in a forge séance.
    forge_session = is_forge_session(session)
    adaptive_lock = (
        None if forge_session else _maybe_apply_adaptive_lock(db, session=session, concept=concept, attempt=attempt)
    )
    if adaptive_lock:
        correction = {**(attempt.correction_payload or {}), "adaptive_lock": adaptive_lock}
        attempt.correction_payload = correction
        db.add(attempt)
    if retest_source:
        source_correction = dict(retest_source.correction_payload or {})
        source_retest = dict(source_correction.get("retest") or {})
        source_retest.update({"status": "completed", "attempt_id": str(attempt.id)})
        source_correction["retest"] = source_retest
        retest_source.correction_payload = source_correction
        db.add(retest_source)
    # WP-S1 / WP-S8: the local verdict's latency, per rung. The relecture
    # amends the same row with its own latency and whether it changed the verdict.
    local_ms = round((perf_counter() - started) * 1000, 1)
    correction = dict(attempt.correction_payload or {})
    second_check_pending = AtelierCorrectionService.ai_review_from_correction(correction).get("status") == "pending"
    correction["latency"] = {**dict(correction.get("latency") or {}), "local_ms": local_ms}
    attempt.correction_payload = correction
    db.add(attempt)
    PilotEventService(db).record(
        FORGE_VERDICT_EVENT,
        user_id=current_user.id,
        entity_type="atelier_attempt",
        entity_id=attempt.id,
        payload={
            "session_id": str(session.id),
            "concept_id": attempt.concept_id,
            "rung": attempt.round,
            "mode": attempt.mode,
            "local_ms": local_ms,
            "local_verdict": attempt.verdict,
            "assessment_status": correction.get("assessment_status"),
            "second_check": "pending" if second_check_pending else "none",
            "async_llm_ms": None,
            "verdict_changed": None,
        },
    )
    db.commit()
    db.refresh(attempt)
    if correction_service.should_auto_start_ai_review(attempt):
        background_tasks.add_task(run_atelier_ai_review, attempt.id)
    if settings.ATELIER_BACKGROUND_PREGENERATION_ENABLED:
        background_tasks.add_task(pregenerate_next_atelier_session, current_user.id)
    minted = [] if retest_source else AtelierRewardService(db).mint_logo_token_for_attempt(attempt, first_submission=first_submission)
    # WP-S3 La Forge: every answered item is evidence (with the forge's caps).
    forge_view = (
        ForgeService(db).observe_attempt(user=current_user, session=session, attempt=attempt)
        if forge_session
        else {}
    )
    return _attempt_response(attempt, minted_collectibles=minted, forge=forge_view)


@router.post("/attempts/{attempt_id}/repair", response_model=AtelierAttemptResponse)
def repair_attempt(
    attempt_id: UUID,
    payload: AtelierAttemptRepairRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierAttemptResponse:
    attempt = _attempt_or_404(db, attempt_id, current_user)
    try:
        updated = AtelierCorrectionService(db).record_micro_repair(
            attempt=attempt,
            text=payload.text,
            erratum_index=payload.erratum_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _attempt_response(updated)


@router.post("/exercises/report", response_model=AtelierExerciseReportResponse, status_code=status.HTTP_201_CREATED)
def report_exercise(
    payload: AtelierExerciseReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierExerciseReportResponse:
    if not (payload.session_id or payload.concept_id or payload.exercise_set_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A session, concept, or exercise set is required to report an Atelier exercise",
        )

    session = _session_or_404(db, payload.session_id, current_user) if payload.session_id else None
    concept = db.get(GrammarConcept, payload.concept_id) if payload.concept_id is not None else None
    if payload.concept_id is not None and not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar concept not found")
    if session and concept and concept.id not in (session.selected_concept_ids or []):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Concept is not part of this session")

    exercise_set = db.get(AtelierExerciseSet, payload.exercise_set_id) if payload.exercise_set_id else None
    if payload.exercise_set_id and not exercise_set:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier exercise set not found")
    if exercise_set:
        if concept and exercise_set.concept_id != concept.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exercise set does not belong to the reported concept",
            )
        if not concept:
            concept = db.get(GrammarConcept, exercise_set.concept_id)
        if session and exercise_set.concept_id not in (session.selected_concept_ids or []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Exercise set does not belong to this session",
            )

    event = AtelierGenerationEvent(
        user_id=current_user.id,
        concept_id=concept.id if concept else None,
        atelier_session_id=session.id if session else None,
        exercise_set_id=exercise_set.id if exercise_set else None,
        generator_version=exercise_set.generator_version if exercise_set else ATELIER_GENERATOR_VERSION,
        event_type="user_report",
        source=exercise_set.source if exercise_set else "human",
        model=exercise_set.model if exercise_set else None,
        passed=False,
        payload={
            "round": payload.round,
            "mode": payload.mode,
            "exercise_id": payload.exercise_id,
            "item_id": payload.item_id,
            "reason": payload.reason.strip(),
        },
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    if exercise_set:
        AtelierExerciseQualityService(db).evaluate_and_retire(exercise_set)
        # WP-S2: a templated set's production prompt may come from a shared
        # pool set; the report then counts against that pool set too.
        forward_report_to_pool(db, exercise_set, round_name=payload.round, event=event)
    return AtelierExerciseReportResponse(ok=True, event_id=event.id)


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
    minted = AtelierRewardService(db).mint_gilt_seal_for_session(session)
    CEFRProgressService(db).recompute(current_user, source="atelier_session_complete")
    PilotEventService(db).record(
        "plan_completed",
        user_id=current_user.id,
        entity_type="atelier_session",
        entity_id=session.id,
        payload={"recap": recap},
    )
    db.commit()
    return AtelierCompleteResponse(session_id=session.id, recap=recap, minted_collectibles=minted)


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
    if payload.repaired:
        PilotEventService(db).record(
            "erratum_repair",
            user_id=current_user.id,
            entity_type="user_error",
            entity_id=error_id,
            payload={"repaired": True, "rating": payload.rating, "source": "review"},
        )
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
    PilotEventService(db).record(
        "erratum_repair",
        user_id=current_user.id,
        entity_type="user_error",
        entity_id=error_id,
        payload={"repaired": bool(result.get("repaired")), "verdict": result.get("verdict")},
    )
    db.commit()
    return AtelierErrataAttemptResponse(**result)


class TranslateRequest(BaseModel):
    text: str


@router.post("/translate")
def translate_for_learner(
    request: TranslateRequest,
    current_user: User = Depends(get_atelier_user),
) -> dict[str, str]:
    """On-demand French -> learner's-language translation for any learner-facing line.

    The target is the account's ``native_language`` (German for a German
    learner, English as the floor), never a fixed English: the help sheet
    quotes this line under the French one, and a translation the learner
    cannot read is no help at all.
    """
    text = (request.text or "").strip()
    if not text:
        return {"translation": "", "language": ""}
    from app.services.glosses import EXPLANATION_LANGUAGE_NAMES, normalize_language
    from app.services.llm_service import LLMService

    language = normalize_language(getattr(current_user, "native_language", None))
    if language == "fr" or language not in EXPLANATION_LANGUAGE_NAMES:
        language = "en"
    language_name = EXPLANATION_LANGUAGE_NAMES[language]

    try:
        result = LLMService().generate_chat_completion(
            messages=[{"role": "user", "content": text}],
            system_prompt=(
                f"Translate the user's French text into natural, concise {language_name}. "
                f"Return ONLY the {language_name} translation — no quotes, labels, or notes."
            ),
            temperature=0.0,
            max_tokens=1200,
            model=settings.ATELIER_CORRECTION_LLM_MODEL,
            reasoning_effort="minimal",
            request_timeout=20.0,
        )
        return {"translation": (result.content or "").strip(), "language": language}
    except Exception:  # pragma: no cover - translation is best-effort
        return {"translation": "", "language": language}
