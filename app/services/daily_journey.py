"""The daily journey state machine (WP-02).

This module is the **only** writer of ``daily_journeys``,
``daily_journey_steps`` and ``daily_journey_mutations``. It owns ordering,
progress, the time envelope, revisions and idempotency. It owns no domain
logic: content, planning, learning evidence, conversation, capabilities and
events all arrive through :mod:`app.services.daily_journey_adapters`.

Transaction shape
-----------------
Expensive provider work never happens inside a held row lock. Creation and
retry therefore run in two phases:

1. Claim durably — insert/refresh the journey row in ``preparing`` with a
   ``generation_claim_id`` and **commit**. A crashed worker leaves a claim that
   expires after :data:`GENERATION_CLAIM_TTL_SECONDS`; ``POST /retry`` reuses
   the same journey id to recover it.
2. Call out, then re-read the row, verify the claim still belongs to us, and
   commit the final state **together with** the mutation receipt, so a
   duplicate request can never apply credit, consume a turn or mint a reward a
   second time.

Every other mutation follows the same two-phase receipt: reserve the key
(commit), do the work, then commit {domain effects + receipt} atomically.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.atelier import AtelierSession
from app.db.models.daily_journey import (
    OCCUPYING_STATUS_VALUES,
    DailyJourney,
    DailyJourneyMutation,
    DailyJourneyStep,
)
from app.db.models.user import User
from app.db.savepoint import best_effort, run_best_effort, session_is_usable
from app.schemas.daily_journey import (
    PRACTICE_ERRATA_HREF,
    AttemptResult,
    CapabilityEvidence,
    CapabilityProgress,
    CapabilitySummary,
    HelpResult,
    JourneyAdvanceRequest,
    JourneyAttemptRequest,
    JourneyBecause,
    JourneyCorrection,
    JourneyCreateRequest,
    JourneyFinishRequest,
    JourneyHelpRequest,
    JourneyRecap,
    JourneyRetryRequest,
    JourneyRevisionRequest,
    JourneySnapshot,
    LegacyResume,
    NextFocus,
    NextTurn,
    PracticedTarget,
    RespondPrompt,
    ScenarioDescriptor,
    StoryOutcome,
    TodayEnvelope,
    practice_href_for,
)
from app.services.daily_journey_adapters import (
    AdapterUnavailable,
    JourneyAdapters,
    preview_scenario,
)
from app.services.grammar import GrammarService
from app.services.journey_capabilities import build_journey_register_line
from app.services.journey_contracts import (
    DEFAULT_DAY_SHAPE,
    FIRST_DAY_KIND,
    AppliedEvidence,
    AssistanceLevel,
    AttemptAnswer,
    ContentUnavailable,
    ControlLanguage,
    Correction,
    DayShape,
    EvidenceKind,
    HelpKind,
    InputMode,
    JourneyErrorCode,
    JourneyEventName,
    JourneyStatus,
    RecallTask,
    ResponseTask,
    ScenarioBrief,
    StepKind,
    StepStatus,
    StoryOutcomeProposal,
    TargetKind,
    TargetRef,
    TaskOutcome,
    effect_source_key,
    normalize_answer_text,
    normalize_control_language,
    strongest_assistance,
)
from app.services.journey_day_shapes import (
    DayShapeInputs,
    choose_day_shape,
    letter_offer_for,
)
from app.services.journey_errata import errata_targets_for_user
from app.services.journey_events import MIN_MEASURED_PACE_DAYS, measured_pace
from app.services.journey_latency import (
    PHASE_DRAFT,
    PHASE_RECAP,
    PHASE_RESPOND,
    has_live_prefetch,
    measure_phase,
    server_wait_ms_since_last_event,
    take_prefetched_scene,
)
from app.services.journey_learning import record_daily_practice_streak
from app.services.journey_rhythm import budget_seconds_for, candidate_limit_for
from app.services.seals import edition_no_for
from app.services.vocabulary_pace import JOURNEY_NEW_WORDS_KEY, journey_new_word_room

logger = logging.getLogger(__name__)


def _target_practice_href(target: dict | object) -> str | None:
    """WP-16 / D-0: where «Plus de pratique» opens for one practised target.

    The legacy exercise Séance is keyed by a grammar concept or by the errata
    queue. A bare vocabulary id is neither, so a vocabulary target gets no
    pointer rather than a link that would land on an unrelated drill set.
    """

    kind = target.get("kind") if isinstance(target, dict) else getattr(target, "kind", None)
    identifier = target.get("id") if isinstance(target, dict) else getattr(target, "id", None)
    kind = str(kind or "")
    if kind == str(TargetKind.GRAMMAR) and identifier:
        return practice_href_for(identifier)
    if kind == str(TargetKind.ERROR):
        return PRACTICE_ERRATA_HREF
    return None


#: WP-36 §8.4. One row per graded respond turn, carrying only what the self-repair
#: policy decided about it. Deliberately **not** one of WP-11's ten frozen journey
#: event names: this is a package's own uptake counter, not part of the journey
#: contract, and it must be addable without touching a frozen vocabulary.
SELF_REPAIR_EVENT_TYPE = "journey_self_repair"

#: A generation claim older than this is recoverable through ``POST /retry``.
GENERATION_CLAIM_TTL_SECONDS = 90
#: A mutation receipt stuck in ``processing`` longer than this is retryable.
MUTATION_PROCESSING_TTL_SECONDS = 60
PROCESSING_RETRY_AFTER_SECONDS = 2
PREPARING_RETRY_AFTER_SECONDS = 3
UNAVAILABLE_RETRY_AFTER_SECONDS = 30
MAX_GENERATION_ATTEMPTS = 3
CANDIDATE_LIMIT = 3
#: WP-78. A practice day sees more of the queue than the reply may oblige: the
#: planner still elicits at most two due targets plus one new anchor in the
#: reply, and the rest become quick items (``journey_learning`` reads a limit
#: above three as room for the practice pool).
PRACTICE_CANDIDATE_LIMIT = 8


def _planned_introduction(plan: Any) -> dict[str, Any] | None:
    """WP-L4: ``{"concept_id", "title_native"}`` of the plan's rule step, or None."""

    for step in getattr(plan, "steps", None) or []:
        if str(getattr(step, "kind", "")) == str(StepKind.RULE):
            prompt = dict(getattr(step, "public_prompt", None) or {})
            return {
                "concept_id": prompt.get("concept_id"),
                "title_native": prompt.get("title_native"),
            }
    return None


def _new_word_ids(plan: Any, candidates: list[Any]) -> list[int]:
    """WP-L6: the vocabulary ids this plan introduces — kept targets that
    were offered as new. The day's reservation in the learner's intake pool."""

    kept = set(getattr(plan, "selected_target_ids", None) or [])
    ids: list[int] = []
    for candidate in candidates:
        target = getattr(candidate, "target", None)
        if target is None or not getattr(candidate, "is_new", False):
            continue
        if str(target.kind) != str(TargetKind.VOCABULARY) or f"{target.kind}:{target.id}" not in kept:
            continue
        try:
            value = int(target.id)
        except (TypeError, ValueError):
            continue
        if value not in ids:
            ids.append(value)
    return ids


#: WP-69. The ``unavailable_reason`` a journey gets when a read finds it in
#: ``preparing`` with a dead (or no) generation claim: the worker that owned it
#: is gone, and the learner is offered a retry instead of an endless spinner.
GENERATION_INTERRUPTED_REASON = "generation_interrupted"
#: WP-69. Written into ``plan_selection["generation_fallback"]["kind"]`` when the
#: story engine could not produce the day and an authored scene was served.
#: Internal telemetry only: the learner is never told which one they got.
AUTHORED_FALLBACK_KIND = "authored"
#: How far back the scenario rotation looks. One journey per learner-local day,
#: so this is a season of history and bounds the query.
SCENARIO_HISTORY_LIMIT = 120
#: How many times a create insert may lose a concurrency race before giving up.
CREATE_RACE_ATTEMPTS = 4

_HELP_TO_ASSISTANCE: dict[HelpKind, AssistanceLevel] = {
    HelpKind.HINT: AssistanceLevel.HINT,
    HelpKind.TRANSLATION: AssistanceLevel.TRANSLATION,
    HelpKind.SOLUTION: AssistanceLevel.SOLUTION,
    HelpKind.SUGGESTED_RESPONSE: AssistanceLevel.SUGGESTED_RESPONSE,
}

_ANSWERABLE_KINDS = (StepKind.RECALL, StepKind.RESPOND)


def _utcnow() -> datetime:
    """Single clock seam so tests can freeze midnight and DST boundaries."""

    return datetime.now(UTC)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def resolve_timezone(value: str | None, fallback: str = "UTC") -> str:
    """Validate a client-supplied IANA zone. Never hardcodes a city."""

    candidate = (value or "").strip()
    if candidate:
        try:
            ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            logger.info("daily_journey: rejecting unknown timezone %r", candidate)
        else:
            return candidate
    return fallback


def _streak_snapshot_fields(db: Session, journey: DailyJourney) -> dict[str, Any]:
    """WP-80: ``streak`` and ``missed_days`` for a snapshot; never costs the day."""

    from app.services.streak import snapshot_fields

    try:
        return snapshot_fields(db, journey.user_id, journey.local_date)
    except Exception:  # pragma: no cover - defensive
        logger.exception("daily_journey: streak snapshot fields unavailable")
        return {}


def local_date_for(timezone_name: str, *, now: datetime | None = None) -> date:
    """The learner's own calendar day in their stored zone."""

    moment = now or _utcnow()
    return moment.astimezone(ZoneInfo(resolve_timezone(timezone_name))).date()


def journey_error(
    status_code: int,
    code: JourneyErrorCode,
    message: str,
    *,
    current_revision: int | None = None,
    refresh_href: str | None = None,
    retry_after_seconds: int | None = None,
) -> HTTPException:
    """Structured ``{"detail": {...}}`` body, per CONTRACT-FREEZE extension 4."""

    detail: dict[str, Any] = {"code": str(code), "message": message}
    if current_revision is not None:
        detail["current_revision"] = current_revision
    if refresh_href is not None:
        detail["refresh_href"] = refresh_href
    if retry_after_seconds is not None:
        detail["retry_after_seconds"] = retry_after_seconds
    return HTTPException(status_code=status_code, detail=detail)


def refresh_href_for(journey_id: uuid.UUID | str) -> str:
    return f"{settings.API_V1_STR}/daily-journeys/{journey_id}"


def _not_found() -> HTTPException:
    """The application's existing non-disclosing 404 convention."""

    return HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND, detail="Daily journey not found"
    )


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def journey_enabled_for(user: User) -> bool:
    """Server-authoritative capability check: flag plus explicit pilot cohort."""

    if not settings.ATELIER_DAILY_JOURNEY_ENABLED:
        return False
    raw_cohort = (settings.ATELIER_DAILY_JOURNEY_COHORT or "").strip()
    if raw_cohort == "*":
        return True
    if not raw_cohort:
        # An empty allowlist opens the journey to everyone in development so
        # tests and local harnesses need no cohort. In production that would
        # turn "shrink the pilot by blanking the list" into "enable every
        # learner", so production requires an explicit "*" (WP-18 finding).
        return settings.APP_ENV.strip().lower() != "production"
    allowed = {entry.strip().lower() for entry in raw_cohort.split(",") if entry.strip()}
    identities = {str(user.id).lower(), (user.email or "").strip().lower()}
    return bool(allowed & identities)


# ---------------------------------------------------------------------------
# Private-task (de)serialization. None of this is ever public.
# ---------------------------------------------------------------------------


def _target_to_json(target: TargetRef) -> dict[str, Any]:
    return target.as_public()


def _target_from_json(payload: dict[str, Any]) -> TargetRef:
    return TargetRef(
        kind=TargetKind(payload["kind"]),
        id=payload["id"],
        label_fr=payload.get("label_fr", ""),
        label_native=payload.get("label_native"),
        concept_title=bool(payload.get("concept_title")),
    )


def _recall_task_to_json(task: RecallTask) -> dict[str, Any]:
    return {
        "task_type": task.task_type,
        "instruction_native": task.instruction_native,
        "prompt_fr": task.prompt_fr,
        "options": [dict(option) for option in task.options],
        "target": _target_to_json(task.target),
        "optional": task.optional,
        "accepted_answers": list(task.accepted_answers),
        "correct_option_id": task.correct_option_id,
        "correct_tile_order": list(task.correct_tile_order),
        "hint_native": task.hint_native,
        "translation_native": task.translation_native,
        "solution_fr": task.solution_fr,
        "estimated_seconds": task.estimated_seconds,
    }


def _recall_task_from_json(payload: dict[str, Any]) -> RecallTask:
    return RecallTask(
        task_type=payload.get("task_type", "short_answer"),
        instruction_native=payload.get("instruction_native", ""),
        prompt_fr=payload.get("prompt_fr"),
        options=[dict(option) for option in payload.get("options", [])],
        target=_target_from_json(payload["target"]),
        optional=bool(payload.get("optional", False)),
        accepted_answers=list(payload.get("accepted_answers", [])),
        correct_option_id=payload.get("correct_option_id"),
        correct_tile_order=list(payload.get("correct_tile_order", [])),
        hint_native=payload.get("hint_native"),
        translation_native=payload.get("translation_native"),
        solution_fr=payload.get("solution_fr"),
        estimated_seconds=int(payload.get("estimated_seconds", 45)),
    )


def _response_task_to_json(task: ResponseTask) -> dict[str, Any]:
    return {
        "objective_native": task.objective_native,
        "character_id": task.character_id,
        "character_name": task.character_name,
        "opening_line_fr": task.opening_line_fr,
        "max_turns": task.max_turns,
        "repair_allowed": task.repair_allowed,
        "targets": [_target_to_json(target) for target in task.targets],
        "required_intents": list(task.required_intents),
        "optional_intents": list(task.optional_intents),
        "allowed_outcomes": list(task.allowed_outcomes),
        "rubric_native": task.rubric_native,
        "suggested_response_fr": task.suggested_response_fr,
        "hint_native": task.hint_native,
        "translation_native": task.translation_native,
        "estimated_seconds": task.estimated_seconds,
    }


def _response_task_from_json(payload: dict[str, Any]) -> ResponseTask:
    return ResponseTask(
        objective_native=payload.get("objective_native", ""),
        character_id=payload.get("character_id", ""),
        character_name=payload.get("character_name", ""),
        opening_line_fr=payload.get("opening_line_fr", ""),
        max_turns=int(payload.get("max_turns", 2)),
        repair_allowed=bool(payload.get("repair_allowed", True)),
        targets=[_target_from_json(item) for item in payload.get("targets", [])],
        required_intents=list(payload.get("required_intents", [])),
        optional_intents=list(payload.get("optional_intents", [])),
        allowed_outcomes=list(payload.get("allowed_outcomes", [])),
        rubric_native=payload.get("rubric_native", ""),
        suggested_response_fr=payload.get("suggested_response_fr"),
        hint_native=payload.get("hint_native"),
        translation_native=payload.get("translation_native"),
        estimated_seconds=int(payload.get("estimated_seconds", 120)),
    )


def _brief_to_json(brief: ScenarioBrief) -> dict[str, Any]:
    return {
        "scenario_key": str(brief.scenario_key),
        "content_version": brief.content_version,
        "title_fr": brief.title_fr,
        "objective_key": brief.objective_key,
        "objective_native": brief.objective_native,
        "level_band": brief.level_band,
        "character_id": brief.character_id,
        "character_name": brief.character_name,
        "location_id": brief.location_id,
        "location_name": brief.location_name,
        "image_url": brief.image_url,
        "setup_fr": brief.setup_fr,
        "setup_native": brief.setup_native,
        "opening_line_fr": brief.opening_line_fr,
        "response_task": _response_task_to_json(brief.response_task),
        "resolution_lines": dict(brief.resolution_lines),
        "resolution_summaries": dict(brief.resolution_summaries),
        "serial_thread_id": brief.serial_thread_id,
        "serial_episode_id": brief.serial_episode_id,
        "estimated_seconds": brief.estimated_seconds,
        "is_authored_fallback": brief.is_authored_fallback,
        "control_language": brief.control_language,
        "story_context": dict(brief.story_context),
    }


def _brief_from_json(payload: dict[str, Any]) -> ScenarioBrief:
    return ScenarioBrief(
        scenario_key=payload["scenario_key"],
        content_version=payload.get("content_version", ""),
        title_fr=payload.get("title_fr", ""),
        objective_key=payload.get("objective_key", ""),
        objective_native=payload.get("objective_native", ""),
        level_band=payload.get("level_band", "A1"),
        character_id=payload.get("character_id", ""),
        character_name=payload.get("character_name", ""),
        location_id=payload.get("location_id", ""),
        location_name=payload.get("location_name", ""),
        image_url=payload.get("image_url"),
        setup_fr=payload.get("setup_fr", ""),
        setup_native=payload.get("setup_native", ""),
        opening_line_fr=payload.get("opening_line_fr"),
        response_task=_response_task_from_json(payload.get("response_task", {})),
        story_context=dict(payload.get("story_context") or {}),
        resolution_lines=dict(payload.get("resolution_lines", {})),
        resolution_summaries=dict(payload.get("resolution_summaries", {})),
        serial_thread_id=payload.get("serial_thread_id"),
        serial_episode_id=payload.get("serial_episode_id"),
        estimated_seconds=int(payload.get("estimated_seconds", 264)),
        is_authored_fallback=bool(payload.get("is_authored_fallback", False)),
        control_language=payload.get("control_language", "en"),
    )



def _scenario_view(snapshot: Any) -> Any:
    """The stored scenario, with its place named in French (WP-50). Journeys
    planned before the world bible carried `name_fr` stored the English
    name; the fold happens here so they read right without a data fix."""
    if not isinstance(snapshot, dict):
        return snapshot
    from app.services.living_story import LOCATION_NAMES_FR

    location_id = str(snapshot.get("location_id") or "")
    french = LOCATION_NAMES_FR.get(location_id)
    if not french:
        return snapshot
    return {**snapshot, "location_name": french}


