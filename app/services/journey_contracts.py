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
#: WP-66. The *plan* contract, versioned separately from the wire contract.
#: Version 2 adds :class:`DayShape` and the three Séance recall formats. Both
#: additions are additive and defaulted, so a plan persisted at version 1 — a
#: standard day with ``choice``/``tiles``/``short_answer`` recall — still loads
#: and still validates. Never bump ``CONTRACT_VERSION`` for this: the wire
#: payloads gained only optional fields.
PLAN_CONTRACT_VERSION = 2
DEFAULT_BUDGET_SECONDS = 300
MAX_PLANNED_STEPS = 5
MAX_RECALL_STEPS = 2
MAX_RESPOND_TURNS = 2
#: A short day still has to be a day: scene, response, ending.
MIN_PLANNED_STEPS = 3
#: WP-75. Marks the learner's authored first day in
#: ``plan_selection["first_day"]["kind"]``. Additive: no wire shape changes
#: except the optional ``JourneySnapshot.cast_intro`` it feeds.
FIRST_DAY_KIND = "first_day"

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


class DayShape(StrEnum):
    """WP-66 — what *kind* of day this is.

    Before this package every journey was one hard template (scene → ≤2 recall
    → 1 respond → resolution), so day 1 and day 40 were the same object with
    different words in it. A shape is not a second content source and not a
    different product: it is which of the same four step kinds are dealt, in
    which order, and what the respond and resolution steps are allowed to be.

    Chosen by seeded per-learner-per-week dice in
    :mod:`app.services.journey_day_shapes` — never a fixed rotation, never a
    coin flip that changes on refresh.

    * ``STANDARD`` — the shape that existed before this package.
    * ``LETTER`` — «jour de lettre»: the respond step is a Courrier letter.
      Behind the WP-64 capability seam and off until a mission is available.
    * ``LISTENING`` — «jour d'écoute»: the scene is heard before it is read and
      recall is posed dictation-style (never a multiple choice, which cannot be
      dictated).
    * ``REPRISE`` — «jour de reprise»: errata-led, dealt at a chapter's
      resolution beat, and the ending carries the chapter recap.
    * ``SHORT`` — «jour court»: three steps, offered after a missed day so
      coming back costs a scene and a reply, not a full session.
    """

    STANDARD = "standard"
    LETTER = "letter"
    LISTENING = "listening"
    REPRISE = "reprise"
    SHORT = "short"


#: The default for every plan written before WP-66, and for any plan that names
#: no shape. Reading a persisted plan must never fail for want of this key.
DEFAULT_DAY_SHAPE = DayShape.STANDARD


class RecallFormat(StrEnum):
    """How one recall opportunity is posed.

    The first three are the daily loop's originals. The last three are the
    Séance formats WP-66 brought into the journey; they are posed from the same
    authored affordances and the same target, never from a model call, and each
    builder returns ``None`` rather than a format it cannot pose without
    revealing the answer (the no-spoil rule).
    """

    CHOICE = "choice"
    TILES = "tiles"
    SHORT_ANSWER = "short_answer"
    TRANSFORM = "transform"
    CLASSIFY = "classify"
    WORD_BANK = "word_bank"


#: Wire-order tuple. Extending it is additive; reordering it is not, because
#: the frontend renderer table and the parity fixtures read this order.
RECALL_FORMATS: tuple[str, ...] = tuple(str(value) for value in RecallFormat)
#: The three the daily loop had before WP-66. A plan persisted at plan contract
#: version 1 can only contain these.
LEGACY_RECALL_FORMATS: tuple[str, ...] = (
    str(RecallFormat.CHOICE),
    str(RecallFormat.TILES),
    str(RecallFormat.SHORT_ANSWER),
)
#: Formats a learner can answer with their voice on a listening day. A choice
#: is excluded on purpose: reading four options is not taking dictation.
DICTATION_RECALL_FORMATS: tuple[str, ...] = (
    str(RecallFormat.SHORT_ANSWER),
    str(RecallFormat.TRANSFORM),
    str(RecallFormat.WORD_BANK),
)


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
    """What the rubric reports on. The first three are scenario objectives.

    ``REGISTER`` (WP-33, wired by WP-37) is the odd one out and deliberately so:
    it is a *dimension* re-read from the same respond turns, scored by the same
    ``_summarize`` and the same ladder — one rubric, never a second one
    (CONTRACTS §8). It carries no scenario of its own, which is why
    ``journey_capabilities._SCENARIO_KEYS`` — not ``tuple(CapabilityKey)`` — is
    what the evidence reader groups by. It is last because the wire list is
    ordered by this enum and the register line belongs after the three
    capabilities it is read from.
    """

    ORDER_AT_CAFE = "order_at_cafe"
    ARRANGE_MEETING = "arrange_meeting"
    EXPLAIN_DELAY = "explain_delay"
    REGISTER = "register"


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
    """The private, complete definition of one recall opportunity.

    WP-66 added ``transform``, ``classify`` and ``word_bank`` without adding a
    field: a classify's labels are its ``options`` and its answer is
    ``correct_option_id``; a word bank's chips are its ``options`` and its
    answer is ``correct_tile_order`` (a *subset* of the chips, unlike ``tiles``
    where every chip is used); a transform's source sentence is ``prompt_fr``
    and its answer key is ``accepted_answers``.
    """

    task_type: Literal[
        "choice", "tiles", "short_answer", "transform", "classify", "word_bank"
    ]
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

    scenario_key: CapabilityKey | str
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

    story_context: dict[str, Any] = field(default_factory=dict)

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
class DayShapeRule:
    """What one day shape is allowed to be.

    WP-66 replaced the single hard template with this table. The shared
    invariants below the table are *not* negotiable per shape — every day still
    opens on the scene, ends on the ending, and holds exactly one response.
    """

    min_steps: int = MIN_PLANNED_STEPS
    max_steps: int = MAX_PLANNED_STEPS
    min_recall: int = 0
    max_recall: int = MAX_RECALL_STEPS
    #: The recall formats this shape may pose. Empty means "any format".
    allowed_formats: tuple[str, ...] = ()


