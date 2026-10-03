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
PLAN_CONTRACT_VERSION = 3
DEFAULT_BUDGET_SECONDS = 300
MAX_PLANNED_STEPS = 5
MAX_RECALL_STEPS = 2
#: The ceiling on a reply's normal turns. The rhythm decides how many a day
#: actually plans (``RhythmCaps.max_turns``); authored scenes keep their own two.
MAX_RESPOND_TURNS = 4
#: A short day still has to be a day: scene, response, ending.
MIN_PLANNED_STEPS = 3
#: WP-78 — «une vraie journée de pratique». Plan contract version 3 adds the
#: *practice day*: quick recall items around the episode — warm-ups before the
#: scene, the rest after the ending (WP-109: never inside the episode).
#: A plan is a practice day only when ``PlannedJourney.practice`` says so, so
#: every plan persisted before WP-78 validates under exactly the envelope it
#: was built for (the five-step constants above).
MAX_PRACTICE_STEPS = 10
MAX_PRACTICE_RECALL_STEPS = 6
#: Warm-ups are the only steps that may come before the scene.
MAX_WARMUP_RECALL_STEPS = 3


# --------------------------------------------------------------------------
# WP-L6 — the rhythm sizes the day
# --------------------------------------------------------------------------

#: The four rhythms' budgets (WORK-PACKAGES-2026-09-23-learning §2.2): Léger
#: 5 min, Régulier 10 (the default), Soutenu 20, Intensif 30. A longer rhythm
#: makes the movements longer, never more numerous — one scene, one reply, one
#: ending on every rhythm (no rhythm plans a second episode).
RHYTHM_BUDGETS: tuple[int, ...] = (300, 600, 1200, 1800)


@dataclass(frozen=True, slots=True)
class RhythmCaps:
    """How big a practice day may get at one budget.

    The 300-second row is exactly the WP-78 envelope (the constants above).
    WP-93 «Plus d'histoire, moins d'exercices»: a longer rhythm buys input
    (a longer page, heard lines, the «Lecture» step), not more drills, so the
    recall ceiling is about 6 · 12 · 20 · 28 items (Léger · Régulier · Soutenu
    · Intensif) and at least :data:`INPUT_FLOOR_SHARE` of the budget is kept
    for reading and listening. ``max_mid`` is kept as a name: those builds now
    come *after* the reply (W5 — nothing sits between a character's question
    and the learner's answer). The counts are ceilings — the planner still
    fills only what the budget's seconds and today's pool allow.
    """

    budget_seconds: int
    max_steps: int
    max_recall: int
    max_warmups: int
    max_mid: int
    max_post: int
    #: The item count the WP-86 floor tops a thin day up to.
    target_items: int
    #: How many candidates the day asks the learning layer for.
    candidate_limit: int
    #: How often one target may come back in one day (never in the same format).
    uses_per_target: int
    #: The reply's exchanges. A story-engine scene keeps the conversation going
    #: until the last one (``turn_plan.keep_talking``): two on Léger, three on
    #: Régulier, four on Soutenu and Intensif. Authored scenes stay at their two.
    max_turns: int
    #: How many of the learner's daily new words the word drill leaves for the
    #: day until the day is planned (§5: one intake pool, the journey first).
    journey_new_words: int
    #: WP-93: how many «Lecture» pages (READ steps) the day may plan — one on
    #: Soutenu, two on Intensif («coulisses» and yesterday's page).
    max_reads: int = 0
    #: WP-93: heard items (a listen-and-tap or a dictation that carries a clip)
    #: a paged day may add *beyond* ``max_recall``: listening is input, and a
    #: longer rhythm buys input, not more drills.
    max_heard: int = 0


