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

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from app.schemas.revue_relecture import RelectureOffer
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


#: WP-S4 — La Forge's one entry: ``/atelier?mode=forge[&concept=<id>]…``. The
#: after-day chip (Léger, Régulier) and the folded step (Soutenu, Intensif)
#: both open it; the page starts the séance through the forge picker.
FORGE_HREF = "/atelier?mode=forge"


def forge_href_for(
    concept_id: object | None = None,
    *,
    budget_seconds: int | None = None,
    step_id: object | None = None,
) -> str:
    """`/atelier?mode=forge[&concept=<id>][&budget=<s>][&step=<journey step id>]`."""

    parts = [FORGE_HREF]
    value = "" if concept_id is None else str(concept_id).strip()
    if value:
        parts.append(f"concept={quote(value, safe='')}")
    if budget_seconds:
        parts.append(f"budget={int(budget_seconds)}")
    if step_id:
        parts.append(f"step={quote(str(step_id), safe='')}")
    return "&".join(parts)


ContractVersion = Literal[1]
#: WP-L6: the four rhythms — Léger 5, Régulier 10, Soutenu 20, Intensif 30 min.
BudgetSeconds = Literal[300, 600, 1200, 1800]


class JourneyModel(BaseModel):
    """Response base: no extra keys may sneak into a public payload."""

    # Responses serialize defaults too; OpenAPI must describe the emitted keys.
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


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


class EpreuveCanDo(JourneyModel):
    id: str
    title_fr: str | None = None
    title_native: str | None = None


class EpreuveView(JourneyModel):
    """WP-94 «Numéro spécial» — the band the épreuve closes and its can-dos."""

    band: str | None = None
    can_dos: list[EpreuveCanDo] = Field(default_factory=list)


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
    #: WP-94. On the offered scenario (``TodayEnvelope.available``) only: the
    #: épreuve is due, so Home can show the special edition before Start.
    #: ``None`` on a created journey's scenario — that one's are on the snapshot.
    special: Literal["epreuve"] | None = None
    epreuve: EpreuveView | None = None


# ---------------------------------------------------------------------------
# Step prompts
# ---------------------------------------------------------------------------


class ScenePanelLine(JourneyModel):
    character_id: str
    character_name: str | None = None
    text_fr: str


class ScenePanel(JourneyModel):
    """One panel of an authored scene's page (2026-09-25)."""

    id: str
    index: int
    narration_fr: str = ""
    dialogue: list[ScenePanelLine] = Field(default_factory=list)
    image_url: str | None = None
    image_status: Literal["panel_art", "setting_reference", "unavailable"] = "unavailable"
    #: WP-116: the scene's location plate, under the drawn cast.
    plate_url: str | None = None


class MarginNote(JourneyModel):
    """WP-97 «Les suites»: a consequence or callback paid back on this page,
    printed as a dated note in the margin («Parce que vous avez dit … — Nº 4»).
    Read from the scene's ``script_payload.margin_notes`` (the story lane)."""

    text_fr: str
    cause_scene_id: str | None = None
    cause_date: str | None = None
    character_id: str | None = None
    #: The edition the cause was played in, when its day is known.
    cause_edition_no: int | None = None
    #: The panel of *this* page the note sits beside (0-based index, and the
    #: reader's public panel id), when the story lane placed it.
    panel_index: int | None = None
    panel_id: str | None = None


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
    #: An authored scene's graphic-novel page (story-engine scenes publish theirs as
    #: an episode). Additive: absent on every scene planned before 2026-09-25.
    panels: list[ScenePanel] | None = None
    #: WP-96 «Précédemment»: up to three chronicle lines above an engine scene,
    #: read at projection time from the bound scene. ``None`` on authored days.
    previously_fr: list[str] | None = None
    #: WP-97: the margin notes this page prints. ``None`` on authored days.
    margin_notes: list[MarginNote] | None = None


