"""Frozen cross-package domain contracts for the Atelier V2 daily journey.

WP-00 owns this module: it is the single place where the interfaces named in
``docs/implementation/atelier-v2/CONTRACTS.md`` §6 are typed, so WP-02 through
WP-11 cannot drift into per-package private payload formats.

Nothing here talks to the database, the network, or a model provider. The
implementing packages own that:

* WP-03 ``app/services/journey_content.py`` produces :class:`ScenarioBrief`.
* WP-04 ``app/services/journey_planner.py`` produces :class:`PlannedJourney`.
* WP-05 ``app/services/journey_learning.py`` produces candidates, evaluations
  and :class:`AppliedEvidence`.
* WP-06 ``app/services/journey_conversation.py`` produces
  :class:`ResponseEvaluation` and :class:`StoryOutcomeRef`.
* WP-02 ``app/services/daily_journey.py`` orchestrates them inside one
  transaction and is the only writer of journey rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

CONTRACT_VERSION = 1
DEFAULT_BUDGET_SECONDS = 300
MAX_PLANNED_STEPS = 5
MAX_RECALL_STEPS = 2
MAX_RESPOND_TURNS = 2

ControlLanguage = Literal["en", "de", "fr"]
SUPPORTED_CONTROL_LANGUAGES: tuple[ControlLanguage, ...] = ("en", "de", "fr")
FALLBACK_CONTROL_LANGUAGE: ControlLanguage = "en"


def normalize_control_language(value: str | None) -> ControlLanguage:
    """Map a learner's stored native language onto a supported control language."""

    candidate = (value or "").strip().lower().replace("_", "-").split("-")[0]
    if candidate in SUPPORTED_CONTROL_LANGUAGES:
        return candidate  # type: ignore[return-value]
    return FALLBACK_CONTROL_LANGUAGE


class JourneyStatus(StrEnum):
    PREPARING = "preparing"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ENDED_EARLY = "ended_early"
    UNAVAILABLE = "unavailable"


TERMINAL_JOURNEY_STATUSES = frozenset(
    {JourneyStatus.COMPLETED, JourneyStatus.ENDED_EARLY}
)
OCCUPYING_JOURNEY_STATUSES = frozenset(
    {JourneyStatus.PREPARING, JourneyStatus.ACTIVE, JourneyStatus.PAUSED}
)


class StepKind(StrEnum):
    SCENE = "scene"
    RECALL = "recall"
    RESPOND = "respond"
    RESOLUTION = "resolution"


class StepStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class InputMode(StrEnum):
    TEXT = "text"
    VOICE = "voice"


class HelpKind(StrEnum):
    HINT = "hint"
    TRANSLATION = "translation"
    SOLUTION = "solution"
    SUGGESTED_RESPONSE = "suggested_response"


class AssistanceLevel(StrEnum):
    """Server-recorded assistance. Never taken from a client self-report."""

    NONE = "none"
    HINT = "hint"
    TRANSLATION = "translation"
    SOLUTION = "solution"
    SUGGESTED_RESPONSE = "suggested_response"


ASSISTANCE_RANK: dict[AssistanceLevel, int] = {
    AssistanceLevel.NONE: 0,
    AssistanceLevel.HINT: 1,
    AssistanceLevel.TRANSLATION: 2,
    AssistanceLevel.SUGGESTED_RESPONSE: 3,
    AssistanceLevel.SOLUTION: 4,
}


def strongest_assistance(levels: list[AssistanceLevel]) -> AssistanceLevel:
    """The most revealing assistance wins; a later hint never 'downgrades' a reveal."""

    if not levels:
        return AssistanceLevel.NONE
    return max(levels, key=lambda level: ASSISTANCE_RANK[level])


class TaskOutcome(StrEnum):
    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_YET = "not_yet"
    UNSCORED = "unscored"


class EvidenceKind(StrEnum):
    """How strong the observation is. Reading or tapping is never production."""

    RECOGNIZED = "recognized"
    PRODUCED_SUPPORTED = "produced_supported"
    PRODUCED_INDEPENDENT = "produced_independent"
    NOT_YET = "not_yet"
    UNSCORED = "unscored"


