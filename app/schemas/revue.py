"""Wire schemas for La Revue de Romy, phases 1–2 (WP-119).

Field-for-field implementation of ``docs/implementation/atelier-v2/WP-119-WIRE.md``.
As in ``app/schemas/daily_journey.py``: public payloads are real models, never
``dict[str, Any]``, and private material (a headline exercise's answer and its
``contradicted_by`` map, the raw state log, provider prompts) has no field on any
response model, so it cannot leak by construction.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

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
MakeKind = Literal["headline_choice", "headline_write", "reader_question", "short_report", "caption", "opinion", "fil",
                   "titre", "intox", "photo", "micro"]
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


class RvPicture(RevueModel):
    """«Papier · photos» (2026-11-20): one picture of the story's gallery — a painted
    illustration (``Illustration · Le Papier``) or a real photo from Wikimedia Commons, with
    its French credit line (always printed), its licence and the link to its source."""

    kind: Literal["illustration", "photo"]
    url: str
    width: int | None = None
    height: int | None = None
    #: The image's text alternative: the caption when there is one, else ``""`` (decorative).
    alt_fr: str = ""
    #: A photo's caption, stated from the dossier's own facts (a named place); never an
    #: illustration's (the desk's caption is the answer of «La légende»).
    caption_fr: str | None = None
    #: «Photo · {author} · {licence} · Wikimedia Commons» or «Illustration · Le Papier».
    credit_fr: str
    licence: str | None = None
    #: The licence's deed, else the file's page (where the licence is stated).
    licence_url: str | None = None
    #: A photo's file page on Commons.
    source_url: str | None = None


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
    #: «Papier · photos» (2026-11-20): the story's pictures in order — its painted picture, its
    #: other painted shots (``REVUE_PICTURES_PER_STORY``), then its Commons photos
    #: (``REVUE_PHOTOS_ENABLED``). With the default switches: the painted picture alone, or none.
    pictures: list[RvPicture] = Field(default_factory=list)


class RvCardAssignment(RevueModel):
    """The assignment a story is dealt for this learner («La photo»…): the chooser names it."""

    key: str
    name_fr: str


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
    #: «Le Papier · les rubriques» (2026-11-21): the assignment the learner would be dealt
    #: (``REVUE_ASSIGNMENTS_ENABLED`` on); omitted otherwise, so the card is today's.
    assignment: RvCardAssignment | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_assignment(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        data = handler(self)
        if isinstance(data, dict) and data.get("assignment") is None:
            data.pop("assignment", None)
        return data


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


class RvAffiche(RevueModel):
    """``REVUE_QUARTIER_AFFICHE_ENABLED``: today's edition as the Quartier's Morris column
    shows it — the story's headline (our French: the lead desk's headline, else the dossier
    title) and whether this period's Papier is filed (the poster's «lu»)."""

    dossier_id: str
    headline_fr: str
    done: bool


class RvOffer(RevueModel):
    week: RvWeek
    recommended: RvStoryCard | None
    recommended_reason: Literal["topic_least_recent", "interests", "first"]
    alternatives: list[RvStoryCard]
    evergreen_only: bool
    resume: RvResume | None = None
    filed: RvFiled | None = None
    #: ``REVUE_QUARTIER_AFFICHE_ENABLED``: the poster on the quai; ``None`` with the switch
    #: off or no edition today (the column keeps its posters).
    affiche: RvAffiche | None = None


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
ComptoirAct = Literal["vote", "react", "intox_who", "intox_fix", "opinion", "opinion_fix", "comeback"]
#: What Romy marks in the learner's opinion (the learner fixes it; the hint never gives the answer).
ComptoirMarkKind = Literal["accord", "conjugaison", "genre", "orthographe", "mot", "ordre", "manque"]
#: Where the learner's opinion stands before print: ``clean`` (nothing to fix), ``marked`` (Romy's
#: marks to fix), ``fixed`` (the learner fixed them), ``corrected`` (Romy fixed what was left after the
#: tries), ``as_written`` (no check ran: printed as the learner wrote it, never «relu par Romy»).
ComptoirProof = Literal["clean", "marked", "fixed", "corrected", "as_written"]


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
    #: A1–A2: the true value and the distractor, in a per-session order. B1+ write the
    #: correction themselves (no sentence is prefilled).
    options: list[str] = Field(default_factory=list)
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


class RvComptoirMark(RevueModel):
    """One of Romy's proof marks: the learner's words to look at again (``span_fr``, at
    ``start`` in ``draft_fr``) and what kind of slip it is; never the corrected words."""

    span_fr: str
    start: int = 0
    kind: ComptoirMarkKind
    #: «Le pourquoi» (``REVUE_POURQUOI_ENABLED``): the rule in the learner's mother tongue,
    #: without the corrected form (no solution before a retry). Omitted when absent.
    why: str | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_why(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        # Additive means byte-identical with the switch off.
        data = handler(self)
        if isinstance(data, dict) and data.get("why") is None:
            data.pop("why", None)
        return data


class RvComptoirNote(RevueModel):
    """«Le pourquoi», once the opinion is settled: one of Romy's marks with its rule in full
    (``why``, the learner's mother tongue; it may show the corrected form now), the same
    pattern in today's story (``example_fr``, found by the app, never written by the model)
    and the grammar rule La Forge brings back (``rule_id``, the Correcteur's rule names)."""

    span_fr: str
    kind: ComptoirMarkKind
    why: str | None = None
    example_fr: str | None = None
    rule_id: str | None = None


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
    #: The sentence as the learner first gave it (with the A2 frame).
    learner_fr: str
    #: The learner's words, as they were at their last try.
    draft_fr: str
    proof: ComptoirProof
    #: ``marked``: what to fix in ``draft_fr`` (never the answer).
    marks: list[RvComptoirMark] = Field(default_factory=list)
    #: Fix tries used, and how many the learner gets before Romy fixes what is left.
    tries: int = 0
    max_tries: int = 2
    #: What goes to print, once the proof is settled (``None`` while ``marked``).
    printed_fr: str | None = None
    #: The regular's answer, once the sentence is printed.
    reply: RvComptoirReply | None = None
    #: A1–A2: the three comeback chips; empty from B1 (one free line).
    comebacks: list[RvComptoirText]
    comeback: RvComptoirComeback | None = None
    #: «Le pourquoi» (``REVUE_POURQUOI_ENABLED``), once settled: the marks explained. Omitted when empty.
    notes: list[RvComptoirNote] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_absent_notes(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        data = handler(self)
        if isinstance(data, dict) and not data.get("notes"):
            data.pop("notes", None)
        return data


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
    #: How the learner's quote reached print (the label under it: «tel que tu l'as écrit»,
    #: «corrigé par toi», «corrigé par Romy»); ``None`` on a page closed before 2026-10-23.
    proof: ComptoirProof | None = None
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
    #: intox_fix (B1+), opinion (A2+), opinion_fix (the sentence again, fixed), comeback (B1+).
    text: str | None = Field(None, max_length=600)
    mode: Literal["text", "voice"] = "text"
    #: opinion_fix: ``value="romy"`` (after one try) lets Romy fix what is left.
    #: opinion at A1: the reason tile.
    reason_index: int | None = Field(None, ge=0, le=9)
    #: comeback at A1–A2: the chip.
    index: int | None = Field(None, ge=0, le=9)


# ---------------------------------------------------------------------------
# «Le fil» (WP-119 «les rubriques», owner 2026-11-20; WIRE §10)
# ---------------------------------------------------------------------------

FilStep = Literal["read", "order", "words", "tell", "page"]
FilAct = Literal["open", "order", "words", "tell", "tell_fix"]
FilRole = Literal["first", "middle", "last"]


class RvFilStrip(RevueModel):
    """A dispatch of the wire at the learner's band. ``key`` is the session's own letter for
    it (``a``–``d`` in the order it was shown): it says nothing of the true order."""

    key: str
    text: RvComptoirText
    #: What the order step's reason calls it («l'annonce» · «the announcement»).
    label: RvComptoirText | None = None


class RvFilHint(RevueModel):
    """After a wrong order: the first strip out of place (``key``) happens after ``after_key``."""

    key: str
    after_key: str


class RvFilOrder(RevueModel):
    """Step 2. ``strips`` in the order they were shown; ``solution`` (the keys in true order)
    only once the order is resolved (right, or two tries used)."""

    strips: list[RvFilStrip]
    tries: int = 0
    max_tries: int = 2
    placed: list[str] = Field(default_factory=list)
    hint: RvFilHint | None = None
    resolved: bool = False
    correct: bool | None = None
    solution: list[str] = Field(default_factory=list)


class RvFilConnector(RevueModel):
    """A sequence word. ``tr`` (its gloss) and ``role`` only once the words step is resolved."""

    id: str
    fr: str
    tr: str | None = None
    role: FilRole | None = None


class RvFilMiss(RevueModel):
    """A sequence word put where it does not fit: what it means and where it goes."""

    position: int
    id: str
    fr: str
    tr: str | None = None
    role: FilRole
    #: What the position needs.
    needs: FilRole


class RvFilWords(RevueModel):
    """Step 3. ``place``: A1 puts its four words on the four strips; ``choose``: from A2 each
    strip offers three (``options``), one per role."""

    input: Literal["place", "choose"]
    #: The strips in true order (the order step is resolved).
    strips: list[RvComptoirText]
    connectors: list[RvFilConnector]
    options: list[list[str]] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    picked: list[str] = Field(default_factory=list)
    misses: list[RvFilMiss] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    solution: list[str] = Field(default_factory=list)


class RvFilTile(RevueModel):
    key: str
    text: RvComptoirText


class RvFilTell(RevueModel):
    """Step 4. A1 builds two sentences from a sequence word and an event tile each (no model
    call); A2 completes the two ``frames``; B1+ write freely with ``min_connectors`` of the
    sequence words. From A2 Romy marks, the learner fixes (as at the counter)."""

    input: Literal["tiles", "frames", "free"]
    phrase: RvComptoirText
    tiles: list[RvFilTile] = Field(default_factory=list)
    connectors: list[RvFilConnector] = Field(default_factory=list)
    frames: list[RvComptoirText] = Field(default_factory=list)
    min_words: int = 0
    min_connectors: int = 0
    #: Once told: the learner's text, Romy's marks, what prints (as ``RvComptoirOpinion``'s).
    learner_fr: str | None = None
    draft_fr: str | None = None
    proof: ComptoirProof | None = None
    marks: list[RvComptoirMark] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    printed_fr: str | None = None
    #: «Le pourquoi» (``REVUE_POURQUOI_ENABLED``), once settled: the marks explained. Omitted when empty.
    notes: list[RvComptoirNote] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_absent_notes(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        data = handler(self)
        if isinstance(data, dict) and not data.get("notes"):
            data.pop("notes", None)
        return data


class RvFilView(RevueModel):
    step: FilStep
    steps: list[FilStep]
    band: Literal["a1", "a2", "b1"]
    title_fr: str
    read: RvComptoirRead
    order: RvFilOrder | None = None
    words: RvFilWords | None = None
    tell: RvFilTell | None = None


class RvFilPageStrip(RevueModel):
    connector_fr: str
    text_fr: str


class RvFilPage(RevueModel):
    """«La page»: the wire printed in order, the learner's telling under their name."""

    title_fr: str
    dateline_fr: str
    strips: list[RvFilPageStrip]
    mine_fr: str
    proof: ComptoirProof | None = None
    phrase_fr: str
    words: list[str]


class RvFilRequest(RevueRequest):
    act: FilAct
    #: order: the strips' keys in the learner's order.
    order: list[str] | None = Field(None, max_length=4)
    #: words: a sequence word's id per strip, in order.
    picks: list[str] | None = Field(None, max_length=4)
    #: tell at A1: [word id, tile key, word id, tile key].
    parts: list[str] | None = Field(None, max_length=4)
    #: tell at A2: the end of each of the two frames.
    texts: list[str] | None = Field(None, max_length=2)
    #: tell at B1+, tell_fix: the text.
    text: str | None = Field(None, max_length=800)
    #: tell_fix: ``"romy"`` (after one try) lets Romy fix what is left.
    value: str | None = Field(None, max_length=20)
    mode: Literal["text", "voice"] = "text"


class RvFilError(RevueModel):
    """Why an act was not recorded, for the copy in the learner's language: ``code`` and the
    strips or words it is about."""

    code: str
    key: str | None = None
    after_key: str | None = None
    count: int | None = None


# ---------------------------------------------------------------------------
# «Le titre» and «L'intox express» (WP-119 «les rubriques», 2026-11-20; WIRE §11)
# ---------------------------------------------------------------------------

#: The acts of the generic assignment route (``POST /revue/sessions/{id}/rubrique``):
#: «Le titre» plays open, pick, trap, build, build_fix; «L'intox express» open, answer, fix.
RubriqueAct = Literal["open", "pick", "trap", "build", "build_fix", "answer", "fix",
                     "choose", "seen", "caption", "caption_fix", "prepare", "ask", "note", "review", "review_fix"]
TitreStep = Literal["read", "three", "trap", "build", "page"]
TitreRole = Literal["honest", "exaggerated", "off"]
IntoxStep = Literal["read", "round", "fix", "page"]


class RvRubriqueCast(RevueModel):
    """Who proposes («Le titre»: Gus, who exaggerates by character)."""

    id: str
    name_fr: str
    role_fr: str


class RvRubriqueQuote(RevueModel):
    """The outlet's verbatim words (≤ 40), its name, and the words in it that settle the
    point (``settles_fr``; empty: nothing is lit)."""

    quote_fr: str
    settles_fr: str = ""
    source_name: str


class RvTitreOption(RevueModel):
    """One headline. ``role`` once the step is resolved; ``why`` and ``claim`` on a wrong
    headline the learner picked (and on both wrong ones once resolved)."""

    key: str
    text: RvComptoirText
    role: TitreRole | None = None
    why: RvComptoirText | None = None
    claim: RvClaim | None = None


class RvTitreThree(RevueModel):
    """Step 2. ``solution`` (the honest headline's key) only once resolved (right, or two tries)."""

    by: RvRubriqueCast
    headlines: list[RvTitreOption]
    tries: int = 0
    max_tries: int = 2
    picked: list[str] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    solution: str | None = None


class RvTitreWord(RevueModel):
    index: int
    fr: str


class RvTitreTrap(RevueModel):
    """Step 3: tap the word(s) of the exaggerated headline that say too much. ``fine``: what
    the last wrong try tapped that the claims do say (never the answer); ``solution`` (the
    words' indices) only once resolved."""

    headline: RvComptoirText
    words: list[RvTitreWord]
    tries: int = 0
    max_tries: int = 2
    picked: list[int] = Field(default_factory=list)
    fine: list[int] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    solution: list[int] = Field(default_factory=list)
    why: RvComptoirText | None = None
    claim: RvClaim | None = None


class RvTitreBuild(RevueModel):
    """Step 4. A1 builds from a ``subjects`` tile and a ``facts`` tile (no model call); A2
    completes ``frame``; B1+ write freely. Never with ``avoid_fr`` (the words that said too
    much). From A2 Romy marks, the learner fixes (as «Le fil»)."""

    input: Literal["tiles", "frame", "free"]
    phrase: RvComptoirText
    subjects: list[RvComptoirText] = Field(default_factory=list)
    facts: list[RvComptoirText] = Field(default_factory=list)
    frame: RvComptoirText | None = None
    max_words: int
    avoid_fr: str
    learner_fr: str | None = None
    draft_fr: str | None = None
    proof: ComptoirProof | None = None
    marks: list[RvComptoirMark] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    printed_fr: str | None = None
    #: «Le pourquoi» (``REVUE_POURQUOI_ENABLED``), once settled: the marks explained. Omitted when empty.
    notes: list[RvComptoirNote] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_absent_notes(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        data = handler(self)
        if isinstance(data, dict) and not data.get("notes"):
            data.pop("notes", None)
        return data


class RvTitreView(RevueModel):
    step: TitreStep
    steps: list[TitreStep]
    band: Literal["a1", "a2", "b1"]
    title_fr: str
    read: RvComptoirRead
    three: RvTitreThree | None = None
    trap: RvTitreTrap | None = None
    build: RvTitreBuild | None = None


class RvTitrePage(RevueModel):
    """«La page»: the story under the learner's headline, signed."""

    headline_fr: str
    proof: ComptoirProof | None = None
    dateline_fr: str
    lead_fr: str
    honest_fr: str
    phrase_fr: str
    words: list[str]


class RvIntoxCard(RevueModel):
    """One statement. Before it is answered only ``key`` and ``text``; after, the verdict,
    ``why`` and, on a false statement or a miss, the source ``quote``."""

    key: str
    text: RvComptoirText
    answer: Literal["vrai", "faux"] | None = None
    true: bool | None = None
    correct: bool | None = None
    why: RvComptoirText | None = None
    quote: RvRubriqueQuote | None = None
    #: A false statement, once answered: the words that are wrong.
    wrong_fr: str | None = None


class RvIntoxRound(RevueModel):
    """Step 2: five statements one at a time; ``current`` is the one to answer."""

    cards: list[RvIntoxCard]
    current: str | None = None
    score: int = 0
    answered: int = 0
    total: int = 5


class RvIntoxFixItem(RevueModel):
    """A false statement to make true. A1–A2 pick (``options``: the true value and another
    of the same kind from the claims, per-session order); B1+ rewrite it. ``right_fr`` and
    ``fixed`` only once resolved (right, or two tries)."""

    key: str
    text: RvComptoirText
    wrong_fr: str
    options: list[str] = Field(default_factory=list)
    quote: RvRubriqueQuote
    tries: int = 0
    max_tries: int = 2
    attempts: list[str] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    right_fr: str | None = None
    fixed: RvComptoirText | None = None


class RvIntoxFix(RevueModel):
    input: Literal["pick", "write"]
    phrase: RvComptoirText
    items: list[RvIntoxFixItem]


class RvIntoxView(RevueModel):
    step: IntoxStep
    steps: list[IntoxStep]
    band: Literal["a1", "a2", "b1"]
    title_fr: str
    #: The story stays one tap away during the round: reading practice, not memory.
    read: RvComptoirRead
    round: RvIntoxRound | None = None
    fix: RvIntoxFix | None = None


class RvIntoxPageLine(RevueModel):
    #: The statement as it should read.
    text_fr: str
    was_false: bool
    wrong_fr: str | None = None
    answered_right: bool
    #: The learner's own correction (B1+, when it was right), else ``None``.
    learner_fr: str | None = None
    fixed_right: bool | None = None


class RvIntoxPage(RevueModel):
    """«La page»: the five statements as they should read, the score, the corrections."""

    title_fr: str
    dateline_fr: str
    lines: list[RvIntoxPageLine]
    score: int
    total: int
    fixed: int
    phrase_fr: str
    words: list[str]


# «La photo» and «Le micro» (2026-11-21; WIRE §12)
# ---------------------------------------------------------------------------

PhotoStep = Literal["read", "planche", "legende", "build", "page"]
MicroStep = Literal["read", "prepare", "interview", "notes", "review", "page"]


class RvPhotoPicture(RevueModel):
    """One picture of the story as the player shows it (``key`` per session), with its credit
    and licence printed; never which one goes with the headline before it is found."""

    key: str
    kind: Literal["illustration", "photo"]
    url: str
    credit_fr: str
    licence: str | None = None
    licence_url: str | None = None
    source_url: str | None = None
    width: int | None = None
    height: int | None = None


class RvPhotoWord(RevueModel):
    index: int
    text: RvComptoirText


class RvPhotoSeen(RevueModel):
    """«Qu'est-ce qu'on voit ?»: tap the things THIS picture shows. After a miss, ``elsewhere``
    (tapped words another picture shows) and ``missing`` (how many are still to find), never
    which; ``solution`` only once resolved."""

    words: list[RvPhotoWord]
    tries: int = 0
    max_tries: int = 2
    picked: list[int] = Field(default_factory=list)
    elsewhere: list[int] = Field(default_factory=list)
    missing: int = 0
    resolved: bool = False
    correct: bool | None = None
    solution: list[int] = Field(default_factory=list)


class RvPhotoPlanche(RevueModel):
    """Step 2: «Laquelle va avec ce titre ?» — pick the picture for the day's headline (two
    tries; a miss says, in the mother tongue, what the picked picture shows), then ``seen``."""

    headline_fr: str
    pictures: list[RvPhotoPicture]
    tries: int = 0
    max_tries: int = 2
    picked: list[str] = Field(default_factory=list)
    #: After a miss: what the last picked picture shows (its things, translated).
    shows: list[RvComptoirText] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    solution: str | None = None
    seen: RvPhotoSeen | None = None


class RvPhotoCaption(RevueModel):
    """One caption of the lead picture; ``role`` and ``why`` for a wrong one picked, and for
    all once resolved."""

    key: str
    text: RvComptoirText
    role: Literal["right", "wrong", "other"] | None = None
    why: RvComptoirText | None = None


class RvPhotoFix(RevueModel):
    """«Qu'est-ce qui est faux ?»: A1–A2 pick (``options``), B1+ rewrite. ``right_fr`` and
    ``fixed`` only once resolved."""

    input: Literal["pick", "write"]
    text: RvComptoirText
    wrong_fr: str
    options: list[str] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    attempts: list[str] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    right_fr: str | None = None
    fixed: RvComptoirText | None = None


class RvPhotoLegende(RevueModel):
    """Step 3: the lead picture and three captions: find the one with the wrong fact (two
    tries), then say what is wrong (``fix``)."""

    picture: RvPhotoPicture
    captions: list[RvPhotoCaption]
    tries: int = 0
    max_tries: int = 2
    picked: list[str] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    solution: str | None = None
    fix: RvPhotoFix | None = None


class RvPhotoChoice(RevueModel):
    """A picture «À toi» can caption, with what it shows (A1 tiles, the word bank from A2)."""

    picture: RvPhotoPicture
    seen: list[RvComptoirText]


class RvPhotoBuild(RevueModel):
    """Step 4: the learner's caption for a picture of their choice. A1 builds it from a thing
    seen and a fact (no model call); A2 completes ``frame``; B1+ write two sentences (what
    the picture shows, then the news). Then Romy's marks, the learner's fix, as «Le titre»."""

    input: Literal["tiles", "frame", "free"]
    phrase: RvComptoirText
    choices: list[RvPhotoChoice]
    facts: list[RvComptoirText] = Field(default_factory=list)
    frame: RvComptoirText | None = None
    max_words: int
    picture: str | None = None
    learner_fr: str | None = None
    draft_fr: str | None = None
    proof: ComptoirProof | None = None
    marks: list[RvComptoirMark] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    printed_fr: str | None = None
    notes: list[RvComptoirNote] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_absent_notes(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        data = handler(self)
        if isinstance(data, dict) and not data.get("notes"):
            data.pop("notes", None)
        return data


class RvPhotoView(RevueModel):
    step: PhotoStep
    steps: list[PhotoStep]
    band: Literal["a1", "a2", "b1"]
    title_fr: str
    read: RvComptoirRead
    planche: RvPhotoPlanche | None = None
    legende: RvPhotoLegende | None = None
    build: RvPhotoBuild | None = None


class RvPhotoPage(RevueModel):
    """«La page»: the picture printed large with the learner's caption, its credit, signed."""

    title_fr: str
    dateline_fr: str
    picture: RvPhotoPicture
    caption_fr: str
    proof: ComptoirProof | None = None
    phrase_fr: str
    words: list[str]


class RvMicroHole(RevueModel):
    """One of Romy's notes with a hole («Combien ? ___»)."""

    key: str
    hole: RvComptoirText
    #: The interview: the witness's answer filled it.
    filled: bool = False


class RvMicroPrepare(RevueModel):
    """Step 2: what Romy still needs; the learner chooses ``need`` of them to go after."""

    holes: list[RvMicroHole]
    chosen: list[str] = Field(default_factory=list)
    need: int = 3


class RvMicroTile(RevueModel):
    key: str
    text: RvComptoirText


class RvMicroTurn(RevueModel):
    """One question and the witness's line. ``kind``: ``answer`` (a hole filled, ``hole_key``),
    ``again`` (asked before), ``shrug`` (the story cannot answer). ``spent``: it used a turn.
    A question's form is never judged here (the slips wait for «Relis tes questions»)."""

    question_fr: str
    answer: RvComptoirText
    kind: Literal["answer", "again", "shrug"]
    spent: bool
    hole_key: str | None = None


class RvMicroInterview(RevueModel):
    """Step 3: three turns. A1 picks a question tile; A2 completes a frame; B1+ write."""

    witness: RvRubriqueCast
    input: Literal["tiles", "frame", "free"]
    phrase: RvComptoirText
    holes: list[RvMicroHole]
    tiles: list[RvMicroTile] = Field(default_factory=list)
    frames: list[RvComptoirText] = Field(default_factory=list)
    turns: list[RvMicroTurn] = Field(default_factory=list)
    spent: int = 0
    total: int = 3
    #: This turn's first shrug (or repeat) is free.
    free: bool = True
    done: bool = False


class RvMicroNote(RevueModel):
    """A hole to fill from the witness's line: A1–A2 pick (``options``), B1+ type."""

    key: str
    hole: RvComptoirText
    answer: RvComptoirText
    options: list[str] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    attempts: list[str] = Field(default_factory=list)
    resolved: bool = False
    correct: bool | None = None
    value_fr: str | None = None


class RvMicroNotes(RevueModel):
    input: Literal["pick", "write"]
    items: list[RvMicroNote]


class RvMicroHint(RevueModel):
    """A slip the app saw in a question («inversion», «question_word»): the rule, said in the
    learner's language, never the corrected question."""

    index: int
    code: Literal["inversion", "question_word"]


class RvMicroReview(RevueModel):
    """Step 5: the learner's questions with Romy's marks, fix-it-yourself first."""

    input: Literal["tiles", "write"]
    questions: list[str]
    hints: list[RvMicroHint] = Field(default_factory=list)
    draft_fr: str | None = None
    proof: ComptoirProof | None = None
    marks: list[RvComptoirMark] = Field(default_factory=list)
    tries: int = 0
    max_tries: int = 2
    printed_fr: str | None = None
    notes: list[RvComptoirNote] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_absent_notes(self, handler: Any):  # noqa: ANN202 - no return type: the schema stays the fields
        data = handler(self)
        if isinstance(data, dict) and not data.get("notes"):
            data.pop("notes", None)
        return data


class RvMicroView(RevueModel):
    step: MicroStep
    steps: list[MicroStep]
    band: Literal["a1", "a2", "b1"]
    title_fr: str
    read: RvComptoirRead
    prepare: RvMicroPrepare | None = None
    interview: RvMicroInterview | None = None
    notes: RvMicroNotes | None = None
    review: RvMicroReview | None = None


class RvMicroPageLine(RevueModel):
    question_fr: str
    answer_fr: str
    source_name: str


class RvMicroPageNote(RevueModel):
    hole_fr: str
    value_fr: str
    right: bool


class RvMicroPage(RevueModel):
    """«La page»: the interview as Q&A under the learner's name, the facts' sources printed."""

    title_fr: str
    dateline_fr: str
    witness: RvRubriqueCast
    byline_fr: str
    lines: list[RvMicroPageLine]
    notes: list[RvMicroPageNote]
    proof: ComptoirProof | None = None
    phrase_fr: str
    words: list[str]


class RvRubriqueRequest(RevueRequest):
    act: RubriqueAct
    #: pick: a headline's key; answer, fix: a statement's key.
    key: str | None = Field(None, max_length=4)
    #: answer: ``vrai`` | ``faux``; fix (A1–A2): the picked value; build_fix: ``romy``.
    value: str | None = Field(None, max_length=120)
    #: trap: the indices of the tapped words.
    words: list[int] | None = Field(None, max_length=20)
    #: build at A1: [subject index, fact index].
    parts: list[int] | None = Field(None, max_length=2)
    #: build (A2: the end of the frame; B1+: the headline), build_fix, fix (B1+): the text.
    text: str | None = Field(None, max_length=300)
    #: «Le micro» prepare: the keys of the holes the learner goes after.
    keys: list[str] | None = Field(None, max_length=6)
    mode: Literal["text", "voice"] = "text"


class RvRubriqueError(RevueModel):
    """Why an act was not recorded, for the copy in the learner's language."""

    code: str
    key: str | None = None
    count: int | None = None


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
    #: «Le fil»: «La page» (``None`` otherwise).
    fil_page: RvFilPage | None = None
    #: «Le titre» and «L'intox express»: «La page» (``None`` otherwise).
    titre_page: RvTitrePage | None = None
    intox_page: RvIntoxPage | None = None
    #: «La photo» and «Le micro» (2026-11-21): «La page» (``None`` otherwise).
    photo_page: RvPhotoPage | None = None
    micro_page: RvMicroPage | None = None


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
    #: The learner has typed or said a line of their own (a quick-reply chip is not one):
    #: «Écrire le papier» and Romy's steer to the make wait for it (2026-10-23).
    own_line: bool = False
    artifact: RvMade | None = None
    closing: RvClosing | None = None
    #: «Au comptoir» (WP-119, 2026-10-19): the mode the session started in, for its whole life.
    mode: Literal["chat", "comptoir", "fil", "titre", "intox", "photo", "micro"] = "chat"
    comptoir: RvComptoirView | None = None
    #: «Le fil» (2026-11-20): the player's view, for a session dealt that assignment.
    fil: RvFilView | None = None
    #: «Le titre» and «L'intox express» (2026-11-20): the dealt assignment's view.
    titre: RvTitreView | None = None
    intox: RvIntoxView | None = None
    #: «La photo» and «Le micro» (2026-11-21): the dealt assignment's view.
    photo: RvPhotoView | None = None
    micro: RvMicroView | None = None


class RvComptoirResult(RevueModel):
    session: RvSessionView
    #: A reason the act was not recorded, said on the same screen («Choisis une raison.»).
    error_fr: str | None = None


class RvFilResult(RevueModel):
    session: RvSessionView
    #: Why the act was not recorded (the client says it in the learner's language).
    error: RvFilError | None = None


class RvRubriqueResult(RevueModel):
    """«Le titre», «L'intox express»: the session after one act, and why it was not recorded."""

    session: RvSessionView
    error: RvRubriqueError | None = None


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
    own_line: bool = False
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
    """WP-119 §8.4 «La légende»: the caption under the story's picture. Every band writes it, at
    most ``max_words`` words, with the picture's words as chips (2026-10-23). ``options``: at
    A1–A2, after a refused try, three captions to choose from instead (one says what the
    picture shows); empty before. ``choice`` is no longer offered first."""

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
    #: A refused written caption at A1–A2: the three captions to choose from, if the learner
    #: would rather pick than write again.
    options: list[RvCaptionOption] = Field(default_factory=list)


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
