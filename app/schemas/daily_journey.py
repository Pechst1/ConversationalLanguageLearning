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
from typing import Annotated, Any, Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, model_serializer

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
    #: WP-L1: ``label_fr`` is a grammar concept's title, not a phrase to say.
    concept_title: bool = False


class ScenarioDescriptor(JourneyModel):
    scenario_key: str
    content_version: str
    title_fr: str
    objective_key: str
    objective_native: str
    # WP-59: C1 is a band of its own.
    level_band: Literal["A1", "A2", "B1", "B2", "C1"]
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
    # WP-49: whether «Écouter d'abord» can be honoured on this deployment. The
    # client offers the listening-first cycle only when this is true, so a
    # learner is never invited into a mode that answers "audio is off".
    audio_available: bool = False
    #: WP-66 «jour d'écoute»: the planner dealt a listening day, so the client
    #: opens on the audio rather than on the text. Additive and defaulted —
    #: every scene persisted before WP-66 reads ``False``. Still subject to
    #: ``audio_available``: a listening day on a deployment whose audio has
    #: since been switched off is read aloud by nobody and must not claim to be.
    listen_first: bool = False


class RecallOption(JourneyModel):
    """Never carries correctness: an option id says nothing about the answer."""

    id: str
    text_fr: str
    #: WP-78. Which language the card's text is in: ``"fr"`` or ``"native"``
    #: (the learner's language). A matching item shows both sides; a
    #: listen-and-tap item's cards are meanings. ``None`` on every older format,
    #: whose cards are all French.
    side: Literal["fr", "native"] | None = None
    #: WP-86. «Qui a dit ça ?»: the cast member this card names, so the device
    #: draws their face. ``None`` (and omitted) on every other format.
    character_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_side(self, handler: Any) -> Any:
        # WP-78: additive means byte-identical for every older format.
        data = handler(self)
        if isinstance(data, dict) and data.get("side") is None:
            data.pop("side", None)
        if isinstance(data, dict) and data.get("character_id") is None:
            data.pop("character_id", None)
        return data


class RecallAnswerKey(JourneyModel):
    """WP-76. A key the client can check a pick against but cannot read.

    ``digests`` are SHA-256 of ``salt + ":" + material`` (see
    ``app/services/journey_answer_key.py``). A preview only: the server's
    verdict on the attempt stays authoritative.
    """

    version: int = 1
    salt: str
    digests: list[str] = Field(default_factory=list)


class RecallPrompt(JourneyModel):
    #: WP-66 brought three Séance formats into the daily loop. Additive: the
    #: three originals are unchanged, so a step persisted before this package
    #: still validates. `classify` renders as a two-label pick and is answered
    #: with `ChoiceAttemptInput`; `word_bank` renders as tiles with chips that
    #: are not part of the answer and is answered with `TilesAttemptInput`;
    #: `transform` renders as a short answer over a printed source sentence.
    #: WP-78 added three quick formats, again additively: `match_pairs` is
    #: answered with `TilesAttemptInput` (the pairs the learner made, as
    #: consecutive fr/native ids), `listen_tap` with `ChoiceAttemptInput`, and
    #: `unscramble` with `TilesAttemptInput`.
    task_type: Literal[
        "choice",
        "tiles",
        "short_answer",
        "transform",
        "classify",
        "word_bank",
        "match_pairs",
        "listen_tap",
        "unscramble",
        # WP-86: «Qui a dit ça ?», answered with `ChoiceAttemptInput`.
        "who_said",
    ]
    instruction_native: str
    prompt_fr: str | None = None
    options: list[RecallOption] = Field(default_factory=list)
    target: TargetRef
    optional: bool
    help_available: list[HelpKind] = Field(default_factory=list)
    #: WP-76. Choice, classify, tiles and word bank only; added at projection
    #: time, never stored. ``None`` for written formats and older servers.
    #: WP-78: listen-and-tap and unscramble too, and one digest *per pair* for
    #: a matching item, so each pair is coloured the moment it is made.
    answer_key: RecallAnswerKey | None = None
    #: WP-78. A listen-and-tap item's clip. ``None`` while no clip is
    #: synthesised for single phrases: the phrase is then printed and the item
    #: is read-and-tap.
    audio_url: str | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_audio(self, handler: Any) -> Any:
        # WP-78: only a listen-and-tap item speaks of audio at all.
        data = handler(self)
        if isinstance(data, dict) and data.get("audio_url") is None and self.task_type != "listen_tap":
            data.pop("audio_url", None)
        return data