RHYTHM_CAPS: dict[int, RhythmCaps] = {
    300: RhythmCaps(300, MAX_PRACTICE_STEPS, MAX_PRACTICE_RECALL_STEPS,
                    MAX_WARMUP_RECALL_STEPS, 2, 1, 5, 8, 2, 2, 2),
    # WP-93: steps = recall + heard + scene, reply, ending, rule, forge and
    # the «Lecture» pages.
    600: RhythmCaps(600, 18, 12, 5, 5, 2, 10, 16, 2, 3, 4),
    1200: RhythmCaps(1200, 32, 20, 8, 8, 4, 16, 32, 3, 4, 8, max_reads=1, max_heard=6),
    1800: RhythmCaps(1800, 49, 28, 11, 11, 6, 24, 48, 3, 4, 12, max_reads=2, max_heard=12),
}

#: WP-93. At least this share of a day's budget is reading or listening — the
#: page (its panels and lines, and their audio when the deployment speaks),
#: the heard items and the «Lecture» step. The planner keeps it free of drills.
INPUT_FLOOR_SHARE = 0.35
#: WP-93. The «Lecture» step (a second page to read) is planned only from this
#: budget up: Soutenu and Intensif buy input, not more drills.
READ_MIN_BUDGET_SECONDS = 1200