def _public_prompt_view(step: DailyJourneyStep) -> dict[str, Any]:
    """The stored public prompt, plus what the client must know about this
    deployment before it offers a mode (WP-49). Read at projection time, never
    stored: a flag flipped after the journey was planned is still honoured."""
    prompt = dict(step.public_prompt or {})
    if StepKind(step.kind) is StepKind.SCENE:
        audio = bool(settings.ATELIER_EPISODE_AUDIO_ENABLED)
        prompt["audio_available"] = audio
        # WP-66. A «jour d'écoute» planned while audio was on, projected after
        # it was switched off, is a day that cannot be listened to. Say so here
        # rather than open the learner on a player that will never play.
        if prompt.get("listen_first") and not audio:
            prompt["listen_first"] = False
    elif StepKind(step.kind) is StepKind.RECALL:
        # WP-76: the one deliberate read of `private_task` in a projection. It
        # leaves as a salted digest the client can check a pick against, never
        # as the answer (`journey_answer_key`).
        from app.services.journey_answer_key import answer_key_for

        private = step.private_task if isinstance(step.private_task, dict) else {}
        key = answer_key_for(str(step.id), private.get("recall_task"))
        if key is not None:
            prompt["answer_key"] = key
    return prompt


#: Evidence kinds that mean the learner *wrote the target*, as opposed to having
#: recognised it or been carried to it. Only these count as an objective met.
_PRODUCED_EVIDENCE = frozenset(
    {str(EvidenceKind.PRODUCED_INDEPENDENT), str(EvidenceKind.PRODUCED_SUPPORTED)}
)


def _produced_target_ids(evaluation: Any) -> list[str]:
    """``["vocabulary:41", "grammar:7"]`` — what this turn actually produced.

    Written for the WP-64 seam (a letter's optional objectives are marked met
    from real observations, never from a good overall verdict), and tolerant of
    an adapter whose evaluation carries no observations at all.
    """

    produced: list[str] = []
    for observation in getattr(evaluation, "observations", None) or []:
        target = getattr(observation, "target", None)
        if target is None:
            continue
        if str(getattr(observation, "evidence_kind", "")) not in _PRODUCED_EVIDENCE:
            continue
        produced.append(f"{target.kind}:{target.id}")
    return produced


def _mapping(value: Any) -> dict[str, Any]:
    """``value`` when it is a dict, ``{}`` otherwise. A brief is JSON from three
    packages; a key that holds the wrong type is an absent key, never a 500."""

    return value if isinstance(value, dict) else {}


def _shape_name(value: Any) -> str | None:
    """A shape name out of a string or out of ``{"shape": …}``, or ``None``."""

    if isinstance(value, dict):
        value = value.get("shape")
    text = str(value or "").strip().lower()
    return text or None


def _stored_day_shape(journey: DailyJourney) -> DayShape:
    """The shape a persisted plan was built with.

    WP-66 stores it inside the existing ``plan_selection`` JSON rather than in a
    new column: there is no migration, and a journey planned before this
    package simply has no key — which reads back as ``standard``, which is what
    it is. A shape name this build does not know (a newer deployment's plan,
    read by an older one) is also read as standard rather than refusing to load
    the learner's day.
    """

    selection = journey.plan_selection if isinstance(journey.plan_selection, dict) else {}
    try:
        return DayShape(str(selection.get("day_shape") or DEFAULT_DAY_SHAPE))
    except ValueError:
        return DEFAULT_DAY_SHAPE


def _stored_cast_intro(journey: DailyJourney) -> list[dict[str, Any]] | None:
    """WP-75: the cast introduction the first day was planned with, or ``None``."""

    first_day = _mapping((journey.plan_selection or {}).get("first_day"))
    rows = first_day.get("cast_intro")
    if not isinstance(rows, list) or not rows:
        return None
    return [dict(row) for row in rows if isinstance(row, dict)] or None


def _journey_input_mode(journey: DailyJourney) -> InputMode:
    """The mode a journey was created in: voice when its reply offered voice."""

    for step in journey.steps or []:
        if str(step.kind) == str(StepKind.RESPOND):
            modes = (step.public_prompt or {}).get("input_modes") or []
            if str(InputMode.VOICE) in [str(mode) for mode in modes]:
                return InputMode.VOICE
    return InputMode.TEXT