class RecallOption(JourneyModel):
    """Never carries correctness: an option id says nothing about the answer."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

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
    def _omit_absent_side(self, handler: Any):
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


def _drop_required(schema: dict[str, Any], *keys: str) -> None:
    """Keys a serializer omits when absent are not ``required`` in OpenAPI."""

    for key in keys:
        if key in schema.get("required", []):
            schema["required"].remove(key)


class RecallMet(JourneyModel):
    """WP-121 A.4: the Papier a recalled word was kept in, as one French line."""

    place_label_fr: str


class RecallPrompt(JourneyModel):
    # This serializer drops audio_url on silent formats, leaving all other defaults.
    model_config = ConfigDict(
        json_schema_extra=lambda schema: _drop_required(schema, "audio_url", "met"),
    )
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
        # WP-91: «Dictée» — a line of today's scene is heard and typed,
        # answered with `TextAttemptInput`. Its prompt carries the instruction
        # and `audio_url` only: never the line.
        "dictation",
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
    #: WP-78. A listen-and-tap item's clip. ``None`` when the deployment does
    #: not speak: the phrase is then printed and the item is read-and-tap.
    #: WP-91: with audio on, a listen-and-tap or dictation item carries
    #: ``/api/v1/daily-journeys/line-audio/{clip_id}`` — an authenticated path,
    #: synthesised on its first request and cached — and a listen-and-tap
    #: item's ``prompt_fr`` is then ``None`` (the phrase is heard, not read).
    audio_url: str | None = None
    #: WP-103 T3 (additive): what to produce, in the learner's language — the
    #: meaning of the sentence to build, or which line of the scene to rebuild.
    #: Always set for word_bank, tiles, unscramble and transform; ``None`` elsewhere
    #: and on steps planned before WP-103.
    goal_native: str | None = None
    #: WP-103 T3 (additive): the French the item starts from when it is shown (the
    #: sentence to correct, the learner's own wording to repair). Never the answer.
    source_fr: str | None = None
    #: WP-121 A.4 (additive): where a card kept in a Papier was met — the small
    #: context line under the prompt («vu au marché d'Aligre, semaine 41»).
    #: Omitted for every other card.
    met: RecallMet | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_audio(self, handler: Any):
        # WP-78: only a listening item speaks of audio at all.
        data = handler(self)
        if (
            isinstance(data, dict)
            and data.get("audio_url") is None
            and self.task_type not in ("listen_tap", "dictation")
        ):
            data.pop("audio_url", None)
        if isinstance(data, dict) and data.get("met") is None:
            data.pop("met", None)
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


class JourneyCorrection(JourneyModel):
    # Persisted corrections predating WP-103 do not carry the additive notes list.
    model_config = ConfigDict(json_schema_serialization_defaults_required=False)
    span_fr: str
    corrected_fr: str
    note_native: str
    #: WP-103 (additive): one note per issue, deduplicated, at most two sentences
    #: each, in the learner's language — a journey correction is one issue, so one
    #: note: ``note_native`` with any sentence it repeats removed.
    notes_native: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_note_per_issue(self) -> JourneyCorrection:
        if not self.notes_native and self.note_native:
            from app.services.forge_grading import notes_native

            self.notes_native = notes_native([{"why_wrong": self.note_native}])
        return self


class ThreadLine(JourneyModel):
    """One spoken line of a many-voiced reply: who says it and what."""

    speaker_id: str | None = None
    speaker_name: str | None = None
    text_fr: str


class ThreadExchange(JourneyModel):
    """WP-89 «Le fil»: one exchange of the reply conversation, as it happened.

    ``character_fr`` is the character's answer to ``learner_fr``; ``correction``
    is the one public correction that turn earned, if any. Additive to contract
    v1: a reloaded client redraws the conversation from it.
    """

    learner_fr: str
    character_fr: str
    correction: JourneyCorrection | None = None
    #: The reply as its speakers' lines, when several people answer (an authored
    #: season page); empty for a one-voiced reply.
    character_lines: list[ThreadLine] = Field(default_factory=list)


class RespondChoice(JourneyModel):
    """WP-113 «Le choix»: one card the learner can tap to answer the question."""

    id: str
    label_fr: str
    label_native: str | None = None


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
    #: WP-89. The exchanges so far, oldest first; empty on turn 0. The last
    #: entry's ``character_fr`` is the ``character_line_fr`` above.
    thread: list[ThreadExchange] = Field(default_factory=list)
    #: WP-113. The current question is «Le choix»: tap one of these cards (its
    #: label is the answer). Empty for a free reply.
    choices: list[RespondChoice] = Field(default_factory=list)


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
    #: The ending is narration (an authored page's «À suivre…» caption): drawn
    #: without a speaker's name or face.
    narrated: bool = False


class _RuleCardModel(JourneyModel):
    """A WP-L10 card field. ``None`` fields are omitted on the wire."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

    @model_serializer(mode="wrap")
    def _omit_none(self, handler: Any):
        data = handler(self)
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value is not None}
        return data


class RuleCardExample(_RuleCardModel):
    #: French, with the WP-L10 marks: ``[x]`` carries the rule, ``{x}`` is silent.
    fr: str
    tr: dict[str, str] | None = None


