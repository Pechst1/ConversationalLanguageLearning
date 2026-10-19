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

#: A period: an ISO week under weekly cadence, an ISO date under daily (WP-119 §12.2, phase 3).
WEEK_PATTERN = r"^\d{4}-(W\d{2}|\d{2}-\d{2})$"

Topic = Literal["food", "culture", "city", "sport", "nature", "work", "politics"]
ClaimKind = Literal["fact", "interpretation", "forecast"]
Outfit = Literal["coat", "suit", "apron", "raincoat", "sport", "scarf_only", "chef", "hi_vis"]
Beat = Literal["arrive", "facts", "pursue", "make", "close"]
RoomPhase = Literal["open", "bouclage", "boucle"]
#: ``caption`` (WP-119 §8.4, «La légende»): the caption under the story's picture.
#: ``opinion`` («Au comptoir», 2026-10-19): the learner's quote in Romy's vox pop.
MakeKind = Literal["headline_choice", "headline_write", "reader_question", "short_report", "caption", "opinion"]
#: WP-119 §8.4: what the site's plate is — the story's own picture, a painted place, a season plate, a stand-in.
PlateKind = Literal["story", "painted", "season", "stand_in"]
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
    #: WP-119 phase 4 (§12.7): the second view (``places[1]``) for ``pursue``/``make``, and
    #: whether the stage has switched to it (at the guest's entrance, or at ``make``).
    plate_url_second: str | None = None
    plate_switched: bool = False
    #: WP-119 §8.4: ``story`` when ``plate_url`` is the story's own picture (painted once at
    #: intake, shared by every learner) and, in a session, the words the picture shows,
    #: glossed in the plan's gloss language (they lead the vocabulary). The desk's caption is
    #: not sent here: it is the answer of «La légende»; the dispatch prints it after the close.
    plate_kind: PlateKind = "season"
    picture_words: list[RvGloss] = Field(default_factory=list)


class RvStoryCard(RevueModel):
    dossier_id: str
    title_fr: str
    #: Home's news card (2026-10-18): six words or fewer; ``None`` before the leads were written.
    headline_fr: str | None = None
    summary_fr: str
    topic: Topic
    place_fr: str
    plate_url: str | None
    evergreen: bool
    stage: RvStage
    #: «Au comptoir» (WP-119, 2026-10-19): the question of the day and the three regulars
    #: (cast ids, in seat order) when the switch is on and the story has takes; else ``None``.
    question_fr: str | None = None
    cast: list[str] | None = None


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
    #: WP-119 §8.4: the story's picture printed with the dispatch, and its caption — the
    #: learner's («La légende», ``caption_by_learner``) or the desk's.
    picture_url: str | None = None
    caption_fr: str | None = None
    caption_by_learner: bool = False


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
    """What happened (2026-10-18): the lead at the learner's band (B1+: the summary), shown as
    text with its translation where the band has the translate button, read aloud on a tap."""

    kind: Literal["summary"] = "summary"
    speaker: str = "romy_tremblay"
    text_fr: str
    translation: str | None = None
    glosses: list[RvGloss] = Field(default_factory=list)


class RvLineItem(_Item):
    kind: Literal["line"] = "line"
    speaker: str = "romy_tremblay"
    #: ``look`` (WP-119 §8.4): on arrival, Romy points at the story's picture with its words.
    role: Literal["purpose", "place_note", "look", "reply", "steer", "fallback", "make_intro", "make_done", "close"]
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
    #: The rubric's register note on this line (from its ``evidence`` event), replayed
    #: on every read so the note under the learner's line survives a reload; ``None``
    #: when the register was fine or the turn was not graded.
    register_note: Literal["vous_to_tu", "tu_to_vous"] | None = None


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
    #: The rubric's outcome for this word across the session's evidence (a word used
    #: correctly once stays ``correct``), filled at close so the mark survives a reload;
    #: ``None`` when the word never came up in a graded turn (and on closings stored
    #: before this field).
    outcome: Literal["correct", "incorrect", "unscored"] | None = None


class RvKept(RevueModel):
    words: list[RvClosedWord]
    claims: list[RvClaim]


# ---------------------------------------------------------------------------
# «Au comptoir» (WP-119, owner 2026-10-19; WIRE §3.9)
# ---------------------------------------------------------------------------

