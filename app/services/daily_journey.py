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
from sqlalchemy import select, update
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
from app.schemas.daily_journey import (
    AttemptResult,
    CapabilityEvidence,
    CapabilityProgress,
    CapabilitySummary,
    HelpResult,
    JourneyAdvanceRequest,
    JourneyAttemptRequest,
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
)
from app.services.daily_journey_adapters import (
    AdapterUnavailable,
    JourneyAdapters,
    preview_scenario,
)
from app.services.journey_contracts import (
    AppliedEvidence,
    AssistanceLevel,
    AttemptAnswer,
    ContentUnavailable,
    ControlLanguage,
    Correction,
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

logger = logging.getLogger(__name__)

#: A generation claim older than this is recoverable through ``POST /retry``.
GENERATION_CLAIM_TTL_SECONDS = 90
#: A mutation receipt stuck in ``processing`` longer than this is retryable.
MUTATION_PROCESSING_TTL_SECONDS = 60
PROCESSING_RETRY_AFTER_SECONDS = 2
PREPARING_RETRY_AFTER_SECONDS = 3
UNAVAILABLE_RETRY_AFTER_SECONDS = 30
MAX_GENERATION_ATTEMPTS = 3
CANDIDATE_LIMIT = 3
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
    if not raw_cohort:
        return True
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


class DailyJourneyService:
    """Transaction boundary and state machine for the Atelier V2 daily journey."""

    def __init__(self, db: Session, adapters: JourneyAdapters) -> None:
        self.db = db
        self.adapters = adapters

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_today(self, user: User, *, timezone_hint: str | None = None) -> TodayEnvelope:
        enabled = journey_enabled_for(user)
        control_language = normalize_control_language(user.native_language)

        journey = self._occupying_journey(user)
        if journey is None:
            fallback_tz = resolve_timezone(timezone_hint)
            today = local_date_for(fallback_tz)
            journey = self._journey_for_date(user, today)

        timezone_name = journey.timezone if journey else resolve_timezone(timezone_hint)
        today = local_date_for(timezone_name)

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
        )

    def get_journey(self, user: User, journey_id: uuid.UUID) -> JourneySnapshot:
        return self.snapshot(self._journey_or_404(user, journey_id))

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
                    "budget_seconds": payload.budget_seconds,
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
        self._commit_mutation(receipt, journey, status_code, snapshot)
        return snapshot, status_code

    def retry_journey(
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
        self._commit_mutation(receipt, journey, status_code, snapshot)
        return snapshot, status_code

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
            },
        )
        return snapshot

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
                "prompt": dict(step.public_prompt or {}),
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
                "scenario": journey.scenario_snapshot,
                "steps": steps,
                "recap": journey.recap_snapshot,
                "retry": self._retry_hint(journey),
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
                and journey.generation_attempts < MAX_GENERATION_ATTEMPTS,
                "after_seconds": journey.unavailable_retry_after_seconds,
            }
        return None

    def _step_assistance(self, step: DailyJourneyStep) -> AssistanceLevel:
        levels = [AssistanceLevel(value) for value in (step.assistance_used or [])]
        return strongest_assistance(levels)

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

        try:
            offer = self._offer_scenario(user)
        except Exception:  # pragma: no cover - defensive: never break generation
            logger.exception("daily_journey: scenario rotation failed")
            return None
        key = getattr(offer, "scenario_key", None)
        return str(key) if key else None

    def _available_descriptor(self, user: User) -> ScenarioDescriptor | None:
        try:
            result = self._offer_scenario(user)
        except AdapterUnavailable as exc:
            # Nothing is on offer, and saying "available: null" is the honest
            # answer. Creation then refuses with generation_unavailable.
            logger.error(
                "daily_journey: content adapter unavailable (%s)", exc.reason
            )
            return None
        except Exception:  # pragma: no cover - defensive: GET must never 500
            logger.exception("daily_journey: scenario preview failed")
            return None
        if isinstance(result, ContentUnavailable) or result is None:
            return None
        return ScenarioDescriptor.model_validate(result.public_descriptor())

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
                self._reclaim(occupying)
                return self._run_generation(
                    user, occupying, payload.preferred_input_mode
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
                budget_seconds=payload.budget_seconds,
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

    def _reclaim(self, journey: DailyJourney) -> None:
        """Take over an expired claim durably before calling a provider again."""

        journey.generation_claim_id = uuid.uuid4().hex
        journey.generation_claimed_at = _utcnow()
        journey.generation_attempts += 1
        self.db.commit()

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
        if journey.generation_attempts >= MAX_GENERATION_ATTEMPTS:
            raise journey_error(
                http_status.HTTP_503_SERVICE_UNAVAILABLE,
                JourneyErrorCode.GENERATION_UNAVAILABLE,
                "This journey could not be prepared. Try again later.",
                current_revision=journey.revision,
                refresh_href=refresh_href_for(journey.id),
            )
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
        journey.status = str(JourneyStatus.PREPARING)
        journey.unavailable_reason = None
        journey.generation_claim_id = uuid.uuid4().hex
        journey.generation_claimed_at = _utcnow()
        journey.generation_attempts += 1
        journey.revision += 1
        self.db.commit()
        return self._run_generation(user, journey, InputMode.TEXT)

    def _run_generation(
        self, user: User, journey: DailyJourney, input_mode: InputMode
    ) -> tuple[DailyJourney, int]:
        """Phase 2: provider work outside the lock, then verify the claim."""

        if journey.steps:
            # Already planned. Step ids stay stable through a generation retry:
            # never re-plan a journey that already has a persisted plan.
            return self._activate_prepared(journey)

        claim = journey.generation_claim_id
        # The family was chosen and persisted at create time (phase 1), so a
        # generation retry re-serves the same scene instead of rotating under an
        # in-flight journey. Only a journey whose snapshot predates that — or
        # was written without a key — falls back to choosing now.
        scenario_key = (journey.scenario_snapshot or {}).get("scenario_key")
        if not scenario_key:
            scenario_key = self._rotated_offer_key(user)
        try:
            result = self.adapters.content.build_scenario_context(
                self.db, user=user, scenario_key=scenario_key, input_mode=input_mode
            )
        except AdapterUnavailable as exc:
            # The content module exists but is broken. Honest dead end, and a
            # retry cannot help until someone fixes the module.
            logger.error("daily_journey: content adapter unavailable (%s)", exc.reason)
            result = ContentUnavailable(
                reason=f"content_adapter_{exc.reason}",
                retry_after_seconds=0,
                retry_allowed=False,
            )
        except Exception:
            logger.exception("daily_journey: scenario generation failed")
            result = ContentUnavailable(reason="generation_failed")

        self.db.expire(journey)
        fresh = self.db.get(DailyJourney, journey.id)
        if fresh is None:  # pragma: no cover - defensive
            raise _not_found()
        if fresh.generation_claim_id != claim or JourneyStatus(
            fresh.status
        ) is not JourneyStatus.PREPARING:
            # Another worker committed first; its result stands.
            return fresh, http_status.HTTP_200_OK

        if isinstance(result, ContentUnavailable):
            return self._mark_unavailable(
                fresh,
                result.reason,
                retry_allowed=result.retry_allowed,
                retry_after_seconds=result.retry_after_seconds,
            )

        try:
            candidates = self.adapters.learning.select_learning_candidates(
                self.db, user=user, scenario=result, limit=CANDIDATE_LIMIT
            )
            plan = self.adapters.planner.plan_journey(
                scenario=result,
                candidates=list(candidates),
                budget_seconds=fresh.budget_seconds,
                pace=None,
                # WP-04 coordination addition, ratified 2026-09-05: the frozen
                # ScenarioBrief carries no modality, so RespondPrompt.input_modes
                # can only know about voice if the create request says so.
                input_mode=input_mode,
            )
            plan.validate()
        except AdapterUnavailable as exc:
            logger.error("daily_journey: %s adapter unavailable (%s)", exc.module_name, exc.reason)
            return self._mark_unavailable(
                fresh,
                f"{exc.module_name}_{exc.reason}",
                retry_allowed=False,
                retry_after_seconds=0,
            )
        except Exception as exc:
            logger.exception("daily_journey: planning failed")
            if self._is_plan_unavailable(exc):
                # A deterministic content defect (no setup, no ending, too long
                # for five minutes). Retrying identical content cannot help.
                return self._mark_unavailable(
                    fresh,
                    str(getattr(exc, "reason", "plan_unavailable")),
                    retry_allowed=False,
                    retry_after_seconds=0,
                )
            return self._mark_unavailable(fresh, "planning_failed")

        session = None
        try:
            session = self.adapters.learning.ensure_journey_learning_session(
                self.db, user=user, journey_id=fresh.id, scenario_key=str((result.story_context.get("draft") or {}).get("capability_key") or result.scenario_key)
            )
            # WP-05 adds and flushes but never commits; the id exists after flush.
            self.db.flush()
        except AdapterUnavailable as exc:
            # No canonical session means no canonical credit. Refuse the journey
            # rather than running one whose evidence goes nowhere.
            logger.error(
                "daily_journey: learning adapter unavailable (%s)", exc.reason
            )
            return self._mark_unavailable(
                fresh,
                f"{exc.module_name}_{exc.reason}",
                retry_allowed=False,
                retry_after_seconds=0,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("daily_journey: learning session bootstrap failed")

        if result.story_context:
            from app.services.living_story import StoryUnavailable, bind_journey
            try:
                result = bind_journey(self.db, user=user, journey=fresh, brief=result)
            except StoryUnavailable as exc:
                return self._mark_unavailable(fresh, str(exc))
        self._persist_plan(fresh, result, plan, input_mode)
        fresh.learning_session_id = getattr(session, "id", None)
        fresh.status = str(JourneyStatus.ACTIVE)
        fresh.started_at = _utcnow()
        fresh.generation_claim_id = None
        fresh.generation_claimed_at = None
        fresh.revision += 1
        self.db.flush()
        self._emit(JourneyEventName.STARTED, user, fresh, {})
        return fresh, http_status.HTTP_201_CREATED

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
        """

        journey.status = str(JourneyStatus.UNAVAILABLE)
        journey.unavailable_reason = reason[:120]
        journey.unavailable_retry_allowed = bool(retry_allowed)
        journey.unavailable_retry_after_seconds = int(retry_after_seconds)
        journey.generation_claim_id = None
        journey.generation_claimed_at = None
        journey.revision += 1
        self.db.flush()
        return journey, http_status.HTTP_200_OK

    def _persist_plan(
        self,
        journey: DailyJourney,
        brief: ScenarioBrief,
        plan: Any,
        input_mode: InputMode,
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
        }
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
        )

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
    "DailyJourneyService",
    "journey_enabled_for",
    "journey_error",
    "local_date_for",
    "resolve_timezone",
]