class _GenerationFailure(Exception):
    """Why a scene could not be turned into a playable day (WP-69).

    Carries exactly what :meth:`DailyJourneyService._mark_unavailable` needs,
    plus whether an authored scene may stand in for it. Adapter outages are
    never eligible: the authored path goes through the same adapters.
    """

    def __init__(
        self,
        reason: str,
        *,
        retry_allowed: bool = True,
        retry_after_seconds: int = UNAVAILABLE_RETRY_AFTER_SECONDS,
        fallback_eligible: bool = False,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_allowed = retry_allowed
        self.retry_after_seconds = retry_after_seconds
        self.fallback_eligible = fallback_eligible


class DailyJourneyService:
    """Transaction boundary and state machine for the Atelier V2 daily journey."""

    def __init__(self, db: Session, adapters: JourneyAdapters) -> None:
        self.db = db
        self.adapters = adapters
        #: WP-26: did *this* service instance serve the draft from a prefetched
        #: scene? ``None`` means no draft was generated on this instance at all.
        self.draft_prefetch_hit: bool | None = None

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_today(self, user: User, *, timezone_hint: str | None = None) -> TodayEnvelope:
        enabled = journey_enabled_for(user)
        control_language = normalize_control_language(user.native_language)

        journey = self._occupying_journey(user)
        if journey is not None and self._heal_interrupted(journey):
            # WP-69: a dead `preparing` journey no longer occupies the day.
            journey = self._occupying_journey(user)
        if journey is None:
            fallback_tz = resolve_timezone(timezone_hint)
            today = local_date_for(fallback_tz)
            journey = self._journey_for_date(user, today)

        timezone_name = journey.timezone if journey else resolve_timezone(timezone_hint)
        today = local_date_for(timezone_name)
        # WP-80: the client's zone is the learner's zone (it moves the streak
        # day and the push schedule), and the streak is settled on this read.
        from app.services.streak import today_fields

        streak_fields = today_fields(self.db, user, timezone_hint=timezone_hint)

        available: ScenarioDescriptor | None = None
        if enabled and journey is None:
            available = self._available_descriptor(user)

        return TodayEnvelope(
            enabled=enabled,
            control_language=control_language,
            local_date=today,
            timezone=timezone_name,
            journey=self.snapshot(journey) if journey else None,
            available=available,
            legacy_resume=self._legacy_resume(user),
            practice_href=self._practice_href(user),
            because=self._because_for(journey),
            is_warm=self._draft_is_warm(user) if enabled and journey is None else False,
            **streak_fields,
        )

    def _because_for(self, journey: DailyJourney | None) -> JourneyBecause | None:
        """WP-24's because-line, read back from the plan that produced it."""

        if journey is None:
            return None
        payload = (journey.plan_selection or {}).get("because")
        if not isinstance(payload, dict):
            return None
        try:
            return JourneyBecause.model_validate(payload)
        except Exception:  # pragma: no cover - written through the same schema
            logger.warning("daily_journey: stored because payload is unreadable")
            return None

    def _draft_is_warm(self, user: User) -> bool:
        """WP-26: is a prefetched scene waiting? A read, never a generation.

        ``GET /today`` must never pay for content (CONTRACTS §4) and this does
        not: it is one indexed lookup on the pilot ledger. False is always the
        safe answer — the client then behaves exactly as it did before.
        """

        # WP-75: the authored first day costs no generation — it is as warm as
        # a scene gets.
        if run_best_effort(
            self.db,
            "daily_journey: first-day warmth",
            lambda: self._first_day_eligible(user, None),
            default=False,
            log=logger,
        ):
            return True
        return run_best_effort(
            self.db,
            "daily_journey: prefetch warmth lookup",
            lambda: bool(has_live_prefetch(self.db, user)),
            default=False,
            log=logger,
        )

    def get_journey(self, user: User, journey_id: uuid.UUID) -> JourneySnapshot:
        journey = self._journey_or_404(user, journey_id)
        self._heal_interrupted(journey)
        # WP-87: a story lane whose worker died gets today's authored ending (free).
        from app.services.story_lanes import heal_stale_lane

        heal_stale_lane(self.db, user, journey)
        return self.snapshot(journey)

    def _heal_interrupted(self, journey: DailyJourney) -> bool:
        """WP-69 (L6): a `preparing` journey whose claim is dead becomes retryable.

        The worker that claimed the generation is gone (crashed, killed, or a
        request that died on an aborted transaction), so nothing will ever move
        the journey out of `preparing` and the learner watches «Deine Szene wird
        gerade vorbereitet» forever. A read cannot generate — `GET` never pays
        for content (CONTRACTS §4) — so it does the one safe thing: it moves the
        journey to `unavailable` with a retry offered at once. `POST /retry` then
        regenerates under a fresh claim.

        Compare-and-set on the revision *and* the claim the read observed, so a
        worker that reclaimed the journey a moment ago is never overwritten, and
        two concurrent reads heal it once. Returns whether this call healed it.
        """

        if JourneyStatus(journey.status) is not JourneyStatus.PREPARING:
            return False
        if self._claim_is_live(journey):
            return False
        observed_claim = journey.generation_claim_id
        claim_matches = (
            DailyJourney.generation_claim_id.is_(None)
            if observed_claim is None
            else DailyJourney.generation_claim_id == observed_claim
        )
        try:
            result = self.db.execute(
                update(DailyJourney)
                .where(
                    DailyJourney.id == journey.id,
                    DailyJourney.status == str(JourneyStatus.PREPARING),
                    DailyJourney.revision == journey.revision,
                    claim_matches,
                )
                .values(
                    status=str(JourneyStatus.UNAVAILABLE),
                    unavailable_reason=GENERATION_INTERRUPTED_REASON,
                    unavailable_retry_allowed=True,
                    unavailable_retry_after_seconds=0,
                    generation_claim_id=None,
                    generation_claimed_at=None,
                    revision=journey.revision + 1,
                )
                .execution_options(synchronize_session=False)
            )
            healed = result.rowcount == 1
            self.db.commit()
        except Exception:  # pragma: no cover - a read must never 500 on a repair
            logger.exception("daily_journey: could not heal an interrupted journey")
            self._rollback_quietly()
            return False
        self.db.refresh(journey)
        if healed:
            logger.warning(
                "daily_journey: journey %s was stuck preparing with a dead claim; now retryable",
                journey.id,
            )
        return healed

    def get_capability_progress(self, user: User) -> CapabilityProgress:
        control_language: ControlLanguage = normalize_control_language(
            user.native_language
        )
        try:
            view = self.adapters.capabilities.build_capability_summary(
                self.db, user=user, control_language=control_language
            )
        except AdapterUnavailable as exc:
            raise self._adapter_unavailable_error(exc) from exc
        return CapabilityProgress(
            rubric_version=view.rubric_version,
            capabilities=[
                CapabilitySummary(
                    capability_key=summary.capability_key,
                    title_native=summary.title_native,
                    state=summary.state,
                    modalities=list(summary.modalities),
                    latest_qualifying_on=summary.latest_qualifying_on,
                    evidence=[
                        CapabilityEvidence(
                            capability_key=item.capability_key,
                            state=item.state,
                            modality=item.modality,
                            observed_on=item.observed_on,
                            context_native=item.context_native,
                        )
                        for item in summary.evidence
                    ],
                )
                for summary in view.capabilities
            ],
        )

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_journey(
        self, user: User, payload: JourneyCreateRequest
    ) -> tuple[JourneySnapshot, int]:
        """WP-26: the draft the learner waits on, measured end to end."""

        with measure_phase(self.db, user=user, phase=PHASE_DRAFT) as timing:
            snapshot, status_code = self._create_journey(user, payload)
            timing.prefetch_hit = self.draft_prefetch_hit
            timing.journey_id = snapshot.id
            return snapshot, status_code

    def _create_journey(
        self, user: User, payload: JourneyCreateRequest
    ) -> tuple[JourneySnapshot, int]:
        if not journey_enabled_for(user):
            raise journey_error(
                http_status.HTTP_403_FORBIDDEN,
                JourneyErrorCode.JOURNEY_DISABLED,
                "The daily journey is not enabled for this account.",
            )

        timezone_name = resolve_timezone(payload.timezone)
        receipt, replay = self._begin_mutation(
            user,
            scope="create",
            mutation_id=payload.mutation_id,
            digest=_digest(
                {
                    "timezone": timezone_name,
                    # WP-L6: the server's budget, not the client's.
                    "budget_seconds": budget_seconds_for(user),
                    "preferred_input_mode": str(payload.preferred_input_mode),
                }
            ),
        )
        if replay is not None:
            return self._replay(JourneySnapshot, replay)

        try:
            journey, status_code = self._create_or_resume(user, payload, timezone_name)
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise

        snapshot = self.snapshot(journey)
        self._settle_receipt(receipt, journey, status_code, snapshot)
        return snapshot, status_code

    def retry_journey(
        self, user: User, journey_id: uuid.UUID, payload: JourneyRetryRequest
    ) -> tuple[JourneySnapshot, int]:
        """A retry is a draft the learner is still waiting on: measured too."""

        with measure_phase(
            self.db, user=user, phase=PHASE_DRAFT, journey_id=journey_id
        ) as timing:
            snapshot, status_code = self._retry_journey(user, journey_id, payload)
            timing.prefetch_hit = self.draft_prefetch_hit
            return snapshot, status_code

    def _retry_journey(
        self, user: User, journey_id: uuid.UUID, payload: JourneyRetryRequest
    ) -> tuple[JourneySnapshot, int]:
        journey = self._journey_or_404(user, journey_id)
        if not journey_enabled_for(user):
            # Draining a rollback keeps read/resume/finish, not fresh generation.
            raise journey_error(
                http_status.HTTP_403_FORBIDDEN,
                JourneyErrorCode.JOURNEY_DISABLED,
                "The daily journey is not enabled for this account.",
            )

        receipt, replay = self._begin_mutation(
            user,
            scope="retry",
            mutation_id=payload.mutation_id,
            digest=_digest({"journey_id": str(journey_id)}),
            journey=journey,
        )
        if replay is not None:
            return self._replay(JourneySnapshot, replay)

        try:
            journey, status_code = self._retry_generation(user, journey)
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise

        snapshot = self.snapshot(journey)
        self._settle_receipt(receipt, journey, status_code, snapshot)
        return snapshot, status_code

    def _settle_receipt(
        self,
        receipt: DailyJourneyMutation,
        journey: DailyJourney,
        status_code: int,
        snapshot: JourneySnapshot,
    ) -> None:
        """Commit a create/retry receipt — unless the answer was "still preparing".

        WP-69: a 202 says *somebody else is generating, look again*. It has no
        effect to protect, and committing it as the receipt meant the client's
        next tap with the same key replayed "preparing" forever — even after
        that other worker had died. The key is released instead, so the same
        request asked again is answered again.
        """

        if status_code == http_status.HTTP_202_ACCEPTED:
            self._release_mutation(receipt)
            self.db.commit()
            return
        self._commit_mutation(receipt, journey, status_code, snapshot)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def use_help(
        self, user: User, journey_id: uuid.UUID, step_id: uuid.UUID, payload: JourneyHelpRequest
    ) -> HelpResult:
        journey = self._journey_or_404(user, journey_id)
        receipt, replay = self._begin_mutation(
            user,
            scope="help",
            mutation_id=payload.mutation_id,
            digest=_digest({"step_id": str(step_id), "help_kind": str(payload.help_kind)}),
            journey=journey,
            expected_revision=payload.expected_revision,
        )
        if replay is not None:
            return self._replay(HelpResult, replay)[0]

        try:
            self._require_revision(journey, payload.expected_revision)
            self._require_active(journey)
            step = self._current_step_or_conflict(journey, step_id)
            if StepKind(step.kind) not in _ANSWERABLE_KINDS:
                raise journey_error(
                    http_status.HTTP_409_CONFLICT,
                    JourneyErrorCode.STEP_NOT_ACTIVE,
                    "That step does not offer help.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(journey.id),
                )
            content_fr, content_native = self._help_content(step, payload.help_kind)
            # Assistance is recorded BEFORE the content is handed over.
            level = _HELP_TO_ASSISTANCE[payload.help_kind]
            self._claim_revision(journey, payload.expected_revision)
            step.assistance_used = [*list(step.assistance_used or []), str(level)]
            self.db.flush()
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise
        except AdapterUnavailable as exc:
            self.db.rollback()
            self._release_mutation(receipt)
            self.db.commit()
            raise self._adapter_unavailable_error(exc) from exc

        result = HelpResult(
            step_id=str(step.id),
            help_kind=payload.help_kind,
            content_fr=content_fr,
            content_native=content_native,
            assistance_level=self._step_assistance(step),
            journey=self.snapshot(journey),
        )
        self._commit_mutation(receipt, journey, http_status.HTTP_200_OK, result)
        self._emit(
            JourneyEventName.HELP_USED,
            user,
            journey,
            {"step_id": str(step.id), "help_kind": str(payload.help_kind)},
        )
        return result

    def submit_attempt(
        self,
        user: User,
        journey_id: uuid.UUID,
        step_id: uuid.UUID,
        payload: JourneyAttemptRequest,
    ) -> AttemptResult:
        """WP-26: the reply turn, measured. It still pays a provider call."""

        try:
            with measure_phase(
                self.db, user=user, phase=PHASE_RESPOND, journey_id=journey_id
            ):
                result = self._submit_attempt(user, journey_id, step_id, payload)
        except BaseException:
            from app.services.story_lanes import discard_pending

            discard_pending(self.db)
            raise
        # WP-87: the story lane starts only once the reply's transaction is durable,
        # and outside the measured respond time — the learner is not waiting on it.
        from app.services.story_lanes import dispatch_pending

        dispatch_pending(self.db)
        return result

    def _submit_attempt(
        self,
        user: User,
        journey_id: uuid.UUID,
        step_id: uuid.UUID,
        payload: JourneyAttemptRequest,
    ) -> AttemptResult:
        journey = self._journey_or_404(user, journey_id)
        answer = self._normalize_attempt(user, payload)

        receipt, replay = self._begin_mutation(
            user,
            scope="attempt",
            mutation_id=payload.mutation_id,
            digest=_digest(
                {
                    "step_id": str(step_id),
                    "input": payload.input.model_dump(mode="json"),
                }
            ),
            journey=journey,
            expected_revision=payload.expected_revision,
        )
        if replay is not None:
            return self._replay(AttemptResult, replay)[0]

        try:
            self._require_revision(journey, payload.expected_revision)
            self._require_active(journey)
            step = self._current_step_or_conflict(journey, step_id)
            kind = StepKind(step.kind)
            if kind not in _ANSWERABLE_KINDS:
                raise journey_error(
                    http_status.HTTP_409_CONFLICT,
                    JourneyErrorCode.STEP_NOT_ACTIVE,
                    "That step does not take an answer.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(journey.id),
                )
            if kind is StepKind.RECALL:
                result = self._attempt_recall(
                    user, journey, step, answer, payload.expected_revision
                )
            else:
                result = self._attempt_respond(
                    user, journey, step, answer, payload.expected_revision
                )
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise
        except AdapterUnavailable as exc:
            # A broken learning/conversation module must never answer 200 while
            # writing no canonical credit. Fail, and keep the key reusable.
            self.db.rollback()
            self._release_mutation(receipt)
            self.db.commit()
            raise self._adapter_unavailable_error(exc) from exc
        except Exception:
            # Provider/infrastructure failure is not a learner mistake: the key
            # stays reusable so the client can retry the identical request.
            self.db.rollback()
            self._release_mutation(receipt)
            self.db.commit()
            raise

        if result.pending:
            # Retryable grading: the key stays reusable, nothing was applied.
            self._release_mutation(receipt)
            self.db.commit()
            return result

        self._commit_mutation(receipt, journey, http_status.HTTP_200_OK, result)
        return result

    def advance(
        self, user: User, journey_id: uuid.UUID, payload: JourneyAdvanceRequest
    ) -> JourneySnapshot:
        journey = self._journey_or_404(user, journey_id)
        receipt, replay = self._begin_mutation(
            user,
            scope="advance",
            mutation_id=payload.mutation_id,
            digest=_digest({"current_step_id": payload.current_step_id}),
            journey=journey,
            expected_revision=payload.expected_revision,
        )
        if replay is not None:
            return self._replay(JourneySnapshot, replay)[0]

        try:
            self._require_revision(journey, payload.expected_revision)
            self._require_active(journey)
            step = self._current_step_or_conflict(
                journey,
                self._parse_uuid(payload.current_step_id),
                require_active=False,
            )
            if (
                StepKind(step.kind) in _ANSWERABLE_KINDS
                and StepStatus(step.status) is not StepStatus.COMPLETED
            ):
                raise journey_error(
                    http_status.HTTP_409_CONFLICT,
                    JourneyErrorCode.STEP_NOT_ACTIVE,
                    "Answer this step before moving on.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(journey.id),
                )
            self._claim_revision(journey, payload.expected_revision)
            if StepStatus(step.status) not in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                step.status = str(StepStatus.COMPLETED)
                step.completed_at = _utcnow()
                if StepKind(step.kind) is StepKind.RULE:
                    self._mark_rule_read(user, step)
            self._activate_next_step(journey, after_ordinal=step.ordinal)
            self.db.flush()
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise

        snapshot = self.snapshot(journey)
        self._commit_mutation(receipt, journey, http_status.HTTP_200_OK, snapshot)
        self._emit(
            JourneyEventName.STEP_COMPLETED,
            user,
            journey,
            {
                "step_id": str(step.id),
                "step_kind": str(step.kind),
                "ordinal": step.ordinal,
                "estimated_seconds": step.estimated_seconds,
                # WP-76: the graded answers of this step were server time, not
                # learner time. WP-11 subtracts what the closing event declares.
                "provider_wait_ms": server_wait_ms_since_last_event(
                    self.db, journey_id=journey.id
                ),
            },
        )
        # WP-76: the event is added after the mutation's commit, and the request
        # session (autoflush off) closes without another one — so it was dropped
        # and WP-11 never saw a step boundary. Telemetry only; never fails the step.
        try:
            self.db.commit()
        except Exception:  # pragma: no cover - telemetry must never break a flow
            logger.exception("daily_journey: step_completed event not persisted")
            self.db.rollback()
        return snapshot

    def _mark_rule_read(self, user: User, step: DailyJourneyStep) -> None:
        """WP-L4: the Règle was read — the unit is introduced (visible to WP-L7)."""

        concept_id = dict(step.private_task or {}).get("concept_id")
        if concept_id is None:
            return
        from app.services.concept_life import mark_introduced

        run_best_effort(
            self.db,
            "daily_journey: mark concept introduced",
            lambda: mark_introduced(self.db, user=user, concept_id=int(concept_id), now=_utcnow()),
            default=None,
            log=logger,
        )

    def pause(
        self, user: User, journey_id: uuid.UUID, payload: JourneyRevisionRequest
    ) -> JourneySnapshot:
        journey = self._journey_or_404(user, journey_id)
        receipt, replay = self._begin_mutation(
            user,
            scope="pause",
            mutation_id=payload.mutation_id,
            digest=_digest({"journey_id": str(journey_id)}),
            journey=journey,
            expected_revision=payload.expected_revision,
        )
        if replay is not None:
            return self._replay(JourneySnapshot, replay)[0]

        try:
            self._require_revision(journey, payload.expected_revision)
            self._require_active(journey)
            self._claim_revision(journey, payload.expected_revision)
            journey.status = str(JourneyStatus.PAUSED)
            self.db.flush()
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise

        snapshot = self.snapshot(journey)
        self._commit_mutation(receipt, journey, http_status.HTTP_200_OK, snapshot)
        self._emit(JourneyEventName.PAUSED, user, journey, {})
        return snapshot

    def resume(
        self, user: User, journey_id: uuid.UUID, payload: JourneyRevisionRequest
    ) -> JourneySnapshot:
        journey = self._journey_or_404(user, journey_id)
        receipt, replay = self._begin_mutation(
            user,
            scope="resume",
            mutation_id=payload.mutation_id,
            digest=_digest({"journey_id": str(journey_id)}),
            journey=journey,
            expected_revision=payload.expected_revision,
        )
        if replay is not None:
            return self._replay(JourneySnapshot, replay)[0]

        try:
            self._require_revision(journey, payload.expected_revision)
            current = JourneyStatus(journey.status)
            if current is JourneyStatus.PAUSED:
                self._claim_revision(journey, payload.expected_revision)
                journey.status = str(JourneyStatus.ACTIVE)
                self.db.flush()
            elif current is not JourneyStatus.ACTIVE:
                # Terminal and unavailable journeys are read-only here.
                raise journey_error(
                    http_status.HTTP_409_CONFLICT,
                    JourneyErrorCode.JOURNEY_NOT_ACTIVE,
                    "This journey cannot be resumed.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(journey.id),
                )
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise

        snapshot = self.snapshot(journey)
        self._commit_mutation(receipt, journey, http_status.HTTP_200_OK, snapshot)
        return snapshot

    def finish(
        self, user: User, journey_id: uuid.UUID, payload: JourneyFinishRequest
    ) -> JourneySnapshot:
        """WP-26: the recap, measured. It is assembled, never generated."""

        with measure_phase(
            self.db, user=user, phase=PHASE_RECAP, journey_id=journey_id
        ):
            return self._finish(user, journey_id, payload)

    def _finish(
        self, user: User, journey_id: uuid.UUID, payload: JourneyFinishRequest
    ) -> JourneySnapshot:
        journey = self._journey_or_404(user, journey_id)
        receipt, replay = self._begin_mutation(
            user,
            scope="finish",
            mutation_id=payload.mutation_id,
            digest=_digest({"finish_kind": payload.finish_kind}),
            journey=journey,
            expected_revision=payload.expected_revision,
        )
        if replay is not None:
            return self._replay(JourneySnapshot, replay)[0]

        try:
            self._require_revision(journey, payload.expected_revision)
            current = JourneyStatus(journey.status)
            if current not in (JourneyStatus.ACTIVE, JourneyStatus.PAUSED):
                raise journey_error(
                    http_status.HTTP_409_CONFLICT,
                    JourneyErrorCode.JOURNEY_NOT_ACTIVE,
                    "This journey is already finished.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(journey.id),
                )
            if payload.finish_kind == "complete":
                unresolved = [
                    step
                    for step in journey.steps
                    if not step.optional
                    and StepStatus(step.status)
                    not in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                ]
                if unresolved:
                    raise journey_error(
                        http_status.HTTP_409_CONFLICT,
                        JourneyErrorCode.STEP_NOT_ACTIVE,
                        "Finish the remaining steps before completing.",
                        current_revision=journey.revision,
                        refresh_href=refresh_href_for(journey.id),
                    )
            # A journey that ends without a derived consequence must not leave
            # the planner's optimistic ending on screen.
            self._settle_resolution_if_unsettled(user, journey)
            recap = self._build_recap(user, journey, payload.finish_kind)
            self._claim_revision(journey, payload.expected_revision)
            for step in journey.steps:
                if StepStatus(step.status) not in (
                    StepStatus.COMPLETED,
                    StepStatus.SKIPPED,
                ):
                    step.status = str(StepStatus.SKIPPED)
            journey.status = str(
                JourneyStatus.COMPLETED
                if payload.finish_kind == "complete"
                else JourneyStatus.ENDED_EARLY
            )
            journey.completed_at = _utcnow()
            journey.current_step_id = None
            journey.recap_snapshot = recap.model_dump(mode="json")
            # WP-16 / decision D-0: the journey IS the daily Séance, so it is
            # what moves the practice streak. The helper is the same rule the
            # legacy loop applies and is a no-op once the day is marked, so a
            # learner who finishes the journey and then drills in
            # «Plus de pratique» gets one increment, not two.
            record_daily_practice_streak(
                self.db, user, on_date=local_date_for(journey.timezone)
            )
            self._close_learning_session(journey, payload.finish_kind)
            self.db.flush()
        except HTTPException as exc:
            self._record_error(receipt, exc)
            raise
        except AdapterUnavailable as exc:
            self.db.rollback()
            self._release_mutation(receipt)
            self.db.commit()
            raise self._adapter_unavailable_error(exc) from exc

        snapshot = self.snapshot(journey)
        self._commit_mutation(receipt, journey, http_status.HTTP_200_OK, snapshot)
        self._emit(
            JourneyEventName.COMPLETED
            if payload.finish_kind == "complete"
            else JourneyEventName.ENDED_EARLY,
            user,
            journey,
            {"finish_kind": payload.finish_kind},
        )
        if payload.finish_kind == "complete":
            self._warm_next_day(user, journey)
        return snapshot

    def _close_learning_session(self, journey: DailyJourney, finish_kind: str) -> None:
        """Close the journey's canonical LearningSession on a real completion.

        Ending early leaves it ``in_progress`` on purpose: ``AchievementService``
        counts completed learning sessions, and a partial stop must not earn
        completion credit.
        """

        if finish_kind != "complete" or journey.learning_session_id is None:
            return
        from app.db.models.session import LearningSession

        session = self.db.get(LearningSession, journey.learning_session_id)
        if session is None or session.status == "completed":
            return
        session.status = "completed"
        session.completed_at = _utcnow()

    # ------------------------------------------------------------------
    # Snapshot projection — the only public serializer
    # ------------------------------------------------------------------

    def snapshot(self, journey: DailyJourney) -> JourneySnapshot:
        """Build the public snapshot. Reads ``public_prompt`` only, never
        ``private_task``, so evaluator material cannot leak by construction."""

        steps = [
            {
                "id": str(step.id),
                "ordinal": step.ordinal,
                "kind": step.kind,
                "status": step.status,
                "estimated_seconds": step.estimated_seconds,
                "assistance_used": list(step.assistance_used or []),
                "prompt": _public_prompt_view(step),
            }
            for step in sorted(journey.steps, key=lambda item: item.ordinal)
        ]
        return JourneySnapshot.model_validate(
            {
                "id": str(journey.id),
                "contract_version": journey.contract_version,
                "revision": journey.revision,
                "status": journey.status,
                "local_date": journey.local_date,
                "timezone": journey.timezone,
                "budget_seconds": journey.budget_seconds,
                "estimated_active_seconds": journey.estimated_active_seconds,
                "current_step_id": (
                    str(journey.current_step_id) if journey.current_step_id else None
                ),
                "scenario": _scenario_view(journey.scenario_snapshot),
                "steps": steps,
                "recap": journey.recap_snapshot,
                "retry": self._retry_hint(journey),
                # WP-66: read from the persisted plan, never recomputed. The
                # claim is about the day the learner actually has.
                "day_shape": str(_stored_day_shape(journey)),
                # WP-75: only the first day carries it; every other day, null.
                "cast_intro": _stored_cast_intro(journey),
                # WP-80: the streak and the absence, read, never written here.
                **_streak_snapshot_fields(self.db, journey),
                # WP-D4: the edition, once, so Home, the recap and the seal
                # collection print the same Nº and press the same seal.
                "edition_no": edition_no_for(self.db, journey),
            }
        )

    # ------------------------------------------------------------------
    # Internals — lookups and guards
    # ------------------------------------------------------------------

    def _journey_or_404(self, user: User, journey_id: uuid.UUID) -> DailyJourney:
        journey = self.db.get(DailyJourney, journey_id)
        if journey is None or journey.user_id != user.id:
            raise _not_found()
        return journey

    def _occupying_journey(self, user: User) -> DailyJourney | None:
        """Yesterday's unfinished journey takes precedence over a new one."""

        stmt = (
            select(DailyJourney)
            .where(
                DailyJourney.user_id == user.id,
                DailyJourney.status.in_(OCCUPYING_STATUS_VALUES),
            )
            .order_by(DailyJourney.local_date.asc(), DailyJourney.created_at.asc())
        )
        return self.db.execute(stmt).scalars().first()

    def _journey_for_date(self, user: User, day: date) -> DailyJourney | None:
        stmt = select(DailyJourney).where(
            DailyJourney.user_id == user.id, DailyJourney.local_date == day
        )
        return self.db.execute(stmt).scalars().first()

    def _lock_user_row(self, user: User) -> None:
        """Serialize concurrent creates on PostgreSQL.

        SQLite has no row locks; there the ``(user_id, local_date)`` unique
        constraint plus the partial unique index do the same job, and the create
        path resolves the loser of the race by re-reading the winner's row.
        """

        try:
            dialect = self.db.get_bind().dialect.name
        except Exception:  # pragma: no cover - unbound session in a unit test
            return
        if dialect != "postgresql":
            return
        self.db.execute(
            select(User.id).where(User.id == user.id).with_for_update()
        ).first()

    def _require_revision(self, journey: DailyJourney, expected_revision: int) -> None:
        if expected_revision != journey.revision:
            self._emit_resume_conflict(
                journey, "version_conflict", expected_revision=expected_revision
            )
            raise journey_error(
                http_status.HTTP_409_CONFLICT,
                JourneyErrorCode.VERSION_CONFLICT,
                "This journey moved on. Refresh to continue.",
                current_revision=journey.revision,
                refresh_href=refresh_href_for(journey.id),
            )

    def _claim_revision(self, journey: DailyJourney, expected_revision: int) -> None:
        """Atomically move ``expected_revision`` to ``expected_revision + 1``.

        This is the real concurrency guard, not the earlier fail-fast read: two
        racing mutations that both *read* the same revision cannot both win,
        because only one conditional UPDATE can match the row. It is issued at
        commit time — after any provider call — so no lock is held across a
        model round trip.
        """

        result = self.db.execute(
            update(DailyJourney)
            .where(
                DailyJourney.id == journey.id,
                DailyJourney.revision == expected_revision,
            )
            .values(revision=expected_revision + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.db.rollback()
            fresh = self.db.get(DailyJourney, journey.id)
            raise journey_error(
                http_status.HTTP_409_CONFLICT,
                JourneyErrorCode.VERSION_CONFLICT,
                "This journey moved on. Refresh to continue.",
                current_revision=fresh.revision if fresh else expected_revision,
                refresh_href=refresh_href_for(journey.id),
            )
        self.db.expire(journey, ["revision"])

    def _require_active(self, journey: DailyJourney) -> None:
        if JourneyStatus(journey.status) is not JourneyStatus.ACTIVE:
            raise journey_error(
                http_status.HTTP_409_CONFLICT,
                JourneyErrorCode.JOURNEY_NOT_ACTIVE,
                "This journey is not active.",
                current_revision=journey.revision,
                refresh_href=refresh_href_for(journey.id),
            )

    def _current_step_or_conflict(
        self,
        journey: DailyJourney,
        step_id: uuid.UUID,
        *,
        require_active: bool = True,
    ) -> DailyJourneyStep:
        """Ownership first (404), ordering second (409).

        ``require_active`` is ``True`` for help and attempts — you cannot answer
        a step twice — and ``False`` for ``advance``, which acknowledges the
        current step precisely when it has just been completed.
        """

        step = self.db.get(DailyJourneyStep, step_id)
        if step is None or step.journey_id != journey.id:
            raise _not_found()
        out_of_order = journey.current_step_id != step.id or (
            require_active and StepStatus(step.status) is not StepStatus.ACTIVE
        )
        if out_of_order:
            self._emit_resume_conflict(journey, "step_not_active")
            raise journey_error(
                http_status.HTTP_409_CONFLICT,
                JourneyErrorCode.STEP_NOT_ACTIVE,
                "That step is not the current one.",
                current_revision=journey.revision,
                refresh_href=refresh_href_for(journey.id),
            )
        return step

    @staticmethod
    def _parse_uuid(value: str) -> uuid.UUID:
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError, TypeError) as exc:
            raise _not_found() from exc

    def _activate_next_step(self, journey: DailyJourney, *, after_ordinal: int) -> None:
        for candidate in sorted(journey.steps, key=lambda item: item.ordinal):
            if candidate.ordinal <= after_ordinal:
                continue
            if StepStatus(candidate.status) is StepStatus.PENDING:
                candidate.status = str(StepStatus.ACTIVE)
                # WP-L9: each step records when it started.
                candidate.started_at = _utcnow()
                journey.current_step_id = candidate.id
                return
        journey.current_step_id = None

    def _retry_hint(self, journey: DailyJourney) -> dict[str, Any] | None:
        status_value = JourneyStatus(journey.status)
        if status_value is JourneyStatus.PREPARING:
            return {"allowed": True, "after_seconds": PREPARING_RETRY_AFTER_SECONDS}
        if status_value is JourneyStatus.UNAVAILABLE:
            return {
                "allowed": bool(journey.unavailable_retry_allowed)
                and (
                    journey.generation_attempts < MAX_GENERATION_ATTEMPTS
                    or self._authored_rescue_possible(journey)
                ),
                "after_seconds": journey.unavailable_retry_after_seconds,
            }
        return None

    def _step_assistance(self, step: DailyJourneyStep) -> AssistanceLevel:
        levels = [AssistanceLevel(value) for value in (step.assistance_used or [])]
        return strongest_assistance(levels)

    def _practice_href(self, user: User) -> str:
        """WP-16 / D-0: where «Plus de pratique» opens.

        The legacy exercise Séance is the drill loop now, and a drill loop is
        entered by concept, never by "today". The concept is the learner's own
        most urgent due grammar concept — the same queue the legacy loop would
        have picked from — so the href seats what the scheduler already thinks
        is fragile. With an empty queue the bare practice entry is returned and
        the loop composes its own set, exactly as it does today.
        """

        with best_effort(
            self.db, "daily_journey: due-concept lookup for practice_href", log=logger
        ) as lookup:
            due = GrammarService(self.db).get_due_concepts(user=user, limit=1)
        if lookup.failed:
            return practice_href_for(None)
        if not due:
            return practice_href_for(None)
        # `get_due_concepts` yields (concept, progress) pairs.
        first = due[0]
        concept = first[0] if isinstance(first, tuple) else first
        return practice_href_for(getattr(concept, "id", None))

    def _legacy_resume(self, user: User) -> LegacyResume | None:
        stmt = (
            select(AtelierSession)
            .where(
                AtelierSession.user_id == user.id,
                AtelierSession.status == "in_progress",
            )
            .order_by(AtelierSession.started_at.desc())
        )
        session = self.db.execute(stmt).scalars().first()
        if session is None:
            return None
        return LegacyResume(
            href=f"/atelier?session={session.id}", session_id=str(session.id)
        )

    def _scenario_history(self, user: User) -> dict[str, date]:
        """The last learner-local date each scenario family was served, if ever.

        Read from the journeys this learner already has — no new table, no
        scheduler, no clock of its own.
        """

        rows = self.db.execute(
            select(DailyJourney.scenario_snapshot, DailyJourney.local_date)
            .where(DailyJourney.user_id == user.id)
            .order_by(DailyJourney.local_date.desc())
            .limit(SCENARIO_HISTORY_LIMIT)
        ).all()
        seen: dict[str, date] = {}
        for snapshot, local_date in rows:
            key = str((snapshot or {}).get("scenario_key") or "")
            if not key or local_date is None:
                continue
            previous = seen.get(key)
            if previous is None or previous < local_date:
                seen[key] = local_date
        return seen

    def _rotated_scenario_key(self, user: User, offered: list[str]) -> str | None:
        """Which family this learner gets next, deterministically (WP-12 D-1).

        A family the learner has never tried wins over one they have; among
        tried families the least recently served wins; ties break on the
        content module's own offer order, so ``order_at_cafe`` still leads for a
        brand-new learner. The result is a pure function of committed journey
        rows, so a retried create or a refresh cannot swap today's scene: the
        chosen key is persisted in ``scenario_snapshot`` by
        :meth:`create_journey` before any provider call, and every reopen and
        every generation retry reads that persisted key back instead of
        choosing again.
        """

        if not offered:
            return None
        history = self._scenario_history(user)
        order = {key: index for index, key in enumerate(offered)}
        return min(
            offered,
            key=lambda key: (
                0 if key not in history else 1,
                history.get(key) or date.min,
                order[key],
            ),
        )

    def _offer_scenario(self, user: User) -> Any:
        """Today's offer: the rotated family, resolved without paying for it.

        ``list_available_scenarios`` is the provider-free catalogue (WP-03
        documents it as costing nothing: generation off, no image call), so the
        rotation never turns a ``GET`` into generation. A content adapter
        without a catalogue keeps the previous single-offer behaviour.
        """

        # WP-75: a learner's first day is the authored café, and the offer
        # card says so rather than promising a story scene the day is not.
        if self._first_day_eligible(user, None):
            first = self.adapters.content.first_day_brief(
                self.db, user=user, input_mode=InputMode.TEXT
            )
            if isinstance(first, ScenarioBrief):
                return first
        describe = getattr(self.adapters.content, "describe_available_scenario", None)
        if callable(describe):
            offer = describe(self.db, user=user, input_mode=InputMode.TEXT)
            if offer is not None:
                return offer
        catalog = getattr(self.adapters.content, "list_available_scenarios", None)
        if callable(catalog):
            offered = list(catalog(self.db, user=user, input_mode=InputMode.TEXT))
            if not offered:
                return ContentUnavailable(
                    reason="no_scenario_content", retry_allowed=False
                )
            by_key = {str(brief.scenario_key): brief for brief in offered}
            chosen = self._rotated_scenario_key(user, list(by_key))
            return by_key[chosen] if chosen else offered[0]
        return preview_scenario(
            self.adapters, self.db, user=user, input_mode=InputMode.TEXT
        )

    def _rotated_offer_key(self, user: User) -> str | None:
        """The rotated family as a bare key, or ``None`` if nothing is offered.

        Only families that actually resolved for this learner are candidates, so
        a rotation can never turn an available day into an unavailable one; when
        it yields nothing the caller falls back to the content module's own
        deterministic priority order.
        """

        offer = run_best_effort(
            self.db,
            "daily_journey: scenario rotation",
            lambda: self._offer_scenario(user),
            default=None,
            log=logger,
        )
        key = getattr(offer, "scenario_key", None)
        return str(key) if key else None

    def _available_descriptor(self, user: User) -> ScenarioDescriptor | None:
        result: Any = None
        try:
            with best_effort(
                self.db,
                "daily_journey: scenario preview",
                reraise=(AdapterUnavailable,),
                log=logger,
            ):
                result = self._offer_scenario(user)
        except AdapterUnavailable as exc:
            # Nothing is on offer, and saying "available: null" is the honest
            # answer. Creation then refuses with generation_unavailable.
            logger.error(
                "daily_journey: content adapter unavailable (%s)", exc.reason
            )
            return None
        if isinstance(result, ContentUnavailable) or result is None:
            return None
        descriptor = dict(result.public_descriptor())
        # WP-L6: the day is planned to the learner's rhythm, so the preview says
        # the rhythm's minutes, not the story brief's own 4½-minute estimate.
        descriptor["estimated_seconds"] = budget_seconds_for(user)
        return ScenarioDescriptor.model_validate(descriptor)

    # ------------------------------------------------------------------
    # Internals — idempotency receipts
    # ------------------------------------------------------------------

    def _begin_mutation(
        self,
        user: User,
        *,
        scope: str,
        mutation_id: str,
        digest: str,
        journey: DailyJourney | None = None,
        expected_revision: int | None = None,
    ) -> tuple[DailyJourneyMutation, tuple[dict[str, Any], int] | None]:
        """Reserve the client key.

        The receipt is looked up **before** any revision check, so a duplicate
        of an already-committed request replays instead of being rejected as
        stale (CONTRACTS §5).
        """

        existing = self._find_receipt(user, scope, mutation_id)
        if existing is not None:
            return existing, self._resolve_existing_receipt(existing, digest)

        receipt = DailyJourneyMutation(
            mutation_id=mutation_id,
            journey_id=journey.id if journey else None,
            user_id=user.id,
            scope=scope,
            request_digest=digest,
            expected_revision=expected_revision,
            status="processing",
            evidence_refs=[],
        )
        self.db.add(receipt)
        try:
            self.db.commit()
        except (IntegrityError, OperationalError):
            self.db.rollback()
            existing = self._find_receipt(user, scope, mutation_id)
            if existing is None:
                raise
            return existing, self._resolve_existing_receipt(existing, digest)
        return receipt, None

    def _find_receipt(
        self, user: User, scope: str, mutation_id: str
    ) -> DailyJourneyMutation | None:
        stmt = select(DailyJourneyMutation).where(
            DailyJourneyMutation.user_id == user.id,
            DailyJourneyMutation.scope == scope,
            DailyJourneyMutation.mutation_id == mutation_id,
        )
        return self.db.execute(stmt).scalars().first()

    def _resolve_existing_receipt(
        self, receipt: DailyJourneyMutation, digest: str
    ) -> tuple[dict[str, Any], int] | None:
        if receipt.request_digest != digest:
            raise journey_error(
                http_status.HTTP_409_CONFLICT,
                JourneyErrorCode.IDEMPOTENCY_CONFLICT,
                "This request id was already used for a different request.",
            )
        if receipt.status == "committed":
            return dict(receipt.response_snapshot or {}), int(
                receipt.response_status or http_status.HTTP_200_OK
            )
        if receipt.status == "processing" and not self._receipt_is_stale(receipt):
            raise journey_error(
                http_status.HTTP_202_ACCEPTED,
                JourneyErrorCode.PROCESSING,
                "This request is still being processed. Reuse the same request.",
                retry_after_seconds=PROCESSING_RETRY_AFTER_SECONDS,
            )
        # Failed, or abandoned by a crashed worker: the key becomes reusable.
        receipt.status = "processing"
        receipt.response_status = None
        receipt.response_snapshot = None
        receipt.created_at = _utcnow()
        receipt.completed_at = None
        self.db.commit()
        return None

    def _receipt_is_stale(self, receipt: DailyJourneyMutation) -> bool:
        created = _as_aware(receipt.created_at)
        if created is None:
            return True
        return _utcnow() - created > timedelta(seconds=MUTATION_PROCESSING_TTL_SECONDS)

    def _commit_mutation(
        self,
        receipt: DailyJourneyMutation,
        journey: DailyJourney | None,
        status_code: int,
        payload: Any,
        *,
        evidence_refs: list[str] | None = None,
    ) -> None:
        """Commit domain effects and the receipt in one transaction."""

        receipt.status = "committed"
        receipt.response_status = status_code
        receipt.response_snapshot = payload.model_dump(mode="json")
        receipt.evidence_refs = list(evidence_refs or [])
        receipt.completed_at = _utcnow()
        if journey is not None and receipt.journey_id is None:
            receipt.journey_id = journey.id
        self.db.commit()

    def _record_error(self, receipt: DailyJourneyMutation, exc: HTTPException) -> None:
        """Persist a deterministic refusal so a replay returns the same answer."""

        self.db.rollback()
        fresh = self.db.get(DailyJourneyMutation, receipt.id)
        if fresh is None:
            return
        fresh.status = "committed"
        fresh.response_status = exc.status_code
        fresh.response_snapshot = {"detail": exc.detail}
        fresh.completed_at = _utcnow()
        self.db.commit()

    def _adapter_unavailable_error(self, exc: AdapterUnavailable) -> HTTPException:
        """A broken domain module fails the operation; it never fakes success."""

        logger.error(
            "daily_journey: %s adapter unavailable (%s); refusing the operation",
            exc.module_name,
            exc.reason,
        )
        return journey_error(
            http_status.HTTP_503_SERVICE_UNAVAILABLE,
            JourneyErrorCode.GENERATION_UNAVAILABLE,
            "This part of the journey is temporarily unavailable.",
            retry_after_seconds=UNAVAILABLE_RETRY_AFTER_SECONDS,
        )

    def _release_mutation(self, receipt: DailyJourneyMutation) -> None:
        """Mark the key retryable after a recoverable infrastructure failure."""

        fresh = self.db.get(DailyJourneyMutation, receipt.id)
        if fresh is None:
            return
        fresh.status = "failed"
        fresh.completed_at = _utcnow()

    @staticmethod
    def _replay(model_cls: Any, replay: tuple[dict[str, Any], int]) -> tuple[Any, int]:
        body, status_code = replay
        if status_code >= 400:
            raise HTTPException(status_code=status_code, detail=body.get("detail"))
        return model_cls.model_validate(body), status_code

    # ------------------------------------------------------------------
    # Internals — creation and generation
    # ------------------------------------------------------------------

    def _create_or_resume(
        self, user: User, payload: JourneyCreateRequest, timezone_name: str
    ) -> tuple[DailyJourney, int]:
        occupying = self._occupying_journey(user)
        if occupying is not None:
            if JourneyStatus(occupying.status) is JourneyStatus.PREPARING:
                if self._claim_is_live(occupying):
                    return occupying, http_status.HTTP_202_ACCEPTED
                if not self._reclaim(occupying):
                    # Another request took the claim a moment ago.
                    return occupying, http_status.HTTP_202_ACCEPTED
                return self._run_generation(
                    user,
                    occupying,
                    payload.preferred_input_mode,
                    # Past the provider budget, a reclaim serves the authored
                    # day instead of paying for a fourth story-engine call.
                    authored_only=occupying.generation_attempts > MAX_GENERATION_ATTEMPTS
                    and self._authored_fallback_enabled(),
                )
            # A timezone change never rekeys or duplicates an open journey.
            return occupying, http_status.HTTP_200_OK

        today = local_date_for(timezone_name)
        existing = self._journey_for_date(user, today)
        if existing is not None:
            return existing, http_status.HTTP_200_OK

        descriptor = self._available_descriptor(user)
        if descriptor is None:
            raise journey_error(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                JourneyErrorCode.GENERATION_UNAVAILABLE,
                "No daily scenario is available right now.",
                retry_after_seconds=UNAVAILABLE_RETRY_AFTER_SECONDS,
            )

        for _ in range(CREATE_RACE_ATTEMPTS):
            self._lock_user_row(user)
            occupying = self._occupying_journey(user)
            if occupying is not None:
                return occupying, http_status.HTTP_200_OK
            existing = self._journey_for_date(user, today)
            if existing is not None:
                return existing, http_status.HTTP_200_OK

            journey = DailyJourney(
                user_id=user.id,
                local_date=today,
                timezone=timezone_name,
                contract_version=1,
                content_version=descriptor.content_version,
                level_band=descriptor.level_band,
                status=str(JourneyStatus.PREPARING),
                revision=1,
                # WP-L6: the learner's rhythm sizes the day, whatever an
                # older client sends.
                budget_seconds=budget_seconds_for(user),
                estimated_active_seconds=0,
                scenario_snapshot=descriptor.model_dump(mode="json"),
                serial_thread_id=descriptor.serial_thread_id,
                serial_episode_id=descriptor.serial_episode_id,
                generation_claim_id=uuid.uuid4().hex,
                generation_claimed_at=_utcnow(),
                generation_attempts=1,
            )
            self.db.add(journey)
            try:
                # Phase 1: the claim is durable before any provider call.
                self.db.commit()
            except (IntegrityError, OperationalError):
                self.db.rollback()
                continue
            self._emit(JourneyEventName.CREATED, user, journey, {})
            return self._run_generation(user, journey, payload.preferred_input_mode)

        # Someone else won every race; return whatever they created.
        winner = self._occupying_journey(user) or self._journey_for_date(user, today)
        if winner is None:  # pragma: no cover - defensive
            raise journey_error(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                JourneyErrorCode.GENERATION_UNAVAILABLE,
                "Could not start a daily journey right now.",
                retry_after_seconds=UNAVAILABLE_RETRY_AFTER_SECONDS,
            )
        return winner, http_status.HTTP_200_OK

    def _reclaim(self, journey: DailyJourney) -> bool:
        """Take over an expired claim durably before calling a provider again.

        WP-69: compare-and-set on the claim this request observed and on the
        revision, so two requests that both saw a dead claim cannot both take
        it over and both pay for a generation. Returns whether this one won.
        """

        observed_claim = journey.generation_claim_id
        claim_matches = (
            DailyJourney.generation_claim_id.is_(None)
            if observed_claim is None
            else DailyJourney.generation_claim_id == observed_claim
        )
        result = self.db.execute(
            update(DailyJourney)
            .where(
                DailyJourney.id == journey.id,
                DailyJourney.status == str(JourneyStatus.PREPARING),
                DailyJourney.revision == journey.revision,
                claim_matches,
            )
            .values(
                generation_claim_id=uuid.uuid4().hex,
                generation_claimed_at=_utcnow(),
                generation_attempts=journey.generation_attempts + 1,
                revision=journey.revision + 1,
            )
            .execution_options(synchronize_session=False)
        )
        won = result.rowcount == 1
        self.db.commit()
        self.db.refresh(journey)
        return won

    def _claim_is_live(self, journey: DailyJourney) -> bool:
        claimed_at = _as_aware(journey.generation_claimed_at)
        if not journey.generation_claim_id or claimed_at is None:
            return False
        return _utcnow() - claimed_at <= timedelta(seconds=GENERATION_CLAIM_TTL_SECONDS)

    def _retry_generation(
        self, user: User, journey: DailyJourney
    ) -> tuple[DailyJourney, int]:
        current = JourneyStatus(journey.status)
        if current not in (JourneyStatus.PREPARING, JourneyStatus.UNAVAILABLE):
            raise journey_error(
                http_status.HTTP_409_CONFLICT,
                JourneyErrorCode.JOURNEY_NOT_ACTIVE,
                "This journey does not need a retry.",
                current_revision=journey.revision,
                refresh_href=refresh_href_for(journey.id),
            )
        if current is JourneyStatus.PREPARING and self._claim_is_live(journey):
            return journey, http_status.HTTP_202_ACCEPTED
        if current is JourneyStatus.UNAVAILABLE and not journey.unavailable_retry_allowed:
            raise journey_error(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                JourneyErrorCode.GENERATION_UNAVAILABLE,
                "There is no valid scenario for this journey; a retry cannot help.",
                current_revision=journey.revision,
                refresh_href=refresh_href_for(journey.id),
            )
        authored_only = False
        if journey.generation_attempts >= MAX_GENERATION_ATTEMPTS:
            # WP-69: the provider budget is spent, but the day is not lost while
            # an authored scene can still be served — one more attempt, with no
            # provider call in it.
            if not self._authored_rescue_possible(journey):
                raise journey_error(
                    http_status.HTTP_503_SERVICE_UNAVAILABLE,
                    JourneyErrorCode.GENERATION_UNAVAILABLE,
                    "This journey could not be prepared. Try again later.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(journey.id),
                )
            authored_only = True
        if current is JourneyStatus.UNAVAILABLE:
            blocker = self._occupying_journey(user)
            if blocker is not None and blocker.id != journey.id:
                raise journey_error(
                    http_status.HTTP_409_CONFLICT,
                    JourneyErrorCode.JOURNEY_NOT_ACTIVE,
                    "Another journey is already open.",
                    current_revision=journey.revision,
                    refresh_href=refresh_href_for(blocker.id),
                )
        # WP-69: the claim is taken with a compare-and-set on the revision this
        # request read, so two concurrent retries cannot both generate.
        taken = self.db.execute(
            update(DailyJourney)
            .where(
                DailyJourney.id == journey.id,
                DailyJourney.revision == journey.revision,
                DailyJourney.status == journey.status,
            )
            .values(
                status=str(JourneyStatus.PREPARING),
                unavailable_reason=None,
                generation_claim_id=uuid.uuid4().hex,
                generation_claimed_at=_utcnow(),
                generation_attempts=journey.generation_attempts + 1,
                revision=journey.revision + 1,
            )
            .execution_options(synchronize_session=False)
        )
        if taken.rowcount != 1:
            self.db.rollback()
            fresh = self.db.get(DailyJourney, journey.id)
            if fresh is None:  # pragma: no cover - defensive
                raise _not_found()
            self.db.refresh(fresh)
            busy = JourneyStatus(fresh.status) is JourneyStatus.PREPARING
            return fresh, (http_status.HTTP_202_ACCEPTED if busy else http_status.HTTP_200_OK)
        self.db.commit()
        self.db.refresh(journey)
        return self._run_generation(
            user, journey, InputMode.TEXT, authored_only=authored_only
        )

    def _run_generation(
        self,
        user: User,
        journey: DailyJourney,
        input_mode: InputMode,
        *,
        authored_only: bool = False,
    ) -> tuple[DailyJourney, int]:
        """Phase 2: provider work outside the lock, then verify the claim.

        WP-69: whatever happens in here, the journey does not stay in
        `preparing`. An unexpected error is logged, the transaction is rolled
        back to its last commit (the claim), and — if the claim is still ours —
        the journey is marked `unavailable` with a retry offered. Before this, a
        crash here left the learner looking at «wird vorbereitet» for the rest
        of the day.
        """

        journey_id = journey.id
        claim = journey.generation_claim_id
        try:
            return self._generate(user, journey, input_mode, authored_only=authored_only)
        except HTTPException:
            raise
        except Exception:
            logger.exception("daily_journey: generation crashed; journey %s made retryable", journey_id)
            self._rollback_quietly()
            fresh = self.db.get(DailyJourney, journey_id)
            if fresh is None:  # pragma: no cover - defensive
                raise _not_found() from None
            self.db.refresh(fresh)
            if fresh.generation_claim_id != claim or JourneyStatus(
                fresh.status
            ) is not JourneyStatus.PREPARING:
                return fresh, http_status.HTTP_200_OK
            return self._mark_unavailable(fresh, "generation_crashed")

    def _generate(
        self,
        user: User,
        journey: DailyJourney,
        input_mode: InputMode,
        *,
        authored_only: bool,
    ) -> tuple[DailyJourney, int]:
        if journey.steps:
            # Already planned. Step ids stay stable through a generation retry:
            # never re-plan a journey that already has a persisted plan.
            return self._activate_prepared(journey)

        claim = journey.generation_claim_id
        result: Any = None
        # WP-75: a learner's first day is authored and instant — no prefetch
        # consumed (that scene is day 2's), no provider call.
        first_day = self._first_day_brief(user, journey, input_mode)
        if first_day is not None:
            result = first_day
            self.draft_prefetch_hit = False
        elif authored_only:
            # WP-69: the provider budget is spent. No provider call, no
            # prefetch: straight to the authored day below.
            result = ContentUnavailable(reason="generation_attempts_exhausted")
            self.draft_prefetch_hit = False
        else:
            # The family was chosen and persisted at create time (phase 1), so a
            # generation retry re-serves the same scene instead of rotating under
            # an in-flight journey. Only a journey whose snapshot predates that —
            # or was written without a key — falls back to choosing now.
            scenario_key = (journey.scenario_snapshot or {}).get("scenario_key")
            if not scenario_key:
                scenario_key = self._rotated_offer_key(user)
            # WP-26 hot path. A prefetched scene whose cache key still matches the
            # story revision, learner context and prompt version is served as-is;
            # anything stale was discarded inside ``take_prefetched_scene`` rather
            # than handed back. Taking one writes its consume row in this same
            # transaction, so the scene is never generated or served twice.
            result = run_best_effort(
                self.db,
                "daily_journey: prefetched scene lookup",
                lambda: take_prefetched_scene(self.db, user, input_mode=input_mode),
                default=None,
                log=logger,
            )
            self.draft_prefetch_hit = result is not None
            if result is None:
                try:
                    with best_effort(
                        self.db,
                        "daily_journey: scenario generation",
                        reraise=(AdapterUnavailable,),
                        log=logger,
                    ) as generation:
                        result = self.adapters.content.build_scenario_context(
                            self.db, user=user, scenario_key=scenario_key, input_mode=input_mode
                        )
                    if generation.failed:
                        result = ContentUnavailable(reason="generation_failed")
                except AdapterUnavailable as exc:
                    # The content module exists but is broken. Honest dead end, and
                    # a retry cannot help until someone fixes the module.
                    logger.error("daily_journey: content adapter unavailable (%s)", exc.reason)
                    result = ContentUnavailable(
                        reason=f"content_adapter_{exc.reason}",
                        retry_after_seconds=0,
                        retry_allowed=False,
                    )

        # A generation that committed internally and then failed is outside any
        # savepoint; make sure the claim check below runs on a live transaction.
        self._ensure_usable_session()
        self.db.expire(journey)
        fresh = self.db.get(DailyJourney, journey.id)
        if fresh is None:  # pragma: no cover - defensive
            raise _not_found()
        if fresh.generation_claim_id != claim or JourneyStatus(
            fresh.status
        ) is not JourneyStatus.PREPARING:
            # Another worker committed first; its result stands.
            return fresh, http_status.HTTP_200_OK
        if not self._lock_claimed_row(fresh, claim):
            # Taken over between the read and the lock: theirs stands too.
            self.db.refresh(fresh)
            return fresh, http_status.HTTP_200_OK

        failure: _GenerationFailure | None
        if isinstance(result, ContentUnavailable):
            failure = _GenerationFailure(
                result.reason,
                retry_allowed=result.retry_allowed,
                retry_after_seconds=result.retry_after_seconds,
                # With the story engine on, every content failure is the
                # engine's; an adapter outage is not, and the authored path
                # would meet the same broken module.
                fallback_eligible=not str(result.reason).startswith("content_adapter_"),
            )
        else:
            failure = self._prepare_scene(
                user, fresh, result, input_mode, first_day=first_day is not None
            )

        if failure is not None and failure.fallback_eligible and self._authored_fallback_enabled():
            failure = self._serve_authored_fallback(user, fresh, input_mode, failure)

        if failure is not None:
            return self._mark_unavailable(
                fresh,
                failure.reason,
                retry_allowed=failure.retry_allowed,
                retry_after_seconds=failure.retry_after_seconds,
            )
        self._emit(JourneyEventName.STARTED, user, fresh, {})
        return fresh, http_status.HTTP_201_CREATED

    def _prepare_scene(
        self,
        user: User,
        journey: DailyJourney,
        brief: ScenarioBrief,
        input_mode: InputMode,
        *,
        fallback: dict[str, Any] | None = None,
        first_day: bool = False,
    ) -> _GenerationFailure | None:
        """Plan, bind and persist one brief as today's day — all or nothing.

        Runs inside a SAVEPOINT (WP-69): a brief that cannot be planned or bound
        leaves no half-written steps, learning session or serial episode
        behind, so an authored scene can be tried on the same journey next.
        Returns ``None`` when the journey is now active, else why not.
        """

        self._ensure_usable_session()
        nested = self.db.begin_nested()
        try:
            self._plan_and_bind(
                user, journey, brief, input_mode, fallback=fallback, first_day=first_day
            )
        except _GenerationFailure as failure:
            self._rollback_savepoint(nested)
            return failure
        except HTTPException:
            self._rollback_savepoint(nested)
            raise
        except Exception:
            logger.exception("daily_journey: preparing the scene failed")
            self._rollback_savepoint(nested)
            return _GenerationFailure(
                "planning_failed", fallback_eligible=bool(brief.story_context)
            )
        if nested.is_active:
            nested.commit()
        return None

    def _plan_and_bind(
        self,
        user: User,
        fresh: DailyJourney,
        result: ScenarioBrief,
        input_mode: InputMode,
        *,
        fallback: dict[str, Any] | None,
        first_day: bool = False,
    ) -> None:
        story_brief = bool(result.story_context)
        # WP-24 §5, wired by WP-28. The learner's ranked due errata are read
        # before the plan is built, merged in front of the day's candidates by
        # the planner, and the target the plan actually keeps becomes the
        # because-line. Reading the queue reschedules nothing; a queue that
        # cannot be read costs the line, never the day.
        errata = self._errata_targets(user)
        because: dict[str, Any] | None = None
        # WP-66. Today's *shape* is decided here, where the cheap facts already
        # are: what yesterday was, whether yesterday happened at all, what beat
        # the story is on, whether this deployment can speak, and how much the
        # errata queue is holding. No provider call, no second content source.
        dice = self._day_shape_inputs(user, fresh, result, errata_count=len(errata))
        decision = choose_day_shape(dice)
        try:
            if first_day:
                # WP-75: the scene's own words, not the (empty) queue of a
                # learner who has never practised.
                candidates = self.adapters.content.first_day_candidates(
                    self.db, user=user, brief=result
                )
            else:
                candidates = self._select_candidates(user, fresh, result)
            introduction = None if first_day else self._introduction_for_today(user, result)
            plan = self._plan_with_shape(
                scenario=result,
                candidates=list(candidates),
                budget_seconds=fresh.budget_seconds,
                # WP-L6: the learner's measured pace, once three days are
                # measured; the priors before that (the planner ignores an
                # untrusted profile).
                pace=self._pace_profile(user, fresh),
                # WP-04 coordination addition, ratified 2026-09-05: the frozen
                # ScenarioBrief carries no modality, so RespondPrompt.input_modes
                # can only know about voice if the create request says so.
                input_mode=input_mode,
                errata_targets=errata,
                dice=dice,
                decision=decision,
                scenario_result=result,
                first_day=first_day,
                introduction=introduction,
            )
            plan.validate()
            because = self._plan_because(plan, list(candidates), errata)
        except AdapterUnavailable as exc:
            logger.error("daily_journey: %s adapter unavailable (%s)", exc.module_name, exc.reason)
            raise _GenerationFailure(
                f"{exc.module_name}_{exc.reason}", retry_allowed=False, retry_after_seconds=0
            ) from exc
        except Exception as exc:
            logger.exception("daily_journey: planning failed")
            if self._is_plan_unavailable(exc):
                # A deterministic content defect (no setup, no ending, too long
                # for five minutes). Retrying identical content cannot help.
                raise _GenerationFailure(
                    str(getattr(exc, "reason", "plan_unavailable")),
                    retry_allowed=False,
                    retry_after_seconds=0,
                    fallback_eligible=story_brief,
                ) from exc
            raise _GenerationFailure("planning_failed", fallback_eligible=story_brief) from exc

        session = None
        try:
            with best_effort(
                self.db,
                "daily_journey: learning session bootstrap",
                reraise=(AdapterUnavailable,),
                log=logger,
            ):
                session = self.adapters.learning.ensure_journey_learning_session(
                    self.db,
                    user=user,
                    journey_id=fresh.id,
                    scenario_key=str(
                        (result.story_context.get("draft") or {}).get("capability_key")
                        or result.scenario_key
                    ),
                )
                # WP-05 adds and flushes but never commits; the id exists after flush.
                self.db.flush()
        except AdapterUnavailable as exc:
            # No canonical session means no canonical credit. Refuse the journey
            # rather than running one whose evidence goes nowhere.
            logger.error("daily_journey: learning adapter unavailable (%s)", exc.reason)
            raise _GenerationFailure(
                f"{exc.module_name}_{exc.reason}", retry_allowed=False, retry_after_seconds=0
            ) from exc

        if story_brief:
            from app.services.living_story import StoryUnavailable, bind_journey

            try:
                result = bind_journey(self.db, user=user, journey=fresh, brief=result)
            except StoryUnavailable as exc:
                raise _GenerationFailure(str(exc), fallback_eligible=True) from exc
        self._persist_plan(fresh, result, plan, input_mode, because=because, fallback=fallback)
        # WP-78: what the dice dealt, so tomorrow's dice do not deal a shape
        # that could not be built today straight back (`previous_dealt_shape`).
        fresh.plan_selection = {
            **dict(fresh.plan_selection or {}),
            "dealt_shape": str(decision.shape),
            # WP-L6: the new words this day introduces — the journey's share
            # of the learner's one intake pool, reserved against the drill.
            JOURNEY_NEW_WORDS_KEY: _new_word_ids(plan, list(candidates)),
            # WP-L4: the grammar unit this day introduces, if its rule made it
            # into the plan. The unit is *introduced* when the rule is read.
            "introduction": _planned_introduction(plan),
        }
        if first_day:
            fresh.plan_selection = {
                **dict(fresh.plan_selection or {}),
                "first_day": {
                    "kind": FIRST_DAY_KIND,
                    "cast_intro": self.adapters.content.first_day_cast_intro(
                        user.native_language
                    ),
                },
            }
        fresh.learning_session_id = getattr(session, "id", None)
        fresh.status = str(JourneyStatus.ACTIVE)
        fresh.started_at = _utcnow()
        fresh.generation_claim_id = None
        fresh.generation_claimed_at = None
        fresh.revision += 1
        self.db.flush()

    # ------------------------------------------------------------------
    # WP-75 — the first day is authored, instant, and introduces the cast
    # ------------------------------------------------------------------

    def _first_day_eligible(self, user: User, journey: DailyJourney | None) -> bool:
        """Is this the learner's first day?

        Only with the deployment flag on, only through a content adapter that
        can author one (the real ``journey_content``; the deterministic test
        stub cannot), and only for a learner who has never completed a day and
        whose story has not started — a day the story engine already bound is
        never rewound to the café.
        """

        if not getattr(settings, "ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED", False):
            return False
        content = self.adapters.content
        if not all(
            callable(getattr(content, name, None))
            for name in ("first_day_brief", "first_day_candidates", "first_day_cast_intro")
        ):
            return False
        others = [DailyJourney.user_id == user.id]
        if journey is not None:
            others.append(DailyJourney.id != journey.id)
        earlier = self.db.execute(
            select(DailyJourney.id)
            .where(
                *others,
                or_(
                    DailyJourney.status == str(JourneyStatus.COMPLETED),
                    DailyJourney.serial_episode_id.isnot(None),
                ),
            )
            .limit(1)
        ).first()
        return earlier is None

    def _first_day_brief(
        self, user: User, journey: DailyJourney, input_mode: InputMode
    ) -> ScenarioBrief | None:
        """The authored first day, or ``None`` (then the day is made as usual)."""

        eligible = run_best_effort(
            self.db,
            "daily_journey: first-day eligibility",
            lambda: self._first_day_eligible(user, journey),
            default=False,
            log=logger,
        )
        if not eligible:
            return None
        brief = run_best_effort(
            self.db,
            "daily_journey: first-day brief",
            lambda: self.adapters.content.first_day_brief(
                self.db, user=user, input_mode=input_mode
            ),
            default=None,
            log=logger,
        )
        return brief if isinstance(brief, ScenarioBrief) else None

    def _warm_next_day(self, user: User, journey: DailyJourney) -> None:
        """WP-75: after the first day, have day 2's scene ready before it is asked for.

        The WP-26 prefetch, scheduled for the learner's next local day (its own
        guard refuses a learner who already has today's journey), in the input
        mode the first day was played in. Cohort, flag and the weekly spend
        guardrail are the prefetch's own checks. Never fatal: a broker outage
        costs the warm start, not the finish.
        """

        if not (journey.plan_selection or {}).get("first_day"):
            return
        try:
            from app.tasks.journey_prefetch import schedule_next_day_warmup

            schedule_next_day_warmup(
                user,
                timezone_name=journey.timezone,
                input_mode=_journey_input_mode(journey),
            )
        except Exception:  # pragma: no cover - never fail a finish for a warm-up
            logger.warning("daily_journey: day-2 warm-up could not be scheduled", exc_info=True)

    # ------------------------------------------------------------------
    # WP-69 — the authored day, when the story engine cannot write one
    # ------------------------------------------------------------------

    def _authored_fallback_enabled(self) -> bool:
        """Can an authored scene stand in for a failed story-engine day?

        Only when the deployment opts in (``ATELIER_JOURNEY_AUTHORED_FALLBACK_ENABLED``),
        only with the story engine on — with it off, the content *is* authored
        and a failure there is the authored content's own — and only through a
        content adapter that can resolve an authored family without generating
        (the real ``journey_content``; the deterministic test stub cannot).
        """

        if not settings.ATELIER_STORY_ENGINE_ENABLED:
            return False
        if not getattr(settings, "ATELIER_JOURNEY_AUTHORED_FALLBACK_ENABLED", False):
            return False
        content = self.adapters.content
        return callable(getattr(content, "resolve_scenario_brief", None)) and bool(
            getattr(content, "SCENARIO_PRIORITY", None)
        )

    def _authored_rescue_possible(self, journey: DailyJourney) -> bool:
        """One provider-free attempt past the budget, while the day has no plan."""

        return (
            self._authored_fallback_enabled()
            and not journey.steps
            and journey.generation_attempts <= MAX_GENERATION_ATTEMPTS
        )

    def _authored_fallback_brief(
        self, user: User, journey: DailyJourney, input_mode: InputMode
    ) -> ScenarioBrief | None:
        """An authored scene for this learner's band, rotated like any other day.

        ``level_band`` is left to the content module, which serves the
        learner's own band or the nearest authored one (the authored ceiling is
        A2, so a B1+ learner gets the A2 variant and its honest level note).
        ``bind_serial=False`` keeps the stand-in out of the living story: it is
        not a chapter, and it must not claim to be one.
        """

        content = self.adapters.content
        resolve = content.resolve_scenario_brief
        keys = [str(key) for key in (content.SCENARIO_PRIORITY or ())]
        if not keys:
            return None
        first = run_best_effort(
            self.db,
            "daily_journey: authored fallback rotation",
            lambda: self._rotated_scenario_key(user, keys),
            default=None,
            log=logger,
        ) or keys[0]
        for key in [first, *[item for item in keys if item != first]]:
            brief = run_best_effort(
                self.db,
                f"daily_journey: authored fallback {key}",
                lambda key=key: resolve(
                    self.db,
                    user=user,
                    scenario_key=key,
                    input_mode=input_mode,
                    allow_generation=False,
                    bind_serial=False,
                ),
                default=None,
                log=logger,
            )
            if isinstance(brief, ScenarioBrief):
                return brief
        return None

    def _serve_authored_fallback(
        self,
        user: User,
        journey: DailyJourney,
        input_mode: InputMode,
        failure: _GenerationFailure,
    ) -> _GenerationFailure | None:
        """Try the authored day; ``None`` when it is now the learner's day."""

        brief = self._authored_fallback_brief(user, journey, input_mode)
        if brief is None:
            logger.error(
                "daily_journey: story engine failed (%s) and no authored scene resolved",
                failure.reason,
            )
            return failure
        marker = {
            "kind": AUTHORED_FALLBACK_KIND,
            "reason": str(failure.reason)[:120],
            "scenario_key": str(brief.scenario_key),
            "level_band": str(brief.level_band),
            "at": _utcnow().isoformat(),
        }
        rescued = self._prepare_scene(user, journey, brief, input_mode, fallback=marker)
        if rescued is not None:
            logger.error(
                "daily_journey: story engine failed (%s); the authored fallback failed too (%s)",
                failure.reason,
                rescued.reason,
            )
            return failure
        logger.warning(
            "daily_journey: story engine failed (%s); journey %s serves authored %s at %s",
            failure.reason,
            journey.id,
            brief.scenario_key,
            brief.level_band,
        )
        return None

    def _lock_claimed_row(self, journey: DailyJourney, claim: str | None) -> bool:
        """Write-lock the journey row while it is still ours to finish.

        A no-op UPDATE guarded by the claim: on PostgreSQL it holds the row until
        the plan commits, so a reclaim cannot interleave with persisting it; on
        SQLite it opens the write transaction *before* the savepoint, so the
        savepoint nests inside it instead of opening a read transaction that a
        concurrent writer would make impossible to upgrade. Returns whether the
        claim still matched.
        """

        result = self.db.execute(
            update(DailyJourney)
            .where(
                DailyJourney.id == journey.id,
                DailyJourney.generation_claim_id == claim,
                DailyJourney.status == str(JourneyStatus.PREPARING),
            )
            .values(revision=DailyJourney.revision)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def _ensure_usable_session(self) -> None:
        if not session_is_usable(self.db):
            logger.warning("daily_journey: the transaction was aborted; rolling back to the claim")
            self._rollback_quietly()

    def _rollback_quietly(self) -> None:
        try:
            self.db.rollback()
        except Exception:  # pragma: no cover - the connection itself is gone
            logger.exception("daily_journey: rollback failed")

    def _rollback_savepoint(self, nested: Any) -> None:
        try:
            if nested.is_active:
                nested.rollback()
        except Exception:  # pragma: no cover - the connection itself is gone
            logger.exception("daily_journey: savepoint rollback failed")
            self._rollback_quietly()
            return
        self._ensure_usable_session()

    def _is_plan_unavailable(self, exc: BaseException) -> bool:
        """Is this WP-04's typed ``PlanUnavailable``?

        Resolved through the adapter rather than imported, so the state machine
        keeps no hard import dependency on the planner package.
        """

        plan_unavailable = getattr(self.adapters.planner, "PlanUnavailable", None)
        return isinstance(plan_unavailable, type) and isinstance(exc, plan_unavailable)

    def _activate_prepared(self, journey: DailyJourney) -> tuple[DailyJourney, int]:
        """Bring an already-planned journey out of ``preparing`` unchanged."""

        journey.status = str(JourneyStatus.ACTIVE)
        journey.generation_claim_id = None
        journey.generation_claimed_at = None
        if journey.started_at is None:
            journey.started_at = _utcnow()
            # WP-L9: a day planned ahead starts its first step now, not at
            # planning time.
            for step in journey.steps:
                if step.id == journey.current_step_id:
                    step.started_at = journey.started_at
        if journey.current_step_id is None:
            self._activate_next_step(journey, after_ordinal=-1)
        journey.revision += 1
        self.db.flush()
        return journey, http_status.HTTP_200_OK

    def _mark_unavailable(
        self,
        journey: DailyJourney,
        reason: str,
        *,
        retry_allowed: bool = True,
        retry_after_seconds: int = UNAVAILABLE_RETRY_AFTER_SECONDS,
    ) -> tuple[DailyJourney, int]:
        """An honest dead end.

        WP-03's deterministic reasons (``scenario_not_authored`` and friends)
        arrive with ``retry_allowed=False``; the public ``retry`` hint then says
        so instead of promising a retry that cannot help.

        WP-69: this must work on a transaction that something before it broke —
        on 2026-09-22 it did not, and the journey stayed `preparing`. A session
        that cannot run a statement is rolled back to its last commit (the
        claim) first; if the claim is no longer this journey's to settle, the
        row is returned as it stands.
        """

        if not session_is_usable(self.db):
            logger.warning("daily_journey: marking unavailable on an aborted transaction; rolling back")
            self._rollback_quietly()
            fresh = self.db.get(DailyJourney, journey.id)
            if fresh is None:  # pragma: no cover - defensive
                raise _not_found()
            self.db.refresh(fresh)
            journey = fresh
            if JourneyStatus(journey.status) is not JourneyStatus.PREPARING:
                return journey, http_status.HTTP_200_OK

        journey.status = str(JourneyStatus.UNAVAILABLE)
        journey.unavailable_reason = reason[:120]
        journey.unavailable_retry_allowed = bool(retry_allowed)
        journey.unavailable_retry_after_seconds = int(retry_after_seconds)
        journey.generation_claim_id = None
        journey.generation_claimed_at = None
        journey.revision += 1
        self.db.flush()
        return journey, http_status.HTTP_200_OK

    # ------------------------------------------------------------------
    # WP-66 — the day's shape
    # ------------------------------------------------------------------

    def _day_shape_inputs(
        self,
        user: User,
        journey: DailyJourney,
        brief: ScenarioBrief,
        *,
        errata_count: int,
    ) -> DayShapeInputs:
        """Everything the seeded dice are allowed to know about today.

        Every field is either already in hand or one cheap indexed read. A
        failure anywhere in here costs the *variation*, never the day: the
        fallbacks are the values that deal a standard day.
        """

        previous_shape: DayShape | None = None
        previous_dealt: DayShape | None = None
        missed = False
        with best_effort(self.db, "daily_journey: previous-day lookup", log=logger):
            yesterday = journey.local_date - timedelta(days=1)
            previous = self._journey_for_date(user, yesterday)
            if previous is None:
                # Nothing yesterday. A learner on their *first* day has not
                # missed anything, so the short shape is offered only to
                # somebody who has been here before.
                missed = self._has_earlier_journey(user, journey.local_date)
            else:
                previous_shape = _stored_day_shape(previous)
                dealt_name = _shape_name(_mapping(previous.plan_selection).get("dealt_shape"))
                if dealt_name and dealt_name != str(previous_shape):
                    try:
                        previous_dealt = DayShape(dealt_name)
                    except ValueError:
                        previous_dealt = None

        story = brief.story_context if isinstance(brief.story_context, dict) else {}
        draft = story.get("draft") if isinstance(story.get("draft"), dict) else {}
        # WP-62/63 put the whole director context under `source`; the top level of
        # a scenario brief holds the draft and the provenance and nothing else.
        # Written before WP-63 landed, this read looked only at the top level and
        # so never found a chapter shape at all (WP-68).
        source = _mapping(story.get("source"))
        chapter = _mapping(story.get("chapter")) or _mapping(source.get("chapter"))
        beat = (
            story.get("beat")
            or story.get("chapter_beat")
            or draft.get("beat")
            or source.get("beat")
        )
        # WP-63 deals a *chapter* shape and one of its five values is «letter»: a
        # chapter whose turn beat is a Courrier letter. It is read with `.get`
        # from every place that package could reasonably put it, and an absent
        # key is simply a chapter that did not ask for one.
        shape_row = _mapping(source.get("chapter_shape"))
        chapter_shape = _shape_name(
            chapter.get("shape")
            or shape_row.get("shape")
            or story.get("chapter_shape")
            or draft.get("chapter_shape")
            or draft.get("shape")
        )
        letter_beat = _shape_name(shape_row.get("letter_beat"))
        if (
            chapter_shape == str(DayShape.LETTER)
            and letter_beat
            and str(beat or "").strip().lower() != letter_beat
        ):
            # A letter chapter names *which* of its beats is the letter. The other
            # three are ordinary days, and dealing four letter days off one
            # chapter would empty the Courrier to fill a chapter that asked for
            # one letter.
            chapter_shape = None

        return DayShapeInputs(
            user_id=str(user.id),
            local_date=journey.local_date,
            previous_shape=previous_shape,
            previous_dealt_shape=previous_dealt,
            missed_previous_day=missed,
            chapter_beat=str(beat) if beat else None,
            chapter_shape=chapter_shape,
            audio_available=bool(settings.ATELIER_EPISODE_AUDIO_ENABLED),
            errata_count=int(errata_count),
            # The WP-64 seam, wired: the letter the Courrier is already showing
            # this learner, read inside this transaction. `None` — no letter
            # waiting, or no provider — makes «jour de lettre» ineligible
            # rather than empty.
            # WP-69: inside a SAVEPOINT. This is the lookup that cost the day
            # on 2026-09-22 — a letter is never worth the day.
            letter=run_best_effort(
                self.db,
                "daily_journey: Courrier letter offer",
                lambda: letter_offer_for(
                    user_id=str(user.id), local_date=journey.local_date, db=self.db
                ),
                default=None,
                log=logger,
            ),
        )

    def _has_earlier_journey(self, user: User, day: date) -> bool:
        """Has this learner had any journey before ``day``?"""

        stmt = select(DailyJourney.id).where(
            DailyJourney.user_id == user.id, DailyJourney.local_date < day
        )
        return self.db.execute(stmt.limit(1)).first() is not None

    def _select_candidates(self, user: User, journey: DailyJourney, scenario: ScenarioBrief) -> Any:
        """The day's candidates, at the rhythm's pool size and inside the
        learner's vocabulary pace (WP-L6).

        The new-word quota is offered only to a learning adapter that accepts
        it, so a stub built before WP-L6 still plans a day.
        """

        select = self.adapters.learning.select_learning_candidates
        kwargs: dict[str, Any] = {
            "user": user,
            "scenario": scenario,
            "limit": (
                # WP-L6: a longer rhythm sees more of the queue.
                max(PRACTICE_CANDIDATE_LIMIT, candidate_limit_for(journey.budget_seconds))
                if settings.ATELIER_JOURNEY_PRACTICE_DAY_ENABLED
                else CANDIDATE_LIMIT
            ),
        }
        try:
            accepted = set(inspect.signature(select).parameters)
        except (TypeError, ValueError):  # pragma: no cover - exotic callables
            accepted = set()
        if "budget_seconds" in accepted:
            # WP-L4: the Rappel's grammar room grows with the rhythm.
            kwargs["budget_seconds"] = journey.budget_seconds
        if "new_word_quota" in accepted:
            kwargs["new_word_quota"] = run_best_effort(
                self.db,
                "daily_journey: vocabulary pace",
                lambda: journey_new_word_room(self.db, user, now=_utcnow()),
                default=None,
                log=logger,
            )
        return select(self.db, **kwargs)

    def _introduction_for_today(self, user: User, scenario: ScenarioBrief) -> Any:
        """WP-L4: today's new grammar unit (a unit brief), or None.

        The rhythm's weekly quota and the one new-concept picker decide
        (`concept_life.introduction_for_today`). Only a practice day has room
        for a rule and its guided items; a failure costs the introduction,
        never the day.
        """

        if not settings.ATELIER_JOURNEY_PRACTICE_DAY_ENABLED:
            return None
        from app.services.concept_life import introduction_for_today

        return run_best_effort(
            self.db,
            "daily_journey: grammar introduction",
            lambda: introduction_for_today(
                self.db,
                user,
                now=_utcnow(),
                control_language=str(scenario.control_language),
            ),
            default=None,
            log=logger,
        )

    def _pace_profile(self, user: User, journey: DailyJourney) -> Any:
        """WP-L6: the planner's pace profile from the learner's measured days.

        ``None`` (the priors) until :data:`MIN_MEASURED_PACE_DAYS` days are
        measured, or when the planner adapter has no profile type.
        """

        profile_type = getattr(self.adapters.planner, "PacingProfile", None)
        if not isinstance(profile_type, type):
            return None
        measured = run_best_effort(
            self.db,
            "daily_journey: pace profile",
            lambda: measured_pace(self.db, user_id=user.id, exclude_journey_id=journey.id),
            default=None,
            log=logger,
        )
        if measured is None or measured.days < MIN_MEASURED_PACE_DAYS:
            return None
        return profile_type(
            step_multiplier=measured.step_multiplier,
            observations=measured.days,
        )

    def _plan_with_shape(
        self,
        *,
        scenario: ScenarioBrief,
        candidates: list[Any],
        budget_seconds: int,
        pace: Any,
        input_mode: InputMode,
        errata_targets: list[Any],
        dice: DayShapeInputs,
        decision: Any,
        scenario_result: ScenarioBrief,
        first_day: bool = False,
        introduction: Any = None,
    ) -> Any:
        """Call the planner with WP-66's arguments, or without them.

        The planner is reached through an adapter, and an adapter built before
        this package — a stub in a test, an older deployment's module — has a
        ``plan_journey`` that has never heard of a day shape. Passing the new
        keywords to it would be a ``TypeError`` on the learner's only path into
        their day, so the shape arguments are offered and dropped rather than
        forced. Dropping them yields the standard day, which is exactly what
        that planner would have built anyway.
        """

        plan_journey = self.adapters.planner.plan_journey
        base: dict[str, Any] = {
            "scenario": scenario,
            "candidates": candidates,
            "budget_seconds": budget_seconds,
            "pace": pace,
            "input_mode": input_mode,
            "errata_targets": errata_targets,
        }
        try:
            accepted = set(inspect.signature(plan_journey).parameters)
        except (TypeError, ValueError):  # pragma: no cover - exotic callables
            accepted = set()
        if "day_shape" not in accepted:
            return plan_journey(**base)
        story = (
            scenario_result.story_context
            if isinstance(scenario_result.story_context, dict)
            else {}
        )
        recap = story.get("chapter_recap_fr") or story.get("chapter_recap")
        if first_day and "first_day" in accepted:
            base["first_day"] = True
        elif "practice" in accepted and settings.ATELIER_JOURNEY_PRACTICE_DAY_ENABLED:
            # WP-78: quick items around the one open reply.
            base["practice"] = True
            if introduction and "introduction" in accepted:
                # WP-L4: today's new grammar unit, its rule and guided items.
                base["introduction"] = introduction
        return plan_journey(
            **base,
            day_shape=decision.shape,
            shape_reason=decision.reason,
            dice=dice,
            letter=dice.letter,
            chapter_recap_fr=str(recap).strip() if recap else None,
            audio_available=dice.audio_available,
        )

    def _errata_targets(self, user: User) -> list[Any]:
        """The learner's ranked due errata. A broken queue is never fatal.

        WP-24 owns the ranking; this reads it. The read must not reschedule
        anything (pinned in ``tests/test_wp24_mistake_loop.py``), and a failure
        here costs the because-line and the erratum's priority — never the
        learner's day.
        """

        return run_best_effort(
            self.db,
            "daily_journey: errata targets",
            lambda: list(errata_targets_for_user(self.db, user)),
            default=[],
            log=logger,
        )

    def _plan_because(
        self, plan: Any, candidates: list[Any], errata: list[Any]
    ) -> dict[str, Any] | None:
        """The because payload for the target the plan actually kept, or None.

        Resolved through the planner adapter rather than imported, for the same
        reason ``PlanUnavailable`` is: the state machine owns no domain logic.
        """

        if not errata:
            return None
        plan_because = getattr(self.adapters.planner, "plan_because", None)
        merge = getattr(self.adapters.planner, "merge_errata_candidates", None)
        if not callable(plan_because):
            return None
        try:
            merged = merge(candidates, errata) if callable(merge) else candidates
            payload = plan_because(plan, list(merged), errata)
        except Exception:  # pragma: no cover - defensive
            logger.exception("daily_journey: because-line unavailable")
            return None
        if not payload:
            return None
        # Validated here so an unprintable payload is dropped at write time
        # rather than 500-ing every subsequent GET /today.
        try:
            return JourneyBecause.model_validate(payload).model_dump(mode="json")
        except Exception:
            logger.warning("daily_journey: because payload rejected by the schema")
            return None

    def _persist_plan(
        self,
        journey: DailyJourney,
        brief: ScenarioBrief,
        plan: Any,
        input_mode: InputMode,
        *,
        because: dict[str, Any] | None = None,
        fallback: dict[str, Any] | None = None,
    ) -> None:
        for existing in list(journey.steps):
            journey.steps.remove(existing)
        self.db.flush()

        first_step_id: uuid.UUID | None = None
        for planned in sorted(plan.steps, key=lambda item: item.ordinal):
            kind = StepKind(planned.kind)
            public_prompt = dict(planned.public_prompt)
            private_task: dict[str, Any] = {}

            if kind is StepKind.SCENE:
                # The pinned brief lives with the scene step: private by
                # construction, and never part of any public projection.
                private_task["scenario_brief"] = _brief_to_json(brief)
            elif kind is StepKind.RECALL and isinstance(planned.private_task, RecallTask):
                private_task["recall_task"] = _recall_task_to_json(planned.private_task)
            elif kind is StepKind.RESPOND and isinstance(
                planned.private_task, ResponseTask
            ):
                private_task["response_task"] = _response_task_to_json(
                    planned.private_task
                )
                # The planner owns the offered modalities; only fill in the
                # always-available fallback if it said nothing at all.
                public_prompt.setdefault(
                    "input_modes",
                    ["text", "voice"] if input_mode is InputMode.VOICE else ["text"],
                )
            elif kind is StepKind.RULE:
                # WP-L4: which unit advancing this step introduces.
                private_task["concept_id"] = public_prompt.get("concept_id")
            elif kind is StepKind.RESOLUTION:
                private_task["resolution_lines"] = dict(brief.resolution_lines)
                private_task["resolution_summaries"] = dict(brief.resolution_summaries)
                private_task["allowed_outcomes"] = list(
                    brief.response_task.allowed_outcomes
                )

            step = DailyJourneyStep(
                id=uuid.uuid4(),
                ordinal=planned.ordinal,
                kind=str(kind),
                # The planner decides the initial status: a target the learner
                # already produced independently arrives SKIPPED, and turning
                # that back into a mandatory drill would be the old ladder.
                status=str(planned.initial_status or StepStatus.PENDING),
                estimated_seconds=planned.estimated_seconds,
                optional=bool(planned.optional),
                target_kind=str(planned.target.kind) if planned.target else None,
                target_id=planned.target.id if planned.target else None,
                public_prompt=public_prompt,
                private_task=private_task,
                assistance_used=[],
            )
            journey.steps.append(step)
            if first_step_id is None and StepStatus(step.status) is StepStatus.PENDING:
                step.status = str(StepStatus.ACTIVE)
                step.started_at = _utcnow()
                first_step_id = step.id

        journey.current_step_id = first_step_id
        journey.content_version = brief.content_version
        journey.level_band = brief.level_band
        # Composite "{kind}:{id}" identities, stored verbatim: a vocabulary row
        # and a grammar concept can share a primary key, so splitting them would
        # merge two different targets.
        journey.plan_selection = {
            "selected_target_ids": list(plan.selected_target_ids),
            "omitted_candidate_ids": list(plan.omitted_candidate_ids),
            "rationale": plan.rationale,
            # WP-24's because-line, stored with the plan that earned it. It is
            # never recomputed on read: the claim is about the scene the
            # learner actually has, not about the queue as it stands now.
            "because": because,
            # WP-66. The day's shape and why the dice dealt it, stored with the
            # plan that was built for it. Inside the existing JSON column on
            # purpose: no migration, and an old row with no key reads back as
            # the standard day it was.
            "day_shape": str(getattr(plan, "day_shape", None) or DEFAULT_DAY_SHAPE),
            "shape_reason": str(getattr(plan, "shape_reason", "") or ""),
            # WP-78. Telemetry: a practice day, and what it poses.
            "practice": bool(getattr(plan, "practice", False)),
        }
        if fallback:
            # WP-69. The story engine could not write this day and an authored
            # scene stands in. Telemetry only — nothing public reads it, and the
            # learner is never shown a "fallback" label.
            journey.plan_selection["generation_fallback"] = dict(fallback)
        journey.estimated_active_seconds = plan.estimated_active_seconds
        journey.serial_thread_id = brief.serial_thread_id
        journey.serial_episode_id = brief.serial_episode_id
        journey.scenario_snapshot = ScenarioDescriptor.model_validate(
            brief.public_descriptor()
        ).model_dump(mode="json")
        self.db.flush()

    # ------------------------------------------------------------------
    # Internals — attempts
    # ------------------------------------------------------------------

    def _normalize_attempt(
        self, user: User, payload: JourneyAttemptRequest
    ) -> AttemptAnswer:
        data = payload.input
        mode = InputMode.VOICE if data.mode == "voice" else InputMode.TEXT
        text = getattr(data, "text", "") or ""
        option_id = getattr(data, "option_id", None)
        tile_ids = list(getattr(data, "tile_ids", []) or [])
        transcript_ref = getattr(data, "transcript_ref", None)

        if transcript_ref:
            self._require_owned_transcript(user, transcript_ref)

        answer = AttemptAnswer(
            mode=mode,
            text=normalize_answer_text(text),
            option_id=option_id,
            tile_ids=tile_ids,
            transcript_ref=transcript_ref,
        )
        if answer.is_blank:
            # 422 before any receipt: a blank answer must not consume the key,
            # a turn, an attempt record, a lapse, or any credit.
            raise journey_error(
                http_status.HTTP_422_UNPROCESSABLE_CONTENT,
                JourneyErrorCode.EMPTY_ANSWER,
                "Write or say something first.",
            )
        return answer

    def _require_owned_transcript(self, user: User, transcript_ref: str) -> None:
        """Contract revision 1: transcripts are not persisted anywhere.

        The check is vacuous, not skipped. Nothing in the schema can attribute a
        transcript id to a caller today, so any supplied reference is refused
        with the non-disclosing 404. If persistence is added, resolve ownership
        here and the check turns on with no call-site change.
        """

        raise _not_found()

    def _attempt_recall(
        self,
        user: User,
        journey: DailyJourney,
        step: DailyJourneyStep,
        answer: AttemptAnswer,
        expected_revision: int,
    ) -> AttemptResult:
        task = _recall_task_from_json(dict(step.private_task or {})["recall_task"])
        assistance = self._step_assistance(step)
        evaluation = self.adapters.learning.evaluate_recall(
            self.db, user=user, task=task, answer=answer, assistance=assistance
        )
        if evaluation.pending:
            return self._pending_result(journey, assistance)

        # The provider call is done; only now is the revision verified and taken.
        self._claim_revision(journey, expected_revision)
        applied = self._apply_evidence(user, journey, step, evaluation, answer.mode)
        step.evidence_ref = applied.evidence_ref
        step.status = str(StepStatus.COMPLETED)
        step.completed_at = _utcnow()
        step.turns_used += 1
        self._store_step_result(step, evaluation, assistance)
        self.db.flush()

        return AttemptResult(
            evidence_ref=applied.evidence_ref,
            task_outcome=evaluation.outcome,
            assistance_level=assistance,
            correction=self._public_correction(evaluation.correction, answer.text),
            character_reply_fr=None,
            next_turn=None,
            pending=False,
            journey=self.snapshot(journey),
        )

    def _attempt_respond(
        self,
        user: User,
        journey: DailyJourney,
        step: DailyJourneyStep,
        answer: AttemptAnswer,
        expected_revision: int,
    ) -> AttemptResult:
        private = dict(step.private_task or {})
        task = _response_task_from_json(private["response_task"])
        brief = self._pinned_brief(journey)
        assistance = self._step_assistance(step)
        history = list(private.get("turns", []))

        evaluation = self.adapters.conversation.evaluate_response(
            self.db,
            user=user,
            scenario=brief,
            task=task,
            answer=answer,
            turn_index=step.turn_index,
            assistance=assistance,
            history=history,
        )
        if evaluation.pending:
            return self._pending_result(journey, assistance)
        evaluation = self._with_concept_evidence(task, answer, evaluation)

        # The provider call is done; only now is the revision verified and taken.
        self._claim_revision(journey, expected_revision)
        applied = self._apply_evidence(user, journey, step, evaluation, answer.mode)
        step.evidence_ref = applied.evidence_ref
        if evaluation.turn_consumed:
            step.turns_used += 1
        history.append(
            {
                "learner": answer.text,
                "character": evaluation.character_reply_fr or "",
            }
        )
        private["turns"] = history
        # Persisted before the ending is settled: WP-06 renders the resolution
        # from the learner's own turns, and the decisive one is this turn.
        step.private_task = private

        # CONTRACTS §3: two normal turns PLUS one optional repair, not two in
        # total. WP-06 owns the arithmetic.
        budget = self.adapters.conversation.turn_budget(task)
        repair_available = evaluation.needs_repair and step.turns_used < budget
        next_turn: NextTurn | None = None
        if repair_available:
            step.turn_index += 1
            prompt = dict(step.public_prompt or {})
            prompt["turn_index"] = step.turn_index
            if evaluation.character_reply_fr:
                prompt["character_line_fr"] = evaluation.character_reply_fr
            prompt["repair_allowed"] = False
            step.public_prompt = prompt
            next_turn = NextTurn(
                step_id=str(step.id), prompt=RespondPrompt.model_validate(prompt)
            )
        else:
            step.status = str(StepStatus.COMPLETED)
            step.completed_at = _utcnow()
            # The resolution the learner is shown must be the one that was
            # actually derived — never the planner's optimistic default.
            self._settle_resolution(
                user, journey, brief, task, proposal=evaluation.consequence
            )

        self._store_step_result(step, evaluation, assistance)
        self.db.flush()
        # After the turn's own flush, and inside a savepoint: a telemetry row
        # must not be able to take a graded turn down with it.
        self._record_feedback_decision(user, journey, step, evaluation)
        # Last, because it is the only thing here that reaches outside the
        # journey: on «jour de lettre» the turn the learner just took *is* the
        # answer to a Courrier letter, and the Courrier must stop waiting for it.
        if step.status == str(StepStatus.COMPLETED):
            self._finish_answered_letter(user, journey, step, evaluation)

        return AttemptResult(
            evidence_ref=applied.evidence_ref,
            task_outcome=evaluation.outcome,
            assistance_level=assistance,
            correction=self._public_correction(evaluation.correction, answer.text),
            character_reply_fr=evaluation.character_reply_fr,
            reply_source=self._reply_source(evaluation),
            next_turn=next_turn,
            pending=False,
            journey=self.snapshot(journey),
        )

    def _with_concept_evidence(
        self, task: ResponseTask, answer: AttemptAnswer, evaluation: Any
    ) -> Any:
        """WP-L4 «Emploi»: the reply's grammar units, read by their detectors."""

        if not any(str(target.kind) == str(TargetKind.GRAMMAR) for target in task.targets):
            return evaluation
        from app.services.concept_evidence import with_concept_evidence

        return run_best_effort(
            self.db,
            "daily_journey: concept evidence",
            lambda: with_concept_evidence(
                self.db,
                evaluation=evaluation,
                task=task,
                text=normalize_answer_text(answer.text),
                modality=answer.mode,
            ),
            default=evaluation,
            log=logger,
        )

    def _record_feedback_decision(
        self,
        user: User,
        journey: DailyJourney,
        step: DailyJourneyStep,
        evaluation: Any,
    ) -> None:
        """WP-36 §8.4: make the self-repair loop countable.

        The package's own question — *does a prompted repair succeed more often
        than a recast?* — was unanswerable because the decision was taken, acted
        on and thrown away. One row per graded respond turn records the reason
        and nothing else: no learner text, no correction, no character line.

        The interesting reasons are the ones where the policy stayed quiet.
        ``repair_not_attempted`` is a learner who was asked « Pardon, un ou une
        café ? » and answered something else — no uptake, which is precisely the
        arm the evidence is being compared against. ``no_open_errata`` is every
        other turn in the app and is not written: a row per turn saying "nothing
        applied" would bury the six that mean something.

        Telemetry, so it never breaks a turn: the flow owns the transaction and
        a failure here is logged and swallowed.
        """

        reason = str(getattr(evaluation, "feedback_reason", "") or "")
        if not reason or reason == "no_open_errata":
            return
        try:
            from app.services.pilot_events import PilotEventService

            # The row is written inside a SAVEPOINT so that a ledger that is
            # unavailable — or a column that has drifted — rolls back this row
            # alone. Without it the failure surfaces on the *next* flush, which
            # is the transaction that carries the learner's turn.
            with self.db.begin_nested():
                PilotEventService(self.db).record(
                    SELF_REPAIR_EVENT_TYPE,
                    user_id=user.id,
                    entity_type="daily_journey_step",
                    entity_id=str(step.id),
                    payload={
                        "reason": reason,
                        "journey_id": str(journey.id),
                        "turn_index": int(step.turn_index),
                        "outcome": str(evaluation.outcome),
                        # Whether the turn actually carried a question to the
                        # learner. A reason alone cannot say so: `repair_failed`
                        # shows a correction, `recurrence` shows a question.
                        "elicited": bool(evaluation.needs_repair),
                    },
                )
        except Exception:  # pragma: no cover - telemetry must never break a turn
            logger.exception("daily_journey: self-repair telemetry failed")

    def _pending_result(
        self, journey: DailyJourney, assistance: AssistanceLevel
    ) -> AttemptResult:
        """Grade error/timeout: retryable, never a learner failure."""

        return AttemptResult(
            evidence_ref="",
            task_outcome=TaskOutcome.UNSCORED,
            assistance_level=assistance,
            correction=None,
            character_reply_fr=None,
            next_turn=None,
            pending=True,
            journey=self.snapshot(journey),
        )

    def _apply_evidence(
        self,
        user: User,
        journey: DailyJourney,
        step: DailyJourneyStep,
        evaluation: Any,
        modality: InputMode,
    ) -> AppliedEvidence:
        session = None
        if journey.learning_session_id is not None:
            from app.db.models.session import LearningSession

            session = self.db.get(LearningSession, journey.learning_session_id)
        return self.adapters.learning.apply_learning_evidence(
            self.db,
            user=user,
            journey_id=journey.id,
            step_id=step.id,
            session=session,
            evaluation=evaluation,
            modality=modality,
            # WP-09's 24-hour rubric needs the learner-local observation date.
            timezone=journey.timezone,
        )

    def _respond_learner_texts(self, journey: DailyJourney) -> list[str]:
        """Everything the learner actually said in the respond step, in order."""

        respond = next(
            (
                step
                for step in journey.steps
                if StepKind(step.kind) is StepKind.RESPOND
            ),
            None,
        )
        if respond is None:
            return []
        turns = (respond.private_task or {}).get("turns") or []
        texts: list[str] = []
        for turn in turns:
            if isinstance(turn, dict):
                text = str(turn.get("learner") or "").strip()
                if text:
                    texts.append(text)
        return texts

    def _finish_answered_letter(
        self,
        user: User,
        journey: DailyJourney,
        step: DailyJourneyStep,
        evaluation: Any,
    ) -> None:
        """WP-66 ⋈ WP-64 — the letter the learner just answered is answered.

        On «jour de lettre» the respond step *is* the reply to a real Courrier
        letter. Finishing it here, through `MissionScheduler.complete`, is what
        keeps the two surfaces from contradicting each other: the mission's
        writeback into the living story, its `kept | partial | missed` outcome,
        the correspondent's mood step and the chain's next instalment all happen
        exactly once, and the letter is no longer sitting in the Courrier as
        unanswered — which is what a learner who just answered it would find
        unforgivable.

        Idempotent three ways: the step remembers that it paid (a replayed
        mutation re-runs this method), the mission carries at most one journey
        attempt, and `complete()` returns early on a finished mission.

        Never fatal. A Courrier that cannot be reached costs the letter's
        bookkeeping, never the turn the learner has already taken and already
        been graded on.
        """

        prompt = step.public_prompt if isinstance(step.public_prompt, dict) else {}
        letter = prompt.get("letter") if isinstance(prompt.get("letter"), dict) else None
        mission_id = str((letter or {}).get("mission_id") or "")
        if not mission_id:
            return
        private = dict(step.private_task or {})
        if private.get("letter_answered"):
            return
        try:
            from app.services import story_correspondence as courrier

            mission = courrier.answer_letter_from_journey(
                self.db,
                user=user,
                mission_id=mission_id,
                learner_text=" ".join(self._respond_learner_texts(journey)),
                outcome=str(getattr(evaluation, "outcome", "") or ""),
                # What the journey actually observed the learner produce. The
                # letter's optional objectives are marked met from this and from
                # nothing else, so a word the letter hoped for and the reply
                # never used stays unmet.
                produced_target_ids=_produced_target_ids(evaluation),
                language=getattr(user, "native_language", None),
            )
        except Exception:
            logger.exception("daily_journey: the answered Courrier letter could not be filed")
            return
        if mission is None:
            return
        private["letter_answered"] = {
            "mission_id": mission_id,
            "outcome": str(getattr(mission, "outcome", "") or ""),
        }
        step.private_task = private
        self.db.add(step)
        self.db.flush()

    def _rendered_ending(
        self,
        renderer: Any,
        brief: ScenarioBrief,
        outcome_key: str,
        learner_texts: list[str],
        *,
        fallback: str,
    ) -> str:
        """One ending string, always rendered, never a raw authored template.

        WP-06 owns the wording; ``learner_texts`` is what lets it name the
        learner's real choice. The keyword is passed only when the conversation
        seam accepts it, so an older or stubbed adapter still returns its
        unpersonalised ending instead of raising.
        """

        try:
            accepts = "learner_texts" in inspect.signature(renderer).parameters
        except (TypeError, ValueError):  # pragma: no cover - exotic callables
            accepts = False
        rendered = (
            renderer(brief, outcome_key, learner_texts=learner_texts)
            if accepts
            else renderer(brief, outcome_key)
        )
        if rendered is not None:
            return str(rendered)
        # The pinned brief has no line for this key; the plan's own private copy
        # is the last resort, and it goes through the same renderer so an
        # unfilled slot can never reach a learner.
        render = getattr(self.adapters.conversation, "render_authored_text", None)
        return str(render(fallback)) if callable(render) else str(fallback or "")

    def _settle_resolution(
        self,
        user: User,
        journey: DailyJourney,
        brief: ScenarioBrief,
        task: ResponseTask,
        *,
        proposal: StoryOutcomeProposal | None,
    ) -> None:
        """Render the ending that was actually earned.

        Integration-owner rule (2026-09-05): WP-04 bakes an optimistic default
        into the plan — for ``arrange_meeting`` that is
        ``meeting_saturday_market``. Showing it to a learner who agreed nothing
        would be a false completion. So:

        * a derived consequence wins;
        * otherwise WP-06's **neutral** ``default_outcome_key`` is used, never
          the planner's.

        The line and summary are then re-rendered for whichever key won, before
        the resolution step can be shown — and re-rendered *from the learner's
        own words*, so the ending names the drink they actually ordered rather
        than the one the authored template happened to mention (WP-12 D-2).
        """

        resolution = next(
            (
                step
                for step in journey.steps
                if StepKind(step.kind) is StepKind.RESOLUTION
            ),
            None,
        )
        if resolution is None:
            return
        if brief.story_context:
            from app.services.living_story import StoryUnavailable, settle_resolution
            try:
                settle_resolution(self.db, user=user, journey=journey, brief=brief, resolution=resolution, proposal=proposal)
            except StoryUnavailable as exc:
                raise journey_error(409, JourneyErrorCode.VERSION_CONFLICT, "The story changed. Refresh and retry your answer.", current_revision=journey.revision, refresh_href=refresh_href_for(journey.id)) from exc
            self._attach_register_line(user, journey, resolution)
            return

        private = dict(resolution.private_task or {})
        allowed = list(private.get("allowed_outcomes", []))
        scenario_key = str(brief.scenario_key)

        outcome_key: str | None = None
        if proposal is not None:
            if allowed and proposal.outcome_key not in allowed:
                logger.warning(
                    "daily_journey: refusing undeclared outcome %r", proposal.outcome_key
                )
            else:
                outcome_key = proposal.outcome_key
        if outcome_key is None:
            outcome_key = self.adapters.conversation.default_outcome_key(
                task, scenario_key
            )
        if outcome_key is None:
            private["resolution_settled"] = True
            resolution.private_task = private
            return

        prompt = dict(resolution.public_prompt or {})
        prompt["outcome_key"] = outcome_key
        learner_texts = self._respond_learner_texts(journey)
        line = self._rendered_ending(
            self.adapters.conversation.resolution_line,
            brief,
            outcome_key,
            learner_texts,
            fallback=private.get("resolution_lines", {}).get(outcome_key, ""),
        )
        summary = self._rendered_ending(
            self.adapters.conversation.resolution_summary,
            brief,
            outcome_key,
            learner_texts,
            fallback=private.get("resolution_summaries", {}).get(outcome_key, ""),
        )
        prompt["character_line_fr"] = line
        prompt["summary_native"] = summary
        resolution.public_prompt = prompt
        self._attach_register_line(user, journey, resolution)

        if proposal is not None and outcome_key == proposal.outcome_key:
            outcome_ref = self.adapters.conversation.apply_story_outcome(
                self.db,
                user=user,
                journey_id=journey.id,
                scenario=brief,
                proposal=proposal,
                # WP-06's canonical key. Its ledger dedupes on the
                # ``journey:{id}:`` prefix and rejects anything else.
                source_key=self.adapters.conversation.story_outcome_source_key(
                    journey.id
                ),
            )
            private["story_outcome"] = {
                "serial_thread_id": outcome_ref.serial_thread_id,
                "serial_episode_id": outcome_ref.serial_episode_id,
                "outcome_key": outcome_ref.outcome_key,
                "callback_fr": outcome_ref.callback_fr,
            }
            # The callback fact is a bounded memory fragment for the serial ledger
            # ("un café en terrasse"), not dialogue. Integration owner 2026-09-05:
            # appending it to the character's spoken line produced
            # "Parfait. Un café en terrasse, ça arrive. un café en terrasse" — a
            # duplicated lowercase fragment in Margaux's mouth. It reaches the
            # learner through the recap's story_outcome instead.
        private["resolution_settled"] = True
        resolution.private_task = private

    def _attach_register_line(
        self, user: User, journey: DailyJourney, resolution: DailyJourneyStep
    ) -> None:
        """WP-66 / WP-33: show the register the learner was already graded on.

        One French line under the ending, plus why it matters in the learner's
        own language. Nothing is written when the dimension was *not evaluated*
        — no counterpart register to hold, or a conversation that addressed
        nobody — because "non évalué" is neither a pass nor a failure and the
        honest rendering of it is no line at all.

        Never fatal: the day's ending does not depend on this sentence.
        """

        try:
            # The turn that decides the verdict was recorded moments ago and is
            # still pending in this transaction. Flush it first: the register
            # reader queries the step row, and reading the exchange without the
            # last thing the learner said would grade half a conversation.
            self.db.flush()
            line = build_journey_register_line(
                self.db,
                user=user,
                journey_id=journey.id,
                control_language=normalize_control_language(user.native_language),
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("daily_journey: register line unavailable")
            return
        if line is None:
            return
        prompt = dict(resolution.public_prompt or {})
        prompt["register_note_fr"] = line.line_fr
        prompt["register_reason_native"] = line.reason_native
        resolution.public_prompt = prompt

    def _settle_resolution_if_unsettled(
        self, user: User, journey: DailyJourney
    ) -> None:
        """Neutral ending for a journey that never produced a consequence."""

        resolution = next(
            (
                step
                for step in journey.steps
                if StepKind(step.kind) is StepKind.RESOLUTION
            ),
            None,
        )
        if resolution is None or (resolution.private_task or {}).get(
            "resolution_settled"
        ):
            return
        respond = next(
            (
                step
                for step in journey.steps
                if StepKind(step.kind) is StepKind.RESPOND
            ),
            None,
        )
        if respond is None:
            return
        try:
            brief = self._pinned_brief(journey)
            task = _response_task_from_json(
                dict(respond.private_task or {})["response_task"]
            )
        except (HTTPException, KeyError):  # pragma: no cover - defensive
            return
        self._settle_resolution(user, journey, brief, task, proposal=None)

    def _store_step_result(
        self, step: DailyJourneyStep, evaluation: Any, assistance: AssistanceLevel
    ) -> None:
        private = dict(step.private_task or {})
        private["result"] = {
            "outcome": str(evaluation.outcome),
            "assistance_level": str(assistance),
            "observations": [
                {
                    "target": _target_to_json(observation.target),
                    "evidence_kind": str(observation.evidence_kind),
                    "assistance_level": str(observation.assistance),
                    "modality": str(observation.modality),
                }
                for observation in evaluation.observations
            ],
        }
        concept_evidence = list(getattr(evaluation, "concept_evidence", None) or [])
        if concept_evidence:
            # WP-L4: what the reply showed about each grammar unit (WP-L7 reads it).
            history = list(private.get("concept_evidence") or [])
            history.extend(concept_evidence)
            private["concept_evidence"] = history
            private["result"]["concept_evidence"] = concept_evidence
        step.private_task = private

    @staticmethod
    def _public_correction(
        correction: Correction | None, learner_text: str
    ) -> JourneyCorrection | None:
        """At most one foreground correction, and never a fabricated span.

        The span is checked against the **normalized** answer: WP-06 builds
        spans from ``normalize_answer_text``, so comparing against a raw string
        would silently drop a correct correction that contains an apostrophe.
        """

        if correction is None or not correction.is_valid_for(
            normalize_answer_text(learner_text)
        ):
            return None
        return JourneyCorrection(
            span_fr=correction.span_fr,
            corrected_fr=correction.corrected_fr,
            note_native=correction.note_native,
        )

    def _reply_source(self, evaluation: Any) -> str:
        """Provenance of the character reply, straight from WP-06.

        An authored line shown as a live model response would be a lie about
        what the learner is talking to, so this is surfaced, not inferred.
        """

        if not getattr(evaluation, "character_reply_fr", None):
            return "none"
        try:
            source = self.adapters.conversation.reply_source(evaluation)
        except AdapterUnavailable:
            raise
        except Exception:  # pragma: no cover - defensive
            logger.exception("daily_journey: reply provenance unavailable")
            return "none"
        return source if source in {"authored", "model", "none"} else "none"

    def _pinned_brief(self, journey: DailyJourney) -> ScenarioBrief:
        """The brief this journey was planned with, never a fresher one.

        The whole brief is persisted with the scene step, so a content bump or a
        learner level change cannot swap the variant mid-journey. If that
        snapshot is ever missing, fall back to WP-03's pinned lookup using the
        stored ``content_version`` and ``level_band`` — still not the latest.
        """

        for step in journey.steps:
            payload = (step.private_task or {}).get("scenario_brief")
            if payload:
                return _brief_from_json(payload)
        resolve = getattr(self.adapters.content, "resolve_scenario_brief", None)
        scenario_key = (journey.scenario_snapshot or {}).get("scenario_key")
        if callable(resolve) and scenario_key:
            resolved = resolve(
                self.db,
                user=self.db.get(User, journey.user_id),
                scenario_key=scenario_key,
                content_version=journey.content_version or None,
                level_band=journey.level_band or None,
                input_mode=InputMode.TEXT,
                allow_generation=False,
                bind_serial=False,
            )
            if isinstance(resolved, ScenarioBrief):
                return resolved
        raise journey_error(
            http_status.HTTP_409_CONFLICT,
            JourneyErrorCode.JOURNEY_NOT_ACTIVE,
            "This journey has no pinned content.",
            current_revision=journey.revision,
            refresh_href=refresh_href_for(journey.id),
        )

    def _help_content(
        self, step: DailyJourneyStep, help_kind: HelpKind
    ) -> tuple[str | None, str | None]:
        private = dict(step.private_task or {})
        kind = StepKind(step.kind)
        if kind is StepKind.RECALL:
            task = _recall_task_from_json(private["recall_task"])
            available = {
                HelpKind.HINT: (None, task.hint_native),
                HelpKind.TRANSLATION: (None, task.translation_native),
                HelpKind.SOLUTION: (task.solution_fr, None),
            }
        else:
            response = _response_task_from_json(private["response_task"])
            available = {
                HelpKind.HINT: (None, response.hint_native),
                HelpKind.TRANSLATION: (None, response.translation_native),
                HelpKind.SUGGESTED_RESPONSE: (
                    response.suggested_response_fr,
                    response.translation_native,
                ),
            }
        if help_kind not in available:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "help_unavailable",
                    "message": "That kind of help is not offered on this step.",
                },
            )
        content_fr, content_native = available[help_kind]
        if content_fr is None and content_native is None:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "help_unavailable",
                    "message": "That kind of help is not offered on this step.",
                },
            )
        return content_fr, content_native

    # ------------------------------------------------------------------
    # Internals — recap
    # ------------------------------------------------------------------

    def _journey_capability_evidence(
        self, user: User, journey: DailyJourney
    ) -> list[CapabilityEvidence]:
        """Ask WP-09 what this journey proved. WP-02 never decides that itself.

        The seam is deliberate: the recap and ``GET /capabilities/progress``
        read the same rubric over the same canonical evidence, so the same
        journey cannot be ``independent_once`` in one place and ``not_tried``
        in the other.
        """

        view = getattr(
            self.adapters.capabilities, "build_journey_capability_evidence", None
        )
        if not callable(view):
            # An older seam has no per-journey rubric. Claim nothing rather
            # than fall back to a second, simplified rule.
            return []
        try:
            items = view(
                self.db,
                user=user,
                journey_id=journey.id,
                control_language=normalize_control_language(user.native_language),
            )
        except AdapterUnavailable:
            raise
        except Exception:  # pragma: no cover - defensive
            logger.exception("daily_journey: capability evidence lookup failed")
            return []
        return [
            CapabilityEvidence(
                capability_key=item.capability_key,
                state=item.state,
                modality=item.modality,
                observed_on=item.observed_on,
                context_native=item.context_native,
            )
            for item in items
        ]

    def _build_recap(
        self, user: User, journey: DailyJourney, finish_kind: str
    ) -> JourneyRecap:
        practiced: list[PracticedTarget] = []
        objective_outcome = TaskOutcome.NOT_YET
        story_outcome: StoryOutcome | None = None
        next_focus: NextFocus | None = None

        for step in sorted(journey.steps, key=lambda item: item.ordinal):
            private = dict(step.private_task or {})
            result = private.get("result")
            if result:
                for observation in result.get("observations", []):
                    practiced.append(
                        PracticedTarget.model_validate(
                            {
                                "target": observation["target"],
                                "evidence_kind": observation["evidence_kind"],
                                "assistance_level": observation["assistance_level"],
                                # WP-16 / D-0: the recap points into the drill
                                # loop for what this scene actually practised.
                                "practice_href": _target_practice_href(
                                    observation["target"]
                                ),
                            }
                        )
                    )
                    if (
                        next_focus is None
                        and observation["evidence_kind"] == str(EvidenceKind.NOT_YET)
                    ):
                        next_focus = NextFocus(
                            target=observation["target"],
                            reason_native="Not yet — this one comes back tomorrow.",
                        )
            if StepKind(step.kind) is StepKind.RESPOND and result:
                objective_outcome = TaskOutcome(result["outcome"])
            if StepKind(step.kind) is StepKind.RESOLUTION and private.get(
                "story_outcome"
            ):
                story_outcome = StoryOutcome.model_validate(private["story_outcome"])

        # WP-09 owns the CONTRACTS §8 rubric. WP-02 asks it what this journey
        # proved and reports that verbatim; it has no rubric of its own, so the
        # recap and GET /capabilities/progress cannot disagree. A journey that
        # proved nothing yields [] — never an inferred claim.
        capability_evidence = self._journey_capability_evidence(user, journey)
        collectible_ids: list[str] = []
        scenario_key = (journey.scenario_snapshot or {}).get("scenario_key")
        if (
            finish_kind == "complete"
            and objective_outcome is TaskOutcome.MET
            and scenario_key
        ):
            try:
                keepsake = self.adapters.capabilities.mint_journey_keepsake(
                    self.db,
                    user=user,
                    journey_id=journey.id,
                    scenario_key=str(scenario_key),
                    completion_kind=finish_kind,
                )
                collectible_ids = list(keepsake.collectible_ids)
            except AdapterUnavailable:
                raise
            except Exception:  # pragma: no cover - defensive
                logger.exception("daily_journey: keepsake minting failed")

        return JourneyRecap(
            completion_kind="complete" if finish_kind == "complete" else "early",
            objective_outcome=objective_outcome,
            practiced_targets=practiced,
            capability_evidence=capability_evidence,
            next_focus=next_focus,
            collectible_ids=collectible_ids,
            story_outcome=story_outcome,
            # WP-02 does not measure active time; a fabricated number would be
            # worse than an honest null (CONTRACTS §9).
            active_seconds=self._measure_active_seconds(journey),
            # WP-79: streak-free reward facts (the streak rides on the
            # snapshot): words, the character's mood, the keepsake, the
            # teaser and a level move — each read, none invented.
            **self._recap_extras(user, journey, practiced, collectible_ids),
        )

    def _recap_extras(
        self,
        user: User,
        journey: DailyJourney,
        practiced: list[PracticedTarget],
        collectible_ids: list[str],
    ) -> dict[str, Any]:
        from app.services.achievement_recap import recap_extras

        try:
            return recap_extras(
                self.db,
                user=user,
                journey=journey,
                practiced=practiced,
                collectible_ids=collectible_ids,
            )
        except Exception:  # pragma: no cover - a reward is never worth the day
            logger.exception("daily_journey: WP-79 recap extras failed")
            return {}

    # ------------------------------------------------------------------
    # Internals — events
    # ------------------------------------------------------------------

    def _emit_resume_conflict(
        self,
        journey: DailyJourney,
        conflict_kind: str,
        *,
        expected_revision: int | None = None,
    ) -> None:
        """A client came back holding a stale view. Diagnostic only, never fatal."""

        record = getattr(self.adapters.events, "record_resume_conflict", None)
        if not callable(record):
            return
        try:
            record(
                self.db,
                user_id=journey.user_id,
                journey_id=journey.id,
                conflict_kind=conflict_kind,
                expected_revision=expected_revision,
                current_revision=journey.revision,
            )
        except Exception:  # pragma: no cover - telemetry must never break a flow
            logger.exception("daily_journey: resume-conflict event failed")

    def _measure_active_seconds(self, journey: DailyJourney) -> int | None:
        """WP-11 measures this; an unmeasurable day stays None.

        Never the plan's estimate: CONTRACTS §9 wants a real duration or an honest
        absence, and a fabricated number is worse than a null.
        """

        measure = getattr(
            self.adapters.events, "measure_journey_active_seconds", None
        )
        if not callable(measure):
            return None
        try:
            # _build_recap runs before completed_at is set, so the finish instant is
            # the boundary that closes the last open segment.
            return measure(self.db, journey_id=journey.id, until=_utcnow())
        except Exception:  # pragma: no cover - telemetry must not break finish
            logger.exception("daily_journey: active-time measurement failed")
            return None

    def _emit(
        self,
        event_name: JourneyEventName,
        user: User,
        journey: DailyJourney,
        metadata: dict[str, Any],
    ) -> None:
        try:
            # WP-11 owns the payload vocabulary. The seam supplies the standard
            # journey fields (IANA snapshot, learner-local date, level band, budget,
            # revision) so day attribution, idle ceilings and pause discrimination
            # are accurate instead of silently falling back to defaults.
            describe = getattr(self.adapters.events, "journey_event_metadata", None)
            base = describe(journey) if callable(describe) else {}
            self.adapters.events.record_journey_event(
                self.db,
                event_name=str(event_name),
                user_id=user.id,
                source_key=effect_source_key(
                    journey_id=journey.id, effect=str(event_name)
                ),
                metadata={**base, "journey_id": str(journey.id), **metadata},
            )
        except Exception:  # pragma: no cover - telemetry must never break a flow
            logger.exception("daily_journey: event %s failed", event_name)


__all__ = [
    "CANDIDATE_LIMIT",
    "GENERATION_CLAIM_TTL_SECONDS",
    "MAX_GENERATION_ATTEMPTS",
    "MUTATION_PROCESSING_TTL_SECONDS",
    "SELF_REPAIR_EVENT_TYPE",
    "DailyJourneyService",
    "journey_enabled_for",
    "journey_error",
    "local_date_for",
    "resolve_timezone",
]