ComptoirStep = Literal["read", "takes", "intox", "opinion", "page"]
ComptoirStance = Literal["pour", "contre", "nuance"]
ComptoirAct = Literal["vote", "react", "intox_who", "intox_fix", "opinion", "comeback"]


class RvComptoirText(RevueModel):
    """A line and its translation in the learner's gloss language (``None`` for French)."""

    fr: str
    tr: str | None = None


class RvComptoirCast(RevueModel):
    id: str
    name_fr: str
    role_fr: str
    stance: ComptoirStance
    #: The take at the learner's band.
    take: RvComptoirText
    reaction: Literal["agree", "disagree"] | None = None


class RvComptoirRead(RevueModel):
    #: «Paris, le 18 octobre» (the place alone for an evergreen).
    dateline_fr: str
    #: What happened, at the learner's band.
    lead: RvComptoirText
    sources: list[RvSource]


class RvComptoirQuote(RevueModel):
    cast_id: str
    name_fr: str
    role_fr: str
    stance: ComptoirStance
    quote_fr: str


class RvComptoirFix(RevueModel):
    correct: bool
    answer_fr: str
    #: «C'est faux, Gus ! C'est plus de 500 000 personnes, pas un million de personnes.»
    line_fr: str
    wrong_fr: str
    right_fr: str
    claim: RvClaim | None = None
    caught: RvComptoirText


class RvComptoirIntox(RevueModel):
    """Step 3. Who lied (``by``), the true value and the distractor are absent until the
    learner named the liar or used their two tries."""

    quotes: list[RvComptoirQuote]
    tries: list[str]
    resolved: bool
    found: bool | None = None
    by: str | None = None
    #: The claim to reread, after a wrong guess.
    hint_claim: RvClaim | None = None
    ask: RvComptoirText | None = None
    #: A1–A2: the true value and the distractor, in a per-session order.
    options: list[str] = Field(default_factory=list)
    #: B1+: «C'est faux, Gus ! C'est …, pas un million de personnes.»
    prefill_fr: str | None = None
    fix: RvComptoirFix | None = None


class RvComptoirKit(RevueModel):
    """Step 4's material: A1 tiles, A2 frame and word bank, B1+ free text."""

    input: Literal["tiles", "frame", "free"]
    phrase: RvComptoirText
    reasons: dict[ComptoirStance, list[RvComptoirText]]
    frames: dict[ComptoirStance, RvComptoirText]
    bank: list[RvComptoirText]
    #: Who answers a learner on each side (B1: «Réponds à …»).
    opponents: dict[ComptoirStance, str]


class RvComptoirNote(RevueModel):
    span_fr: str
    why: str


class RvComptoirReply(RevueModel):
    by: str
    name_fr: str
    line: RvComptoirText


class RvComptoirComeback(RevueModel):
    text_fr: str
    index: int | None = None
    #: The guest's last word.
    last_word: RvComptoirText


class RvComptoirOpinion(RevueModel):
    stance: ComptoirStance
    learner_fr: str
    #: Romy's edit (the learner's own sentence when the edit failed its checks).
    edited_fr: str
    notes: list[RvComptoirNote]
    reply: RvComptoirReply
    #: A1–A2: the three comeback chips; empty from B1 (one free line).
    comebacks: list[RvComptoirText]
    comeback: RvComptoirComeback | None = None


class RvComptoirView(RevueModel):
    step: ComptoirStep
    #: The dots: five, or four when the learner's band has no intox.
    steps: list[ComptoirStep]
    band: Literal["a1", "a2", "b1"]
    question: RvComptoirText
    read: RvComptoirRead
    cast: list[RvComptoirCast]
    has_intox: bool
    vote: ComptoirStance | None = None
    intox: RvComptoirIntox | None = None
    kit: RvComptoirKit | None = None
    opinion: RvComptoirOpinion | None = None


class RvComptoirVotes(RevueModel):
    pour: int
    contre: int
    nuance: int


class RvComptoirPageIntox(RevueModel):
    by: str
    name_fr: str
    wrong_fr: str
    right_fr: str
    source_name: str


class RvComptoirPage(RevueModel):
    """«La page»: Romy's vox pop, the learner's quote printed with the regulars'."""

    question_fr: str
    dateline_fr: str
    standfirst_fr: str
    quotes: list[RvComptoirQuote]
    mine: RvComptoirQuote
    votes: RvComptoirVotes
    intox: RvComptoirPageIntox | None = None
    phrase_fr: str
    words: list[str]