def rhythm_caps(budget_seconds: int | None) -> RhythmCaps:
    """The caps of the largest rhythm that fits ``budget_seconds``.

    Anything under five minutes (or unknown) reads the five-minute row, which
    is the pre-WP-L6 envelope.
    """

    budget = int(budget_seconds or DEFAULT_BUDGET_SECONDS)
    fitting = [value for value in RHYTHM_BUDGETS if value <= budget]
    return RHYTHM_CAPS[max(fitting) if fitting else RHYTHM_BUDGETS[0]]


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
    #: WP-L4 «Règle»: the day's new grammar unit, as its rule card, followed by
    #: its guided items. WP-93 (W5): read *before* the scene — the reply asks
    #: for the unit, and nothing may sit between the scene's closing question
    #: and the reply. Not answered: it is advanced, like the scene, and
    #: advancing it introduces the unit.
    RULE = "rule"
    #: WP-S4 «La Forge», folded into a Soutenu/Intensif day: a hand-off step
    #: that opens the forge block on today's rule and comes back to the day.
    #: WP-93: with the rule, before the scene. Not answered here: the forge
    #: credits its own items; the step is advanced when the learner returns.
    FORGE = "forge"
    #: WP-93 «Lecture»: a second page to read on a long rhythm — yesterday's
    #: page again («relecture», heard when audio is on) or today's evening from
    #: another cast member's side («coulisses»). Optional, advanced not
    #: answered, at most one a day, after the ending.
    READ = "read"


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
    * ``REVUE`` — «jour du Papier» (WP-119 phase 3): once a week, never on a
      season tentpole, the day is a short classic story day (scene, at most two
      recalls, the reply, the ending — five steps at most, inside the budget,
      no practice items) and the journey player mounts Le Papier de Romy
      (``RvEncounter``) after the ending. Dealt only while ``REVUE_ENABLED``.
    """

    STANDARD = "standard"
    LETTER = "letter"
    LISTENING = "listening"
    REPRISE = "reprise"
    SHORT = "short"
    REVUE = "revue"


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
    #: WP-78. Four French cards, four cards in the learner's language, tap to
    #: pair. Graded on the day's target only: the other three pairs are context.
    MATCH_PAIRS = "match_pairs"
    #: WP-78. Hear (or, with no audio on the deployment, read) a French phrase
    #: and tap its meaning among three cards in the learner's language.
    LISTEN_TAP = "listen_tap"
    #: WP-78. Rebuild a sentence the learner has just read in the scene.
    UNSCRAMBLE = "unscramble"
    #: WP-86. «Qui a dit ça ?» — a line of today's scene and the cast's faces;
    #: tap who said it. A pick graded by option id, posed only after the scene.
    WHO_SAID = "who_said"
    #: WP-91. «Dictée» — one short line of today's scene is *heard* (never
    #: printed: the public prompt carries only the instruction and the clip)
    #: and typed. Answered with ``TextAttemptInput``; case, punctuation,
    #: apostrophes and quotes never count, a missing accent is partly met.
    #: Posed only when the deployment can speak (``audio_available``).
    DICTATION = "dictation"


#: Wire-order tuple. Extending it is additive; reordering it is not, because
#: the frontend renderer table and the parity fixtures read this order.
RECALL_FORMATS: tuple[str, ...] = tuple(str(value) for value in RecallFormat)
#: The six a plan could pose before WP-78 (plan contract version 2).
CLASSIC_RECALL_FORMATS: tuple[str, ...] = RECALL_FORMATS[:6]
#: WP-78. The formats a practice day poses as quick items — each answered in a
#: few taps, each gradable on the device from the hashed key (WP-76).
QUICK_RECALL_FORMATS: tuple[str, ...] = (
    str(RecallFormat.MATCH_PAIRS),
    str(RecallFormat.LISTEN_TAP),
    str(RecallFormat.UNSCRAMBLE),
    str(RecallFormat.WHO_SAID),
    str(RecallFormat.DICTATION),
)
#: WP-91. The formats that are *heard*: with audio on the deployment each
#: carries a clip (``RecallPrompt.audio_url``); a dictation is never posed
#: without one.
LISTENING_RECALL_FORMATS: tuple[str, ...] = (
    str(RecallFormat.LISTEN_TAP),
    str(RecallFormat.DICTATION),
)
#: The three the daily loop had before WP-66. A plan persisted at plan contract
#: version 1 can only contain these.
LEGACY_RECALL_FORMATS: tuple[str, ...] = (
    str(RecallFormat.CHOICE),
    str(RecallFormat.TILES),
    str(RecallFormat.SHORT_ANSWER),
)
#: Formats a learner can answer with their voice on a listening day. A choice
#: is excluded on purpose: reading four options is not taking dictation.
#: WP-91: a listening day now poses what is actually *heard* too — the
#: listen-and-tap item with its clip, and the dictation itself.
DICTATION_RECALL_FORMATS: tuple[str, ...] = (
    str(RecallFormat.SHORT_ANSWER),
    str(RecallFormat.TRANSFORM),
    str(RecallFormat.WORD_BANK),
    str(RecallFormat.LISTEN_TAP),
    str(RecallFormat.DICTATION),
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
    #: WP-L1: ``label_fr`` is a grammar concept's *title*, not a phrase the
    #: learner could recall or say. Authored grammar targets are phrases.
    concept_title: bool = False

    def as_public(self) -> dict[str, Any]:
        public = {
            "kind": str(self.kind),
            "id": self.id,
            "label_fr": self.label_fr,
            "label_native": self.label_native,
        }
        if self.concept_title:
            public["concept_title"] = True
        return public


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

    WP-78 added three more, again without a field: a ``match_pairs`` item's
    cards are its ``options`` (each with ``side`` ``"fr"`` or ``"native"``) and
    its answer is ``correct_tile_order`` read as consecutive ``(fr, native)``
    pairs, the day's target first; a ``listen_tap`` item's French phrase is
    ``prompt_fr``, its cards (``side="native"``) are ``options`` and its answer
    is ``correct_option_id``; an ``unscramble`` is tiles over a scene sentence.
    """

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
        "who_said",
        "dictation",
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
    #: WP-94: what a correct answer proves, when it is not what ``task_type``
    #: proves (``memory.FORMAT_BY_NAME``): the Rappel's coach mini-scene is a
    #: ``short_answer`` on the wire and a ``conversation`` (free use) in memory.
    evidence_format: str | None = None
    #: WP-103 T3: what to produce, in the learner's language — the meaning of the
    #: sentence to build («Build: "A small white table is in the kitchen."»), or
    #: which line of the scene to rebuild. Public (``RecallPrompt.goal_native``);
    #: required for :data:`GOAL_REQUIRED_RECALL_FORMATS`. Never the French answer.
    goal_native: str | None = None
    #: WP-103 T3: the French the item starts from, when it is shown — the sentence
    #: to correct, the learner's own wording to repair. Never the answer.
    source_fr: str | None = None


