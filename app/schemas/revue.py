"""Wire schemas for La Revue de Romy, phases 1–2 (WP-119).

Field-for-field implementation of ``docs/implementation/atelier-v2/WP-119-WIRE.md``.
As in ``app/schemas/daily_journey.py``: public payloads are real models, never
``dict[str, Any]``, and private material (a headline exercise's answer and its
``contradicted_by`` map, the raw state log, provider prompts) has no field on any
response model, so it cannot leak by construction.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.revue_vignette import VignetteView

WEEK_PATTERN = r"^\d{4}-W\d{2}$"

Topic = Literal["food", "culture", "city", "sport", "nature", "work", "politics"]
ClaimKind = Literal["fact", "interpretation", "forecast"]
Outfit = Literal["coat", "suit", "apron", "raincoat", "sport", "scarf_only", "chef", "hi_vis"]
Beat = Literal["arrive", "facts", "pursue", "make", "close"]
RoomPhase = Literal["open", "bouclage", "boucle"]
MakeKind = Literal["headline_choice", "headline_write", "reader_question", "short_report"]
FallbackReason = Literal["model_down", "knowledge_refused", "budget", "no_match"]
GuestPosition = Literal["for", "against", "moved"]
GuestMove = Literal["enter", "follow_up", "disagree", "moved"]
Language = Literal["en", "de", "fr"]
Purpose = Literal["understand_change", "explain_disagreement", "choose_angle", "prepare_dispatch"]
Span = tuple[int, int]


class RevueModel(BaseModel):
    """Base for every response model: unknown fields are a bug."""

    model_config = ConfigDict(extra="forbid")


class RevueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Shared types (WIRE §1)
# ---------------------------------------------------------------------------


class RvWeek(RevueModel):
    iso: str
    label: str
    range: str


class RvSource(RevueModel):
    id: str
    name: str
    url: str
    published_at: str


class RvClaim(RevueModel):
    id: str
    kind: ClaimKind
    fr: str
    quote: str
    attributed_to: str | None = None
    source: RvSource


class RvGloss(RevueModel):
    fr: str
    gloss: str
    claim_id: str


class RvStageMember(RevueModel):
    id: str
    hold: str | None = None


class RvStage(RevueModel):
    place_id: str
    place_fr: str
    plate_url: str | None
    plate_place_id: str
    place_is_real: bool
    dress: Outfit
    cast: list[RvStageMember]


class RvStoryCard(RevueModel):
    dossier_id: str
    title_fr: str
    summary_fr: str
    topic: Topic
    place_fr: str
    plate_url: str | None
    evergreen: bool
    stage: RvStage


class RvSupport(RevueModel):
    glosses: Literal["shown", "tap", "none"]
    translation: Literal["one_tap", "on_request", "none"]
    reading_target_words: int
    vocab_target: int
    level: int


class RvRoom(RevueModel):
    used: int = Field(ge=0, le=7)
    phase: RoomPhase
    remaining_turns: int = Field(ge=0)


class RvMade(RevueModel):
    kind: MakeKind
    text_fr: str
    contribution: list[Span]
    learner_fr: str | None = None


class RvDispatch(RevueModel):
    kicker_fr: str
    headline_fr: str
    body_fr: list[str]
    contribution: list[Span]
    byline_fr: str
    sources: list[RvSource]


class RvQuickReply(RevueModel):
    label: str
    send_fr: str


# ---------------------------------------------------------------------------
# Thread items (WIRE §2)
# ---------------------------------------------------------------------------


class _Item(RevueModel):
    id: str
    seq: int
    at: str


class RvNarrationItem(_Item):
    kind: Literal["narration"] = "narration"
    text_fr: str


class RvSummaryItem(_Item):
    kind: Literal["summary"] = "summary"
    speaker: str = "romy_tremblay"
    text_fr: str


class RvLineItem(_Item):
    kind: Literal["line"] = "line"
    speaker: str = "romy_tremblay"
    role: Literal["purpose", "place_note", "reply", "steer", "fallback", "make_intro", "make_done", "close"]
    text_fr: str
    translation: str | None = None
    glosses: list[RvGloss] = Field(default_factory=list)
    reason: FallbackReason | None = None   # phase 2: set on every ``fallback`` line, else null


class RvGuestItem(_Item):
    """Phase 2: a guest speaks (one guest per Papier)."""

    kind: Literal["guest"] = "guest"
    cast_id: str
    text_fr: str
    move: GuestMove
    position: GuestPosition | None = None
    reason_fr: str | None = None           # why they care, on the ``enter`` move only
    reason: FallbackReason | None = None   # an authored line stands in (model_down | knowledge_refused)
    glosses: list[RvGloss] = Field(default_factory=list)


class RvMineItem(_Item):
    kind: Literal["mine"] = "mine"
    text_fr: str
    mode: Literal["text", "voice"] = "text"


class RvClaimsItem(_Item):
    kind: Literal["claims"] = "claims"
    claims: list[RvClaim]


class RvUncertaintyItem(_Item):
    kind: Literal["uncertainty"] = "uncertainty"
    text_fr: str


class RvAngleRef(RevueModel):
    id: str
    fr: str


class RvShiftItem(_Item):
    kind: Literal["shift"] = "shift"
    reason: Literal["simplify", "angle", "bouclage", "boucle"]
    angle: RvAngleRef | None = None


class RvMadeItem(_Item):
    kind: Literal["made"] = "made"
    made: RvMade


RvThreadItem = Annotated[
    RvNarrationItem
    | RvSummaryItem
    | RvLineItem
    | RvGuestItem
    | RvMineItem
    | RvClaimsItem
    | RvUncertaintyItem
    | RvShiftItem
    | RvMadeItem,
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# GET /revue/week, POST /revue/match (WIRE §3.1, §3.2)
# ---------------------------------------------------------------------------


class RvResume(RevueModel):
    session_id: str
    dossier_id: str
    title_fr: str
    started_at: str
    beat: Beat
    open_question_fr: str | None = None


class RvFiled(RevueModel):
    session_id: str
    dossier_id: str
    title_fr: str
    closed_at: str
    made: RvMade | None = None
    dispatch: RvDispatch | None = None


class RvOffer(RevueModel):
    week: RvWeek
    recommended: RvStoryCard | None
    recommended_reason: Literal["topic_least_recent", "interests", "first"]
    alternatives: list[RvStoryCard]
    evergreen_only: bool
    resume: RvResume | None = None
    filed: RvFiled | None = None


class RvMatchRequest(RevueRequest):
    text: str = Field(min_length=1, max_length=300)
    week: str | None = Field(None, pattern=WEEK_PATTERN)


class RvMatchResult(RevueModel):
    match: str | None
    romy_line_fr: str | None = None


# ---------------------------------------------------------------------------
# Sessions (WIRE §3.3, §3.4)
# ---------------------------------------------------------------------------


class RvStartRequest(RevueRequest):
    week: str | None = Field(None, pattern=WEEK_PATTERN)
    dossier_id: str | None = Field(None, min_length=1, max_length=120)
    free_request: str | None = Field(None, max_length=300)
    angle_id: str | None = Field(None, min_length=1, max_length=40)


class RvDossierView(RevueModel):
    id: str
    title_fr: str
    summary_fr: str
    topic: Topic
    evergreen: bool
    sources: list[RvSource]


class RvAngle(RevueModel):
    id: str
    fr: str
    purpose: Purpose


class RvBudget(RevueModel):
    turns: int
    minutes: int


class RvPlanView(RevueModel):
    band: Literal["A1", "A2", "B1", "B2"]
    ui_language: Language
    gloss_language: Language
    chosen_by: Literal["learner", "recommended"]
    angle: RvAngle
    support: RvSupport
    vocabulary: list[RvGloss]
    make_options: list[MakeKind]
    budget: RvBudget


class RvClosedWord(RevueModel):
    fr: str
    gloss: str
    claim_id: str
    used: bool


class RvKept(RevueModel):
    words: list[RvClosedWord]
    claims: list[RvClaim]


class RvClosing(RevueModel):
    romy_line_fr: str
    dispatch: RvDispatch
    kept: RvKept
    question_kept_fr: str | None = None
    #: WP-120 §4.3: the vignette minted at close (None when minting failed or is off).
    vignette: VignetteView | None = None
    colophon_fr: Literal["La suite la semaine prochaine."] = "La suite la semaine prochaine."


class RvSessionView(RevueModel):
    id: str
    week: RvWeek
    status: Literal["active", "closed", "abandoned"]
    started_at: str
    closed_at: str | None = None
    dossier: RvDossierView
    plan: RvPlanView
    stage: RvStage
    beat: Beat
    room: RvRoom
    thread: list[RvThreadItem]
    quick_replies: list[RvQuickReply]
    steer_to_make: bool
    artifact: RvMade | None = None
    closing: RvClosing | None = None


# ---------------------------------------------------------------------------
# Turns (WIRE §3.5)
# ---------------------------------------------------------------------------


class RvTurnRequest(RevueRequest):
    text: str = Field(min_length=1, max_length=600)
    mode: Literal["text", "voice"] = "text"
    client_turn_id: str | None = Field(None, min_length=1, max_length=64)


Outcome = Literal["correct", "incorrect", "unscored"]


class RvWordEvidence(RevueModel):
    fr: str
    outcome: Outcome
    capability_known: bool


class RvEvidence(RevueModel):
    outcome: Outcome
    capability_known: bool
    grader: str
    # Phase 2 (revue-rubric-v1): per target word, the fact fit and the register note (a code).
    words: list[RvWordEvidence] = Field(default_factory=list)
    fact_fit: Literal["supported", "unsupported", "contradicted", "not_applicable"] = "not_applicable"
    register_note: Literal["ok", "vous_to_tu", "tu_to_vous"] = "ok"


class RvTurnResult(RevueModel):
    items: list[RvThreadItem]
    beat: Beat
    room: RvRoom
    support: RvSupport
    quick_replies: list[RvQuickReply]
    steer_to_make: bool
    evidence: RvEvidence


# ---------------------------------------------------------------------------
# Make (WIRE §3.6, §3.7)
# ---------------------------------------------------------------------------


class RvHeadlineOption(RevueModel):
    id: str
    text_fr: str


class RvHeadlineChoiceOffer(RevueModel):
    kind: Literal["headline_choice"] = "headline_choice"
    options: list[RvHeadlineOption]


class RvReaderQuestionOffer(RevueModel):
    kind: Literal["reader_question"] = "reader_question"
    seed_fr: str | None = None
    uncertainty_fr: str | None = None


class RvHeadlineWriteOffer(RevueModel):
    kind: Literal["headline_write"] = "headline_write"
    max_words: int


class RvShortReportOffer(RevueModel):
    kind: Literal["short_report"] = "short_report"
    seconds: int = 30


class RvMakeOffer(RevueModel):
    recommended: MakeKind
    options: list[
        Annotated[
            RvHeadlineChoiceOffer | RvHeadlineWriteOffer | RvReaderQuestionOffer | RvShortReportOffer,
            Field(discriminator="kind"),
        ]
    ]
    intro: RvLineItem | None = None        # Romy's ``make_intro`` line (written once, on the first GET)


class RvHeadlinePick(RevueRequest):
    kind: Literal["headline_choice"]
    action: Literal["pick"]
    option_id: str = Field(min_length=1, max_length=40)


class RvQuestionPropose(RevueRequest):
    kind: Literal["reader_question"]
    action: Literal["propose"]
    text: str | None = Field(None, max_length=400)


class RvQuestionSend(RevueRequest):
    kind: Literal["reader_question"]
    action: Literal["send"]
    text_fr: str = Field(min_length=1, max_length=300)


class RvHeadlineWrite(RevueRequest):
    kind: Literal["headline_write"]
    action: Literal["write"]
    text_fr: str = Field(min_length=1, max_length=160)


class RvShortReport(RevueRequest):
    kind: Literal["short_report"]
    action: Literal["report"]
    transcript: str = Field(min_length=1, max_length=1200)
    mode: Literal["text", "voice"] = "voice"


RvMakeRequest = Annotated[
    RvHeadlinePick | RvQuestionPropose | RvQuestionSend | RvHeadlineWrite | RvShortReport,
    Field(discriminator="action"),
]


class RvHeadlineEvidence(RevueModel):
    claim_id: str
    quote: str
    source: RvSource


class RvHeadlinePickResult(RevueModel):
    kind: Literal["headline_choice"] = "headline_choice"
    correct: bool
    answer_id: str
    evidence: RvHeadlineEvidence
    made: RvMade
    line: RvLineItem | None = None         # Romy's ``make_done`` line


class RvQuestionDraft(RevueModel):
    learner_fr: str
    proposal_fr: str
    contribution: list[Span]
    why_native: str | None = None


class RvQuestionProposeResult(RevueModel):
    kind: Literal["reader_question"] = "reader_question"
    draft: RvQuestionDraft


class RvQuestionSendResult(RevueModel):
    kind: Literal["reader_question"] = "reader_question"
    made: RvMade
    line: RvLineItem | None = None


class RvHeadlineWriteResult(RevueModel):
    kind: Literal["headline_write"] = "headline_write"
    accepted: bool                         # false: a shown claim contradicts it; nothing filed, write again
    evidence: RvEvidence
    made: RvMade | None = None
    line: RvLineItem | None = None


class RvShortReportResult(RevueModel):
    kind: Literal["short_report"] = "short_report"
    evidence: RvEvidence
    made: RvMade
    line: RvLineItem | None = None


RvMakeResult = (
    RvHeadlinePickResult
    | RvQuestionProposeResult
    | RvQuestionSendResult
    | RvHeadlineWriteResult
    | RvShortReportResult
)


# ---------------------------------------------------------------------------
# Close (WIRE §3.8)
# ---------------------------------------------------------------------------


class RvCloseResult(RevueModel):
    session: RvSessionView
    closing: RvClosing


__all__ = [name for name in dir() if name.startswith("Rv")] + ["WEEK_PATTERN"]