class RespondLetter(JourneyModel):
    """WP-66 «jour de lettre»: the letter the learner is answering.

    Public by construction — it is what the learner reads — and deliberately
    flat strings rather than a mission model: WP-64 owns the Courrier and this
    contract must not depend on its internals. ``None`` on every other shape.
    """

    mission_id: str
    correspondent_id: str
    correspondent_name: str
    subject_fr: str
    body_fr: str
    objective_native: str


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
    #: WP-66. Present only on a «jour de lettre»; ``None`` is the shipping
    #: value until WP-64 registers a letter provider.
    letter: RespondLetter | None = None


class ResolutionPrompt(JourneyModel):
    outcome_key: str
    character_line_fr: str
    summary_native: str
    image_url: str | None = None
    #: WP-66 «jour de reprise»: one French paragraph recapping the chapter that
    #: just closed. ``None`` on every other shape, and ``None`` when the story
    #: had nothing to recap — an empty recap block is worse than none.
    chapter_recap_fr: str | None = None
    #: WP-33 / WP-66. The graded register dimension, finally shown: one French
    #: line about what the learner held (or let slip) in this conversation…
    register_note_fr: str | None = None
    #: …and why it matters, in the learner's own language. Both are ``None``
    #: together whenever register was *not evaluated* — nothing observable
    #: happened, which is never dressed up as a pass or as a failure.
    register_reason_native: str | None = None
    #: WP-87: the story lane is still writing this ending. The client shows a short
    #: waiting state and polls ``GET /daily-journeys/{id}``; the line and summary are
    #: empty until it turns false (the lane's ending, or today's authored one).
    story_pending: bool = False


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


# --- WP-79 (begin): the end-of-day reward, every field read, none invented ---


class RecapWord(JourneyModel):
    """One vocabulary target the day actually practised (not a "not yet")."""

    id: str
    label_fr: str
    label_native: str | None = None
    evidence_kind: EvidenceKind


class RecapMood(JourneyModel):
    """The day's character, as the living story's WP-61 mood ledger left them.

    ``shift`` is ``None`` unless the ledger's last move was *this* journey's
    exchange (``last_event_id``), so a face never claims a change the day did
    not make. ``mood`` is the ledger's −2 … +2.
    """

    character_id: str
    character_name: str
    mood: int = 0
    shift: Literal["warmer", "colder", "steady"] | None = None


class RecapKeepsake(JourneyModel):
    """The vignette minted for a completed day (WP-09 §4), finally shown."""

    collectible_id: str
    title_fr: str
    location_name: str | None = None
    image_url: str | None = None
    local_date: date


class RecapTeaser(JourneyModel):
    """«La suite demain» — one French line in a character's voice.

    ``source``: ``engine`` (the living story's ``next_teaser``), ``resolution``
    (the resolution's last forward-looking line) or ``authored`` (a line per
    band that promises no plot point). Same order as WP-80's morning push.
    """

    text_fr: str
    character_id: str | None = None
    character_name: str | None = None
    source: Literal["engine", "resolution", "authored"]


class RecapLevelUp(JourneyModel):
    """The CEFR estimate moved up since the previous recap (shown once)."""

    from_level: str
    to_level: str
    mastered_vocabulary: int = 0
    mastered_grammar: int = 0


# --- WP-79 (end) -------------------------------------------------------------


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
    # WP-79. All additive and defaulted: a recap persisted before WP-79 reads
    # with none of them, and the client derives nothing it was not sent.
    #: Steps the learner completed (not skipped) — the honest count shown
    #: when ``active_seconds`` is not measurable.
    steps_done: int = 0
    words: list[RecapWord] = Field(default_factory=list)
    mood: RecapMood | None = None
    keepsake: RecapKeepsake | None = None
    teaser: RecapTeaser | None = None
    #: The story-written teaser only (engine or resolution), never an authored
    #: line: WP-80's morning push reads this key and calls it the engine's.
    teaser_fr: str | None = None
    #: The CEFR estimate when this recap was written; the next recap compares.
    level: str | None = None
    level_up: RecapLevelUp | None = None