#: WP-103 T3 (the owner's test: «Build the sentence. Some chips are not needed.» —
#: which sentence?). A drill in these formats must say what to produce.
GOAL_REQUIRED_RECALL_FORMATS: frozenset[str] = frozenset(
    {"word_bank", "tiles", "unscramble", "transform"}
)

#: WP-103 T3: the goal lines of the journey's drills, in the three chrome languages.
RECALL_GOALS: dict[str, dict[str, str]] = {
    "build": {
        "en": 'Build: "{meaning}"',
        "de": "Bau den Satz: „{meaning}“",
        "fr": "Construisez : « {meaning} »",
    },
    "rebuild_line": {
        "en": 'Rebuild what {speaker} said: "{meaning}"',
        "de": "Bau nach, was {speaker} gesagt hat: „{meaning}“",
        "fr": "Reconstruisez ce qu'a dit {speaker} : « {meaning} »",
    },
    "rebuild_speaker": {
        "en": "Rebuild what {speaker} said in today's scene.",
        "de": "Bau nach, was {speaker} in der Szene von heute gesagt hat.",
        "fr": "Reconstruisez ce qu'a dit {speaker} dans la scène du jour.",
    },
    "rebuild_scene": {
        "en": 'Rebuild the sentence from the scene: "{meaning}"',
        "de": "Bau den Satz aus der Szene nach: „{meaning}“",
        "fr": "Reconstruisez la phrase de la scène : « {meaning} »",
    },
    "rebuild_word": {
        "en": 'Rebuild the sentence from today\'s scene that has «{word}» in it.',
        "de": "Bau den Satz aus der Szene von heute nach, in dem «{word}» vorkommt.",
        "fr": "Reconstruisez la phrase de la scène du jour où se trouve « {word} ».",
    },
    "complete_line": {
        "en": 'Complete what {speaker} said: "{meaning}"',
        "de": "Ergänze, was {speaker} gesagt hat: „{meaning}“",
        "fr": "Complétez ce qu'a dit {speaker} : « {meaning} »",
    },
    "fix_meaning": {
        "en": 'Correct it so that it says: "{meaning}"',
        "de": "Korrigiere den Satz, sodass er sagt: „{meaning}“",
        "fr": "Corrigez la phrase pour dire : « {meaning} »",
    },
    "fix_rule": {
        "en": "Correct the sentence: fix the part that breaks today's rule, keep the rest.",
        "de": "Korrigiere den Satz: Ändere den Teil, der gegen die Regel von heute verstößt.",
        "fr": "Corrigez la phrase : changez la partie qui enfreint la règle du jour.",
    },
    "repair_own": {
        "en": "Write what you said, correctly.",
        "de": "Schreib richtig, was du gesagt hast.",
        "fr": "Écrivez correctement ce que vous avez dit.",
    },
    "readdress": {
        "en": 'Say the same thing to someone you call "{pronoun}".',
        "de": "Sag dasselbe zu jemandem, den du mit „{pronoun}“ ansprichst.",
        "fr": "Dites la même chose à quelqu'un que vous appelez « {pronoun} ».",
    },
}


def recall_goal(kind: str, language: Any, **fields: Any) -> str:
    """One goal line (WP-103 T3) in the learner's chrome language."""

    table = RECALL_GOALS[kind]
    template = table.get(str(language or "en")[:2]) or table["en"]
    return template.format(**{key: str(value or "").strip() for key, value in fields.items()})