class TargetKind(StrEnum):
    VOCABULARY = "vocabulary"
    GRAMMAR = "grammar"
    ERROR = "error"


class CapabilityKey(StrEnum):
    ORDER_AT_CAFE = "order_at_cafe"
    ARRANGE_MEETING = "arrange_meeting"
    EXPLAIN_DELAY = "explain_delay"


class CapabilityState(StrEnum):
    NOT_TRIED = "not_tried"
    WITH_SUPPORT = "with_support"
    INDEPENDENT_ONCE = "independent_once"
    USED_AGAIN_LATER = "used_again_later"
    UNKNOWN = "unknown"


CAPABILITY_RUBRIC_VERSION = "capability-rubric-v1"
JOURNEY_CONTENT_VERSION = "journey-content-v1"


class JourneyErrorCode(StrEnum):
    VERSION_CONFLICT = "journey_version_conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    STEP_NOT_ACTIVE = "step_not_active"
    JOURNEY_NOT_ACTIVE = "journey_not_active"
    EMPTY_ANSWER = "empty_answer"
    JOURNEY_DISABLED = "journey_disabled"
    GENERATION_UNAVAILABLE = "generation_unavailable"
    PROCESSING = "processing"


# --------------------------------------------------------------------------
# Source keys (CONTRACTS §7)
# --------------------------------------------------------------------------

def evidence_source_key(
    *,
    journey_id: UUID | str,
    step_id: UUID | str,
    target_kind: str,
    target_id: str,
    evidence_kind: str,
) -> str:
    """One stable key per (journey, step, target, evidence kind).

    Stable across HTTP retry, worker retry and alternate UI surfaces, so the
    same observation cannot be credited twice.
    """

    return f"journey:{journey_id}:{step_id}:{target_kind}:{target_id}:{evidence_kind}"


def effect_source_key(*, journey_id: UUID | str, effect: str) -> str:
    """Key for a once-only journey side effect (story outcome, keepsake, event)."""

    return f"journey:{journey_id}:{effect}"


# --------------------------------------------------------------------------
# Shared value objects
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class TargetRef:
    """A learning target that already exists in the learner's own records."""

    kind: TargetKind
    id: str
    label_fr: str
    label_native: str | None = None

    def as_public(self) -> dict[str, Any]:
        return {
            "kind": str(self.kind),
            "id": self.id,
            "label_fr": self.label_fr,
            "label_native": self.label_native,
        }


_QUOTE_FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201b": "'", "\u2032": "'", "\u00b4": "'",
    "\u0060": "'", "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",
}


def normalize_answer_text(value: str | None) -> str:
    """Fold iOS smart quotes and exotic spaces before any answer comparison.

    iOS inserts U+2019 for a typed apostrophe; comparing it raw marks correct
    French (``s'il vous plait``) wrong.
    """

    text = value or ""
    for source, replacement in _QUOTE_FOLD.items():
        text = text.replace(source, replacement)
    return " ".join(text.split())


@dataclass(frozen=True, slots=True)
class AttemptAnswer:
    """Normalized server-side view of the client ``AttemptInput`` union."""

    mode: InputMode
    text: str
    option_id: str | None = None
    tile_ids: list[str] = field(default_factory=list)
    transcript_ref: str | None = None

    @property
    def is_blank(self) -> bool:
        return not normalize_answer_text(self.text) and not self.option_id and not self.tile_ids


@dataclass(frozen=True, slots=True)
class LearningCandidate:
    """WP-05 result: an existing due/fragile item, never a new scheduler row."""

    target: TargetRef
    priority_score: float
    due_since_days: int
    estimated_seconds: int
    is_new: bool = False
    relevance: float = 0.0
    source_item_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RecallTask:
    """The private, complete definition of one recall opportunity."""

    task_type: Literal["choice", "tiles", "short_answer"]
    instruction_native: str
    prompt_fr: str | None
    options: list[dict[str, str]]
    target: TargetRef
    optional: bool
    accepted_answers: list[str] = field(default_factory=list)
    correct_option_id: str | None = None
    correct_tile_order: list[str] = field(default_factory=list)
    hint_native: str | None = None
    translation_native: str | None = None
    solution_fr: str | None = None
    estimated_seconds: int = 45


