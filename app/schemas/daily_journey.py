"""Wire schemas for the Atelier V2 daily journey (contract_version 1).

Field-for-field implementation of
``docs/implementation/atelier-v2/CONTRACT-FREEZE.md``. Two rules hold everywhere
in this module:

1. Public payloads are **real** discriminated models, never ``dict[str, Any]``.
2. Private evaluator material (rubric, accepted answers, correct option id,
   solution text, allowed outcomes) has no field on any response model, so it
   cannot leak by construction.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from app.services.journey_contracts import (
    AssistanceLevel,
    CapabilityKey,
    CapabilityState,
    ControlLanguage,
    EvidenceKind,
    HelpKind,
    InputMode,
    JourneyErrorCode,
    JourneyStatus,
    StepKind,
    StepStatus,
    TargetKind,
    TaskOutcome,
)

CONTRACT_VERSION = 1
BUDGET_SECONDS = 300

#: WP-16 / decision D-0. The legacy exercise Séance is the «Plus de pratique»
#: drill activity; it is entered by grammar concept or by the errata queue,
#: never as "today". Kept here so the schema, the service and the tests agree
#: on one spelling.
PRACTICE_HREF = "/atelier?mode=practice"
#: The drill loop's other legitimate entry: the learner's errata queue.
PRACTICE_ERRATA_HREF = "/atelier?mode=practice&queue=errata"


def practice_href_for(concept_id: object | None = None) -> str:
    """`/atelier?mode=practice[&concept=<id>]`."""

    value = "" if concept_id is None else str(concept_id).strip()
    return f"{PRACTICE_HREF}&concept={quote(value, safe='')}" if value else PRACTICE_HREF


ContractVersion = Literal[1]
BudgetSeconds = Literal[300]


class JourneyModel(BaseModel):
    """Response base: no extra keys may sneak into a public payload."""

    model_config = ConfigDict(extra="forbid")


class JourneyRequest(BaseModel):
    """Request base: unknown client fields are rejected, not silently accepted."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------


class TargetRef(JourneyModel):
    kind: TargetKind
    id: str
    label_fr: str
    label_native: str | None = None


class ScenarioDescriptor(JourneyModel):
    scenario_key: str
    content_version: str
    title_fr: str
    objective_key: str
    objective_native: str
    level_band: Literal["A1", "A2", "B1", "B2"]
    character_id: str
    character_name: str
    location_id: str
    location_name: str
    image_url: str | None = None
    serial_thread_id: str | None = None
    serial_episode_id: str | None = None
    estimated_seconds: int


# ---------------------------------------------------------------------------
# Step prompts
# ---------------------------------------------------------------------------


class ScenePrompt(JourneyModel):
    setup_fr: str
    setup_native: str
    objective_native: str
    character_line_fr: str | None = None
    character_line_audio_url: str | None = None
    image_url: str | None = None


class RecallOption(JourneyModel):
    """Never carries correctness: an option id says nothing about the answer."""

    id: str
    text_fr: str


class RecallPrompt(JourneyModel):
    task_type: Literal["choice", "tiles", "short_answer"]
    instruction_native: str
    prompt_fr: str | None = None
    options: list[RecallOption] = Field(default_factory=list)
    target: TargetRef
    optional: bool
    help_available: list[HelpKind] = Field(default_factory=list)


class RespondPrompt(JourneyModel):
    turn_index: int
    max_turns: int
    repair_allowed: bool
    character_id: str
    character_name: str
    character_line_fr: str
    character_line_audio_url: str | None = None
    objective_native: str
    input_modes: list[InputMode]
    targets: list[TargetRef] = Field(default_factory=list)
    help_available: list[HelpKind] = Field(default_factory=list)


class ResolutionPrompt(JourneyModel):
    outcome_key: str
    character_line_fr: str
    summary_native: str
    image_url: str | None = None


class _PublicStepBase(JourneyModel):
    id: str
    ordinal: int
    status: StepStatus
    estimated_seconds: int
    assistance_used: list[AssistanceLevel] = Field(default_factory=list)


class SceneStep(_PublicStepBase):
    kind: Literal[StepKind.SCENE] = StepKind.SCENE
    prompt: ScenePrompt


class RecallStep(_PublicStepBase):
    kind: Literal[StepKind.RECALL] = StepKind.RECALL
    prompt: RecallPrompt


class RespondStep(_PublicStepBase):
    kind: Literal[StepKind.RESPOND] = StepKind.RESPOND
    prompt: RespondPrompt