def recall_goal_gap(step: Any) -> str | None:
    """The contract check (WP-103 T3): a drill in a goal-required format with no
    goal, named, else ``None``."""

    task = getattr(step, "private_task", None)
    task_type = str(getattr(task, "task_type", "") or "")
    if task_type in GOAL_REQUIRED_RECALL_FORMATS and not str(getattr(task, "goal_native", "") or "").strip():
        return f"a {task_type} recall must say what to produce (goal_native)"
    return None


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
    #: WP-113: an authored season day's «Le choix» must be reached: the rhythm may
    #: shorten the conversation, never below this many exchanges.
    min_turns: int = 0
    #: WP-113: the opening question is «Le choix»: its cards ``[{id, label_fr, label_native}]``.
    opening_choices: list[dict[str, Any]] = field(default_factory=list)


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
    #: 2026-09-25. An authored scene's graphic-novel page, as the scene step shows
    #: it: ``[{index, narration_fr, dialogue: [{character_id, character_name,
    #: text_fr}], image_url}]``. Empty for a story-engine scene, whose panels are
    #: published as an episode (``/story-engine/episodes``), and for older content.
    panels: list[dict[str, Any]] = field(default_factory=list)

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
    # WP-119 phase 3: the Papier day. The story part is the classic day (never a
    # practice day: the Papier after the ending is the day's second half), at
    # most five steps, so the two together stay close to one day's budget.
    DayShape.REVUE: DayShapeRule(max_steps=MAX_PLANNED_STEPS),
}


def is_heard_step(step: Any) -> bool:
    """WP-93: a recall step the learner *hears* — a listen-and-tap or dictation
    that carries its clip (``public_prompt.audio_url``)."""

    prompt = getattr(step, "public_prompt", None) or {}
    return (
        getattr(step, "kind", None) is StepKind.RECALL
        and str(prompt.get("task_type") or "") in LISTENING_RECALL_FORMATS
        and bool(prompt.get("audio_url"))
    )