@dataclass(frozen=True, slots=True)
class ResponseTask:
    """The private definition of the purposeful response opportunity."""

    objective_native: str
    character_id: str
    character_name: str
    opening_line_fr: str
    max_turns: int = MAX_RESPOND_TURNS
    repair_allowed: bool = True
    targets: list[TargetRef] = field(default_factory=list)
    required_intents: list[str] = field(default_factory=list)
    optional_intents: list[str] = field(default_factory=list)
    allowed_outcomes: list[str] = field(default_factory=list)
    rubric_native: str = ""
    suggested_response_fr: str | None = None
    hint_native: str | None = None
    translation_native: str | None = None
    estimated_seconds: int = 120


@dataclass(frozen=True, slots=True)
class ScenarioBrief:
    """WP-03 result. Bounded, validated, and pinned by ``content_version``."""

    scenario_key: CapabilityKey
    content_version: str
    title_fr: str
    objective_key: str
    objective_native: str
    level_band: str
    character_id: str
    character_name: str
    location_id: str
    location_name: str
    image_url: str | None
    setup_fr: str
    setup_native: str
    opening_line_fr: str | None
    response_task: ResponseTask
    resolution_lines: dict[str, str] = field(default_factory=dict)
    resolution_summaries: dict[str, str] = field(default_factory=dict)
    serial_thread_id: str | None = None
    serial_episode_id: str | None = None
    estimated_seconds: int = 264
    is_authored_fallback: bool = False
    control_language: ControlLanguage = FALLBACK_CONTROL_LANGUAGE

    def public_descriptor(self) -> dict[str, Any]:
        return {
            "scenario_key": str(self.scenario_key),
            "content_version": self.content_version,
            "title_fr": self.title_fr,
            "objective_key": self.objective_key,
            "objective_native": self.objective_native,
            "level_band": self.level_band,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "location_id": self.location_id,
            "location_name": self.location_name,
            "image_url": self.image_url,
            "serial_thread_id": self.serial_thread_id,
            "serial_episode_id": self.serial_episode_id,
            "estimated_seconds": self.estimated_seconds,
        }


@dataclass(frozen=True, slots=True)
class ContentUnavailable:
    """Deterministic, honest 'no valid content' result. Never a placeholder scene."""

    reason: str
    retry_after_seconds: int = 30
    retry_allowed: bool = True


ScenarioContextResult = ScenarioBrief | ContentUnavailable


@dataclass(frozen=True, slots=True)
class PlannedStep:
    """One planned step. ``public_prompt`` never contains answer-key material."""

    ordinal: int
    kind: StepKind
    estimated_seconds: int
    public_prompt: dict[str, Any]
    private_task: RecallTask | ResponseTask | None = None
    target: TargetRef | None = None
    optional: bool = False
    initial_status: StepStatus = StepStatus.PENDING


@dataclass(frozen=True, slots=True)
class PlannedJourney:
    """WP-04 result: an immutable plan the state machine persists verbatim."""

    scenario: ScenarioBrief
    steps: list[PlannedStep]
    estimated_active_seconds: int
    budget_seconds: int = DEFAULT_BUDGET_SECONDS
    selected_target_ids: list[str] = field(default_factory=list)
    omitted_candidate_ids: list[str] = field(default_factory=list)
    rationale: str = ""

    def validate(self) -> None:
        """Guard the CONTRACTS §3/§9 envelope at the producer boundary."""

        if not self.steps:
            raise ValueError("a planned journey needs at least one step")
        if len(self.steps) > MAX_PLANNED_STEPS:
            raise ValueError(f"plan has {len(self.steps)} steps, max {MAX_PLANNED_STEPS}")
        kinds = [step.kind for step in self.steps]
        if kinds[0] is not StepKind.SCENE:
            raise ValueError("a plan must open with the scene step")
        if kinds[-1] is not StepKind.RESOLUTION:
            raise ValueError("a plan must end with the resolution step")
        if kinds.count(StepKind.RESPOND) != 1:
            raise ValueError("a plan needs exactly one respond step")
        if kinds.count(StepKind.RECALL) > MAX_RECALL_STEPS:
            raise ValueError(f"at most {MAX_RECALL_STEPS} recall steps are allowed")
        if [step.ordinal for step in self.steps] != list(range(len(self.steps))):
            raise ValueError("step ordinals must be a stable 0..n-1 sequence")
        mandatory = sum(
            step.estimated_seconds for step in self.steps if not step.optional
        )
        if mandatory > self.budget_seconds:
            raise ValueError(
                f"mandatory estimate {mandatory}s exceeds budget {self.budget_seconds}s"
            )