class RvComptoirRequest(RevueRequest):
    act: ComptoirAct
    guest_id: str | None = Field(None, min_length=1, max_length=40)
    #: vote: the side; react: agree | disagree; intox_fix (A1–A2): the value picked;
    #: opinion: the side.
    value: str | None = Field(None, max_length=200)
    #: intox_fix (B1+), opinion (A2+), comeback (B1+).
    text: str | None = Field(None, max_length=600)
    mode: Literal["text", "voice"] = "text"
    #: opinion at A1: the reason tile.
    reason_index: int | None = Field(None, ge=0, le=9)
    #: comeback at A1–A2: the chip.
    index: int | None = Field(None, ge=0, le=9)


class RvClosing(RevueModel):
    romy_line_fr: str
    dispatch: RvDispatch
    kept: RvKept
    question_kept_fr: str | None = None
    #: WP-120 §4.3: the vignette minted at close (None when minting failed or is off).
    vignette: VignetteView | None = None
    #: «La suite demain.» when the Papier is daily (its period is a day, §12.2).
    colophon_fr: Literal["La suite la semaine prochaine.", "La suite demain."] = "La suite la semaine prochaine."
    #: «Au comptoir»: «La page» (``None`` for a chat session).
    comptoir_page: RvComptoirPage | None = None


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
    #: «Au comptoir» (WP-119, 2026-10-19): the mode the session started in, for its whole life.
    mode: Literal["chat", "comptoir"] = "chat"
    comptoir: RvComptoirView | None = None


class RvComptoirResult(RevueModel):
    session: RvSessionView
    #: A reason the act was not recorded, said on the same screen («Choisis une raison.»).
    error_fr: str | None = None


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
    # WP-119 §10e.8: the critic had not answered within 2 s; this turn's evidence lands on the next turn.
    pending: bool = False


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


class RvCaptionOption(RevueModel):
    id: str
    text_fr: str


class RvCaptionOffer(RevueModel):
    """WP-119 §8.4 «La légende»: the caption under the story's picture. ``choice`` (A1–A2): three
    captions, one says what the picture shows; ``write`` (B1+): the learner writes it, at most
    ``max_words`` words, with the picture's words as chips."""

    kind: Literal["caption"] = "caption"
    format: Literal["choice", "write"]
    picture_url: str
    options: list[RvCaptionOption] = Field(default_factory=list)
    words: list[RvGloss] = Field(default_factory=list)
    max_words: int = 16


class RvMakeOffer(RevueModel):
    recommended: MakeKind
    options: list[
        Annotated[
            RvHeadlineChoiceOffer | RvHeadlineWriteOffer | RvReaderQuestionOffer | RvShortReportOffer | RvCaptionOffer,
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


class RvCaptionMake(RevueRequest):
    """«La légende»: ``option_id`` for the choice, ``text_fr`` for the written caption."""

    kind: Literal["caption"]
    action: Literal["caption"]
    option_id: str | None = Field(None, min_length=1, max_length=40)
    text_fr: str | None = Field(None, min_length=1, max_length=200)


RvMakeRequest = Annotated[
    RvHeadlinePick | RvQuestionPropose | RvQuestionSend | RvHeadlineWrite | RvShortReport | RvCaptionMake,
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


class RvCaptionResult(RevueModel):
    """The caption filed under the picture. ``choice``: ``correct`` and ``answer_id`` (a wrong pick
    files the caption the picture shows, uncredited, like the headline); ``write``: graded by the
    rubric, refused (``accepted`` false, nothing filed) when a claim contradicts it."""

    kind: Literal["caption"] = "caption"
    format: Literal["choice", "write"]
    accepted: bool
    correct: bool | None = None
    answer_id: str | None = None
    evidence: RvEvidence | None = None
    made: RvMade | None = None
    line: RvLineItem | None = None


RvMakeResult = (
    RvHeadlinePickResult
    | RvQuestionProposeResult
    | RvQuestionSendResult
    | RvHeadlineWriteResult
    | RvShortReportResult
    | RvCaptionResult
)


# ---------------------------------------------------------------------------
# Close (WIRE §3.8)
# ---------------------------------------------------------------------------


class RvCloseResult(RevueModel):
    session: RvSessionView
    closing: RvClosing


__all__ = [name for name in dir() if name.startswith("Rv")] + ["WEEK_PATTERN"]