def practice_day_shape_rule(
    shape: DayShape | str | None, budget_seconds: int | None = None
) -> DayShapeRule:
    """WP-78 — a shape's rule on a practice day.

    The same shape, with room for the quick items: a «jour court» stays three
    steps (coming back after a missed day still costs a scene and a reply),
    and a «jour d'écoute» still poses only what can be taken down by ear.
    WP-L6: the room grows with the rhythm (:func:`rhythm_caps`); without a
    budget it is the five-minute room.
    """

    rule = day_shape_rule(shape)
    if rule.max_steps == MIN_PLANNED_STEPS and rule.max_recall == 0:
        return rule
    caps = rhythm_caps(budget_seconds)
    return DayShapeRule(
        min_steps=rule.min_steps,
        max_steps=caps.max_steps,
        min_recall=rule.min_recall,
        max_recall=caps.max_recall,
        allowed_formats=rule.allowed_formats,
    )


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
    #: WP-78. A practice day: quick recall items may come before the scene and
    #: after the reply. ``False`` for every plan written before plan contract
    #: version 3, which then validates exactly as it did.
    practice: bool = False

    def validate(self) -> None:
        """Guard the CONTRACTS §3/§9 envelope at the producer boundary.

        WP-66: the envelope is now validated *as a set of shapes* rather than
        against one template. The shared invariants are checked for every shape;
        the per-shape bounds come from :data:`DAY_SHAPE_RULES`.
        """

        if not self.steps:
            raise ValueError("a planned journey needs at least one step")
        if self.practice:
            self._validate_practice()
            return
        rule = day_shape_rule(self.day_shape)
        shape = str(self.day_shape)
        if len(self.steps) > MAX_PLANNED_STEPS:
            raise ValueError(f"plan has {len(self.steps)} steps, max {MAX_PLANNED_STEPS}")
        kinds = [step.kind for step in self.steps]
        first_day = self.shape_reason == "first_day"
        # WP-93 walk: the first day may open on its warm-ups (the words the
        # reply will ask for); every other classic day opens on the scene.
        lead = 0
        if first_day:
            while lead < len(kinds) and kinds[lead] is StepKind.RECALL:
                lead += 1
        if lead >= len(kinds) or kinds[lead] is not StepKind.SCENE:
            raise ValueError("a plan must open with the scene step")
        if kinds[-1] is not StepKind.RESOLUTION:
            raise ValueError("a plan must end with the resolution step")
        if kinds.count(StepKind.RESPOND) != 1:
            raise ValueError("a plan needs exactly one respond step")
        if StepKind.RULE in kinds:
            raise ValueError("only a practice day introduces a rule")
        if StepKind.FORGE in kinds:
            raise ValueError("only a practice day folds in the forge")
        if StepKind.READ in kinds:
            raise ValueError("only a practice day plans a «Lecture»")
        if (
            first_day
            and kinds.count(StepKind.RESPOND) == 1
            and kinds.index(StepKind.RESPOND) != lead + 1
        ):
            # WP-93 (W5): the first day's page ends on Margaux's question; the
            # reply answers it next, never after an exercise. (The classic
            # non-first day is the pre-WP-78 kill switch and keeps its shape.)
            raise ValueError("nothing may sit between the scene and the reply")
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
        for step in self.steps:
            gap = recall_goal_gap(step) if step.kind is StepKind.RECALL else None
            if gap:
                raise ValueError(gap)

        mandatory = sum(
            step.estimated_seconds for step in self.steps if not step.optional
        )
        if mandatory > self.budget_seconds:
            raise ValueError(
                f"mandatory estimate {mandatory}s exceeds budget {self.budget_seconds}s"
            )

    def _validate_practice(self) -> None:
        """WP-78 — the practice day's envelope.

        Still one scene, one reply, one ending. What changes: warm-up recall
        steps may come *before* the scene, recall steps may follow the reply,
        and the whole day — not only its mandatory part — has to fit the stated
        budget, because the learner is told the whole day's minutes.

        WP-93 (W5): the reply comes straight after the scene — its closing
        line is the question the reply answers. The rule card, its guided
        items and the forge come before the scene. WP-109: the ending comes
        straight after the reply; the day's other practice follows the ending,
        and one optional «Lecture» comes last.
        """

        rule = practice_day_shape_rule(self.day_shape, self.budget_seconds)
        caps = rhythm_caps(self.budget_seconds)
        shape = str(self.day_shape)
        kinds = [step.kind for step in self.steps]
        if len(self.steps) > caps.max_steps:
            raise ValueError(f"plan has {len(self.steps)} steps, max {caps.max_steps}")
        if kinds.count(StepKind.SCENE) != 1:
            raise ValueError("a plan needs exactly one scene step")
        if kinds.count(StepKind.RESPOND) != 1:
            raise ValueError("a plan needs exactly one respond step")
        reads = kinds.count(StepKind.READ)
        if reads > caps.max_reads:
            raise ValueError(f"a day at this rhythm plans at most {caps.max_reads} «Lecture» page(s)")
        body = kinds[: len(kinds) - reads] if reads else kinds
        if any(kind is not StepKind.READ for kind in kinds[len(body):]):
            raise ValueError("the «Lecture» comes last")
        if kinds.count(StepKind.RESOLUTION) != 1:
            raise ValueError("a plan needs exactly one resolution step")
        if StepKind.READ in body:
            raise ValueError("the «Lecture» comes last")
        # WP-109 «Une seule maison»: the episode is never interrupted — the ending
        # follows the reply, and the day's practice wraps before and after it.
        resolution_at = kinds.index(StepKind.RESOLUTION)
        if resolution_at != kinds.index(StepKind.RESPOND) + 1:
            raise ValueError("nothing may sit between the reply and the ending")
        if any(kind is not StepKind.RECALL for kind in body[resolution_at + 1 :]):
            raise ValueError("only practice may follow the ending")
        for step in self.steps:
            if step.kind is StepKind.READ and not step.optional:
                raise ValueError("the «Lecture» is optional")
        scene_at = kinds.index(StepKind.SCENE)
        respond_at = kinds.index(StepKind.RESPOND)
        allowed_before = (StepKind.RECALL, StepKind.RULE, StepKind.FORGE)
        if any(kind not in allowed_before for kind in kinds[:scene_at]):
            raise ValueError("only warm-ups, the rule and the forge may come before the scene")
        # Warm-ups are the recall steps before the rule; the rule's guided
        # items follow it.
        rule_at = kinds.index(StepKind.RULE) if StepKind.RULE in kinds else scene_at
        warmups = sum(1 for kind in kinds[: min(rule_at, scene_at)] if kind is StepKind.RECALL)
        if warmups > caps.max_warmups:
            raise ValueError(f"at most {caps.max_warmups} warm-ups before the scene")
        if respond_at != scene_at + 1:
            raise ValueError("nothing may sit between the scene and the reply")
        if kinds.count(StepKind.RULE) > 1:
            raise ValueError("a day introduces at most one rule")
        if StepKind.RULE in kinds and not rule_at < scene_at:
            raise ValueError("the rule card comes before the scene")
        if kinds.count(StepKind.FORGE) > 1:
            raise ValueError("a day folds in at most one forge block")
        if StepKind.FORGE in kinds and not kinds.index(StepKind.FORGE) < scene_at:
            raise ValueError("the forge block comes before the scene, with the rule")
        if [step.ordinal for step in self.steps] != list(range(len(self.steps))):
            raise ValueError("step ordinals must be a stable 0..n-1 sequence")
        recalls = kinds.count(StepKind.RECALL)
        if not rule.min_steps <= len(self.steps) <= rule.max_steps:
            raise ValueError(
                f"a {shape} day holds {rule.min_steps}..{rule.max_steps} steps, "
                f"not {len(self.steps)}"
            )
        # WP-93: heard items beyond the recall ceiling are input, allowed up to
        # the rhythm's ``max_heard``; every other item counts against the ceiling.
        heard = sum(1 for step in self.steps if is_heard_step(step))
        extra = min(heard, caps.max_heard)
        if not rule.min_recall <= recalls <= rule.max_recall + extra:
            raise ValueError(
                f"a {shape} day holds {rule.min_recall}..{rule.max_recall} recall "
                f"step(s) (+{caps.max_heard} heard), not {recalls}"
            )
        for index, step in enumerate(self.steps):
            if step.kind is not StepKind.RECALL:
                continue
            task_type = str(getattr(step.private_task, "task_type", "") or "")
            if rule.allowed_formats and task_type and task_type not in rule.allowed_formats:
                raise ValueError(f"a {shape} day cannot pose a {task_type} recall")
            if task_type in (
                str(RecallFormat.UNSCRAMBLE),
                str(RecallFormat.WHO_SAID),
                str(RecallFormat.DICTATION),
            ) and index < scene_at:
                # The sentence is the scene's: it cannot be rebuilt before it is read.
                raise ValueError("an unscramble cannot come before the scene")
            gap = recall_goal_gap(step)
            if gap:
                raise ValueError(gap)
        total = sum(step.estimated_seconds for step in self.steps)
        if total > self.budget_seconds:
            raise ValueError(f"estimate {total}s exceeds budget {self.budget_seconds}s")