DAY_SHAPE_RULES: dict[DayShape, DayShapeRule] = {
    # The shape every pre-WP-66 plan has. Its rule is the old template, so a
    # persisted plan validates exactly as it did before.
    DayShape.STANDARD: DayShapeRule(),
    DayShape.LETTER: DayShapeRule(),
    # A listening day has to give the learner something to write down, and a
    # multiple choice is not dictation.
    DayShape.LISTENING: DayShapeRule(
        min_recall=1, allowed_formats=DICTATION_RECALL_FORMATS
    ),
    # A reprise is errata-led: without at least one recall it is just a
    # standard day wearing a recap.
    DayShape.REPRISE: DayShapeRule(min_steps=4, min_recall=1),
    # Three steps, and the third is the ending. Coming back after a missed day
    # costs a scene and a reply.
    DayShape.SHORT: DayShapeRule(
        min_steps=MIN_PLANNED_STEPS, max_steps=MIN_PLANNED_STEPS, max_recall=0
    ),
}


def day_shape_rule(shape: DayShape | str | None) -> DayShapeRule:
    """The rule for a shape, defaulting to ``STANDARD``.

    A shape name this build has never heard of — a plan persisted by a newer
    deployment, read by an older one — falls back to the standard rule rather
    than refusing to load the learner's day.
    """

    try:
        return DAY_SHAPE_RULES[DayShape(str(shape or DEFAULT_DAY_SHAPE))]
    except (KeyError, ValueError):
        return DAY_SHAPE_RULES[DEFAULT_DAY_SHAPE]


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
    #: WP-66. Additive and defaulted: a plan written before this package names
    #: no shape and is read back as ``STANDARD``, which validates under exactly
    #: the rule it was written against.
    day_shape: DayShape = DEFAULT_DAY_SHAPE
    #: Why the dice dealt this shape, for operators and tests. Never rendered.
    shape_reason: str = ""

    def validate(self) -> None:
        """Guard the CONTRACTS §3/§9 envelope at the producer boundary.

        WP-66: the envelope is now validated *as a set of shapes* rather than
        against one template. The shared invariants are checked for every shape;
        the per-shape bounds come from :data:`DAY_SHAPE_RULES`.
        """

        if not self.steps:
            raise ValueError("a planned journey needs at least one step")
        rule = day_shape_rule(self.day_shape)
        shape = str(self.day_shape)
        if len(self.steps) > MAX_PLANNED_STEPS:
            raise ValueError(f"plan has {len(self.steps)} steps, max {MAX_PLANNED_STEPS}")
        kinds = [step.kind for step in self.steps]
        if kinds[0] is not StepKind.SCENE:
            raise ValueError("a plan must open with the scene step")
        if kinds[-1] is not StepKind.RESOLUTION:
            raise ValueError("a plan must end with the resolution step")
        if kinds.count(StepKind.RESPOND) != 1:
            raise ValueError("a plan needs exactly one respond step")
        recalls = kinds.count(StepKind.RECALL)
        if recalls > MAX_RECALL_STEPS:
            raise ValueError(f"at most {MAX_RECALL_STEPS} recall steps are allowed")
        if [step.ordinal for step in self.steps] != list(range(len(self.steps))):
            raise ValueError("step ordinals must be a stable 0..n-1 sequence")

        if not rule.min_steps <= len(self.steps) <= rule.max_steps:
            raise ValueError(
                f"a {shape} day holds {rule.min_steps}..{rule.max_steps} steps, "
                f"not {len(self.steps)}"
            )
        if not rule.min_recall <= recalls <= rule.max_recall:
            raise ValueError(
                f"a {shape} day holds {rule.min_recall}..{rule.max_recall} recall "
                f"step(s), not {recalls}"
            )
        if rule.allowed_formats:
            for step in self.steps:
                if step.kind is not StepKind.RECALL:
                    continue
                task_type = str(getattr(step.private_task, "task_type", "") or "")
                if task_type and task_type not in rule.allowed_formats:
                    raise ValueError(
                        f"a {shape} day cannot pose a {task_type} recall"
                    )

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
    details: dict[str, Any] = field(default_factory=dict)


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
    #: WP-36 §8.4 telemetry: what the self-repair policy decided about this turn
    #: (``recurrence``, ``repair_succeeded``, ``repair_failed``,
    #: ``repair_not_attempted``, ``already_prompted``, ``last_turn``,
    #: ``pragmatic_move_missing``, ``no_open_errata``). It changes nothing about
    #: the grading and is **never** shown to a learner: it exists so the pilot
    #: can count how often a prompted repair actually lands.
    feedback_reason: str | None = None


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