class RetryHint(JourneyModel):
    allowed: bool
    after_seconds: int


class CastIntroEntry(JourneyModel):
    """WP-75. One face of the cast, introduced on the learner's first day.

    ``character_id`` names a directory under
    ``web-frontend/public/assets/serial/characters/``; ``role_native`` and
    ``line_native`` are in the learner's language, ``line_fr`` is one short A1
    line the character says.
    """

    character_id: str
    name: str
    role_native: str
    line_fr: str
    line_native: str


class StreakView(JourneyModel):
    """WP-80. The practice streak, checked against the learner's local date.

    ``days`` is 0 the moment a day was missed without a banked «jour de
    relâche»; ``freeze_used_on`` is the local day the last one covered.
    """

    days: int
    today_done: bool
    freeze_available: bool
    freeze_used_on: date | None = None


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
    #: WP-66. Which kind of day this is: ``standard``, ``letter``,
    #: ``listening``, ``reprise`` or ``short``. A free string on the wire on
    #: purpose — a client that meets a shape a newer server deals must render
    #: the steps it was sent, not refuse the day. Journeys planned before
    #: WP-66 read ``standard``, which is what they are.
    day_shape: str = "standard"
    #: WP-75. Three faces, one line each — only on the learner's first
    #: (authored) day; ``None`` on every other day and on every journey
    #: planned before WP-75.
    cast_intro: list[CastIntroEntry] | None = None
    #: WP-80. Additive; ``None`` only when the learner row is unreadable.
    streak: StreakView | None = None
    #: WP-80. Whole local days with no practice before this day. From 2, the
    #: day is labelled «Reprise en douceur».
    missed_days: int = 0
    #: WP-D4. The edition this day played (the serial episode's
    #: ``episode_index + 1``; the learner's own day count when there is no
    #: episode). Its seal composition is fixed by this number.
    edition_no: int | None = None


class LegacyResume(JourneyModel):
    href: str
    session_id: str


class JourneyBecause(JourneyModel):
    """Why today's scene is this scene (WP-24, wired by WP-28).

    Structured, never a rendered sentence: the server names the mistake and the
    component writes the French. ``kind`` is the only field a renderer may
    branch on, and an unknown kind must print nothing rather than guess —
    ``app/services/journey_errata.py::ErrataTarget.as_because`` produces it and
    ``app/services/journey_planner.py::plan_because`` decides whether the plan
    actually kept the target it names.
    """

    #: ``"erratum"`` today. Deliberately a free string, like ``target_reason``.
    kind: str
    #: Machine-readable, e.g. ``"erratum:2f9c…"``. Telemetry, never printed.
    reason: str | None = None
    #: The mistake's own label, in the learner's control language where stored.
    label: str
    #: ``"une homme → un homme"``, when both halves were recorded.
    example: str | None = None


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
    #: WP-24 / WP-28. Why today's scene is this scene, when the plan actually
    #: kept a target that exists because of a recorded mistake. ``None`` means
    #: today owes nothing to an erratum and Home prints no line at all. Read
    #: from the persisted plan, never recomputed: the claim is about the scene
    #: the learner has, not about the queue as it stands this second.
    because: JourneyBecause | None = None
    #: WP-26. ``True`` when a prefetched scene is waiting for this learner, so
    #: the client knows the draft will be warm instead of inferring it from how
    #: fast the answer came back. A warm scene whose preconditions changed is
    #: still discarded at serve time, so this is a promise about the cache, not
    #: about the wire: the client must stay honest if the draft turns cold.
    is_warm: bool = False
    #: WP-80. The streak on this read, a missed day already settled.
    streak: StreakView | None = None
    #: WP-80. Whole local days with no practice before today.
    missed_days: int = 0


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
    "CastIntroEntry",
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
    "JourneyBecause",
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
    "RespondLetter",
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