@dataclass(frozen=True, slots=True)
class TargetObservation:
    """One observation about one target, ready for canonical credit."""

    target: TargetRef
    evidence_kind: EvidenceKind
    assistance: AssistanceLevel
    modality: InputMode
    learner_text: str | None = None
    corrected_text: str | None = None
    #: WP-L4: the recall format that produced the observation (``choice``,
    #: ``word_bank``, ``transform`` …), so a grammar unit is credited with the
    #: weight of what it proved (recognise < guided < transform < a reply).
    #: ``None``: a reply.
    task_format: str | None = None


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
    #: WP-L4: what the reply showed about each grammar unit it was asked to
    #: use — ``[{concept_id, outcome: correct | error | avoided, span}]``.
    #: «avoided» is neutral: no lapse, no credit.
    concept_evidence: list[dict[str, Any]] = field(default_factory=list)
    #: The reply as spoken lines, when more than one person answers (an authored
    #: season page): ``[{speaker_id, speaker_name, text_fr}]``. Each is drawn as its
    #: own bubble with its own face; ``character_reply_fr`` stays the joined text.
    reply_lines: list[dict[str, Any]] = field(default_factory=list)
    #: WP-113: the next question is «Le choix» — its cards ``[{id, label_fr,
    #: label_native}]``; the learner answers by tapping one. Empty otherwise.
    next_choices: list[dict[str, Any]] = field(default_factory=list)
    #: WP-113: what the learner is asked to do next, in their language, when the
    #: next question is a posed solve (it replaces the day's objective line).
    next_task_native: str | None = None


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