class ResolutionStep(_PublicStepBase):
    kind: Literal[StepKind.RESOLUTION] = StepKind.RESOLUTION
    prompt: ResolutionPrompt


PublicStep = Annotated[
    SceneStep | RecallStep | RespondStep | ResolutionStep,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Recap and snapshot
# ---------------------------------------------------------------------------


class PracticedTarget(JourneyModel):
    target: TargetRef
    evidence_kind: EvidenceKind
    assistance_level: AssistanceLevel
    #: WP-16 / decision D-0. Where «Plus de pratique» — the legacy exercise
    #: Séance, now the explicit drill activity — opens for this target.
    #: ``None`` for a target the drill loop cannot seat: it is keyed by a
    #: grammar concept or by the errata queue, never by a bare vocabulary id.
    practice_href: str | None = None


class CapabilityEvidence(JourneyModel):
    capability_key: CapabilityKey
    state: CapabilityState
    modality: InputMode
    observed_on: date
    context_native: str


class NextFocus(JourneyModel):
    target: TargetRef
    reason_native: str


class StoryOutcome(JourneyModel):
    serial_thread_id: str | None = None
    serial_episode_id: str | None = None
    outcome_key: str
    callback_fr: str | None = None


class JourneyRecap(JourneyModel):
    completion_kind: Literal["complete", "early"]
    objective_outcome: TaskOutcome
    practiced_targets: list[PracticedTarget] = Field(default_factory=list)
    capability_evidence: list[CapabilityEvidence] = Field(default_factory=list)
    next_focus: NextFocus | None = None
    collectible_ids: list[str] = Field(default_factory=list)
    story_outcome: StoryOutcome | None = None
    #: Measured active seconds. ``None`` when the runtime was not measurable.
    active_seconds: int | None = None


class RetryHint(JourneyModel):
    allowed: bool
    after_seconds: int


class JourneySnapshot(JourneyModel):
    id: str
    contract_version: ContractVersion = CONTRACT_VERSION
    revision: int
    status: JourneyStatus
    local_date: date
    timezone: str
    budget_seconds: BudgetSeconds = BUDGET_SECONDS
    estimated_active_seconds: int
    current_step_id: str | None = None
    scenario: ScenarioDescriptor
    steps: list[PublicStep] = Field(default_factory=list)
    recap: JourneyRecap | None = None
    retry: RetryHint | None = None


class LegacyResume(JourneyModel):
    href: str
    session_id: str


class TodayEnvelope(JourneyModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    enabled: bool
    control_language: ControlLanguage
    local_date: date
    timezone: str
    journey: JourneySnapshot | None = None
    available: ScenarioDescriptor | None = None
    legacy_resume: LegacyResume | None = None
    #: WP-16 / decision D-0. The one entry to the legacy exercise Séance, which
    #: is now the explicit «Plus de pratique» activity rather than the day's
    #: primary action. Carries the learner's current grammar focus when the
    #: scheduler has one, so the drill loop starts from a concept and never
    #: from "today". Additive: ``contract_version`` is unchanged.
    practice_href: str = PRACTICE_HREF


# ---------------------------------------------------------------------------
# Mutation results
# ---------------------------------------------------------------------------


class JourneyCorrection(JourneyModel):
    span_fr: str
    corrected_fr: str
    note_native: str


class NextTurn(JourneyModel):
    step_id: str
    prompt: RespondPrompt


#: Provenance of ``character_reply_fr``. An authored line must never be
#: presented to the learner as a live model response (WP-06, ratified as an
#: additive field 2026-09-05). Optional so the frozen v1 fixtures still validate.
ReplySource = Literal["authored", "model", "none"]


class AttemptResult(JourneyModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    evidence_ref: str
    task_outcome: TaskOutcome
    assistance_level: AssistanceLevel
    correction: JourneyCorrection | None = None
    character_reply_fr: str | None = None
    #: Where ``character_reply_fr`` came from. ``"none"`` when there is no reply.
    reply_source: ReplySource = "none"
    next_turn: NextTurn | None = None
    #: ``True`` means grading is retryable; the outcome is then ``unscored``.
    pending: bool = False
    journey: JourneySnapshot


class HelpResult(JourneyModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    step_id: str
    help_kind: HelpKind
    content_fr: str | None = None
    content_native: str | None = None
    #: Recorded before the content is returned, never client-asserted.
    assistance_level: AssistanceLevel
    journey: JourneySnapshot


class CapabilitySummary(JourneyModel):
    capability_key: CapabilityKey
    title_native: str
    state: CapabilityState
    modalities: list[InputMode] = Field(default_factory=list)
    latest_qualifying_on: date | None = None
    evidence: list[CapabilityEvidence] = Field(default_factory=list)


class CapabilityProgress(JourneyModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    rubric_version: str
    capabilities: list[CapabilitySummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Error bodies
# ---------------------------------------------------------------------------


class JourneyErrorDetail(JourneyModel):
    code: JourneyErrorCode
    message: str
    current_revision: int | None = None
    refresh_href: str | None = None
    retry_after_seconds: int | None = None


class JourneyErrorBody(JourneyModel):
    detail: JourneyErrorDetail


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class ChoiceAttemptInput(JourneyRequest):
    mode: Literal["choice"] = "choice"
    option_id: str


class TilesAttemptInput(JourneyRequest):
    mode: Literal["tiles"] = "tiles"
    tile_ids: list[str] = Field(default_factory=list)


class TextAttemptInput(JourneyRequest):
    mode: Literal["text"] = "text"
    text: str


class VoiceAttemptInput(JourneyRequest):
    mode: Literal["voice"] = "voice"
    text: str
    #: Contract revision 1 (2026-09-05): optional and nullable. The existing
    #: ``POST /audio/transcribe`` endpoint is stateless and persists no
    #: transcript row, so there is no id to reference. When a client does send
    #: one, the service still refuses a reference it cannot attribute to the
    #: caller, so the ownership check turns on if persistence is ever added.
    transcript_ref: str | None = None


AttemptInput = Annotated[
    ChoiceAttemptInput | TilesAttemptInput | TextAttemptInput | VoiceAttemptInput,
    Field(discriminator="mode"),
]


class JourneyCreateRequest(JourneyRequest):
    mutation_id: str = Field(min_length=1, max_length=80)
    timezone: str = Field(default="UTC", max_length=64)
    budget_seconds: BudgetSeconds = BUDGET_SECONDS
    preferred_input_mode: InputMode = InputMode.TEXT


class JourneyHelpRequest(JourneyRequest):
    mutation_id: str = Field(min_length=1, max_length=80)
    expected_revision: int
    help_kind: HelpKind


class JourneyAttemptRequest(JourneyRequest):
    mutation_id: str = Field(min_length=1, max_length=80)
    expected_revision: int
    input: AttemptInput


class JourneyAdvanceRequest(JourneyRequest):
    mutation_id: str = Field(min_length=1, max_length=80)
    expected_revision: int
    current_step_id: str


class JourneyRevisionRequest(JourneyRequest):
    """Body for pause and resume."""

    mutation_id: str = Field(min_length=1, max_length=80)
    expected_revision: int


class JourneyFinishRequest(JourneyRequest):
    mutation_id: str = Field(min_length=1, max_length=80)
    expected_revision: int
    finish_kind: Literal["complete", "early"]


class JourneyRetryRequest(JourneyRequest):
    mutation_id: str = Field(min_length=1, max_length=80)


__all__ = [
    "AttemptInput",
    "AttemptResult",
    "BUDGET_SECONDS",
    "CONTRACT_VERSION",
    "CapabilityEvidence",
    "CapabilityProgress",
    "CapabilitySummary",
    "ChoiceAttemptInput",
    "HelpResult",
    "JourneyAdvanceRequest",
    "JourneyAttemptRequest",
    "JourneyCorrection",
    "JourneyCreateRequest",
    "JourneyErrorBody",
    "JourneyErrorDetail",
    "JourneyFinishRequest",
    "JourneyHelpRequest",
    "JourneyRecap",
    "JourneyRetryRequest",
    "JourneyRevisionRequest",
    "JourneySnapshot",
    "LegacyResume",
    "NextFocus",
    "NextTurn",
    "PracticedTarget",
    "PublicStep",
    "RecallOption",
    "RecallPrompt",
    "RecallStep",
    "ReplySource",
    "ResolutionPrompt",
    "ResolutionStep",
    "RespondPrompt",
    "RespondStep",
    "RetryHint",
    "ScenePrompt",
    "SceneStep",
    "ScenarioDescriptor",
    "StoryOutcome",
    "TargetRef",
    "TextAttemptInput",
    "TilesAttemptInput",
    "TodayEnvelope",
    "VoiceAttemptInput",
]