class RuleCardRow(_RuleCardModel):
    #: ``rows`` patterns: a gender shape and a label; ``table`` patterns: a person.
    shape: str | None = None
    label: str | None = None
    p: str | None = None
    fr: str


class RuleCardPattern(_RuleCardModel):
    kind: Literal["rows", "table"]
    rows: list[RuleCardRow] = Field(default_factory=list)
    verb: str | None = None
    note: dict[str, str] | None = None


class RuleCardContrast(_RuleCardModel):
    wrong: str
    right: str


class RuleCardPayload(_RuleCardModel):
    """The card, every authored language at once; the client picks the learner's."""

    speaker: str | None = None
    example: RuleCardExample
    rule: dict[str, str]
    pattern: RuleCardPattern | None = None
    contrast: RuleCardContrast | None = None
    more: dict[str, str] | None = None
    #: The headline is a line of today's scene, not the catalogue's example.
    from_scene: bool | None = None


class RulePrompt(JourneyModel):
    """WP-L4 «Règle»: the day's new grammar unit as its WP-L10 rule card.

    What the learner reads, so it carries no answer key. The step is advanced,
    not answered; advancing it introduces the unit.
    """

    concept_id: int
    title_native: str = ""
    title_fr: str = ""
    rule_card: RuleCardPayload
    #: WP-92: a cast line of today's scene that uses the unit (its
    #: ``grammar_marks`` name it, or the unit's detector finds it), the form in
    #: the card's ``[…]`` marks («Je [suis allé] au marché»), and the cast id of
    #: who says it — the form as the learner is about to meet it. ``None`` when
    #: the scene holds none (or the day was planned before WP-92).
    scene_example_fr: str | None = None
    scene_example_speaker: str | None = None


class ForgePrompt(JourneyModel):
    """WP-S4 «La Forge», folded into the day: a hand-off, not an exercise.

    ``href`` opens the forge block on today's rule; ``forged`` turns true once
    a forge block started from this step was completed, so the step reads
    «Continue» when the learner comes back. Both are projected, never stored.
    """

    concept_id: int | None = None
    title_native: str = ""
    title_fr: str = ""
    budget_seconds: int
    href: str = FORGE_HREF
    forged: bool = False


class ReadPrompt(JourneyModel):
    """WP-93 «Lecture»: a second page on a long rhythm, after the ending.

    ``relecture`` is yesterday's page again (heard when ``audio_available``);
    ``coulisses`` is today's evening from another cast member's side, written
    after the day is planned. ``scene_id`` opens it through
    ``GET /api/v1/story-engine/episodes/{scene_id}`` once ``status`` is
    ``ready``; ``writing`` means poll the journey, ``unavailable`` means there
    is nothing to read today (the step is optional). Advanced, not answered.
    Projected on every read, never trusted from the stored plan alone.
    """

    variant: Literal["relecture", "coulisses"]
    title_fr: str
    scene_id: str | None = None
    status: Literal["ready", "writing", "unavailable"]
    audio_available: bool = False
    #: «coulisses»: the cast member whose evening it is (the page's point of
    #: view), once the page is written; ``None`` while it is being written and
    #: on a «relecture».
    character_id: str | None = None
    character_name: str | None = None


class DeskPrompt(JourneyModel):
    """«Le bureau» (WP-121/122): one of the Revue's other desks, folded into an
    ordinary practice day after the ending. Advanced, not answered — each desk
    grades through its own routes. The client mounts:

    * ``relecture`` — ``CarteRelecture`` on ``relecture`` (the offer of
      ``GET /revue/relecture/offer``), answered with ``POST /revue/relecture/{session_id}``;
    * ``radio`` — the Radio bulletin of ``dossier_id`` (``GET /revue/radio/{id}``),
      listen first, then the dictée, then «C'est entendu»;
    * ``correcteur`` — ``CorrecteurDesk`` on a new draft of ``dossier_id``
      (``POST /revue/correcteur/{id}``).
    """

    desk: Literal["relecture", "radio", "correcteur"]
    title_fr: str
    dossier_id: str | None = None
    relecture: RelectureOffer | None = None
    #: The Radio's bulletin length, rounded to 5 s, when known.
    seconds: int | None = None


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


class RuleStep(_PublicStepBase):
    kind: Literal[StepKind.RULE] = StepKind.RULE
    prompt: RulePrompt


class ForgeStep(_PublicStepBase):
    kind: Literal[StepKind.FORGE] = StepKind.FORGE
    prompt: ForgePrompt