@dataclass(frozen=True, slots=True)
class TargetObservation:
    """One observation about one target, ready for canonical credit."""

    target: TargetRef
    evidence_kind: EvidenceKind
    assistance: AssistanceLevel
    modality: InputMode
    learner_text: str | None = None
    corrected_text: str | None = None


@dataclass(frozen=True, slots=True)
class Correction:
    """At most one of these is foregrounded per turn (CONTRACTS §7)."""

    span_fr: str
    corrected_fr: str
    note_native: str

    def is_valid_for(self, learner_text: str) -> bool:
        """Reject no-op corrections and spans the learner never wrote."""

        span = (self.span_fr or "").strip()
        corrected = (self.corrected_fr or "").strip()
        if not span or not corrected or span == corrected:
            return False
        return span in (learner_text or "")


@dataclass(frozen=True, slots=True)
class RecallEvaluation:
    """WP-05 result for a recall step."""

    outcome: TaskOutcome
    assistance: AssistanceLevel
    observations: list[TargetObservation]
    correction: Correction | None = None
    pending: bool = False
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class StoryOutcomeProposal:
    """A model may propose only one of the brief's declared outcome keys."""

    outcome_key: str
    callback_fr: str | None = None
    character_id: str | None = None


@dataclass(frozen=True, slots=True)
class ResponseEvaluation:
    """WP-06 result for a respond step."""

    outcome: TaskOutcome
    assistance: AssistanceLevel
    observations: list[TargetObservation]
    character_reply_fr: str | None = None
    correction: Correction | None = None
    consequence: StoryOutcomeProposal | None = None
    needs_repair: bool = False
    turn_consumed: bool = True
    pending: bool = False
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AppliedEvidence:
    """WP-05 result: what was actually written to canonical learning records."""

    evidence_ref: str
    source_keys: list[str]
    applied_target_ids: list[str] = field(default_factory=list)
    deduplicated_source_keys: list[str] = field(default_factory=list)
    learning_session_id: UUID | None = None
    learning_moment_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class StoryOutcomeRef:
    """WP-06 result: a reference into the existing serial ledger, or nothing."""

    applied: bool
    outcome_key: str
    serial_thread_id: str | None = None
    serial_episode_id: str | None = None
    callback_fr: str | None = None
    already_applied: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityEvidenceView:
    capability_key: CapabilityKey
    state: CapabilityState
    modality: InputMode
    observed_on: date
    context_native: str


@dataclass(frozen=True, slots=True)
class CapabilitySummary:
    capability_key: CapabilityKey
    title_native: str
    state: CapabilityState
    modalities: list[InputMode]
    latest_qualifying_on: date | None
    evidence: list[CapabilityEvidenceView]


@dataclass(frozen=True, slots=True)
class CapabilityProgressView:
    rubric_version: str
    capabilities: list[CapabilitySummary]


@dataclass(frozen=True, slots=True)
class KeepsakeResult:
    minted: bool
    collectible_ids: list[str] = field(default_factory=list)
    already_minted: bool = False


class JourneyEventName(StrEnum):
    CREATED = "journey_created"
    STARTED = "journey_started"
    STEP_COMPLETED = "journey_step_completed"
    HELP_USED = "journey_help_used"
    PAUSED = "journey_paused"
    COMPLETED = "journey_completed"
    ENDED_EARLY = "journey_ended_early"
    GENERATION_FALLBACK = "journey_generation_fallback"
    PROVIDER_FAILED = "journey_provider_failed"
    RESUME_CONFLICT = "journey_resume_conflict"


__all__ = [name for name in dir() if not name.startswith("_")]