class ReadStep(_PublicStepBase):
    kind: Literal[StepKind.READ] = StepKind.READ
    prompt: ReadPrompt


class DeskStep(_PublicStepBase):
    kind: Literal[StepKind.DESK] = StepKind.DESK
    prompt: DeskPrompt


PublicStep = Annotated[
    SceneStep | RecallStep | RespondStep | ResolutionStep | RuleStep | ForgeStep | ReadStep | DeskStep,
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


class RecapForecastLine(JourneyModel):
    """WP-L8 — «At this rhythm: A1.2 around <month>» (the client writes it)."""

    target: str
    band: str | None = None
    #: ``YYYY-MM``: the month of the forecast's central day.
    month: str
    range_days: list[int] = Field(default_factory=list)
    rhythm: str | None = None
    measured: bool = True


# --- WP-79 (end) -------------------------------------------------------------


class RecapChapterClosed(JourneyModel):
    """WP-96: the chapter today closed, for the «Fin du chapitre» colophon."""

    index: int
    title_fr: str = ""
    digest_fr: str | None = None


class RecapSeasonFinished(JourneyModel):
    """WP-96: the season today finished — it becomes «Tome N»."""

    number: int
    title_fr: str = ""


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
    #: WP-L6 §2.2: the auto-throttle is on — «Cette semaine, on consolide.»
    consolidating: bool = False
    #: WP-L8: once a week at the Seal, from a *measured* forecast only.
    forecast_line: RecapForecastLine | None = None
    #: WP-94: ``passed`` / ``failed`` when today was a «Numéro spécial».
    epreuve_result: Literal["passed", "failed"] | None = None
    #: WP-94: the engine's pass (or kind fail) line, in a character's voice.
    epreuve_line_fr: str | None = None
    #: WP-95: can-do ids this day pressed into the Carnet (first stamps only).
    can_dos_stamped: list[str] = Field(default_factory=list)
    #: WP-97: the margin notes today's page printed (a consequence paid back).
    margin_notes: list[MarginNote] = Field(default_factory=list)
    #: WP-96: «Fin du chapitre» — today closed a chapter.
    chapter_closed: RecapChapterClosed | None = None
    #: WP-96: «Tome N» — today closed the season.
    season_finished: RecapSeasonFinished | None = None


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


class EntreTempsItem(JourneyModel):
    """WP-99. One off-screen beat the cast lived while the learner was away."""

    text_fr: str
    date: str | None = None
    character_id: str | None = None


class LapsedLetter(JourneyModel):
    """WP-99. A letter that went cold during the absence."""

    mission_id: str
    correspondent_name: str | None = None


class AbsenceView(JourneyModel):
    """WP-99 «Pendant votre absence». Present from two missed days, else ``null``.

    ``greeting_fr`` is the scene's own line for the gap (the engine writes
    ``script_payload.absence``), ``null`` when there is none; ``entre_temps`` is
    at most five beats, oldest first, since the last finished day.
    """

    days: int
    greeting_fr: str | None = None
    entre_temps: list[EntreTempsItem] = Field(default_factory=list)
    lapsed_letters: list[LapsedLetter] = Field(default_factory=list)


class SeasonPremiereView(JourneyModel):
    """WP-98/99. Today's scene opens a season: «Nouvelle saison»."""

    number: int
    title_fr: str
    logline_fr: str | None = None


class InterludeView(JourneyModel):
    """WP-98/99. The story is between seasons, named honestly, with its return date."""

    returns_on: str | None = None
    reason_fr: str | None = None


class MasteryToday(JourneyModel):
    """WP-S7: mastery earned on the journey's local day."""

    held_concept_ids: list[int] = Field(default_factory=list)
    tested_out_concept_ids: list[int] = Field(default_factory=list)


class JourneySnapshot(JourneyModel):
    #: Current learner estimate, independent of the persisted scene's band.
    learner_level: str | None = None
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
    #: WP-S7. The rules that became held on this local day (a Seal ring each)
    #: and those among them that a test-out held. ``None`` with the flag off.
    mastery_today: MasteryToday | None = None
    #: WP-94. ``"epreuve"`` on a «Numéro spécial» day, else ``None``.
    special: Literal["epreuve"] | None = None
    #: WP-94. What the épreuve asks: its band and can-dos, in the learner's language.
    epreuve: EpreuveView | None = None
    #: WP-99. «Pendant votre absence» from two missed days, else ``None``.
    absence: AbsenceView | None = None
    #: WP-99. Set on the day whose scene opens a season.
    season_premiere: SeasonPremiereView | None = None
    #: WP-99. Set while the story is between seasons.
    interlude: InterludeView | None = None


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


class ForgeEntry(JourneyModel):
    """WP-S4 — where «Forge today's rule» opens, and how the day carries it.

    ``folded``: Soutenu and Intensif carry the forge inside the day (a step in
    the Scène movement); Home then keeps «More practice» after the day.
    Léger and Régulier (``folded`` false) get the forge as the after-day chip.
    """

    href: str = FORGE_HREF
    concept_id: int | None = None
    budget_seconds: int
    folded: bool = False


class HeadlineCastMember(JourneyModel):
    id: str
    name: str


class EpisodeHeadline(JourneyModel):
    """WP-109: today's episode as Home and the Feuilleton headline it."""

    edition_no: int | None = None
    #: The day's title when known: the scene's, or an authored tentpole's. A generated
    #: day not yet written has none — the teaser leads.
    title_fr: str | None = None
    #: Yesterday's «À suivre…».
    teaser_fr: str | None = None
    season_title_fr: str | None = None
    #: The episode's picture: the scene's first panel, else its opening place.
    image_url: str | None = None
    cast: list[HeadlineCastMember] = Field(default_factory=list)
    #: WP-116: the drawn cast's per-learner looks, e.g. ``{"camille_marchand": "f"}``.
    #: Only choices the learner has made; empty before them.
    cast_variants: dict[str, str] = Field(default_factory=dict)


class TodayEnvelope(JourneyModel):
    learner_level: str | None = None
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
    #: WP-S4. La Forge's entry for today (``None`` with the capability off).
    forge: ForgeEntry | None = None
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
    #: WP-99. «Pendant votre absence» from two missed days, else ``None``
    #: (before today's journey exists too, so Home can say it first).
    absence: AbsenceView | None = None
    #: WP-99. Today's scene opens a season (``None`` before the journey exists).
    season_premiere: SeasonPremiereView | None = None
    #: WP-99. The story is between seasons, with its return date.
    interlude: InterludeView | None = None
    #: WP-109. Today's episode, headlined (``None`` once it is over, or with no story).
    headline: EpisodeHeadline | None = None


# ---------------------------------------------------------------------------
# Mutation results
# ---------------------------------------------------------------------------


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
    #: The reply as its speakers' lines, when several people answer; empty otherwise.
    character_lines: list[ThreadLine] = Field(default_factory=list)
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
    model_config = ConfigDict(json_schema_serialization_defaults_required=False)
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
    #: WP-L6: accepted for older clients and **ignored** — the server sizes
    #: the day from the learner's rhythm (``users.daily_goal_minutes``), so a
    #: build that still sends 300 cannot pin a Régulier learner to five minutes.
    budget_seconds: BudgetSeconds | None = None
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


# ---------------------------------------------------------------------------
# WP-91 «Les voix»: one line of a step, spoken in its character's voice
# ---------------------------------------------------------------------------


class LineAudioRequest(JourneyRequest):
    """``POST /daily-journeys/{journey_id}/steps/{step_id}/line-audio``.

    ``text_fr`` must be a line that actually appears in that step for this
    learner (404 otherwise): the route never speaks arbitrary text.
    ``character_id`` is a hint for which speaker is meant when two say the same
    words; the voice is always the server's, from the line it matched.
    """

    text_fr: str = Field(min_length=1, max_length=600)
    character_id: str | None = Field(default=None, max_length=80)


class LineAudioResult(JourneyModel):
    """``ready`` carries the clip to fetch; ``disabled`` means "use the device
    voice" (audio off on this deployment, the provider unavailable, or the
    learner's daily cap near). The four other fields are present only when
    ``ready``."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=False)

    status: Literal["ready", "disabled"]
    clip_id: str | None = None
    content_type: str | None = None
    voice: str | None = None
    cached: bool | None = None

    @model_serializer(mode="wrap")
    def _only_what_the_status_carries(self, handler: Any):
        data = handler(self)
        if isinstance(data, dict) and self.status != "ready":
            return {"status": self.status}
        return data


__all__ = [
    "LineAudioRequest",
    "LineAudioResult",
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
    "MarginNote",
    "RecapChapterClosed",
    "RecapSeasonFinished",
    "ScenePrompt",
    "SceneStep",
    "ScenarioDescriptor",
    "StoryOutcome",
    "TargetRef",
    "TextAttemptInput",
    "ThreadExchange",
    "TilesAttemptInput",
    "TodayEnvelope",
    "VoiceAttemptInput",
]
