"""WP-04 — the five-minute planner and integrated review selection.

One journey is a *plan*, not a drill quota. The legacy Atelier ladder in
:mod:`app.services.atelier` owes a learner three recognition modes of three
items, three transforms and three output rounds — fifteen obligations for every
selected concept. Nothing in this module reproduces that shape: a plan is three
to five explicit steps, and a hundred due words still produce at most two recall
opportunities.

The planner is deliberately narrow:

* It **selects** at most two relevant existing due/fragile targets plus at most
  one new anchor from the candidates WP-05 already ranked. It never calls a
  scheduler, never moves a due date, and never marks anything reviewed — an
  omitted candidate stays exactly as due as it was.
* It **shapes** one recall task per selected target from the scene's own
  authored affordances (:mod:`app.services.journey_content`). No second content
  source, no model call.
* It **estimates** every step from a bounded, documented cost model covering
  reading, answering, normal feedback, audio playback and one repair allowance,
  and it fits the mandatory plan inside the budget before returning.

``plan_journey`` is pure: it takes no ``Session``, performs no I/O beyond
reading WP-03's authored scenario data, and returns a byte-identical
:class:`~app.services.journey_contracts.PlannedJourney` for identical inputs.
Every identifier it mints is derived by hash from stable content, so a refresh
never re-randomises an option order or a tile layout.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

from app.services import grammar_items, pragmatics
from app.services.cast_voices import NARRATOR_ID, line_audio_url, voice_for_character
from app.services.journey_content import (
    SPOILER_SIMILARITY,
    line_spoils_reply,
    render_authored_text,
    scenario_target_affordances,
)
from app.services.journey_contracts import (
    CLASSIC_RECALL_FORMATS,
    DEFAULT_BUDGET_SECONDS,
    DEFAULT_DAY_SHAPE,
    DESK_KINDS,
    INPUT_FLOOR_SHARE,
    LISTENING_RECALL_FORMATS,
    MAX_PLANNED_STEPS,
    MAX_RECALL_STEPS,
    MAX_RESPOND_TURNS,
    READ_MIN_BUDGET_SECONDS,
    ControlLanguage,
    DayShape,
    HelpKind,
    InputMode,
    LearningCandidate,
    PlannedJourney,
    PlannedStep,
    RecallFormat,
    RecallTask,
    ResponseTask,
    RhythmCaps,
    ScenarioBrief,
    StepKind,
    StepStatus,
    TargetKind,
    TargetRef,
    article_optional,
    day_shape_rule,
    normalize_answer_text,
    practice_day_shape_rule,
    recall_goal,
    rhythm_caps,
    split_article,
)
from app.services.journey_day_shapes import (
    DESK_SHAPES,
    DayShapeInputs,
    LetterOffer,
    rotate_recall_formats,
    shape_allows_format,
)
from app.services.scene_items import draft_of, lexicon_of, line_meanings, meaning_of, scene_lines

if TYPE_CHECKING:  # pragma: no cover - typing only
    # WP-24. Imported for types alone: `journey_errata` reaches the ORM, and the
    # planner is contractually a pure function over its arguments (there is a
    # test that fails if it imports a scheduler). At runtime an errata target is
    # anything with `as_candidate()`, `as_because()` and `reason`.
    from app.services.journey_errata import ErrataTarget

PLANNER_VERSION = "journey-planner-v1"

# --------------------------------------------------------------------------
# Selection policy (CONTRACTS §9)
# --------------------------------------------------------------------------

#: At most two *existing* due/fragile targets may become today's obligation.
MAX_DUE_TARGETS = 2
#: Plus at most one brand-new anchor, which is an offer and never an obligation.
MAX_NEW_TARGETS = 1
MAX_SELECTED_TARGETS = MAX_DUE_TARGETS + MAX_NEW_TARGETS

#: Below this scene fit a target may still be *rehearsed* (it is genuinely due),
#: but it is never attached to the response step as an elicited target. Without
#: an explicit elicitation obligation an omitted word must not become a lapse
#: (CONTRACTS §7), so an unrelated urgent word never rides along on the reply.
ELICITATION_FIT_THRESHOLD = 0.5

#: ``LearningCandidate.metadata`` keys that mean "the learner already produced
#: this independently, a rehearsal would be redundant". Absent or falsy is the
#: honest default: nothing is skipped by accident.
DEMONSTRATED_FLAG_KEYS: tuple[str, ...] = (
    "demonstrated_independently",
    "already_demonstrated",
)
#: ``metadata["last_evidence_kind"]`` values that count as already demonstrated.
DEMONSTRATED_EVIDENCE_KINDS = frozenset({"produced_independent", "used_again_later"})

# --------------------------------------------------------------------------
# Estimate model (CONTRACTS §9)
# --------------------------------------------------------------------------

#: Reading pace for a mixed French/native prompt, in seconds per whitespace
#: token. 0.45 s/token ≈ 133 words per minute — a beginner reading French with a
#: native gloss, not a native skimming their own language.
DEFAULT_SECONDS_PER_TOKEN = 0.45
#: WP-128. The prior is level-aware: what a *mixed* prompt (a native
#: instruction around a French line) costs a reader of this band. Each value is
#: the mean of the band's French reading pace and a native reader's
#: (``tests/experience_walk.Timer``: French 45 / 70 / 100 / 140 / 180 wpm at
#: A1…C1, native 220 wpm → (1.33 + 0.27) / 2 = 0.80 at A1, 0.56 at A2, 0.44 at
#: B1, 0.35 at B2, 0.30 at C1), rounded to the review's proposal. B1 keeps the
#: old 0.45, which was a B1 reader's pace all along. Unknown bands read B1.
READING_PRIOR_SECONDS_PER_TOKEN: dict[str, float] = {
    "A1": 0.75,
    "A2": 0.60,
    "B1": 0.45,
    "B2": 0.38,
    "C1": 0.32,
    "C2": 0.32,
}
#: A measured pace outside this band is a measurement artefact, not a learner.
#: WP-128: widened with the level-aware prior and calibrated *with* the page
#: factor below — 1.0 s a token on a prompt is a page read at 2.0 s a token by
#: an A1 reader (30 wpm, the slowest real reader the walk's Timer models after
#: its ×1.4 «struggling» factor), 0.25 is a native skim (240 wpm).
SECONDS_PER_TOKEN_BOUNDS = (0.25, 1.00)
#: A measured per-step multiplier is clamped here too. Beyond 1.35 the honest
#: answer is a shorter plan, not a longer estimate.
STEP_MULTIPLIER_BOUNDS = (0.80, 1.35)
#: How many measured days a pace profile needs before it is trusted at all.
#: Under this threshold the bounded defaults are used verbatim. WP-L6: three
#: measured days (was five journeys), the point at which the planner is fed
#: the learner's own pace instead of the priors.
MIN_PACE_OBSERVATIONS = 3

#: Orientation, looking at the art, deciding to begin. WP-128: 12 → 6.
SCENE_BASE_SECONDS = 6
#: WP-93 «Price the input». A page is priced by what is on it: each panel is
#: looked at (its art, then «Suivant»), each line of narration or dialogue may
#: send the learner to a word's help, and the French itself is read at a
#: learner's pace — story text in the target language, not a mixed prompt, so
#: the reading pace is scaled by :data:`PAGE_READING_FACTOR` (0.45 × 2 = 0.9 s
#: a word ≈ 67 words a minute, an A1–A2 reader of L2 prose). A painted panel
#: is looked at before it is read: eight seconds.
#: WP-128: three seconds a panel and one a line. The words are priced by the
#: band's prose pace now, so the orientation is only the glance and the tap:
#: the walk's Timer gives a panel 2 s and a «Suivant» 1.5 s, and the old 8 + 2
#: made the scene the one step priced at twice its time at every level.
SCENE_PANEL_SECONDS = 3
SCENE_LINE_HELP_SECONDS = 1
PAGE_READING_FACTOR = 2.0
#: WP-128. The factor shrinks with the band: a page is pure French prose, a
#: prompt is half native, and the gap between the two closes as French reading
#: approaches native speed. Calibrated *with* the prior, so a page is never
#: priced twice for being French: prior × factor is the band's prose pace in
#: the walk's Timer — French at 45 / 70 / 100 / 140 / 180 wpm plus, at A1–A2,
#: half a glance at each line's gloss (1.47 / 0.99 / 0.60 / 0.43 / 0.33 s a
#: word). A1 keeps the old 2.0 (0.75 × 2.0 = 1.5); C1 reads a page almost as
#: it reads a prompt (0.32 × 1.05 = 0.34). The review's priors × the old 2.0
#: would have charged B2 0.76 s a word, nearly twice the Timer's.
PAGE_READING_FACTOR_BY_BAND: dict[str, float] = {
    "A1": 2.0,
    "A2": 1.65,
    "B1": 1.35,
    "B2": 1.15,
    "C1": 1.05,
    "C2": 1.05,
}
#: WP-128. Composing a reply in French, seconds per word, thinking included —
#: 60 / the Timer's 5 / 8 / 11 / 15 / 19 words a minute on a phone. The reply
#: is the largest part of a beginner's day (the walk's A1 day spent 60 % of its
#: minutes there, against a flat 38 s a turn), so it is priced by band.
COMPOSE_SECONDS_PER_WORD: dict[str, float] = {
    "A1": 12.0,
    "A2": 7.5,
    "B1": 5.5,
    "B2": 4.0,
    "C1": 3.2,
    "C2": 3.2,
}
#: WP-128. How long a reply is expected to be: the scene's own suggested reply
#: (the size of answer the objective asks for), never shorter than one
#: sentence at the band, and at most two sentences. The floor sits between the
#: season's authored A1 example answers (4–6 words, a later exchange often a
#: card) and the free replies the walk's learners write on generated days
#: (9–13 words): 7 at A1, one more word a band up to 10.
REPLY_WORDS_FLOOR: dict[str, int] = {"A1": 7, "A2": 8, "B1": 9, "B2": 10, "C1": 10, "C2": 10}
REPLY_WORDS_CEILING = 16
#: WP-128. The single repair slot is a whole extra exchange when it is used —
#: the story keeps talking through it — which the walk saw on a fifth to two
#: fifths of days; priced as this share of one exchange, never under
#: :data:`REPAIR_ALLOWANCE_SECONDS`.
REPAIR_TURN_SHARE = 0.35
#: WP-128. Per exchange, besides composing: reading the character's answer
#: (about this many words of French prose) and sending.
RESPOND_REPLY_TOKENS = 12
RESPOND_TURN_FIXED_SECONDS = 4
#: WP-128: «Le choix» — deciding between the cards and tapping one.
CHOICE_TAP_SECONDS = 4
#: WP-128. A native-language explanation (a rule card's rule) — 220 wpm.
NATIVE_SECONDS_PER_TOKEN = 0.27
#: WP-128. Typing a short answer on a phone, seconds per character (the
#: Timer's 0.35 s), after a fixed start.
TYPING_SECONDS_PER_CHAR = 0.35
TYPED_START_SECONDS = 3
TYPED_FORMATS = frozenset({"short_answer", "transform"})
#: WP-93 (W5/W11). What the landing page's taste («Romy», then «Commandez un
#: café.») already taught, as in ``web-frontend/lib/onboarding-taste.ts``: the
#: learner answered «Bonjour !» / «Merci !» to Romy and built «Un café, s'il vous
#: plaît» for Margaux. Day 1 never drills them again. Kept in sync by hand: the
#: taste is authored client-side and has no server copy.
TASTE_WORDS_FR: tuple[str, ...] = ("un café", "s'il vous plaît", "bonjour", "merci")
#: Reading the ending, the summary, and closing the day. WP-128: 45 → 12. The
#: ending's own lines are priced by their words on top; the walk's Timer spends
#: 6–15 s on the whole ending, so 45 s of base made every day look 30 s longer.
RESOLUTION_BASE_SECONDS = 12
#: Answering cost per recall renderer. WP-66's three additions are priced from
#: the renderer they reuse: a classify is a two-option pick (cheaper than a
#: four-option choice), a word bank is tiles plus the chips that have to be
#: rejected, and a transform is a short answer the learner has to think about
#: twice — read the source, then rewrite it.
RECALL_ANSWER_SECONDS: dict[str, int] = {
    "choice": 18,
    "tiles": 26,
    "short_answer": 30,
    "classify": 14,
    "word_bank": 32,
    "transform": 38,
}
#: Reading the normal (non-repair) feedback on a recall step.
RECALL_FEEDBACK_SECONDS = 10
#: Composing one learner turn in the response step.
RESPOND_TURN_SECONDS = 38
#: Reading the character's reply and the normal feedback.
RESPOND_FEEDBACK_SECONDS = 10
#: The single allowed repair (CONTRACTS §9: "repair at most once").
REPAIR_ALLOWANCE_SECONDS = 20
#: Listening to a character line when audio actually exists.
AUDIO_PLAYBACK_SECONDS_PER_TOKEN = 0.55

#: WP-78 — what one *quick* item costs on a practice day, before reading.
#: Priors, not measurements: WP-11 records step boundaries but no per-format
#: medians exist yet, so these are the owner's «≤ 10 s per item» written down
#: per renderer, and a trusted :class:`PacingProfile` multiplier scales them
#: exactly as it scales everything else. With WP-76's answer key the verdict
#: lands on the device in milliseconds, so a quick item is priced without the
#: ten seconds of server-graded feedback the classic recall step carries.
QUICK_ANSWER_SECONDS: dict[str, int] = {
    "classify": 3,
    "listen_tap": 4,
    "choice": 5,
    "tiles": 6,
    "word_bank": 7,
    "unscramble": 7,
    "short_answer": 8,
    "match_pairs": 9,
    "transform": 12,
    # WP-86: «Qui a dit ça ?» — read one line, tap a face.
    "who_said": 4,
    # WP-91: «Dictée» — the fixed part; hearing the line twice and typing it
    # are priced per word (`DICTATION_SECONDS_PER_WORD`).
    "dictation": 8,
}
#: WP-91. What each word of a dictated line costs: heard twice at
#: :data:`AUDIO_PLAYBACK_SECONDS_PER_TOKEN`, then typed.
DICTATION_TYPING_SECONDS_PER_WORD = 1.5
#: WP-91. The longest line a dictation may ask for, by band: a short line from
#: today's scene, never a paragraph. Bands above A2 share the last cap.
DICTATION_MAX_WORDS: dict[str, int] = {"A1": 8, "A2": 12}
DICTATION_MAX_WORDS_DEFAULT = 16
DICTATION_MIN_WORDS = 2
#: WP-91. With audio on the deployment, how many listen-and-tap items a day
#: carries at least, by rhythm (budget seconds) — plus one dictation. Régulier
#: therefore holds three real listening items a day.
LISTEN_TAP_ITEMS_BY_BUDGET: dict[int, int] = {300: 1, 600: 2, 1200: 3, 1800: 4}
DICTATION_ITEMS_PER_DAY = 1
#: WP-129: a thin A1/A2 day (fewer of today's words than the day has room for)
#: dictates up to this many more lines of the story.
THIN_DAY_EXTRA_DICTATIONS = 2
#: Seeing the colour and tapping «Continuer».
QUICK_FEEDBACK_SECONDS = 2
#: A practice day aims for this many quick items: with the reply that is six
#: graded interactions (WORK-PACKAGES-2026-09-22 WP-78).
PRACTICE_TARGET_ITEMS = 5
#: How often one target may come back in one day, always in a different format.
PRACTICE_MAX_USES_PER_TARGET = 2
#: The five-minute rhythm, whose practice day is exactly WP-78's.
RHYTHM_FIVE_MINUTES = 300
#: The cards a matching item shows per side.
MATCH_PAIR_COUNT = 4
#: WP-L4 «Règle»: the rule card is a thirty-second read (§2.1).
RULE_CARD_SECONDS = 30
#: WP-128: looking at the card before its words are read (its words are priced).
RULE_CARD_LOOK_SECONDS = 15
#: WP-L4 «Réemploi»: at most this many grammar units are asked for in the
#: reply, the day's new unit included (§2.4: ≤ 2 per day).
MAX_REPLY_GRAMMAR_TARGETS = 2
#: WP-129 (owner decision 2026-10-04, «fewer replies, more items»). At A1 and
#: A2 a composed word costs 12 and 7.5 seconds (WP-128), so three exchanges
#: filled a ten-minute day and left about four items. On Léger and Régulier
#: the core reply asks for this many exchanges — or the authored page's minimum (a «Le choix», a gate,
#: a turn that routes or sets a flag), whichever is more; the rest are optional
#: and not counted in the core estimate. The story is still played in full:
#: an authored page's unreached turns settle as written (``season.runtime``).
LOW_BAND_CORE_REPLY_TURNS = 2
LOW_BANDS = frozenset({"A1", "A2"})

RecallTaskType = Literal["choice", "tiles", "short_answer"]

# --------------------------------------------------------------------------
# Control-language templates. Every learner-facing string is resolved into the
# brief's control language; French content keeps its own ``_fr`` fields.
# --------------------------------------------------------------------------

_CHOICE_INSTRUCTION: dict[str, str] = {
    "en": 'Which French phrase means "{native}"?',
    "de": 'Welcher französische Ausdruck bedeutet „{native}“?',
    "fr": "Quelle expression française veut dire « {native} » ?",
}
_TILES_INSTRUCTION_WITH_GLOSS: dict[str, str] = {
    "en": 'Put the words in order to say "{native}".',
    "de": 'Bring die Wörter in die richtige Reihenfolge für „{native}“.',
    "fr": "Remets les mots dans l'ordre pour dire « {native} ».",
}
_TILES_INSTRUCTION: dict[str, str] = {
    "en": "Put the words in the right order.",
    "de": "Bring die Wörter in die richtige Reihenfolge.",
    "fr": "Remets les mots dans le bon ordre.",
}
_SHORT_ANSWER_INSTRUCTION: dict[str, str] = {
    "en": 'How do you say "{native}" in French?',
    "de": 'Wie sagt man „{native}“ auf Französisch?',
    "fr": "Comment dit-on « {native} » en français ?",
}
#: An erratum is not a translation: the learner wrote something, and the task
#: is to write it correctly. Its stored explanation is never the "translation"
#: (it usually contains the answer), so the learner's own words are the prompt.
_ERROR_INSTRUCTION: dict[str, str] = {
    "en": "Write this correctly in French.",
    "de": "Schreib das richtig auf Französisch.",
    "fr": "Écrivez ceci correctement en français.",
}
_HINT_TEMPLATE: dict[str, str] = {
    "en": 'It is {words} long and starts with "{initial}".',
    "de": 'Es ist {words} lang und beginnt mit „{initial}“.',
    "fr": "C'est {words} et ça commence par « {initial} ».",
}
#: QA-PRACTICE (owner, 2026-10-03): «Wie sagt man „Wohnung“?» hinted «2 Wort/Wörter,
#: beginnt mit „u“» — the article, which a gloss without one never asked for. A noun
#: asked from such a gloss is hinted by the noun, and the article is said optional.
_NOUN_HINT_TEMPLATE: dict[str, str] = {
    "en": 'A noun starting with "{initial}" (the article is optional).',
    "de": 'Ein Nomen, das mit „{initial}“ beginnt (der Artikel ist freiwillig).',
    "fr": "Un nom qui commence par « {initial} » (l'article est facultatif).",
}
#: One word / several words, in each chrome language (never «Wort/Wörter»).
_WORD_COUNT: dict[str, tuple[str, str]] = {
    "en": ("{count} word", "{count} words"),
    "de": ("{count} Wort", "{count} Wörter"),
    "fr": ("{count} mot", "{count} mots"),
}


def word_count_phrase(count: int, control_language: Any) -> str:
    """«1 Wort» / «3 Wörter», «1 word» / «3 words», «1 mot» / «3 mots»."""

    one, many = _WORD_COUNT.get(str(control_language or "en")[:2], _WORD_COUNT["en"])
    return (one if int(count) == 1 else many).format(count=int(count))

# -- WP-66: the three Séance formats, posed in the journey -------------------
#: A word bank is tiles with chips that are *not* in the answer, so the chip row
#: stops being the answer written down in the wrong order.
_WORD_BANK_INSTRUCTION_WITH_GLOSS: dict[str, str] = {
    "en": 'Build "{native}". Some chips are not needed.',
    "de": 'Bau „{native}“. Nicht jeder Baustein wird gebraucht.',
    "fr": "Construisez « {native} ». Certains mots sont en trop.",
}
_WORD_BANK_INSTRUCTION: dict[str, str] = {
    "en": "Build the phrase. Some chips are not needed.",
    "de": "Bau den Ausdruck. Nicht jeder Baustein wird gebraucht.",
    "fr": "Construisez l'expression. Certains mots sont en trop.",
}
#: Gender is asked about the bare noun: the article is what answers it, so the
#: article is exactly what the prompt may not show.
_CLASSIFY_GENDER_INSTRUCTION: dict[str, str] = {
    "en": "Masculine or feminine?",
    "de": "Maskulin oder feminin?",
    "fr": "Masculin ou féminin ?",
}
#: QA-CLOSE (owner decision e): the labels are chrome, in the learner's language.
_CLASSIFY_GENDER_LABELS: dict[str, tuple[str, str]] = {
    "en": ("masculine", "feminine"),
    "de": ("männlich", "weiblich"),
    "fr": ("masculin", "féminin"),
}
_CLASSIFY_ADDRESS_INSTRUCTION: dict[str, str] = {
    "en": "Who is this said to?",
    "de": "Zu wem wird das gesagt?",
    "fr": "On s'adresse à qui ?",
}
#: The two labels are French forms of address, so they stay French in every
#: control language: they are the thing being classified, not chrome.
_CLASSIFY_ADDRESS_LABELS: tuple[str, str] = ("tu", "vous")
#: A directed rewrite names the form to use and never writes the answer word.
_TRANSFORM_INSTRUCTION: dict[str, str] = {
    "en": 'Say the same thing with "{pronoun}": change "{span}".',
    "de": "Sag dasselbe mit „{pronoun}“: ändere „{span}“.",
    "fr": "Dites la même chose avec « {pronoun} » : changez « {span} ».",
}
_TRANSFORM_HINT: dict[str, str] = {
    "en": 'Only the part with "{span}" changes.',
    "de": "Nur der Teil mit „{span}“ ändert sich.",
    "fr": "Seule la partie avec « {span} » change.",
}
# -- WP-78: the quick formats --------------------------------------------------
_MATCH_INSTRUCTION: dict[str, str] = {
    "en": "Tap the pairs that mean the same.",
    "de": "Tippe die Paare an, die dasselbe bedeuten.",
    "fr": "Touchez les paires qui veulent dire la même chose.",
}
_LISTEN_TAP_INSTRUCTION: dict[str, str] = {
    "en": "What does it mean?",
    "de": "Was bedeutet das?",
    "fr": "Qu'est-ce que ça veut dire ?",
}
_UNSCRAMBLE_INSTRUCTION: dict[str, str] = {
    "en": "Put the sentence from the scene back in order.",
    "de": "Bring den Satz aus der Szene wieder in die richtige Reihenfolge.",
    "fr": "Remettez dans l'ordre la phrase de la scène.",
}
#: WP-91. The dictation's only public text: the line itself is heard, never shown.
_DICTATION_INSTRUCTION: dict[str, str] = {
    "en": "Listen and write what you hear.",
    "de": "Hör zu und schreib, was du hörst.",
    "fr": "Écoutez et écrivez ce que vous entendez.",
}
_DICTATION_HINT: dict[str, str] = {
    "en": "The line has {words}.",
    "de": "Der Satz hat {words}.",
    "fr": "La phrase a {words}.",
}
#: A scene sentence is rebuilt only when it is short enough to be a quick item
#: and long enough to be a puzzle.
UNSCRAMBLE_WORDS = (3, 9)

#: French articles that settle a noun's gender. ``l'`` settles nothing and is
#: deliberately absent: a classify whose answer is a guess is not a question.
_GENDER_ARTICLES: dict[str, str] = {
    "un": "m", "le": "m", "du": "m",
    "une": "f", "la": "f",
}


def _localized(table: dict[str, str], control_language: ControlLanguage) -> str:
    return table.get(str(control_language), table["en"])


# --------------------------------------------------------------------------
# Public value objects
# --------------------------------------------------------------------------


class PlanUnavailable(RuntimeError):
    """The brief cannot support a real five-minute ending.

    Raised instead of emitting a placeholder plan. WP-02 maps this onto the
    frozen ``generation_unavailable`` error code and offers an honest retry; it
    must never be turned into a scene with no objective or no ending.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _band_key(band: str | None) -> str | None:
    coarse = str(band or "").strip().upper()[:2]
    return coarse if coarse in READING_PRIOR_SECONDS_PER_TOKEN else None


def reading_prior(band: str | None) -> float:
    """WP-128: the band's prior reading pace for a mixed prompt (B1 when unknown)."""

    key = _band_key(band)
    return READING_PRIOR_SECONDS_PER_TOKEN[key] if key else DEFAULT_SECONDS_PER_TOKEN


def page_reading_factor(band: str | None) -> float:
    """WP-128: how much slower than a prompt a page of French prose reads.

    ``None`` (a caller that names no band) keeps the WP-93 factor.
    """

    key = _band_key(band)
    return PAGE_READING_FACTOR_BY_BAND[key] if key else PAGE_READING_FACTOR


def compose_seconds_per_word(band: str | None) -> float:
    key = _band_key(band) or "B1"
    return COMPOSE_SECONDS_PER_WORD[key]


@dataclass(frozen=True, slots=True)
class PacingProfile:
    """Measured active pace, or nothing yet.

    ``observations`` is the number of *completed, measured* journeys behind the
    numbers. Below :data:`MIN_PACE_OBSERVATIONS` the profile is ignored
    entirely and the bounded defaults are used: two noisy samples must not be
    allowed to shrink a plan into a false promise or inflate it into a
    ten-minute day. Above the threshold both values are clamped, so provider
    waiting or a backgrounded app cannot leak into the learning estimate.
    """

    #: WP-128: ``None`` — nothing measured per token (the WP-L6 profile
    #: measures a step multiplier only), so reading keeps the band's prior.
    seconds_per_token: float | None = None
    step_multiplier: float = 1.0
    observations: int = 0

    @property
    def is_trusted(self) -> bool:
        return self.observations >= MIN_PACE_OBSERVATIONS

    def effective_seconds_per_token(self, band: str | None = None) -> float:
        """The measured pace once trusted and measured, else the band's prior."""

        if not self.is_trusted or self.seconds_per_token is None:
            return reading_prior(band)
        low, high = SECONDS_PER_TOKEN_BOUNDS
        return min(max(float(self.seconds_per_token), low), high)

    def effective_step_multiplier(self) -> float:
        if not self.is_trusted:
            return 1.0
        low, high = STEP_MULTIPLIER_BOUNDS
        return min(max(float(self.step_multiplier), low), high)


@dataclass(frozen=True, slots=True)
class SelectedTarget:
    """One candidate the planner kept, with the scene fit it was kept for."""

    candidate: LearningCandidate
    fit: float
    demonstrated: bool
    #: How well the target fits the reply itself, when that differs from ``fit``
    #: (which also ranks the day). ``None`` reads ``fit``.
    reply_fit: float | None = None

    @property
    def target(self) -> TargetRef:
        return self.candidate.target

    @property
    def is_elicitable(self) -> bool:
        """May this target be *required* in the spoken/written reply?"""

        fit = self.fit if self.reply_fit is None else self.reply_fit
        return fit >= ELICITATION_FIT_THRESHOLD


@dataclass(frozen=True, slots=True)
class TargetSelection:
    """The outcome of selection, before any step is shaped."""

    selected: list[SelectedTarget]
    omitted: list[LearningCandidate]
    omission_reasons: dict[str, str]


# --------------------------------------------------------------------------
# Small deterministic helpers
# --------------------------------------------------------------------------


#: Unit separator; keeps hashed identifiers injection-proof across parts.
_SEPARATOR = chr(31)


def _digest(*parts: str) -> str:
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def target_identity(target: TargetRef) -> str:
    """The planner's candidate/target identifier: ``"{kind}:{id}"``.

    A vocabulary row and a grammar concept can share a primary key, so the bare
    record id is not unique across kinds. ``selected_target_ids`` and
    ``omitted_candidate_ids`` both use this composite form.
    """

    return f"{target.kind}:{target.id}"


def _tokens(*texts: str | None) -> int:
    return sum(len((text or "").split()) for text in texts)


def _fold(value: str | None) -> str:
    return normalize_answer_text(value).casefold()


#: Leading articles of the three languages a card may be in.
_ANY_ARTICLE = re.compile(
    r"^(?:le|la|les|un|une|des|du|l'|ein|eine|einen|der|die|das|a|an|the)(?:\s+|(?<=')\s*)(?=\S)",
    re.IGNORECASE,
)


def _bare(value: str | None) -> str:
    """A card's text without its leading article (French, German or English), folded:
    «un appartement» and «appartement», «eine Wohnung» and «Wohnung» are one card."""

    return _ANY_ARTICLE.sub("", _fold(value).strip(), count=1).strip()


def candidate_is_demonstrated(candidate: LearningCandidate) -> bool:
    """Has the learner already produced this target independently?

    Read from ``LearningCandidate.metadata`` so the planner stays pure. The
    honest default is ``False``: a target is only treated as demonstrated when
    the evidence layer explicitly says so, never inferred from a due date.
    """

    metadata = candidate.metadata or {}
    if isinstance(metadata.get("grammar_brief"), dict):
        # WP-L4: a grammar unit's own memory says when it is due again; one
        # past production does not retire it («Tenue» needs more than that).
        return False
    for key in DEMONSTRATED_FLAG_KEYS:
        if bool(metadata.get(key)):
            return True
    return str(metadata.get("last_evidence_kind") or "") in DEMONSTRATED_EVIDENCE_KINDS


def reemploi_order(entries: list[SelectedTarget]) -> list[SelectedTarget]:
    """WP-130 B: the reply's «Réemploi» goes first to a unit owed a free use.

    A unit whose second free use is owed (``held_opportunity == "free_use"``
    on its brief, set by the learning adapter) leads; the other strong units
    keep their order behind it. Stable, so nothing else moves.
    """

    def owed(entry: SelectedTarget) -> int:
        brief = (entry.candidate.metadata or {}).get("grammar_brief")
        return 0 if isinstance(brief, dict) and brief.get("held_opportunity") == "free_use" else 1

    return sorted(entries, key=owed)


def scenario_fit(target: TargetRef, affordances: list[str], scenario: ScenarioBrief) -> float:
    """How well this target suits the scene, in ``[0, 1]``.

    An exact match against what the scene affords is 1.0, a containment match
    0.75, and a partial token overlap proportional. A target the response task
    already declares is 1.0 by definition, so a thin authored affordance list
    cannot demote something the scene demonstrably needs.
    """

    for declared in scenario.response_task.targets:
        if declared.kind == target.kind and declared.id == target.id:
            return 1.0
    label = _fold(target.label_fr)
    if not label:
        return 0.0
    folded = [_fold(item) for item in affordances if item]
    best = 0.0
    label_tokens = set(label.split())
    for phrase in folded:
        if not phrase:
            continue
        if phrase == label:
            return 1.0
        if label in phrase or phrase in label:
            best = max(best, 0.75)
            continue
        if label_tokens:
            overlap = len(label_tokens & set(phrase.split())) / len(label_tokens)
            best = max(best, round(overlap * 0.8, 4))
    return best


def supported_input_modes(
    scenario: ScenarioBrief, *, input_mode: InputMode = InputMode.TEXT
) -> list[str]:
    """The modes the response step offers.

    Text is always available (CONTRACTS §10): a denied microphone, a failed
    transcription or a text-only device must never block the day's objective.
    Voice is added only when the journey was actually created for voice.
    """

    if input_mode is InputMode.VOICE:
        return [str(InputMode.TEXT), str(InputMode.VOICE)]
    return [str(InputMode.TEXT)]


def default_outcome_key(scenario: ScenarioBrief) -> str | None:
    """The ending the plan shows before the learner has spoken.

    The first *authored* allowed outcome that actually has a resolution line.
    WP-06 replaces it with the outcome the learner earned; until then the plan
    shows a real, authored ending rather than an invented one.
    """

    if scenario.story_context:
        return "pending"
    for key in scenario.response_task.allowed_outcomes:
        if scenario.resolution_lines.get(key):
            return key
    for key, line in scenario.resolution_lines.items():
        if line:
            return key
    return None


# --------------------------------------------------------------------------
# 1. Selection
# --------------------------------------------------------------------------


def select_plan_targets(
    scenario: ScenarioBrief,
    candidates: list[LearningCandidate],
    *,
    max_new: int = MAX_NEW_TARGETS,
) -> TargetSelection:
    """At most two existing due/fragile targets plus at most one new anchor.

    Ranking is scene fit first, then the urgency WP-05 already computed, then
    how long the item has been due, then a stable identity tiebreak. A hundred
    due words therefore yield two obligations, not a hundred — and the other
    ninety-eight are reported in ``omitted``, still due, untouched.
    """

    affordances = _affordances_for(scenario)
    ranked: list[tuple[tuple[float, float, float, str], SelectedTarget]] = []
    seen: set[str] = set()
    duplicates: list[LearningCandidate] = []
    for candidate in candidates:
        identity = target_identity(candidate.target)
        if identity in seen:
            duplicates.append(candidate)
            continue
        seen.add(identity)
        on_scene = scenario_fit(candidate.target, affordances, scenario)
        fit = max(on_scene, round(min(max(float(candidate.relevance or 0.0), 0.0), 1.0), 4))
        entry = SelectedTarget(
            candidate=candidate,
            fit=fit,
            demonstrated=candidate_is_demonstrated(candidate),
            reply_fit=_erratum_reply_fit(candidate, scenario, on_scene),
        )
        ranked.append(
            (
                (
                    -entry.fit,
                    -float(candidate.priority_score or 0.0),
                    -float(candidate.due_since_days or 0),
                    identity,
                ),
                entry,
            )
        )
    ranked.sort(key=lambda row: row[0])

    selected: list[SelectedTarget] = []
    omitted: list[LearningCandidate] = []
    reasons: dict[str, str] = {}
    due_used = 0
    new_used = 0
    for _key, entry in ranked:
        identity = target_identity(entry.target)
        if entry.candidate.is_new:
            if new_used >= max_new:
                omitted.append(entry.candidate)
                reasons[identity] = "new_anchor_cap_reached"
                continue
            new_used += 1
        else:
            if due_used >= MAX_DUE_TARGETS:
                omitted.append(entry.candidate)
                reasons[identity] = "due_target_cap_reached"
                continue
            due_used += 1
        selected.append(entry)
    for candidate in duplicates:
        omitted.append(candidate)
        reasons.setdefault(target_identity(candidate.target), "duplicate_candidate")
    return TargetSelection(selected=selected, omitted=omitted, omission_reasons=reasons)


def _erratum_reply_fit(
    candidate: LearningCandidate, scenario: ScenarioBrief, on_scene: float
) -> float | None:
    """An erratum's importance ranks the day, but only a story-engine scene was
    written with the learner's errata in hand (WP-24): in an authored scene a
    mistake is asked for in the reply only when the scene's own words afford it.
    Otherwise the learner was handed "Elle attendait quand j'ai répondu." as a
    word to use while ordering a coffee (owner screenshot, 2026-09-25). The
    erratum is still practised in the day's recall steps."""

    if candidate.target.kind is not TargetKind.ERROR or scenario.story_context:
        return None
    return on_scene


#: WP-93: a story-engine scene whose lexicon names at least this many phrases
#: poses its choices and word banks from them alone (closes WP-68 L-1).
STORY_AFFORDANCES_MIN = 3


def _story_words(scenario: ScenarioBrief, kind: str) -> list[str]:
    """The engine's «mots à placer» (``placed``) or recycled words (``recycled``).

    Read from the story context's ``words`` outcome (what the engine measured
    on the accepted draft), the draft's own ``<kind>_lemmas`` or the stored
    ``script_payload`` copy — whichever the scene carries.
    """

    story = scenario.story_context if isinstance(scenario.story_context, dict) else {}
    sources = [
        (story.get("words") or {}).get(kind) if isinstance(story.get("words"), dict) else None,
        draft_of(scenario).get(f"{kind}_lemmas"),
        (story.get("script_payload") or {}).get(f"{kind}_lemmas")
        if isinstance(story.get("script_payload"), dict)
        else None,
    ]
    for values in sources:
        if isinstance(values, list) and values:
            return [" ".join(str(value or "").split()) for value in values if str(value or "").strip()]
    return []


def story_affordances(scenario: ScenarioBrief) -> list[str]:
    """WP-93 — what a story-engine scene affords: the words it teaches.

    ``SceneDraft.lexicon`` (validated against the page, WP-86) first, then the
    «mots à placer» and recycled words the director was handed, when the draft
    records them. Empty for an authored scene.
    """

    phrases: list[str] = [str(entry.get("surface_fr") or "") for entry in lexicon_of(scenario)]
    for values in (*_story_words(scenario, "placed"), *_story_words(scenario, "recycled")):
        phrases.append(str(values or ""))
    unique: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        text = " ".join(phrase.split())
        if text and _fold(text) not in seen:
            seen.add(_fold(text))
            unique.append(text)
    return unique


def _affordances_for(scenario: ScenarioBrief) -> list[str]:
    """The phrases a recall item may lean on (distractors, extra chips, fit).

    WP-93 (WP-68 L-1): on a story-engine day these are the scene's own words —
    a choice whose wrong options come from another scene is not a question
    about this story. The authored family's phrases fill in only when the
    scene's lexicon is too thin to pose from.
    """

    story = story_affordances(scenario)
    if len(story) >= STORY_AFFORDANCES_MIN:
        return story
    try:
        authored = scenario_target_affordances(
            scenario.scenario_key,
            level_band=scenario.level_band,
            content_version=scenario.content_version,
        )
    except (OSError, ValueError, KeyError, TypeError):
        # A scenario family with no authored data simply affords nothing; that
        # is a thinner recall task, not a planner failure.
        authored = []
    seen = {_fold(phrase) for phrase in story}
    return [*story, *(phrase for phrase in authored if _fold(phrase) not in seen)]


# --------------------------------------------------------------------------
# 2. Recall task shaping
# --------------------------------------------------------------------------


_FR_ARTICLE = re.compile(r"^(?:(le|la|les|un|une|des|du)\s+|(l')\s*)(?=\S)", re.IGNORECASE)
_ELIDES = re.compile(r"^[aeiouyhàâéèêëîïôûù]", re.IGNORECASE)


def _shaped_like(label: str, phrase: str, genders: dict[str, str] | None) -> str | None:
    """``phrase`` in the same shape as ``label``: with an article of the same kind
    when the label has one, bare when it has none; ``None`` when that cannot be
    done honestly (a noun of unknown gender, a verb beside a noun).

    QA-PRACTICE: «une lettre» beside «appartement» and «clé» was the only card
    with an article — the answer, picked out by its shape."""

    label_article = _FR_ARTICLE.match(" ".join(label.split()))
    phrase = " ".join(phrase.split())
    phrase_article = _FR_ARTICLE.match(phrase)
    if bool(label_article) == bool(phrase_article):
        return phrase
    if phrase_article:
        return phrase[phrase_article.end():].strip() or None
    kind = (label_article.group(1) or label_article.group(2)).lower()
    gender = (genders or {}).get(_fold(phrase))
    if gender not in ("m", "f") or kind in ("les", "des", "du"):
        return None
    if kind in ("un", "une"):
        return ("un " if gender == "m" else "une ") + phrase
    if _ELIDES.match(phrase):
        return "l'" + phrase
    return ("le " if gender == "m" else "la ") + phrase


def _distractors(
    target: TargetRef,
    affordances: list[str],
    limit: int = 2,
    *,
    genders: dict[str, str] | None = None,
) -> list[str]:
    """Scene phrases that are plausible here but are not the answer, each in the
    answer's shape (article or none, :func:`_shaped_like`)."""

    label = _fold(target.label_fr)
    pool: list[str] = []
    for raw in affordances:
        phrase = _shaped_like(target.label_fr or "", raw, genders) if label else raw
        if not phrase:
            continue
        if _bare(phrase) == _bare(label):
            continue
        folded = _fold(phrase)
        if not folded or folded == label:
            continue
        if label and (folded in label or label in folded):
            continue
        if folded in {_fold(item) for item in pool}:
            continue
        pool.append(phrase)
    pool.sort(key=lambda phrase: _digest(target.id, phrase))
    return pool[:limit]


def _hint_for(target: TargetRef, control_language: ControlLanguage) -> str:
    """The paid letter hint. A noun whose article the prompt does not ask for
    (:func:`journey_learning.article_optional`) is hinted by the noun itself."""

    label = " ".join((target.label_fr or "").split())
    _article, noun = split_article(label)
    if noun and article_optional(target):
        return _localized(_NOUN_HINT_TEMPLATE, control_language).format(initial=noun[:1])
    words = label.split()
    initial = words[0][:1] if words and words[0] else "?"
    return _localized(_HINT_TEMPLATE, control_language).format(
        words=word_count_phrase(len(words) or 1, control_language), initial=initial
    )


def public_recall_target(target: TargetRef) -> dict[str, Any]:
    """The recall target as the *asking* payload may carry it.

    WP-12 defect D-4: ``TargetRef.label_fr`` **is** the answer to a recall
    prompt — for a choice it is one of the options verbatim, for tiles and short
    answer it is the string being elicited — so shipping it inside the payload
    that poses the question both spoils it and bypasses the assistance ledger
    (the paid ``solution`` reveal returns exactly that string). The frozen
    ``TargetRef`` shape is kept intact, and every field that identifies the
    target without answering the question is kept with it; only the answer
    itself is withheld until the learner has answered or paid for it.
    """

    public = target.as_public()
    public["label_fr"] = ""
    return public


def _repairs_the_wording(learner: str, answer: str) -> bool:
    """Is ``answer`` recognisably a correction of ``learner`` (shared material)?

    A shared word of three letters or more, or a bigram overlap (Dice) of at least
    0.35: «appartment»/«appartement», «Je veux»/«Je voudrais».
    """

    given, wanted = _fold(learner), _fold(answer)
    if not given or not wanted:
        return False
    shared = {w for w in given.split() if len(w) >= 3} & {w for w in wanted.split() if len(w) >= 3}
    if shared:
        return True

    def bigrams(text: str) -> list[str]:
        return [text[i : i + 2] for i in range(len(text) - 1)]

    left, right = bigrams(given), bigrams(wanted)
    if not left or not right:
        return False
    pool = list(right)
    common = 0
    for gram in left:
        if gram in pool:
            pool.remove(gram)
            common += 1
    return 2 * common / (len(left) + len(right)) >= 0.35


def build_recall_task(
    *,
    target: TargetRef,
    scenario: ScenarioBrief,
    affordances: list[str],
    optional: bool,
    learner_text: str | None = None,
) -> RecallTask | None:
    """One recall opportunity — a single task, never a fifteen-item ladder.

    Returns ``None`` when the target cannot be posed without revealing itself:
    a one-word target with no gloss and no distractors has no honest question,
    so it gets no step at all rather than a fake one.

    An erratum (``TargetKind.ERROR``) is posed as a repair of ``learner_text``,
    the learner's own wrong wording: "write this correctly", never "how do you
    say <explanation>". Its ``label_native`` is an explanation, not a gloss, so
    it is not offered as the translation help either. Without the learner's
    wording there is no honest repair question, and the target gets no step.
    """

    language = scenario.control_language
    if target.concept_title:
        # WP-L1: a concept's label is its *title* («Les articles définis : le, la,
        # l', les»), not a phrase to recall; asking what it means, or cutting it
        # into tiles, is a fake question. Grammar gets its own items in WP-L4.
        return None
    label_fr = (target.label_fr or "").strip()
    if not label_fr:
        return None
    gloss = (target.label_native or "").strip() or None
    tokens = label_fr.split()
    genders = {
        _fold(entry.get("surface_fr")): str(entry.get("gender") or "")
        for entry in lexicon_of(scenario)
        if entry.get("surface_fr") and entry.get("gender") in ("m", "f")
    }
    distractors = _distractors(target, affordances, genders=genders)
    prompt_fr: str | None = None
    instruction_override: str | None = None

    goal: str | None = None
    if target.kind is TargetKind.ERROR:
        learner = " ".join(str(learner_text or "").split())
        if not learner or _fold(learner) == _fold(label_fr):
            return None
        if _fold(label_fr) in _fold(learner):
            # The wrong wording already contains the whole answer: showing it
            # would spoil the repair.
            return None
        if not _repairs_the_wording(learner, label_fr):
            # EXPERIENCE-REVIEW 2026-10-04: «Schreib richtig, was du gesagt hast»
            # over a whole letter, with «clé» as the answer (a word the letter did
            # not use), or over «der Schlüssel» (a tapped card). A repair is only
            # honest when the right answer is recognisably a fix of the wording.
            return None
        task_type: RecallTaskType = "tiles" if len(tokens) >= 2 else "short_answer"
        prompt_fr = learner
        instruction_override = _localized(_ERROR_INSTRUCTION, language)
        gloss = None
        goal = recall_goal("repair_own", language)
    elif gloss and len(distractors) >= 2:
        task_type = "choice"
    elif _is_phrase(tokens) and gloss:
        # WP-103 T3: tiles say what they build; a phrase nobody glossed has no goal
        # to give, and gets no tiles. Owner test 2026-09-30: «la» + «clé» in two
        # tiles is not an exercise — a word with its article is typed, not built.
        task_type = "tiles"
        goal = recall_goal("build", language, meaning=gloss)
    elif gloss:
        task_type = "short_answer"
    else:
        return None

    hint = _hint_for(target, language)
    common: dict[str, Any] = {
        "target": target,
        "optional": optional,
        "hint_native": hint,
        "translation_native": gloss,
        "solution_fr": label_fr,
    }

    if task_type == "choice":
        texts = [label_fr, *distractors]
        options = [
            {"id": "opt_" + _digest(target.id, text)[:8], "text_fr": text} for text in texts
        ]
        options.sort(key=lambda option: _digest(target.id, "order", option["text_fr"]))
        correct_id = "opt_" + _digest(target.id, label_fr)[:8]
        return RecallTask(
            task_type="choice",
            instruction_native=_localized(_CHOICE_INSTRUCTION, language).format(native=gloss),
            prompt_fr=None,
            options=options,
            correct_option_id=correct_id,
            accepted_answers=[label_fr],
            estimated_seconds=0,
            **common,
        )

    if task_type == "tiles":
        ordered = [
            {"id": "tile_" + _digest(target.id, str(index), token)[:8], "text_fr": token}
            for index, token in enumerate(tokens)
        ]
        correct_order = [tile["id"] for tile in ordered]
        shown = sorted(ordered, key=lambda tile: _digest(target.id, "layout", tile["id"]))
        if [tile["id"] for tile in shown] == correct_order and len(shown) > 1:
            shown = shown[1:] + shown[:1]
        instruction = instruction_override or (
            _localized(_TILES_INSTRUCTION_WITH_GLOSS, language).format(native=gloss)
            if gloss
            else _localized(_TILES_INSTRUCTION, language)
        )
        return RecallTask(
            task_type="tiles",
            instruction_native=instruction,
            prompt_fr=prompt_fr,
            options=shown,
            correct_tile_order=correct_order,
            accepted_answers=[label_fr],
            estimated_seconds=0,
            goal_native=goal,
            source_fr=prompt_fr,
            **common,
        )

    return RecallTask(
        task_type="short_answer",
        instruction_native=instruction_override
        or _localized(_SHORT_ANSWER_INSTRUCTION, language).format(native=gloss),
        prompt_fr=prompt_fr,
        options=[],
        accepted_answers=[label_fr],
        estimated_seconds=0,
        goal_native=goal,
        source_fr=prompt_fr,
        **common,
    )


# --------------------------------------------------------------------------
# 2b. WP-66 — the three Séance formats, posed from the same authored material
#
# Each builder returns ``None`` the moment it cannot pose its format *without
# revealing the answer*. That is the whole no-spoil rule: a format that cannot
# be asked honestly is not asked, and the rotation falls through to the next
# one. None of them calls a model, reads a scheduler, or invents content.
# --------------------------------------------------------------------------


def _extra_chips(target: TargetRef, affordances: list[str], answer_tokens: list[str]) -> list[str]:
    """Single words from the scene that are plausible here and are not used.

    Drawn from the same authored affordances the choice distractors come from,
    so a word bank is scene vocabulary the learner could reasonably reach for —
    never a random string and never a word that is part of the answer.
    """

    used = {_fold(token) for token in answer_tokens}
    pool: list[str] = []
    seen: set[str] = set()
    for phrase in affordances:
        for word in str(phrase or "").split():
            folded = _fold(word)
            if not folded or folded in used or folded in seen:
                continue
            seen.add(folded)
            pool.append(word)
    pool.sort(key=lambda word: _digest(target.id, "chip", word))
    return pool[:2]


_ARTICLES = frozenset({"le", "la", "les", "l'", "l’", "un", "une", "des", "du", "de", "d'", "d’"})


def _is_phrase(tokens: list[str]) -> bool:
    """Worth building from pieces: three words or more, or two that are not just an
    article and its noun («la clé» is typed, «bonne nuit» may be built)."""

    if len(tokens) >= 3:
        return True
    return len(tokens) == 2 and tokens[0].casefold() not in _ARTICLES


def build_word_bank_task(
    *,
    target: TargetRef,
    affordances: list[str],
    optional: bool,
    control_language: ControlLanguage,
) -> RecallTask | None:
    """Build the phrase from chips, *some of which are not needed*.

    The difference from ``tiles`` is the whole point: with only the answer's own
    words on screen, the chip row is the answer written down in the wrong order,
    and a learner can solve it by counting. With at least one plausible chip that
    does not belong, they have to know the phrase.
    """

    if target.concept_title:
        # WP-L1: a concept title is not a sentence to rebuild.
        return None
    label_fr = (target.label_fr or "").strip()
    tokens = label_fr.split()
    if not _is_phrase(tokens):
        # A word with its article is not built from chips (owner test 2026-09-30).
        return None
    extras = _extra_chips(target, affordances, tokens)
    if not extras:
        return None
    gloss = (target.label_native or "").strip() or None
    if gloss is None or target.kind is TargetKind.ERROR:
        # WP-103 T3 (the owner's test): «Some chips are not needed» — of which
        # phrase? A word bank says what it builds, or it is not posed.
        return None

    answer = [
        {"id": "tile_" + _digest(target.id, str(index), token)[:8], "text_fr": token}
        for index, token in enumerate(tokens)
    ]
    correct_order = [tile["id"] for tile in answer]
    chips = [
        *answer,
        *(
            {"id": "chip_" + _digest(target.id, "extra", word)[:8], "text_fr": word}
            for word in extras
        ),
    ]
    if len({chip["id"] for chip in chips}) != len(chips):
        # Two chips with the same id cannot be told apart in an answer.
        return None
    shown = sorted(chips, key=lambda chip: _digest(target.id, "bank", chip["id"]))
    instruction = (
        _localized(_WORD_BANK_INSTRUCTION_WITH_GLOSS, control_language).format(native=gloss)
        if gloss
        else _localized(_WORD_BANK_INSTRUCTION, control_language)
    )
    return RecallTask(
        task_type="word_bank",
        instruction_native=instruction,
        prompt_fr=None,
        options=shown,
        target=target,
        optional=optional,
        correct_tile_order=correct_order,
        accepted_answers=[label_fr],
        hint_native=_hint_for(target, control_language),
        translation_native=gloss,
        solution_fr=label_fr,
        estimated_seconds=0,
        goal_native=recall_goal("build", control_language, meaning=gloss),
    )


def build_classify_task(
    *, target: TargetRef, optional: bool, control_language: ControlLanguage
) -> RecallTask | None:
    """Sort one French item under two contrastive labels.

    Two sources, both read off the target itself and both genuinely contrastive
    (the legacy Séance rejects ``true/false`` and ``yes/no`` label pairs for
    exactly this reason):

    * **gender**, for a noun stored with its article — the article settles the
      answer, so the article is precisely what the prompt does not show;
    * **address**, for a phrase that unambiguously says ``tu`` or ``vous``.

    A noun behind ``l'`` has no answer to give and gets no classify step.
    """

    label_fr = (target.label_fr or "").strip()
    tokens = label_fr.split()
    if not tokens:
        return None

    article = tokens[0].casefold().strip(".,;:!?")
    gender = _GENDER_ARTICLES.get(article) if len(tokens) >= 2 else None
    if gender is not None:
        noun = " ".join(tokens[1:]).strip()
        if not noun or _GENDER_ARTICLES.get(noun.casefold()) is not None:
            return None
        # QA-CLOSE (owner decision e): «masculin/féminin» was French chrome for a
        # German A1 learner. The labels follow the control language; outside
        # French they are the learner's own words (``side: native``).
        masculine, feminine = _CLASSIFY_GENDER_LABELS.get(str(control_language), _CLASSIFY_GENDER_LABELS["fr"])
        side = {} if str(control_language) == "fr" else {"side": "native"}
        options = [
            {"id": "cls_" + _digest(target.id, "masculin")[:8], "text_fr": masculine, **side},
            {"id": "cls_" + _digest(target.id, "feminin")[:8], "text_fr": feminine, **side},
        ]
        correct = options[0]["id"] if gender == "m" else options[1]["id"]
        return RecallTask(
            task_type="classify",
            instruction_native=_localized(_CLASSIFY_GENDER_INSTRUCTION, control_language),
            prompt_fr=noun,
            options=options,
            target=target,
            optional=optional,
            correct_option_id=correct,
            accepted_answers=[label_fr],
            # Neither the letter hint nor the native gloss may be offered here:
            # both spell out the article, which *is* the answer.
            hint_native=None,
            translation_native=None,
            solution_fr=label_fr,
            estimated_seconds=0,
        )

    if len(tokens) < 2:
        return None
    observed = pragmatics.address_register(label_fr)
    if observed not in _CLASSIFY_ADDRESS_LABELS:
        return None
    if observed in re.split(r"[^a-zàâçéèêëîïôûùüÿœ]+", _fold(label_fr)):
        # QA-PRACTICE: «s'il vous plaît» — tu or vous? The answer is printed in
        # the question; a classify is honest only when the verb carries it.
        return None
    options = [
        {"id": "cls_" + _digest(target.id, label)[:8], "text_fr": label}
        for label in _CLASSIFY_ADDRESS_LABELS
    ]
    correct = next(
        option["id"] for option, label in zip(options, _CLASSIFY_ADDRESS_LABELS, strict=True)
        if label == observed
    )
    return RecallTask(
        task_type="classify",
        instruction_native=_localized(_CLASSIFY_ADDRESS_INSTRUCTION, control_language),
        prompt_fr=label_fr,
        options=options,
        target=target,
        optional=optional,
        correct_option_id=correct,
        accepted_answers=[label_fr],
        hint_native=None,
        translation_native=(target.label_native or "").strip() or None,
        solution_fr=label_fr,
        estimated_seconds=0,
    )


def build_transform_task(
    *, target: TargetRef, optional: bool, control_language: ControlLanguage
) -> RecallTask | None:
    """Say the same thing to the other person — a directed rewrite.

    The source is the learner's own due phrase and the answer is that phrase in
    the opposite form of address, computed by the same deterministic detectors
    that grade register live (:mod:`app.services.pragmatics`), so the exercise
    and the grader can never disagree.

    The three no-spoil conditions, which are the journey's half of the
    three-gates rule (generation prompt · structural validator · AI critic) and
    are pinned against the legacy Séance's own validators in
    ``tests/test_journey_planner.py``:

    1. the answer may not be the sentence already printed above it;
    2. the instruction quotes the source fragment to change, which is in the
       source by construction;
    3. the instruction names the target *form* (``tu``/``vous``) and never the
       conjugated answer word — so a swap where the pronoun alone is the whole
       answer (« pour toi » → « pour vous ») is refused rather than given away.
    """

    label_fr = (target.label_fr or "").strip()
    if len(label_fr.split()) < 2:
        return None
    observed = pragmatics.address_register(label_fr)
    if observed not in _CLASSIFY_ADDRESS_LABELS:
        return None
    wanted = "vous" if observed == "tu" else "tu"
    span, replacement = pragmatics.slip_span(label_fr, expected=wanted)
    if not span or not replacement or span not in label_fr:
        return None
    if _fold(replacement) == _fold(wanted):
        # The pronoun *is* the answer; naming the target form would print it.
        return None
    expected = label_fr.replace(span, replacement, 1)
    if _fold(expected) == _fold(label_fr):
        return None
    instruction = _localized(_TRANSFORM_INSTRUCTION, control_language).format(
        pronoun=wanted, span=span
    )
    revealed = [
        word
        for word in replacement.split()
        if _fold(word) != _fold(wanted) and _fold(word) in _fold(instruction).split()
    ]
    if revealed:  # pragma: no cover - the template names only span and pronoun
        return None
    return RecallTask(
        task_type="transform",
        instruction_native=instruction,
        prompt_fr=label_fr,
        options=[],
        target=target,
        optional=optional,
        accepted_answers=[expected],
        hint_native=_localized(_TRANSFORM_HINT, control_language).format(span=span),
        # The stored gloss describes the *source*, not the rewrite that is
        # being asked for, so offering it as "the translation" would mislead.
        translation_native=None,
        solution_fr=expected,
        estimated_seconds=0,
        goal_native=recall_goal("readdress", control_language, pronoun=wanted),
        source_fr=label_fr,
    )


# --------------------------------------------------------------------------
# 2c. WP-78 — the quick formats of a practice day
#
# Same rule as §2b: no model call, no invented content, and ``None`` whenever
# the format cannot be posed honestly. The material is the learner's own due
# words (with the glosses the evidence layer already resolved in their
# language) and the sentences of the scene they have just read.
# --------------------------------------------------------------------------


def _glossed(target: TargetRef) -> str | None:
    """The target's gloss when it *is* a gloss — never an erratum's explanation
    and never a grammar concept's category label."""

    if target.kind is not TargetKind.VOCABULARY:
        return None
    gloss = " ".join(str(target.label_native or "").split())
    if not gloss or not (target.label_fr or "").strip():
        return None
    return gloss


def _gloss_partners(
    target: TargetRef, pool: list[TargetRef] | tuple[TargetRef, ...], count: int
) -> list[TargetRef]:
    """Other glossed words of today, none sharing a French side or a meaning."""

    # QA-PRACTICE: compared without articles — «appartement» beside «un
    # appartement» (or «Wohnung» beside «eine Wohnung») made two right answers.
    taken_fr = {_bare(target.label_fr)}
    taken_gloss = {_bare(_glossed(target))}
    partners: list[TargetRef] = []
    ranked = sorted(pool, key=lambda item: _digest(target.id, "partner", target_identity(item)))
    for item in ranked:
        gloss = _glossed(item)
        if gloss is None or target_identity(item) == target_identity(target):
            continue
        if _bare(item.label_fr) in taken_fr or _bare(gloss) in taken_gloss:
            continue
        taken_fr.add(_bare(item.label_fr))
        taken_gloss.add(_bare(gloss))
        partners.append(item)
        if len(partners) == count:
            break
    return partners


def build_match_pairs_task(
    *,
    target: TargetRef,
    pool: list[TargetRef] | tuple[TargetRef, ...],
    optional: bool,
    control_language: ControlLanguage,
) -> RecallTask | None:
    """Four French cards, four meanings, tap to pair.

    Graded on the day's target alone: it is the first pair in
    ``correct_tile_order``, and only the first pairing the learner makes with
    either of its two cards counts. The other three pairs are today's other
    words, there so the one that counts has to be *known*, not guessed by
    elimination. Needs four glossed words with four different meanings.
    """

    gloss = _glossed(target)
    if gloss is None:
        return None
    partners = _gloss_partners(target, pool, MATCH_PAIR_COUNT - 1)
    if len(partners) < MATCH_PAIR_COUNT - 1:
        return None
    words = [target, *partners]
    fr_cards = [
        {"id": "mfr_" + _digest(target.id, "match-fr", target_identity(word))[:8],
         "text_fr": word.label_fr.strip(), "side": "fr"}
        for word in words
    ]
    native_cards = [
        {"id": "mna_" + _digest(target.id, "match-na", target_identity(word))[:8],
         "text_fr": str(_glossed(word)), "side": "native"}
        for word in words
    ]
    ids = [card["id"] for card in (*fr_cards, *native_cards)]
    if len(set(ids)) != len(ids):
        return None
    order: list[str] = []
    for fr_card, native_card in zip(fr_cards, native_cards, strict=True):
        order.extend((fr_card["id"], native_card["id"]))
    shown_fr = sorted(fr_cards, key=lambda card: _digest(target.id, "col-fr", card["id"]))
    shown_native = sorted(
        native_cards, key=lambda card: _digest(target.id, "col-na", card["id"])
    )
    fr_rank = {card["id"]: index for index, card in enumerate(fr_cards)}
    native_rank = {card["id"]: index for index, card in enumerate(native_cards)}
    if [fr_rank[c["id"]] for c in shown_fr] == [native_rank[c["id"]] for c in shown_native]:
        # Two columns in the same order would be the answer drawn as rows.
        shown_native = shown_native[1:] + shown_native[:1]
    return RecallTask(
        task_type="match_pairs",
        instruction_native=_localized(_MATCH_INSTRUCTION, control_language),
        prompt_fr=None,
        options=[*shown_fr, *shown_native],
        target=target,
        optional=optional,
        correct_tile_order=order,
        accepted_answers=[target.label_fr.strip()],
        # Every meaning is already on the table; a hint or a translation would
        # be the answer, so a quick item offers neither.
        hint_native=None,
        translation_native=None,
        solution_fr=None,
        estimated_seconds=0,
    )


def build_listen_tap_task(
    *,
    target: TargetRef,
    pool: list[TargetRef] | tuple[TargetRef, ...],
    optional: bool,
    control_language: ControlLanguage,
) -> RecallTask | None:
    """A French phrase, three meanings in the learner's language, one tap.

    «Écouter et toucher» when the deployment can speak the phrase; the phrase
    is printed instead when it cannot (no audio is synthesised for it yet —
    the episode-audio flag stays off), which is read-and-tap: the
    same question, answered the same way. The distractors are today's other
    words' meanings, so no scene affordance is needed — which is what lets a
    story-engine day, whose scene affords nothing, pose a recognition item.
    """

    gloss = _glossed(target)
    if gloss is None:
        return None
    partners = _gloss_partners(target, pool, 2)
    if len(partners) < 2:
        return None
    options = [
        {"id": "lt_" + _digest(target.id, "listen", target_identity(word))[:8],
         "text_fr": str(_glossed(word)), "side": "native"}
        for word in (target, *partners)
    ]
    correct = options[0]["id"]
    shown = sorted(options, key=lambda option: _digest(target.id, "listen-order", option["id"]))
    return RecallTask(
        task_type="listen_tap",
        instruction_native=_localized(_LISTEN_TAP_INSTRUCTION, control_language),
        prompt_fr=target.label_fr.strip(),
        options=shown,
        target=target,
        optional=optional,
        correct_option_id=correct,
        accepted_answers=[target.label_fr.strip()],
        hint_native=None,
        translation_native=None,
        solution_fr=None,
        estimated_seconds=0,
    )


_SENTENCE_END = frozenset(".!?…")
_QUOTE_MARKS = "«»“”\"„"


def scene_sentences(*texts: str | None) -> list[str]:
    """The sentences of what the learner reads, in order, without repeats."""

    sentences: list[str] = []
    seen: set[str] = set()
    for text in texts:
        current: list[str] = []
        for raw in " ".join(str(text or "").split()).split(" "):
            # Quotation marks are layout, not words: a tile reading «»
            # would be a puzzle about typography.
            word = raw.strip(_QUOTE_MARKS)
            if not word:
                continue
            current.append(word)
            if word[-1] in _SENTENCE_END:
                sentence = " ".join(current)
                current = []
                if _fold(sentence) not in seen:
                    seen.add(_fold(sentence))
                    sentences.append(sentence)
        if current:
            sentence = " ".join(current)
            if _fold(sentence) not in seen:
                seen.add(_fold(sentence))
                sentences.append(sentence)
    return sentences


def _contains_label(sentence: str, label: str) -> bool:
    words = [word.strip(".,;:!?…«»\"'()") for word in _fold(sentence).split()]
    needle = [word.strip(".,;:!?…«»\"'()") for word in _fold(label).split()]
    needle = [word for word in needle if word]
    if not needle:
        return False
    return any(words[index:index + len(needle)] == needle for index in range(len(words)))


def build_unscramble_task(
    *,
    target: TargetRef,
    sentences: list[str] | tuple[str, ...],
    optional: bool,
    control_language: ControlLanguage,
    meanings: dict[str, str] | None = None,
) -> RecallTask | None:
    """Rebuild the scene's sentence that holds today's word.

    Posed only *after* the scene (``PlannedJourney`` refuses it before), from a
    sentence the learner has just read — or, for a word they kept from a story
    (tap-to-keep), from the sentence they kept it with. Tiles, so it is graded
    by identity and coloured on the device.
    """

    label = (target.label_fr or "").strip()
    if not label or target.kind is TargetKind.ERROR:
        return None
    low, high = UNSCRAMBLE_WORDS
    chosen = next(
        (
            sentence
            for sentence in sentences
            if low <= len(sentence.split()) <= high and _contains_label(sentence, label)
        ),
        None,
    )
    if chosen is None:
        return None
    from app.services.scene_items import tile_words

    tokens = tile_words(chosen)
    if len(tokens) < low:
        return None
    ordered = [
        {"id": "tile_" + _digest(target.id, "unscramble", str(index), token)[:8], "text_fr": token}
        for index, token in enumerate(tokens)
    ]
    correct_order = [tile["id"] for tile in ordered]
    if len(set(correct_order)) != len(correct_order):
        return None
    shown = sorted(ordered, key=lambda tile: _digest(target.id, "unscramble-layout", tile["id"]))
    if [tile["id"] for tile in shown] == correct_order:
        shown = shown[1:] + shown[:1]
    return RecallTask(
        task_type="unscramble",
        instruction_native=_localized(_UNSCRAMBLE_INSTRUCTION, control_language),
        prompt_fr=None,
        options=shown,
        target=target,
        optional=optional,
        correct_tile_order=correct_order,
        accepted_answers=[chosen],
        hint_native=None,
        translation_native=None,
        solution_fr=chosen,
        estimated_seconds=0,
        # WP-103 T3: which sentence — its meaning when the scene translated it,
        # else the word it holds (every tile is on screen: naming one spoils nothing).
        goal_native=(
            recall_goal("rebuild_scene", control_language, meaning=meaning)
            if (meaning := meaning_of(meanings or {}, chosen))
            else recall_goal("rebuild_word", control_language, word=label)
        ),
    )


# -- WP-91: what is heard ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HeardLine:
    """One line of today's scene as it is spoken: who, and exactly what."""

    character_id: str
    text_fr: str

    @property
    def voice(self) -> str:
        return voice_for_character(self.character_id)


def _speakable(text: str | None) -> str:
    clean = " ".join(str(text or "").split()).strip(_QUOTE_MARKS + " ")
    # An authored template that was never rendered is not a line to speak.
    return "" if "{" in clean or "}" in clean else clean


def scene_heard_lines(scenario: ScenarioBrief) -> list[HeardLine]:
    """Every line today's scene speaks, in reading order, without repeats.

    The characters' own lines first (a story-engine draft's dialogue and the
    opening line, :func:`scene_items.scene_lines`; an authored page's panels),
    then the narration. The same set the line-audio route accepts for the scene
    step, so a clip a listening item carries is always a line the learner met.
    """

    lines: list[HeardLine] = []
    for line in scene_lines(scenario):
        lines.append(HeardLine(line.character_id, _speakable(line.text_fr)))
    narration: list[HeardLine] = []
    for panel in scenario.panels or []:
        if not isinstance(panel, dict):
            continue
        for entry in panel.get("dialogue") or []:
            if isinstance(entry, dict) and entry.get("character_id"):
                lines.append(
                    HeardLine(str(entry["character_id"]), _speakable(entry.get("text_fr")))
                )
        narration.append(HeardLine(NARRATOR_ID, _speakable(panel.get("narration_fr"))))
    story = scenario.story_context if isinstance(scenario.story_context, dict) else {}
    draft = story.get("draft") if isinstance(story.get("draft"), dict) else {}
    for panel in draft.get("panels") or []:
        if isinstance(panel, dict):
            narration.append(HeardLine(NARRATOR_ID, _speakable(panel.get("narration_fr"))))
    seen: set[str] = set()
    unique: list[HeardLine] = []
    for line in [*lines, *narration]:
        key = _fold(line.text_fr)
        if not line.text_fr or key in seen:
            continue
        seen.add(key)
        unique.append(line)
    return unique


def dictation_lines(scenario: ScenarioBrief) -> list[HeardLine]:
    """What a dictation may ask for: each sentence of each line of today's
    scene, with its speaker — a long line still offers its short sentences.
    The scene's setup comes last, in the narrator's voice."""

    lines = [*scene_heard_lines(scenario), HeardLine(NARRATOR_ID, _speakable(scenario.setup_fr))]
    sentences: list[HeardLine] = []
    seen: set[str] = set()
    for line in lines:
        for sentence in scene_sentences(line.text_fr):
            clean = _speakable(sentence)
            if clean and _fold(clean) not in seen:
                seen.add(_fold(clean))
                sentences.append(HeardLine(line.character_id, clean))
    return sentences


def dictation_word_cap(level_band: str | None) -> int:
    """≤ 8 words at A1, ≤ 12 at A2, ≤ 16 from B1."""

    band = str(level_band or "").strip().upper()[:2]
    return DICTATION_MAX_WORDS.get(band, DICTATION_MAX_WORDS_DEFAULT)


def build_dictation_task(
    *,
    target: TargetRef,
    line: HeardLine,
    optional: bool,
    control_language: ControlLanguage,
) -> RecallTask:
    """«Dictée»: hear one line of today's scene, type it.

    The public side is the instruction and the clip, nothing else: no
    ``prompt_fr``, no options, and the target's label is withheld as for every
    recall item. The line is the answer key (``accepted_answers``) and the paid
    reveal (``solution_fr``). Optional: a bonus of listening, so a day whose
    audio went dark after it was planned can still be finished.
    """

    words = len(line.text_fr.split())
    return RecallTask(
        task_type="dictation",
        instruction_native=_localized(_DICTATION_INSTRUCTION, control_language),
        prompt_fr=None,
        options=[],
        target=target,
        optional=optional,
        accepted_answers=[line.text_fr],
        hint_native=_localized(_DICTATION_HINT, control_language).format(
            words=word_count_phrase(words, control_language)
        ),
        translation_native=None,
        solution_fr=line.text_fr,
        estimated_seconds=0,
    )


def listen_tap_line(scenario: ScenarioBrief, target: TargetRef) -> HeardLine:
    """Who speaks a listen-and-tap phrase: the character whose line holds it
    today, else the scene's own character, else the narrator. The phrase is the
    target's own words — the meaning the three cards gloss."""

    phrase = _speakable(target.label_fr)
    for line in scene_heard_lines(scenario):
        if line.character_id != NARRATOR_ID and _contains_label(line.text_fr, phrase):
            return HeardLine(line.character_id, phrase)
    return HeardLine(str(scenario.character_id or NARRATOR_ID), phrase)


def build_recall_task_in_format(
    task_type: str,
    *,
    target: TargetRef,
    scenario: ScenarioBrief,
    affordances: list[str],
    optional: bool,
    learner_text: str | None = None,
    pool: list[TargetRef] | tuple[TargetRef, ...] = (),
    sentences: list[str] | tuple[str, ...] = (),
) -> RecallTask | None:
    """One recall opportunity in one named format, or ``None``.

    ``None`` means "not this format, honestly" — the target may still be posed
    another way. It is never an error. ``pool`` (today's other words) and
    ``sentences`` (what the learner reads today) feed WP-78's quick formats.
    """

    language = scenario.control_language
    if task_type == str(RecallFormat.MATCH_PAIRS):
        return build_match_pairs_task(
            target=target, pool=pool, optional=optional, control_language=language
        )
    if task_type == str(RecallFormat.LISTEN_TAP):
        return build_listen_tap_task(
            target=target, pool=pool, optional=optional, control_language=language
        )
    if task_type == str(RecallFormat.UNSCRAMBLE):
        return build_unscramble_task(
            target=target, sentences=sentences, optional=optional, control_language=language,
            meanings=line_meanings(scenario),
        )
    if task_type == str(RecallFormat.WORD_BANK):
        return build_word_bank_task(
            target=target,
            affordances=affordances,
            optional=optional,
            control_language=language,
        )
    if task_type == str(RecallFormat.CLASSIFY):
        return build_classify_task(
            target=target, optional=optional, control_language=language
        )
    if task_type == str(RecallFormat.TRANSFORM):
        return build_transform_task(
            target=target, optional=optional, control_language=language
        )
    legacy = build_recall_task(
        target=target,
        scenario=scenario,
        affordances=affordances,
        optional=optional,
        learner_text=learner_text,
    )
    return legacy if legacy is not None and legacy.task_type == task_type else None


def build_rotated_recall_task(
    *,
    target: TargetRef,
    scenario: ScenarioBrief,
    affordances: list[str],
    optional: bool,
    formats: list[str],
    day_shape: DayShape = DEFAULT_DAY_SHAPE,
    learner_text: str | None = None,
) -> RecallTask | None:
    """Walk today's seeded format order and take the first honest fit.

    The legacy builder is the floor, not a competitor: when none of the rotated
    formats can be posed without revealing the answer, the target is posed the
    way it always was — and only if *that* is impossible does it lose its step.
    The floor still respects the day's shape, so a listening day never falls
    back onto a multiple choice nobody can take down by ear.
    """

    for task_type in formats:
        task = build_recall_task_in_format(
            task_type,
            target=target,
            scenario=scenario,
            affordances=affordances,
            optional=optional,
            learner_text=learner_text,
        )
        if task is not None:
            return task
    fallback = build_recall_task(
        target=target,
        scenario=scenario,
        affordances=affordances,
        optional=optional,
        learner_text=learner_text,
    )
    if fallback is not None and not shape_allows_format(day_shape, fallback.task_type):
        if (
            shape_allows_format(day_shape, str(RecallFormat.SHORT_ANSWER))
            and target.kind is not TargetKind.ERROR
            and _glossed(target) is not None
        ):
            # A word the shape cannot pose as its first choice is typed from its
            # meaning — never dropped (a day must keep its practice).
            label = target.label_fr.strip()
            return RecallTask(
                task_type="short_answer",
                instruction_native=_localized(
                    _SHORT_ANSWER_INSTRUCTION, scenario.control_language
                ).format(native=_glossed(target)),
                prompt_fr=None,
                options=[],
                target=target,
                optional=optional,
                accepted_answers=[label],
                hint_native=_hint_for(target, scenario.control_language),
                translation_native=None,
                solution_fr=label,
                estimated_seconds=0,
            )
        return None
    return fallback


def _letter_prompt(letter: LetterOffer | None) -> dict[str, Any] | None:
    """The public half of a Courrier letter, or ``None``.

    The whole of WP-66's dependency on WP-64 passes through this one function
    and :func:`app.services.journey_day_shapes.set_letter_provider`. Nothing
    here knows what a mission is.
    """

    if letter is None or not letter.is_renderable():
        return None
    return {
        "mission_id": str(letter.mission_id),
        "correspondent_id": str(letter.correspondent_id),
        "correspondent_name": letter.correspondent_name,
        "subject_fr": letter.subject_fr,
        "body_fr": letter.body_fr,
        "objective_native": letter.objective_native,
    }


def _recall_help(task: RecallTask) -> list[str]:
    available = [str(HelpKind.HINT)] if task.hint_native else []
    if task.translation_native:
        available.append(str(HelpKind.TRANSLATION))
    if task.solution_fr:
        available.append(str(HelpKind.SOLUTION))
    return available


def _respond_help(task: ResponseTask) -> list[str]:
    available: list[str] = []
    if task.hint_native:
        available.append(str(HelpKind.HINT))
    if task.translation_native:
        available.append(str(HelpKind.TRANSLATION))
    if task.suggested_response_fr:
        available.append(str(HelpKind.SUGGESTED_RESPONSE))
    return available


# --------------------------------------------------------------------------
# 3. Estimates
# --------------------------------------------------------------------------


def _reading_seconds(seconds_per_token: float, *texts: str | None) -> float:
    return _tokens(*texts) * seconds_per_token


def _playback_seconds(audio_url: str | None, *texts: str | None) -> float:
    """Listening time, which is zero until a step actually carries audio."""

    if not audio_url:
        return 0.0
    return _tokens(*texts) * AUDIO_PLAYBACK_SECONDS_PER_TOKEN


def scene_page(scenario: ScenarioBrief) -> list[dict[str, Any]]:
    """The page the scene step shows: an authored scene's panels, or the
    story-engine draft's (published as the episode the reader opens)."""

    if scenario.panels:
        return [panel for panel in scenario.panels if isinstance(panel, dict)]
    return [panel for panel in draft_of(scenario).get("panels") or [] if isinstance(panel, dict)]


def page_texts(panels: list[dict[str, Any]]) -> list[str]:
    """Every French text a page prints: narration, then each line, in order."""

    texts: list[str] = []
    for panel in panels:
        narration = str(panel.get("narration_fr") or "").strip()
        if narration:
            texts.append(narration)
        for line in panel.get("dialogue") or []:
            text = str((line or {}).get("text_fr") or "").strip() if isinstance(line, dict) else ""
            if text:
                texts.append(text)
    return texts


def page_seconds(
    texts: list[str], *, panels: int, spt: float, multiplier: float, audio: bool,
    band: str | None = None,
) -> float:
    """WP-93: looking at ``panels`` panels, reading ``texts`` at a learner's
    pace with a word's help now and then, and — when the deployment speaks —
    hearing every line once. WP-128: the prose factor is the band's."""

    orientation = SCENE_PANEL_SECONDS * panels + SCENE_LINE_HELP_SECONDS * len(texts)
    reading = _reading_seconds(spt, *texts) * page_reading_factor(band)
    playback = _tokens(*texts) * AUDIO_PLAYBACK_SECONDS_PER_TOKEN if audio else 0.0
    return orientation * multiplier + reading + playback


def scene_seconds(
    scenario: ScenarioBrief, *, spt: float, multiplier: float, audio: bool = False,
    band: str | None = None,
) -> int:
    """Orientation, the setup and the objective, then the page itself.

    WP-93: the page is priced by what is on it — its panels and every line of
    narration and dialogue (plus the closing question when the page does not
    print it), and their audio when ``audio`` says the deployment speaks. A
    page-less brief (legacy content) keeps the pre-WP-93 price: the setup,
    the objective and the opening line.
    """

    reading = _reading_seconds(
        spt, scenario.setup_fr, scenario.setup_native, scenario.objective_native
    )
    key = _band_key(band)
    if key:
        # WP-128: the setup's gloss is half-glanced at A1–A2 and not leaned on
        # from B1, where the chrome is French; the setup itself is prose.
        gloss = 0.5 if key in ("A1", "A2") else 0.0
        reading = (
            _reading_seconds(spt, scenario.setup_fr) * page_reading_factor(band)
            + _tokens(scenario.objective_native) * NATIVE_SECONDS_PER_TOKEN
            + gloss * _tokens(scenario.setup_native) * NATIVE_SECONDS_PER_TOKEN
        )
    panels = scene_page(scenario)
    if not panels:
        reading += _reading_seconds(spt, scenario.opening_line_fr)
        return max(1, round(SCENE_BASE_SECONDS * multiplier + reading))
    texts = page_texts(panels)
    opening = " ".join(str(scenario.opening_line_fr or "").split())
    if opening and not any(_fold(opening) in _fold(text) for text in texts):
        texts.append(opening)
    page = page_seconds(
        texts, panels=len(panels), spt=spt, multiplier=multiplier, audio=audio, band=band
    )
    return max(1, round(SCENE_BASE_SECONDS * multiplier + reading + page))


def reading_step_seconds(
    reading: dict[str, Any], scenario: ScenarioBrief, *, spt: float, multiplier: float,
    audio: bool, band: str | None = None,
) -> int:
    """WP-93 «Lecture»: a second page. A «relecture» is priced from yesterday's
    page as stored; «coulisses» is written after the plan, so it is priced as
    today's page (the same evening, from another side, the same length)."""

    texts = [str(text) for text in reading.get("texts_fr") or [] if str(text or "").strip()]
    panels = int(reading.get("panel_count") or 0)
    if not texts:
        page = scene_page(scenario)
        texts = page_texts(page) or [scenario.setup_fr]
        panels = panels or len(page)
    panels = panels or max(1, len(texts) // 2)
    heard = audio and bool(reading.get("audio_available", audio))
    return max(
        1,
        round(
            SCENE_BASE_SECONDS * multiplier
            + page_seconds(
                texts, panels=panels, spt=spt, multiplier=multiplier, audio=heard, band=band
            )
        ),
    )


def recall_seconds(task: RecallTask, *, spt: float, multiplier: float) -> int:
    """Reading the task, answering it once, and reading the normal feedback."""

    texts = [task.instruction_native, task.prompt_fr]
    texts.extend(str(option.get("text_fr") or "") for option in task.options)
    fixed = RECALL_ANSWER_SECONDS.get(task.task_type, 30) + RECALL_FEEDBACK_SECONDS
    return max(1, round(fixed * multiplier + _reading_seconds(spt, *texts)))


def quick_recall_seconds(task: RecallTask, *, spt: float, multiplier: float) -> int:
    """WP-78 — one quick item: read the instruction and the prompt, answer,
    see the colour. The cards themselves are priced inside the answer."""

    fixed = QUICK_ANSWER_SECONDS.get(task.task_type, 10) + QUICK_FEEDBACK_SECONDS
    # WP-128: everything the item prints is read — its goal, its source line
    # and its cards too (a matching grid is eight cards; at A1 reading them is
    # most of the item) — at the band's prompt pace.
    reading = _reading_seconds(
        spt,
        task.instruction_native,
        task.prompt_fr,
        getattr(task, "goal_native", None),
        getattr(task, "source_fr", None),
        *(str(option.get("text_fr") or "") for option in task.options or []),
    )
    if task.task_type in TYPED_FORMATS:
        # WP-128: a typed answer is typed — a start, then its characters
        # (the walk's Timer: 3 s, then 0.35 s a character).
        fixed = (
            TYPED_START_SECONDS
            + TYPING_SECONDS_PER_CHAR * len(str(task.solution_fr or ""))
            + QUICK_FEEDBACK_SECONDS
        )
    if task.task_type == str(RecallFormat.DICTATION):
        # WP-91: heard twice, then typed — priced per word of the line.
        words = _tokens(task.solution_fr)
        fixed += words * (2 * AUDIO_PLAYBACK_SECONDS_PER_TOKEN + DICTATION_TYPING_SECONDS_PER_WORD)
    return max(1, round(fixed * multiplier + reading))


def expected_reply_words(task: ResponseTask, band: str | None = None) -> int:
    """WP-128: the reply's expected length — the suggested reply's, at least
    the band's sentence (:data:`REPLY_WORDS_FLOOR`), at most two sentences."""

    floor = REPLY_WORDS_FLOOR[_band_key(band) or "B1"]
    words = max(_tokens(getattr(task, "suggested_response_fr", None)), floor)
    return min(words, REPLY_WORDS_CEILING)


def authored_turns(scenario: ScenarioBrief) -> list[tuple[str, int]]:
    """WP-128: an authored (season) page's exchanges as ``(kind, words)`` —
    ``("card", words on the cards)`` for «Le choix», else ``("reply", the length
    of the turn's authored example answer)``. Empty for a generated day."""

    context = scenario.story_context if isinstance(scenario.story_context, dict) else {}
    season = context.get("season") if isinstance(context.get("season"), dict) else {}
    out: list[tuple[str, int]] = []
    for turn in season.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        replies = [reply for reply in turn.get("replies") or [] if isinstance(reply, dict)]
        if turn.get("choice"):
            out.append(("card", sum(_tokens(str(reply.get("label") or "")) for reply in replies)))
            continue
        lengths = sorted(
            _tokens(str((reply.get("examples") or [""])[0])) for reply in replies if reply.get("examples")
        )
        out.append(("reply", lengths[len(lengths) // 2] if lengths else 0))
    return out


def unit_sentence_words(brief: dict[str, Any] | None, band: str | None) -> int:
    """WP-128: the extra sentence a reply that asks for a unit costs — its first
    example's length, else one sentence at the band."""

    examples = (brief or {}).get("examples") if isinstance(brief, dict) else None
    first = next((str(item) for item in examples or [] if str(item or "").strip()), "")
    return _tokens(first) or REPLY_WORDS_FLOOR[_band_key(band) or "B1"]


def respond_seconds(
    task: ResponseTask, *, turns: int, spt: float, multiplier: float, band: str | None = None,
    asks_unit: int = 0, authored: list[tuple[str, int]] | None = None,
) -> int:
    """WP-03's authored envelope, floored by an explicit bottom-up model.

    WP-128: with a ``band`` the reply is priced bottom-up only, by what it
    asks of a reader and writer of that band — per exchange, composing the
    expected reply (:func:`expected_reply_words` × the band's
    :data:`COMPOSE_SECONDS_PER_WORD`), reading the character's answer as
    prose and sending it; once, the opening line and the objective, the
    normal feedback and the single repair. The authored envelope is a
    level-blind guess and no longer floors it. Without a band (legacy
    callers) the WP-03 envelope stands.

    The bottom-up model is reading the character line and the objective, one
    composition block per allowed turn, the normal feedback, and the single
    repair allowance. When the plan drops to one turn the authored envelope is
    reduced by exactly one composition block rather than discarded.

    Reading is priced with the measured ``spt``; everything the learner *does*
    is priced with the measured ``multiplier``. The two are never compounded on
    the same seconds, so a slow reader is not charged twice for the same line.
    """

    reading = _reading_seconds(spt, task.opening_line_fr, task.objective_native)
    reading += _playback_seconds(None, task.opening_line_fr)
    repair = REPAIR_ALLOWANCE_SECONDS if task.repair_allowed else 0
    if _band_key(band):
        unit_words = max(0, int(asks_unit or 0))

        def exchange(words: int) -> float:
            # The reply asks for a grammar unit («Emploi»/«Réemploi») in every
            # exchange: a learner who does what it asks writes one more sentence
            # that uses it, each time.
            words = min(REPLY_WORDS_CEILING + unit_words, words + unit_words)
            return (words * compose_seconds_per_word(band) + RESPOND_TURN_FIXED_SECONDS) * multiplier

        answer = RESPOND_REPLY_TOKENS * spt * page_reading_factor(band)
        default_turn = exchange(expected_reply_words(task, band)) + answer

        def card(labels_words: int) -> float:
            return labels_words * spt * page_reading_factor(band) + CHOICE_TAP_SECONDS * multiplier

        if authored:
            # An authored page says what each exchange asks: a card to tap, or
            # an answer the size of its own example (never under the band's
            # sentence: a learner's own answer is rarely shorter than the model's).
            costs = []
            for index in range(turns):
                kind, words = authored[index] if index < len(authored) else ("reply", 0)
                if kind == "card":
                    costs.append(card(words))
                else:
                    floor = REPLY_WORDS_FLOOR[_band_key(band) or "B1"]
                    costs.append(exchange(max(floor, words)) + answer)
        else:
            costs = [default_turn] * turns
            cards = [c for c in getattr(task, "opening_choices", None) or [] if isinstance(c, dict)]
            if cards and costs:
                # WP-113 «Le choix»: the first exchange is a card, read and tapped.
                costs[0] = card(sum(_tokens(str(c.get("label_fr") or "")) for c in cards))
        if task.repair_allowed:
            # The repair slot, when used, is one more exchange like the last.
            repair_cost = max(
                REPAIR_ALLOWANCE_SECONDS * multiplier,
                REPAIR_TURN_SHARE * (costs[-1] if costs else default_turn),
            )
        else:
            repair_cost = 0.0
        once = RESPOND_FEEDBACK_SECONDS * multiplier + repair_cost + reading
        return max(1, round(sum(costs) + once))
    fixed = RESPOND_TURN_SECONDS * turns + RESPOND_FEEDBACK_SECONDS + repair
    bottom_up = fixed * multiplier + reading
    envelope = float(task.estimated_seconds or 0)
    dropped = max(0, (task.max_turns or MAX_RESPOND_TURNS) - turns)
    envelope = max(0.0, envelope - RESPOND_TURN_SECONDS * dropped) * multiplier
    return max(1, round(max(envelope, bottom_up)))


def story_alone_seconds(scenario: ScenarioBrief, *, pace: PacingProfile | None = None) -> int:
    """WP-128: the story alone — the page, the reply at its minimum, the ending —
    at the band's prior. What an offer whose page is known costs at the least:
    above the rhythm, the day is a longer day before it is planned."""

    band = _band_key(scenario.level_band)
    profile = pace or PacingProfile()
    spt = profile.effective_seconds_per_token(band)
    multiplier = profile.effective_step_multiplier()
    task = scenario.response_task
    authored = authored_turns(scenario)
    turns = max(1, int(getattr(task, "min_turns", 0) or 0))
    outcome = default_outcome_key(scenario)
    ending = (
        resolution_seconds(scenario, outcome, spt=spt, multiplier=multiplier) if outcome else 0
    )
    return (
        scene_seconds(scenario, spt=spt, multiplier=multiplier, band=band)
        + respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier, band=band, authored=authored)
        + ending
    )


def reply_input_seconds(
    task: ResponseTask, *, turns: int, spt: float, band: str | None = None
) -> int:
    """WP-128: the French the reply makes the learner read — the opening line and
    each of the character's answers — which is input as much as a page is (WP-93's
    floor counts reading and listening). Zero for a caller that names no band,
    which keeps the WP-93 floor exactly."""

    if not _band_key(band):
        return 0
    tokens = _tokens(task.opening_line_fr) + RESPOND_REPLY_TOKENS * max(0, turns)
    return round(tokens * spt * page_reading_factor(band))


def resolution_seconds(
    scenario: ScenarioBrief, outcome_key: str, *, spt: float, multiplier: float
) -> int:
    """Reading the ending the learner earned, plus closing the day."""

    reading = _reading_seconds(
        spt,
        render_authored_text(scenario.resolution_lines.get(outcome_key)),
        render_authored_text(scenario.resolution_summaries.get(outcome_key)),
    )
    return max(1, round(RESOLUTION_BASE_SECONDS * multiplier + reading))


# --------------------------------------------------------------------------
# 4. The plan
# --------------------------------------------------------------------------


def target_reason(candidate: LearningCandidate) -> str | None:
    """Why this target is in today's plan, machine-readable, or None.

    WP-24. The only reason produced today is ``"erratum:<id>"`` (see
    :mod:`app.services.journey_errata`), but the field is deliberately a free
    string: a target chosen because a chapter needs it, or because the learner
    asked for it, will say so here without another contract change.
    """

    metadata = candidate.metadata or {}
    reason = str(metadata.get("target_reason") or "").strip()
    return reason or None


def merge_errata_candidates(
    candidates: list[LearningCandidate],
    errata_targets: list[ErrataTarget] | None,
) -> list[LearningCandidate]:
    """Put the learner's ranked errata in front of the day's other candidates.

    An erratum that is *also* in ``candidates`` (the same target, reached
    through the ordinary due queue) is replaced rather than duplicated, so the
    reason survives and the planner still sees exactly one candidate for it.
    """

    ranked = [target.as_candidate() for target in (errata_targets or [])]
    if not ranked:
        return list(candidates)
    identities = {target_identity(candidate.target) for candidate in ranked}
    rest = [
        candidate
        for candidate in candidates
        if target_identity(candidate.target) not in identities
    ]
    return [*ranked, *rest]


def plan_target_reasons(
    plan: PlannedJourney, candidates: list[LearningCandidate]
) -> dict[str, str]:
    """``{target identity: reason}`` for the targets the plan actually kept.

    The plan itself stores identities, not reasons — the wire contract forbids
    extra keys on the public prompts — so the reason is recovered from the same
    candidate list the plan was built from. Candidates that were offered and not
    kept are not in the answer: nothing is happening today because of them.
    """

    kept = set(plan.selected_target_ids)
    reasons: dict[str, str] = {}
    for candidate in candidates:
        identity = target_identity(candidate.target)
        reason = target_reason(candidate)
        if reason and identity in kept:
            reasons[identity] = reason
    return reasons


def plan_because(
    plan: PlannedJourney,
    candidates: list[LearningCandidate],
    errata_targets: list[ErrataTarget] | None = None,
) -> dict[str, Any] | None:
    """The day's because-line payload, or None when today owes nothing to a mistake.

    Structured — ``{"kind", "reason", "label", "example"}`` — never a rendered
    sentence: the French copy belongs beside the rest of the learner-facing copy
    in the component that prints it.
    """

    reasons = plan_target_reasons(plan, candidates)
    if not reasons:
        return None
    by_reason = {target.reason: target for target in (errata_targets or [])}
    for identity in plan.selected_target_ids:
        reason = reasons.get(identity)
        if not reason:
            continue
        target = by_reason.get(reason)
        if target is not None:
            return target.as_because()
    return None


# --------------------------------------------------------------------------
# WP-75 — the first day's recall, and the respond step that must not answer
# itself (walk L9)
# --------------------------------------------------------------------------

#: What the character says instead: an invitation to speak that carries no
#: content and no register, so it fits a tu scene and a vous scene alike.
SPOILER_SAFE_OPENING_FR = "Alors ?"


def guard_opening_line(task: ResponseTask) -> ResponseTask:
    """Refuse a respond opening line that speaks the objective's expected reply."""

    if line_spoils_reply(task.opening_line_fr, task.suggested_response_fr):
        return replace(task, opening_line_fr=SPOILER_SAFE_OPENING_FR)
    return task


def _scene_line_without_spoiler(scenario: ScenarioBrief) -> str | None:
    line = scenario.opening_line_fr
    if line_spoils_reply(line, scenario.response_task.suggested_response_fr):
        return None
    return line


def _first_day_recall(
    *,
    target: TargetRef,
    scenario: ScenarioBrief,
    affordances: list[str],
    optional: bool,
    position: int,
) -> RecallTask | None:
    """Choice first, then tiles: two different quick wins, neither typed.

    Tiles are posed by withholding the distractors — the legacy builder turns a
    glossed phrase into a choice whenever the scene offers two other phrases —
    and only for a phrase of two words or more, which is what tiles need.
    """

    if scenario.level_band in {"B1", "B2", "C1", "C2"}:
        return practice_task("short_answer", target=target, scenario=scenario,
            affordances=affordances, optional=optional, learner_text=None,
            pool=[], sentences=scene_sentences(scenario.setup_fr, scenario.opening_line_fr))
    if position % 2 and len((target.label_fr or "").split()) >= 2:
        tiles = build_recall_task(
            target=target, scenario=scenario, affordances=[], optional=optional
        )
        if tiles is not None and tiles.task_type == str(RecallFormat.TILES):
            return tiles
    return build_recall_task(
        target=target, scenario=scenario, affordances=affordances, optional=optional
    )


def plan_journey(
    *,
    scenario: ScenarioBrief,
    candidates: list[LearningCandidate],
    budget_seconds: int = DEFAULT_BUDGET_SECONDS,
    pace: PacingProfile | None = None,
    input_mode: InputMode = InputMode.TEXT,
    errata_targets: list[ErrataTarget] | None = None,
    day_shape: DayShape | str | None = None,
    shape_reason: str = "",
    dice: DayShapeInputs | None = None,
    letter: LetterOffer | None = None,
    chapter_recap_fr: str | None = None,
    audio_available: bool = False,
    first_day: bool = False,
    practice: bool = False,
    introduction: dict[str, Any] | None = None,
    forge: dict[str, Any] | None = None,
    reading: dict[str, Any] | list[dict[str, Any]] | None = None,
    desk: dict[str, Any] | None = None,
    page_review: list[dict[str, Any]] | None = None,
) -> PlannedJourney:
    """Build today's immutable plan.

    ``page_review`` (WP-129, content program D7) — on a tentpole day, the
    briefs of units the page uses that the learner met on an earlier day: one
    of them is reviewed after the ending, in a line of the page
    (:func:`page_review_step`). Never an introduction, never credited.

    ``desk`` («Le bureau», WP-121/122) is the one Revue desk today deals, as
    :func:`desk_offer` shapes it — ``{"desk": "relecture"|"radio"|"correcteur",
    "title_fr", "dossier_id", "relecture", "seconds"}``. Planned on a practice
    day only, as one optional step after the ending (before the «Lecture»),
    while the budget holds it; the day then gives up one ordinary recall item.
    Never on «jour du Papier», «jour court», a tentpole or the first day.

    WP-93 «Plus d'histoire, moins d'exercices»: the page is priced by what is
    on it (:func:`scene_seconds`), at least :data:`INPUT_FLOOR_SHARE` of a
    paged practice day's budget is kept for reading and listening, recall is
    capped per rhythm, and nothing sits between the scene's closing question
    and the reply (W5): warm-ups, the rule card, its guided items and the
    forge come before the scene; every other item comes after the reply.
    ``reading`` (Soutenu and Intensif) is today's «Lecture» offer, one page or
    a list — ``{"variant": "relecture"|"coulisses", "title_fr", "scene_id",
    "status", "audio_available", "texts_fr", "panel_count"}`` — planned as
    optional steps after the ending, up to the rhythm's ``max_reads``, while
    the budget holds them.

    ``forge`` (WP-S4) folds La Forge into a practice day (Soutenu and Intensif,
    owner decision 3): ``{"concept_id", "title_native", "title_fr",
    "reserve_seconds", "max_seconds"}``. The day keeps ``reserve_seconds`` free
    of quick items, and one «Forge» step — a hand-off to the forge block that
    returns to the day — is placed in the Scène movement, after the guided
    items and just before the reply, sized from what the day leaves (at most
    ``max_seconds``, at least :data:`FORGE_MIN_SECONDS`, else it is skipped).

    ``introduction`` (WP-L4) is today's new grammar unit, as a unit brief
    (:func:`app.services.grammar_units.unit_brief`). On a practice day it adds
    the «Règle» step (the unit's rule card, after the scene), three or four
    guided items built from the unit and the scene's lines, and the unit as
    the reply's grammar target. Everything else in the day shrinks to fit the
    same budget. Ignored on a first day and on a classic (non-practice) day.

    ``practice`` (WP-78) builds a *practice day*: quick recall items around the
    one open reply — warm-ups before the scene, one or two between the scene
    and the reply, one after it on a word from today. Off by default, so a
    caller that does not ask gets exactly the day it always got.

    ``first_day`` (WP-75) is the learner's very first day: the candidates are
    the authored scene's own words, every one of them new, so up to
    :data:`MAX_RECALL_STEPS` new anchors are kept (not one) and their recall
    steps are required rather than optional — a first day is a few quick wins
    before the reply, not a reply alone. The shape is always the standard day
    and formats are posed choice first, then tiles.

    ``input_mode`` is a coordination addition, not a contract change: the frozen
    :class:`ScenarioBrief` carries no modality and ``RespondPrompt.input_modes``
    has to say whether voice is on offer. Omitting it yields the safe answer —
    text only, which is always available.

    ``errata_targets`` (WP-24) are the learner's ranked due mistakes. Passed,
    they are merged in front of the other candidates and every step they reach
    is stamped with ``target_reason`` — which is what lets Home say the scene
    exists because of a mistake, and telemetry say which one. Omitted, the plan
    is exactly what it was before this package.

    ``day_shape`` and ``dice`` (WP-66) are the day's *kind* and the seed the
    recall formats are rotated with. Both are optional and both default to what
    this function did before the package: a standard day whose formats are
    chosen by the legacy preference order. Nothing about a plan built without
    them changes — which is also why a plan persisted before WP-66 still loads
    and still validates.
    """

    outcome_key = _require_plannable(scenario)
    if first_day:
        day_shape, dice, letter = DEFAULT_DAY_SHAPE, None, None
        shape_reason = "first_day"
    shape = DayShape(str(day_shape)) if day_shape else DEFAULT_DAY_SHAPE
    rule = day_shape_rule(shape)
    if letter is not None and not letter.is_renderable():
        letter = None
    if shape is DayShape.LETTER and letter is None:
        # The shape was dealt against a letter that is no longer there. A day
        # that promises a letter and shows none is the phantom loop, so the day
        # falls back to the shape that needs nothing extra.
        shape = DEFAULT_DAY_SHAPE
        rule = day_shape_rule(shape)
        shape_reason = "letter_withdrawn"
    if shape is DayShape.REVUE:
        # WP-119 phase 3: the Papier day's story part is the classic day — scene,
        # at most two recalls, the reply, the ending (five steps at most, inside
        # the budget). No practice items, rule, forge or «Lecture»: the player
        # mounts Le Papier after the ending, and the two together are the day.
        practice = False
        introduction = forge = reading = desk = None
    profile = pace or PacingProfile()
    # WP-128: the reading prior, the page's prose factor and the reply's
    # composition are the scene's band's.
    band = _band_key(scenario.level_band)
    spt = profile.effective_seconds_per_token(band)
    multiplier = profile.effective_step_multiplier()
    authored = authored_turns(scenario)
    notes: list[str] = []
    if pace is not None and not profile.is_trusted:
        notes.append(
            f"measured pace ignored: {profile.observations} observation(s), "
            f"{MIN_PACE_OBSERVATIONS} required"
        )
    if scenario.is_authored_fallback:
        notes.append("scene is the authored fallback; no serial episode was bound")

    # WP-78. Context cards for a matching/listen-and-tap item: words the learner
    # already owns, never a target of today (no evidence, no schedule).
    partners = [
        candidate.target
        for candidate in candidates
        if (candidate.metadata or {}).get("partner_only")
    ]
    candidates = [
        candidate for candidate in candidates if not (candidate.metadata or {}).get("partner_only")
    ]
    # WP-129: introduced units a B1+ day may practise in its free time — never a
    # reply obligation, so they stay out of the selection.
    practice_units = [
        candidate for candidate in candidates if (candidate.metadata or {}).get("practice_unit")
    ]
    candidates = [
        candidate for candidate in candidates if not (candidate.metadata or {}).get("practice_unit")
    ]
    candidates = merge_errata_candidates(candidates, errata_targets)
    if first_day:
        # WP-93 (W11): the taste already taught these; day 1 teaches new words.
        taste = {_fold(word) for word in TASTE_WORDS_FR}
        kept = [c for c in candidates if _fold(c.target.label_fr) not in taste]
        if len(kept) != len(candidates):
            notes.append(f"first day: {len(candidates) - len(kept)} taste word(s) not drilled again")
        candidates = kept
    reasons_by_identity = {
        target_identity(candidate.target): reason
        for candidate in candidates
        if (reason := target_reason(candidate))
    }
    selection = select_plan_targets(
        scenario,
        candidates,
        max_new=MAX_RECALL_STEPS if first_day else MAX_NEW_TARGETS,
    )
    affordances = _affordances_for(scenario)
    task = guard_opening_line(scenario.response_task)
    if task.opening_line_fr != scenario.response_task.opening_line_fr:
        notes.append("respond opening line replaced: it spoke the expected reply")

    # --- fit the non-removable core (scene, response, resolution) -----------
    turns = max(
        1,
        min(
            int(task.max_turns or MAX_RESPOND_TURNS),
            MAX_RESPOND_TURNS,
            rhythm_caps(budget_seconds).max_turns,
        ),
    )
    if first_day:
        # WP-75: the first reply is one turn (a repair is still allowed), so
        # the two quick recall wins fit in front of it inside five minutes.
        turns = 1
    # WP-113: an authored day's «Le choix» is never cut by the rhythm.
    turns = max(turns, int(getattr(task, "min_turns", 0) or 0))
    optional_turns = 0
    if practice and not first_day and band in LOW_BANDS and rhythm_caps(budget_seconds).budget_seconds <= 600:
        # WP-129 (owner decision): fewer reply exchanges, more practice items —
        # on Léger and Régulier, where the reply filled the day. Soutenu and
        # Intensif keep their four: a longer rhythm buys story and input
        # (WP-93), and their days had room for items already.
        core_turns = max(LOW_BAND_CORE_REPLY_TURNS, int(getattr(task, "min_turns", 0) or 0))
        if turns > core_turns:
            optional_turns = turns - core_turns
            turns = core_turns
            notes.append(
                f"core reply: {turns} exchange(s) at {band}; {optional_turns} more optional, "
                "not in the core estimate"
            )
    # WP-93: the page is heard as well as read when the deployment speaks —
    # priced from Régulier up; the five-minute day reads it (its audio is a
    # replay the learner may take, not a cost the day promises).
    scene_audio = bool(audio_available) and budget_seconds > RHYTHM_FIVE_MINUTES
    scene_cost = scene_seconds(
        scenario, spt=spt, multiplier=multiplier, audio=scene_audio, band=band
    )
    resolution_cost = resolution_seconds(scenario, outcome_key, spt=spt, multiplier=multiplier)
    respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier, band=band, authored=authored)
    min_turns = max(1, int(getattr(task, "min_turns", 0) or 0))
    while scene_cost + respond_cost + resolution_cost > budget_seconds and turns > min_turns:
        turns -= 1
        respond_cost = respond_seconds(
            task, turns=turns, spt=spt, multiplier=multiplier, band=band, authored=authored
        )
        notes.append("response reduced to one turn to keep the plan inside the budget")
    if scene_cost + respond_cost + resolution_cost > budget_seconds and scene_audio:
        # The lines' audio is a replay the learner may skip; a five-minute day
        # that cannot also hold it is priced as read.
        scene_audio = False
        scene_cost = scene_seconds(scenario, spt=spt, multiplier=multiplier, band=band)
        notes.append("scene priced without its audio to keep the plan inside the budget")
    if scene_cost + respond_cost + resolution_cost > budget_seconds and (
        spt > reading_prior(band) or multiplier > 1.0
    ):
        # A measured pace this slow cannot fit a scene that still has a real
        # ending. The plan stays whole and the estimate falls back to the base
        # pace rather than silently deleting the objective or the resolution.
        spt = reading_prior(band)
        multiplier = 1.0
        scene_cost = scene_seconds(
            scenario, spt=spt, multiplier=multiplier, audio=scene_audio, band=band
        )
        resolution_cost = resolution_seconds(scenario, outcome_key, spt=spt, multiplier=multiplier)
        respond_cost = respond_seconds(
            task, turns=turns, spt=spt, multiplier=multiplier, band=band, authored=authored
        )
        notes.append("measured pace set aside to the base pace: the core plan did not fit")
    longer_day = scene_cost + respond_cost + resolution_cost > budget_seconds
    if longer_day:
        # WP-128. Scene, response and resolution are not removable (CONTRACTS
        # §3), and a page is never cut. A page that cannot fit the rhythm even
        # at the band's prior is a *longer day*: planned as the story alone —
        # no practice, no rule, no forge, no «Lecture» — and flagged, so every
        # surface says the longer estimate before the learner starts. (It used
        # to refuse the day: `PlanUnavailable("scene_exceeds_budget")`.)
        notes.append(
            f"longer day: the story alone is {scene_cost + respond_cost + resolution_cost}s "
            f"against a {budget_seconds}s rhythm; nothing else is planned"
        )
        forge = reading = desk = None
        if introduction is None or first_day:
            # The new unit, when there is one, is kept (a deferral would hand
            # tomorrow the same unit again; a reprise would repeat forever):
            # the practice day plans the story and its rule, flagged.
            practice = False

    if practice and not first_day and practice_day_shape_rule(shape, budget_seconds).max_recall > 0:
        practice_plan = _plan_practice_day(
            scenario=scenario,
            task=task,
            outcome_key=outcome_key,
            candidates=candidates,
            selection=selection,
            affordances=affordances,
            reasons_by_identity=reasons_by_identity,
            shape=shape,
            shape_reason=shape_reason,
            dice=dice,
            letter=letter,
            chapter_recap_fr=chapter_recap_fr,
            audio_available=audio_available,
            input_mode=input_mode,
            budget_seconds=budget_seconds,
            turns=turns,
            spt=spt,
            multiplier=multiplier,
            scene_cost=scene_cost,
            resolution_cost=resolution_cost,
            notes=notes,
            partners=partners,
            introduction=introduction,
            forge=forge,
            reading=reading,
            scene_audio=scene_audio,
            desk=desk,
            band=band,
            story_longer=longer_day,
            practice_units=practice_units,
            page_review=page_review,
        )
        if practice_plan is not None:
            return practice_plan
        # WP-128: a longer story whose unit has no card to show: the story alone.

    # --- shape the recall steps inside whatever headroom is left -----------
    def shape_recalls(
        headroom: int,
    ) -> tuple[
        list[Any], list[SelectedTarget], list[LearningCandidate], dict[str, str], list[str]
    ]:
        notes: list[str] = []
        recalls: list[tuple[SelectedTarget, RecallTask, int, bool]] = []
        used_targets: list[SelectedTarget] = []
        dropped: list[LearningCandidate] = []
        reasons = dict(selection.omission_reasons)
        for entry in selection.selected:
            identity = target_identity(entry.target)
            # The shape may ask for fewer recall steps than the contract allows;
            # it may never ask for more.
            if len(recalls) >= min(rule.max_recall, MAX_RECALL_STEPS):
                # Still selected: it is elicited in the reply, it just gets no drill.
                used_targets.append(entry)
                if rule.max_recall == 0 and shape is DayShape.SHORT:
                    notes.append(f"{identity}: short day, no recall step")
                continue
            planned_real = sum(1 for _e, _t, _c, was_skipped in recalls if not was_skipped)
            optional = entry.demonstrated or entry.candidate.is_new or planned_real >= 1
            if first_day:
                optional = bool(entry.demonstrated)
            metadata = entry.candidate.metadata or {}
            learner_wording = metadata.get("erratum_learner") or metadata.get("original_text")
            if first_day:
                recall = _first_day_recall(
                    target=entry.target,
                    scenario=scenario,
                    affordances=affordances,
                    optional=optional,
                    position=len(recalls),
                )
            elif dice is None:
                recall = practice_task(
                    "short_answer", target=entry.target, scenario=scenario,
                    affordances=affordances, optional=optional, learner_text=learner_wording,
                    pool=[], sentences=scene_sentences(scenario.setup_fr, scenario.opening_line_fr),
                ) if scenario.level_band in {"B1", "B2", "C1", "C2"} else build_recall_task(
                    target=entry.target,
                    scenario=scenario,
                    affordances=affordances,
                    optional=optional,
                    learner_text=learner_wording,
                )
                if recall is not None and not shape_allows_format(shape, recall.task_type):
                    recall = None
            else:
                formats = rotate_recall_formats(
                    inputs=dice,
                    shape=shape,
                    target_kind=str(entry.target.kind),
                    target_id=identity,
                    eligible=("short_answer", "transform", "word_bank", "tiles") if scenario.level_band in {"B1", "B2", "C1", "C2"} else CLASSIC_RECALL_FORMATS,
                )
                recall = build_rotated_recall_task(
                    target=entry.target,
                    scenario=scenario,
                    affordances=affordances,
                    optional=optional,
                    formats=formats,
                    day_shape=shape,
                    learner_text=learner_wording,
                )
            if recall is None:
                used_targets.append(entry)
                notes.append(f"{identity}: no recall form could be posed without revealing it")
                continue
            if entry.demonstrated:
                recalls.append((entry, recall, 0, True))
                used_targets.append(entry)
                notes.append(f"{identity}: already produced independently, recall step skipped")
                continue
            cost = recall_seconds(recall, spt=spt, multiplier=multiplier)
            if cost > headroom:
                dropped.append(entry.candidate)
                reasons[identity] = "no_budget_headroom"
                continue
            headroom -= cost
            recalls.append((entry, recall, cost, False))
            used_targets.append(entry)
        return recalls, used_targets, dropped, reasons, notes

    recalls, used_targets, dropped, reasons, recall_notes = shape_recalls(
        budget_seconds - (scene_cost + respond_cost + resolution_cost)
    )
    if (
        not first_day
        and not longer_day
        and turns > 1
        and dropped
        and not any(not skipped for _e, _t, _c, skipped in recalls)
    ):
        # WP-93: a page priced by its panels can leave a five-minute day no
        # room for a single recall; the reply gives up its second turn (it
        # keeps its repair) — the trade WP-75 made for day one.
        shorter = respond_seconds(
            task, turns=turns - 1, spt=spt, multiplier=multiplier, band=band, authored=authored
        )
        retry = shape_recalls(budget_seconds - (scene_cost + shorter + resolution_cost))
        if any(not skipped for _e, _t, _c, skipped in retry[0]):
            turns, respond_cost = turns - 1, shorter
            recalls, used_targets, dropped, reasons, recall_notes = retry
            recall_notes.append("reply reduced to one turn so a recall step fits the budget")
    notes.extend(recall_notes)

    # WP-66. A shape that needs a recall step and could not get one is not a
    # failure and is certainly not a reason to refuse the learner's day: the
    # day is simply standard today, and the rationale says why. The shape is
    # downgraded *before* the steps are built, so `validate()` never has to
    # reject a plan this function produced.
    if len(recalls) < rule.min_recall:
        notes.append(
            f"{shape} day downgraded to {DEFAULT_DAY_SHAPE}: "
            f"{len(recalls)} recall step(s), {rule.min_recall} required"
        )
        shape = DEFAULT_DAY_SHAPE
        rule = day_shape_rule(shape)
        shape_reason = "shape_needs_a_recall_step"

    # --- assemble ----------------------------------------------------------
    # WP-24: which of today's kept targets is here because of a past mistake.
    # The first one in planner order is the day's reason; a scene rarely carries
    # two, and Home has room for one line.
    # The public step prompts are a frozen wire contract that forbids extra
    # keys (`JourneyModel`, extra="forbid"), so the reason is NOT smuggled into
    # them. It travels in the plan's rationale for operators and telemetry, and
    # `plan_target_reasons` / `plan_because` hand the structured form to whoever
    # builds the learner's envelope.
    primary_reason = next(
        (
            reason
            for reason in (
                reasons_by_identity.get(target_identity(entry.target)) for entry in used_targets
            )
            if reason
        ),
        None,
    )
    if primary_reason:
        notes.append(f"today's targets include {primary_reason}")

    steps: list[PlannedStep] = []
    ordinal = 0
    steps.append(
        PlannedStep(
            ordinal=ordinal,
            kind=StepKind.SCENE,
            estimated_seconds=scene_cost,
            public_prompt={
                "setup_fr": scenario.setup_fr,
                "setup_native": scenario.setup_native,
                "objective_native": scenario.objective_native,
                "character_line_fr": _scene_line_without_spoiler(scenario),
                "character_line_audio_url": None,
                "image_url": scenario.image_url,
                # WP-66 «jour d'écoute»: the scene is heard before it is read.
                # Claimed only when this deployment can actually speak it —
                # `audio_available` is read at plan time and re-read at
                # projection time, so a flag flipped off later still wins.
                "listen_first": bool(shape is DayShape.LISTENING and audio_available),
                # An authored scene's graphic-novel page; absent when it has none.
                **({"panels": [dict(panel) for panel in scenario.panels]} if scenario.panels else {}),
            },
            private_task=None,
            target=None,
            optional=False,
            initial_status=StepStatus.PENDING,
        )
    )
    ordinal += 1
    # WP-93 (W5): the first day's page ends on Margaux's question and the
    # reply answers it next; its recall comes back after the reply. The
    # classic non-first day is the pre-WP-78 kill switch (the practice-day
    # flag off) and keeps its old order.
    recall_steps: list[PlannedStep] = []
    for entry, recall, cost, skipped in recalls:
        recall_steps.append(
            PlannedStep(
                ordinal=0,
                kind=StepKind.RECALL,
                estimated_seconds=cost,
                public_prompt={
                    "task_type": recall.task_type,
                    "instruction_native": recall.instruction_native,
                    "prompt_fr": recall.prompt_fr,
                    "options": [dict(option) for option in recall.options],
                    "target": public_recall_target(recall.target),
                    "optional": recall.optional,
                    "help_available": _recall_help(recall),
                    # WP-103 T3: what to produce, and what it starts from.
                    "goal_native": recall.goal_native,
                    "source_fr": recall.source_fr,
                    **recall_met(entry.candidate),
                },
                private_task=replace(recall, estimated_seconds=cost),
                target=entry.target,
                optional=recall.optional,
                initial_status=StepStatus.SKIPPED if skipped else StepStatus.PENDING,
            )
        )

    if not first_day:
        for recall_step in recall_steps:
            steps.append(replace(recall_step, ordinal=ordinal))
            ordinal += 1

    elicited = [entry.target for entry in used_targets if entry.is_elicitable]
    respond_task = replace(
        task,
        max_turns=turns,
        targets=list(elicited),
        estimated_seconds=respond_cost,
    )
    steps.append(
        PlannedStep(
            ordinal=ordinal,
            kind=StepKind.RESPOND,
            estimated_seconds=respond_cost,
            public_prompt={
                "turn_index": 0,
                "max_turns": turns,
                "repair_allowed": bool(task.repair_allowed),
                "character_id": task.character_id,
                "character_name": task.character_name,
                "character_line_fr": task.opening_line_fr,
                "character_line_audio_url": None,
                "objective_native": task.objective_native,
                "input_modes": supported_input_modes(scenario, input_mode=input_mode),
                "targets": [target.as_public() for target in elicited],
                "help_available": _respond_help(task),
                # WP-66 «jour de lettre». `None` on every other shape, which is
                # every day until WP-64 registers a letter provider.
                "letter": _letter_prompt(letter) if shape is DayShape.LETTER else None,
                # WP-113: the opening question is «Le choix»: its cards.
                "choices": list(getattr(task, "opening_choices", None) or []),
            },
            private_task=respond_task,
            target=None,
            optional=False,
            initial_status=StepStatus.PENDING,
        )
    )
    ordinal += 1
    if first_day and recall_steps:
        # WP-93 walk (2026-09-29): the day-1 words («au comptoir», «à emporter»)
        # are what the reply asks for, so a beginner meets them *before* the
        # page, as warm-ups — never between Margaux's question and the answer
        # (W5), and not after the reply that needed them.
        steps = [
            replace(step, ordinal=index)
            for index, step in enumerate([*recall_steps, *steps])
        ]
        ordinal = len(steps)
    steps.append(
        PlannedStep(
            ordinal=ordinal,
            kind=StepKind.RESOLUTION,
            estimated_seconds=resolution_cost,
            public_prompt={
                "outcome_key": outcome_key,
                # The plan is built before the learner has spoken, so the ending
                # is rendered with no learner detail at all: every authored slot
                # falls back to wording that claims no drink and no day. WP-06
                # re-renders it with the real choice once the turn is graded.
                "character_line_fr": render_authored_text(
                    scenario.resolution_lines.get(outcome_key, "")
                ),
                "summary_native": render_authored_text(
                    scenario.resolution_summaries.get(outcome_key, "")
                ),
                "image_url": scenario.image_url,
                # WP-66 «jour de reprise»: the chapter that just closed, in one
                # French paragraph. `None` on every other shape, and `None`
                # here too when the story had no recap to give — an empty
                # recap block is worse than no recap block.
                "chapter_recap_fr": (
                    (chapter_recap_fr or "").strip() or None
                    if shape is DayShape.REPRISE
                    else None
                ),
                # WP-66 / WP-33: filled in by WP-02 once the respond turns have
                # actually been graded. The plan cannot know it: nobody has
                # spoken yet.
                "register_note_fr": None,
                "register_reason_native": None,
            },
            private_task=None,
            target=None,
            optional=False,
            initial_status=StepStatus.PENDING,
        )
    )

    omitted = [*selection.omitted, *dropped]
    rationale = _rationale(
        selected=used_targets,
        recalls=recalls,
        omitted=omitted,
        reasons=reasons,
        candidates=candidates,
        notes=notes,
    )
    plan = PlannedJourney(
        scenario=scenario,
        steps=steps,
        estimated_active_seconds=sum(step.estimated_seconds for step in steps),
        budget_seconds=budget_seconds,
        selected_target_ids=[target_identity(entry.target) for entry in used_targets],
        omitted_candidate_ids=[target_identity(item.target) for item in omitted],
        rationale=rationale,
        day_shape=shape,
        shape_reason=shape_reason,
        longer_day=longer_day,
    )
    plan.validate()
    if len(plan.steps) > MAX_PLANNED_STEPS:  # pragma: no cover - validate() already raises
        raise PlanUnavailable("plan_exceeds_step_budget")
    return plan


# --------------------------------------------------------------------------
# 5. WP-78 — the practice day
# --------------------------------------------------------------------------

#: Which formats each position of a practice day tries, in preference order.
#: Warm-ups are recognition (the scene has not been read yet); between the scene
#: and the reply the learner builds; after the reply one word from today comes
#: back, produced if it can be.
PRACTICE_SLOT_FORMATS: dict[str, tuple[str, ...]] = {
    "warmup": (
        str(RecallFormat.MATCH_PAIRS),
        str(RecallFormat.LISTEN_TAP),
        str(RecallFormat.CLASSIFY),
        str(RecallFormat.CHOICE),
    ),
    "mid": (
        str(RecallFormat.UNSCRAMBLE),
        str(RecallFormat.WORD_BANK),
        str(RecallFormat.TILES),
        str(RecallFormat.TRANSFORM),
        str(RecallFormat.SHORT_ANSWER),
        str(RecallFormat.LISTEN_TAP),
    ),
    "post": (
        str(RecallFormat.SHORT_ANSWER),
        str(RecallFormat.TILES),
        str(RecallFormat.WORD_BANK),
        str(RecallFormat.UNSCRAMBLE),
        str(RecallFormat.LISTEN_TAP),
        str(RecallFormat.CLASSIFY),
        str(RecallFormat.CHOICE),
    ),
}
#: The order positions are *filled* in, so a tight budget still gets one of
#: each (a warm-up, a build, a word from today) before it gets a second warm-up.
PRACTICE_FILL_ORDER: tuple[tuple[str, int], ...] = (
    ("warmup", 0),
    ("mid", 0),
    ("post", 0),
    ("warmup", 1),
    ("mid", 1),
    ("warmup", 2),
)
#: «Jour d'écoute»: the scene is heard first, so nothing is posed before it.
LISTENING_FILL_ORDER: tuple[tuple[str, int], ...] = (
    ("mid", 0),
    ("post", 0),
    ("mid", 1),
    ("mid", 2),
    ("mid", 3),
)


def practice_fill_order(
    caps: RhythmCaps | None = None, *, listening: bool = False
) -> tuple[tuple[str, int], ...]:
    """WP-L6 — the order a day's positions are filled in, at its rhythm.

    The five-minute rhythm is exactly :data:`PRACTICE_FILL_ORDER` (or
    :data:`LISTENING_FILL_ORDER`). A longer rhythm continues past it, always
    taking the slot with the most room left in proportion — so a tight budget
    still gets a warm-up, a build and a word from today before any second
    helping, and a generous one grows the Rappel and the Scène together.
    """

    caps = caps or rhythm_caps(None)
    base = LISTENING_FILL_ORDER if listening else PRACTICE_FILL_ORDER
    if caps.budget_seconds <= RHYTHM_FIVE_MINUTES:
        return base
    limits = {
        # A listening day hears the scene first: nothing before it.
        "warmup": 0 if listening else caps.max_warmups,
        "mid": caps.max_mid,
        "post": caps.max_post,
    }
    placed = dict.fromkeys(limits, 0)
    order: list[tuple[str, int]] = []
    for slot, _position in base:
        if placed[slot] < limits[slot]:
            order.append((slot, placed[slot]))
            placed[slot] += 1
    while True:
        room = {
            slot: (limits[slot] - placed[slot]) / limits[slot]
            for slot in limits
            if limits[slot] and placed[slot] < limits[slot]
        }
        if not room:
            break
        slot = max(room, key=lambda name: (room[name], -("warmup", "mid", "post").index(name)))
        order.append((slot, placed[slot]))
        placed[slot] += 1
    return tuple(order)


@dataclass(frozen=True, slots=True)
class PracticeItem:
    """One quick item placed on a practice day."""

    slot: str
    position: int
    entry: SelectedTarget
    task: RecallTask
    cost: int
    #: WP-91. The clip a listening item carries (``RecallPrompt.audio_url``);
    #: ``None`` when the deployment does not speak.
    audio_url: str | None = None


def _kept(candidate: LearningCandidate) -> bool:
    return bool((candidate.metadata or {}).get("kept"))


def practice_entries(
    scenario: ScenarioBrief,
    selection: TargetSelection,
    affordances: list[str],
) -> list[SelectedTarget]:
    """Every target today may practise, best first.

    The selected targets (the reply's obligations) first, then the rest of the
    ranked queue the selection cap left out — a practice day has room to *see*
    more words than it can ask the learner to say. A word the learner kept from
    a story (tap-to-keep) leads, because keeping it was asking to see it again.
    A target already produced independently is not drilled.
    """

    entries = list(selection.selected)
    seen = {target_identity(entry.target) for entry in entries}
    for candidate in selection.omitted:
        identity = target_identity(candidate.target)
        if identity in seen:
            continue
        seen.add(identity)
        entries.append(
            SelectedTarget(
                candidate=candidate,
                fit=scenario_fit(candidate.target, affordances, scenario),
                demonstrated=candidate_is_demonstrated(candidate),
            )
        )
    ranked = [entry for entry in entries if not entry.demonstrated]
    return sorted(
        ranked, key=lambda entry: (0 if _kept(entry.candidate) else 1, ranked.index(entry))
    )


def practice_task(
    task_type: str,
    *,
    target: TargetRef,
    scenario: ScenarioBrief,
    affordances: list[str],
    optional: bool,
    learner_text: str | None,
    pool: list[TargetRef],
    sentences: list[str],
) -> RecallTask | None:
    """One quick item in one named format, or ``None``.

    Two formats are posed more directly than the legacy builder poses them,
    because on a practice day the format is *chosen* rather than inferred from
    what the scene affords: tiles are tiles even when the scene could have
    offered a multiple choice (the distractors are withheld, as on day one),
    and a glossed word may be asked for in writing whatever its length.
    """

    if task_type == "short_answer" and scenario.level_band in {"B1", "B2", "C1", "C2"} and _glossed(target) is None:
        label = target.label_fr.strip()
        for sentence in sentences:
            match = re.search(r"(?<!\w)" + re.escape(label) + r"(?!\w)", sentence, re.IGNORECASE)
            if match and 3 <= len(sentence.split()) <= 22:
                prompt = sentence[:match.start()] + "…" + sentence[match.end():]
                return RecallTask(
                    task_type="short_answer", instruction_native="Complétez la phrase de la scène.",
                    prompt_fr=prompt, options=[], target=target, optional=optional,
                    accepted_answers=[label], solution_fr=label, estimated_seconds=0,
                    goal_native="Écrivez les mots manquants.", source_fr=prompt,
                )
        return None
    if task_type == str(RecallFormat.TILES) and target.kind is not TargetKind.ERROR:
        tiles = build_recall_task(
            target=target, scenario=scenario, affordances=[], optional=optional
        )
        return tiles if tiles is not None and tiles.task_type == task_type else None
    if task_type == str(RecallFormat.SHORT_ANSWER) and _glossed(target) is not None:
        label = target.label_fr.strip()
        return RecallTask(
            task_type="short_answer",
            instruction_native=_localized(
                _SHORT_ANSWER_INSTRUCTION, scenario.control_language
            ).format(native=_glossed(target)),
            prompt_fr=None,
            options=[],
            target=target,
            optional=optional,
            accepted_answers=[label],
            hint_native=_hint_for(target, scenario.control_language),
            translation_native=None,
            solution_fr=label,
            estimated_seconds=0,
        )
    return build_recall_task_in_format(
        task_type,
        target=target,
        scenario=scenario,
        affordances=affordances,
        optional=optional,
        learner_text=learner_text,
        pool=pool,
        sentences=sentences,
    )


_RECOGNITION_FORMATS = frozenset({"choice", "classify", "match_pairs", "listen_tap", "who_said"})
_PRODUCTION_FORMATS = frozenset({"short_answer", "transform"})


def _vocabulary_rung(entry: SelectedTarget, band: str) -> str | None:
    """WP-115b: the recall ladder's rung for a vocabulary target of the day."""

    if entry.target.kind is not TargetKind.VOCABULARY or entry.candidate.is_new:
        return None
    metadata = entry.candidate.metadata or {}
    try:
        stability = float(metadata.get("stability"))
    except (TypeError, ValueError):
        return None
    from app.services.recall_ladder import rung

    return rung(stability=stability, reps=1, lapses=None, level=band, has_example=False)


def _slot_formats(
    slot: str,
    *,
    shape: DayShape,
    dice: DayShapeInputs | None,
    identity: str,
    used_today: dict[str, int],
    used_by_target: set[str],
    learner_band: str = "A1",
    recognition_used: int = 0,
    rung: str | None = None,
    new_word: bool = False,
) -> list[str]:
    declared = PRACTICE_SLOT_FORMATS[slot]
    if new_word and slot == "warmup":
        # EXPERIENCE-REVIEW 2026-10-04: a beginner's first item ever was «Maskulin
        # oder feminin? clé» — the gender of a word not met yet, a pure guess. Before
        # the scene, a new word is only met by its meaning.
        declared = tuple(task for task in declared if task != str(RecallFormat.CLASSIFY))
    if learner_band in {"B1", "B2", "C1", "C2"}:
        # One recognition warm-up at most. The rest asks the learner to produce.
        declared = ("transform", "short_answer")
        if slot == "warmup" and recognition_used == 0:
            declared = ("choice", *declared)
    allowed = [
        task_type
        for task_type in declared
        if shape_allows_format(shape, task_type) and task_type not in used_by_target
    ]

    def ladder(task_type: str) -> int:
        """WP-115b: a word still fragile is recognised first; a word held long enough
        is produced first. Unknown memory (grammar, a new word) keeps the old order."""

        if rung == "recognition":
            return 0 if task_type in _RECOGNITION_FORMATS else 1
        if rung in {"production", "audio", "cloze"}:
            return 0 if task_type in _PRODUCTION_FORMATS else 1
        return 0

    def key(task_type: str) -> tuple[int, int, str]:
        tie = (
            _digest(*dice.seed_parts, identity, slot, task_type)
            if dice is not None
            else f"{declared.index(task_type):04d}"
        )
        return (ladder(task_type), used_today.get(task_type, 0), tie)

    return sorted(allowed, key=key)


#: The day's item blocks as the learner meets them: the warm-ups before the scene,
#: and everything after it («mid» and «post» end up side by side after the ending).
_BLOCK_OF: dict[str, str] = {"warmup": "before", "mid": "after", "post": "after"}
#: Formats that ask for French to be produced from memory.
_PRODUCTION_FORMATS = frozenset({"short_answer", "transform", "dictation"})


def _task_face(task: RecallTask) -> tuple[str, ...]:
    """What the learner sees of an item, folded: two items with one face are one item."""

    cards = sorted(_fold(str(option.get("text_fr") or "")) for option in task.options or [])
    return (
        str(task.task_type),
        _fold(task.instruction_native),
        _fold(task.prompt_fr),
        _fold(task.goal_native),
        "|".join(cards),
    )


#: WP-129: two grids that share this many French cards are one grid twice
#: (EXPERIENCE-REVIEW F-14: «vendredi/pas/chose/lettre», then «chose/lettre/pas/votre»).
GRID_OVERLAP_CARDS = 2


def _french_cards(task: RecallTask) -> set[str]:
    return {
        _fold(str(option.get("text_fr") or ""))
        for option in task.options or []
        if option.get("side") != "native" and str(option.get("text_fr") or "").strip()
    }


def overlaps_the_day(task: RecallTask, tasks: list[RecallTask], avoid: set[str] | frozenset[str] = frozenset()) -> bool:
    """WP-129: does ``task`` materially repeat an item already in the day?

    Two items on one sentence (the line one prints to work on, or its answer:
    :func:`grammar_items.item_sentences`) — Wave 1 posed two Rappels for two
    units on «Tu as une minute ?» — or two matching grids that share
    :data:`GRID_OVERLAP_CARDS` French cards. ``avoid`` is sentences the day
    already holds outside ``tasks`` (the rule's guided items).
    """

    own = grammar_items.item_sentences(task)
    if own & set(avoid):
        return True
    cards = _french_cards(task) if task.task_type == "match_pairs" else set()
    for other in tasks:
        if own & grammar_items.item_sentences(other):
            return True
        if cards and other.task_type == "match_pairs" and len(cards & _french_cards(other)) >= GRID_OVERLAP_CARDS:
            return True
    return False


def _repeats_the_day(
    task: RecallTask, entry: SelectedTarget, items: list[PracticeItem], *, slot: str | None = None,
    avoid: set[str] | frozenset[str] = frozenset(),
) -> bool:
    """EXERCISE-QA (learner walk): never the same item twice in a day — two
    «match the pairs» over the same four words differ only in which pair is
    graded — and never ask to *produce* a word in the same block as an item that
    puts it on the screen (that is copying, not recall; the scene between two
    blocks is the spacing that makes the second one a retrieval). WP-129: nor
    an item that materially overlaps one already placed (:func:`overlaps_the_day`)."""

    face = _task_face(task)
    if any(_task_face(item.task) == face for item in items):
        return True
    if overlaps_the_day(task, [item.task for item in items], avoid):
        return True
    identity = target_identity(entry.target)
    block = _BLOCK_OF.get(str(slot), str(slot)) if slot is not None else None
    for item in items:
        if block is not None and _BLOCK_OF.get(item.slot, item.slot) != block:
            continue
        if target_identity(item.entry.target) != identity:
            continue
        if task.task_type in _PRODUCTION_FORMATS or item.task.task_type in _PRODUCTION_FORMATS:
            return True
    return False


def fill_practice_items(
    *,
    scenario: ScenarioBrief,
    shape: DayShape,
    entries: list[SelectedTarget],
    affordances: list[str],
    sentences: list[str],
    safe_sentences: list[str],
    dice: DayShapeInputs | None,
    headroom: int,
    spt: float,
    multiplier: float,
    max_items: int | None = None,
    partners: list[TargetRef] | tuple[TargetRef, ...] = (),
    caps: RhythmCaps | None = None,
    avoid_sentences: set[str] | frozenset[str] = frozenset(),
) -> list[PracticeItem]:
    """Place the day's quick items inside ``headroom`` seconds.

    WP-129: ``avoid_sentences`` — sentences the day already holds (the rule's
    guided items); no item repeats one, nor one placed here.

    Deterministic: the same inputs place the same items. A target comes back
    at most :data:`PRACTICE_MAX_USES_PER_TARGET` times and never twice in the
    same format; across the day the least-used format is tried first, so a day
    is a mix and not five matching grids.
    """

    pool = [entry.target for entry in entries if _glossed(entry.target) is not None]
    pool.extend(target for target in partners if _glossed(target) is not None)
    caps = caps or rhythm_caps(None)
    order = practice_fill_order(caps, listening=shape is DayShape.LISTENING)
    rule = practice_day_shape_rule(shape, caps.budget_seconds)
    cap = min(caps.max_recall if max_items is None else max_items, rule.max_recall, caps.max_recall)
    max_uses = caps.uses_per_target
    items: list[PracticeItem] = []
    uses: dict[str, int] = {}
    formats_by_target: dict[str, set[str]] = {}
    used_today: dict[str, int] = {}
    in_scene = {
        target_identity(entry.target)
        for entry in entries
        if any(_contains_label(sentence, entry.target.label_fr or "") for sentence in sentences)
    }

    def today_rank(entry: SelectedTarget) -> int:
        identity = target_identity(entry.target)
        if entry.candidate.is_new or _kept(entry.candidate) or identity in in_scene:
            return 0
        return 1 if uses.get(identity) else 2

    day_key = "|".join(dice.seed_parts) if dice is not None else ""
    for slot, position in order:
        if len(items) >= cap:
            break
        if slot == "warmup" and position >= caps.max_warmups:
            continue
        ranked = [
            entry
            for entry in entries
            if uses.get(target_identity(entry.target), 0) < max_uses
        ]
        # WP-L4 «Rappel»: a due grammar unit is one interleaved warm-up, posed
        # in the format its stability calls for (grammar_items.review_item).
        grammar_placed: PracticeItem | None = None
        if slot == "warmup":
            for entry in ranked:
                brief = (entry.candidate.metadata or {}).get("grammar_brief")
                if entry.target.kind is not TargetKind.GRAMMAR or not isinstance(brief, dict):
                    continue
                if uses.get(target_identity(entry.target)):
                    continue
                held = set(avoid_sentences)
                for item in items:
                    held |= grammar_items.item_sentences(item.task)
                task = grammar_items.review_item(
                    {**brief, "level": scenario.level_band},
                    sentences=list(safe_sentences),
                    language=scenario.control_language,
                    day_key=day_key,
                    meanings=line_meanings(scenario),
                    avoid=held,
                )
                if task is None and grammar_items.review_band(brief.get("stability")) == "high":
                    # WP-94: past 10 days of stability the Rappel is the coach's
                    # mini-scene — free use elicited, not hoped for in the reply.
                    # Built by the learning adapter (``coach_scene`` on the brief).
                    task = _coach_scene_task(brief)
                if task is None or not shape_allows_format(shape, task.task_type):
                    continue
                if overlaps_the_day(task, [item.task for item in items], avoid_sentences):
                    continue
                if grammar_uses(items) >= 1 and _same_concept_last(items, entry.target):
                    continue
                cost = grammar_item_seconds(task, spt=spt, multiplier=multiplier)
                if cost > headroom:
                    continue
                grammar_placed = PracticeItem(
                    slot=slot, position=position, entry=entry, task=task, cost=cost
                )
                break
        if grammar_placed is not None:
            identity = target_identity(grammar_placed.entry.target)
            headroom -= grammar_placed.cost
            # One item per unit per day: the Rappel interleaves, it does not drill.
            uses[identity] = max_uses
            used_today[grammar_placed.task.task_type] = (
                used_today.get(grammar_placed.task.task_type, 0) + 1
            )
            items.append(grammar_placed)
            continue
        ranked = [entry for entry in ranked if entry.target.kind is not TargetKind.GRAMMAR]
        if slot == "post":
            ranked.sort(key=lambda entry: (today_rank(entry), entries.index(entry)))
        else:
            ranked.sort(
                key=lambda entry: (uses.get(target_identity(entry.target), 0), entries.index(entry))
            )
        placed: PracticeItem | None = None
        for entry in ranked:
            identity = target_identity(entry.target)
            metadata = entry.candidate.metadata or {}
            learner_wording = metadata.get("erratum_learner") or metadata.get("original_text")
            kept_example = str(metadata.get("example_fr") or "").strip()
            readable = list(sentences if slot == "post" else safe_sentences)
            if kept_example:
                readable.append(kept_example)
            for task_type in _slot_formats(
                slot,
                shape=shape,
                dice=dice,
                identity=identity,
                used_today=used_today,
                used_by_target=formats_by_target.get(identity, set()),
                learner_band=scenario.level_band,
                recognition_used=1 if caps.budget_seconds == 300 else sum(item.task.task_type in {"choice", "classify", "match_pairs", "listen_tap", "who_said"} for item in items),
                rung=_vocabulary_rung(entry, str(scenario.level_band or "A1")),
                new_word=bool(entry.candidate.is_new) and entry.target.kind is TargetKind.VOCABULARY,
            ):
                task = practice_task(
                    task_type,
                    target=entry.target,
                    scenario=scenario,
                    affordances=affordances,
                    optional=bool(entry.candidate.is_new),
                    learner_text=learner_wording,
                    pool=pool,
                    sentences=readable,
                )
                if task is None:
                    continue
                if _repeats_the_day(task, entry, items, slot=slot, avoid=avoid_sentences):
                    continue
                cost = quick_recall_seconds(task, spt=spt, multiplier=multiplier)
                if cost > headroom:
                    continue
                placed = PracticeItem(slot=slot, position=position, entry=entry, task=task, cost=cost)
                break
            if placed is not None:
                break
        if placed is None:
            continue
        identity = target_identity(placed.entry.target)
        headroom -= placed.cost
        uses[identity] = uses.get(identity, 0) + 1
        formats_by_target.setdefault(identity, set()).add(placed.task.task_type)
        used_today[placed.task.task_type] = used_today.get(placed.task.task_type, 0) + 1
        items.append(placed)
    return items


# ---------------------------------------------------------------------------
# WP-129 — practice that fills a B1+ day: mixed units, contrasts, free sentences
# ---------------------------------------------------------------------------

#: The bands whose practice is production and mixed-unit (the chrome is French).
ADVANCED_BANDS = frozenset({"B1", "B2", "C1", "C2"})
#: WP-129 (owner decision 4): a B1+ day's practice items at each rhythm, the
#: rule's guided items included. A *ceiling* the seconds, the learner's
#: introduced units and each item's quality decide under — never a count to
#: meet: an item that cannot be posed honestly is not posed.
ADVANCED_ITEM_TARGET: dict[int, int] = {300: 5, 600: 9, 1200: 12, 1800: 14}
#: How often one unit comes back in this fill (never twice in one format).
ADVANCED_ITEMS_PER_UNIT = 2
#: The fill's formats: a contrast between two introduced partner units, a
#: repair (✗ → ✓) and a free sentence of the learner's own.
ADVANCED_FORMATS: tuple[str, ...] = ("contrast", "transform", "free")


def _unit_brief(entry: SelectedTarget) -> dict[str, Any] | None:
    brief = (entry.candidate.metadata or {}).get("grammar_brief")
    return brief if isinstance(brief, dict) and brief.get("concept_id") is not None else None


def _advanced_task(
    fmt: str,
    brief: dict[str, Any],
    *,
    partners: list[dict[str, Any]],
    language: ControlLanguage,
    day_key: str,
    avoid: set[str],
    level_ok: set[str] | None = None,
) -> RecallTask | None:
    def fits(text: str) -> bool:
        # WP-129: the learning adapter lists each unit's sentences at the
        # learner's level (``level_ok_fr``); without the list, all of them.
        return level_ok is None or grammar_items._fold(grammar_items.plain(text)) in level_ok

    if fmt == "contrast":
        for partner in partners:
            task = grammar_items.contrast_item(
                brief, partner, language=language, day_key=day_key, avoid=avoid, fits=fits
            )
            if task is not None:
                return task
        return None
    if fmt == "transform":
        pairs = list(brief.get("contrast_pairs") or [])
        pairs.sort(key=lambda pair: _digest(day_key, str(brief.get("concept_id")), str(pair.get("wrong"))))
        for pair in pairs:
            task = grammar_items.transform_item(
                {**brief, "contrast_pairs": [pair]}, language=language, review=True
            )
            if (
                task is not None
                and not (grammar_items.item_sentences(task) & avoid)
                and fits(str(task.solution_fr or ""))
            ):
                return task
        return None
    if fmt == "free":
        return grammar_items.free_sentence_item(brief, language=language, avoid=avoid, fits=fits)
    return None


def is_interleaved_item(item: PracticeItem, intro_identity: str | None) -> bool:
    """WP-129: a grammar item on a unit other than today's new one — practice
    of an earlier unit mixed into the day (a contrast is one by construction)."""

    return item.entry.target.kind is TargetKind.GRAMMAR and target_identity(item.entry.target) != intro_identity


def fill_advanced_practice(
    *,
    scenario: ScenarioBrief,
    shape: DayShape,
    units: list[SelectedTarget],
    items: list[PracticeItem],
    headroom: int,
    spt: float,
    multiplier: float,
    caps: RhythmCaps,
    max_items: int | None = None,
    reserved: int = 0,
    avoid_sentences: set[str] | frozenset[str] = frozenset(),
    day_key: str = "",
) -> list[PracticeItem]:
    """WP-129 — fill a B1+ day's free practice time with mixed-unit production.

    ``units`` are grammar units the learner has *already been introduced to*
    (the due Rappel units and ``practice_unit`` candidates, each with its
    brief); today's new unit is never among them (its guided items are
    ``reserved``). Round by round, each unit gets at most
    :data:`ADVANCED_ITEMS_PER_UNIT` items in different formats — a contrast
    with an introduced ``contrast_partners`` unit, a repair, a free sentence —
    never the same unit twice running (interleaving), never a sentence the day
    already holds, up to :data:`ADVANCED_ITEM_TARGET` and inside ``headroom``.
    After the ending («post»): the episode is never interrupted. Below B1 the
    day is returned unchanged.
    """

    if scenario.level_band not in ADVANCED_BANDS:
        return items
    rule = practice_day_shape_rule(shape, caps.budget_seconds)
    cap = min(caps.max_recall, rule.max_recall, max_items if max_items is not None else caps.max_recall)
    want = min(cap, ADVANCED_ITEM_TARGET.get(caps.budget_seconds, 5) - max(0, reserved))
    placed = list(items)
    if len(placed) >= want or headroom <= 0:
        return placed
    by_external: dict[str, dict[str, Any]] = {}
    pool: list[tuple[SelectedTarget, dict[str, Any]]] = []
    for entry in units:
        brief = _unit_brief(entry)
        if brief is None or entry.target.kind is not TargetKind.GRAMMAR:
            continue
        if any(target_identity(entry.target) == target_identity(other.target) for other, _b in pool):
            continue
        pool.append((entry, brief))
        if brief.get("external_id"):
            by_external[str(brief["external_id"])] = brief

    def partners_of(brief: dict[str, Any]) -> list[dict[str, Any]]:
        own = str(brief.get("external_id") or "")
        named = [by_external[ref] for ref in brief.get("contrast_partners") or [] if ref in by_external]
        # The catalogue names a pair on one side only, sometimes: both directions.
        named += [
            other for ref, other in by_external.items()
            if own and own in (other.get("contrast_partners") or []) and other not in named and ref != own
        ]
        return named

    listed = [brief.get("level_ok_fr") for _entry, brief in pool if isinstance(brief.get("level_ok_fr"), list)]
    level_ok: set[str] | None = {str(text) for texts in listed for text in texts} if listed else None
    # Units with an introduced partner first: the contrast is the point (§2.5).
    pool.sort(key=lambda pair: 0 if partners_of(pair[1]) else 1)
    uses: dict[str, int] = {}
    formats_used: dict[str, set[str]] = {}
    for item in placed:
        identity = target_identity(item.entry.target)
        uses[identity] = uses.get(identity, 0) + 1
        formats_used.setdefault(identity, set()).add(
            "free" if item.task.evidence_format == grammar_items.FREE_SENTENCE_FORMAT
            else "contrast" if item.task.task_type == "classify" else str(item.task.task_type)
        )
    language = scenario.control_language
    offset = int(_digest("advanced", day_key)[:2], 16)
    for round_index in range(ADVANCED_ITEMS_PER_UNIT):
        for unit_index, (entry, brief) in enumerate(pool):
            if len(placed) >= want:
                return placed
            identity = target_identity(entry.target)
            if uses.get(identity, 0) >= round_index + 1 or uses.get(identity, 0) >= ADVANCED_ITEMS_PER_UNIT:
                continue
            if placed and target_identity(placed[-1].entry.target) == identity:
                continue
            held = set(avoid_sentences)
            for item in placed:
                held |= grammar_items.item_sentences(item.task)
            start = offset + round_index + unit_index
            order = [ADVANCED_FORMATS[(start + k) % len(ADVANCED_FORMATS)] for k in range(len(ADVANCED_FORMATS))]
            for fmt in order:
                if fmt in formats_used.get(identity, set()):
                    continue
                task = _advanced_task(
                    fmt, brief, partners=partners_of(brief), language=language, day_key=day_key,
                    avoid=held, level_ok=level_ok,
                )
                if task is None or not shape_allows_format(shape, task.task_type):
                    continue
                if overlaps_the_day(task, [item.task for item in placed], avoid_sentences):
                    continue
                cost = grammar_item_seconds(task, spt=spt, multiplier=multiplier)
                if cost > headroom:
                    continue
                owner = target_identity(task.target)
                owner_entry = entry if owner == identity else next(
                    (other for other, _b in pool if target_identity(other.target) == owner), entry
                )
                if placed and target_identity(placed[-1].entry.target) == owner:
                    continue
                placed.append(
                    PracticeItem(
                        slot="post", position=_next_position(placed, "post"),
                        entry=owner_entry, task=task, cost=cost,
                    )
                )
                headroom -= cost
                uses[owner] = uses.get(owner, 0) + 1
                formats_used.setdefault(owner, set()).add(fmt)
                if owner != identity:
                    # The contrast drew on both units: it is this unit's turn too.
                    formats_used.setdefault(identity, set()).add(fmt)
                break
    return placed


#: WP-129 / content program D7 «Rayons X»: looking at the card again, behind
#: the page's own line (the line and the rule's one sentence are priced too).
PAGE_REVIEW_LOOK_SECONDS = 8


def page_review_contract_ready() -> bool:
    """Does the day's contract accept the review step after the ending?

    The review is a ``rule`` step marked ``review`` after the ending; the
    contract (``journey_contracts.PAGE_REVIEW_AFTER_ENDING``) and the wire
    (``RulePrompt.review``) carry it. Until both do, no review is planned.
    """

    from app.services import journey_contracts

    return bool(getattr(journey_contracts, "PAGE_REVIEW_AFTER_ENDING", False))


def page_review_step(
    scenario: ScenarioBrief,
    briefs: list[dict[str, Any]] | None,
    *,
    spt: float,
    multiplier: float,
    band: str | None = None,
) -> PlannedStep | None:
    """WP-129 / D7 — after a tentpole's ending, one unit the learner has *already
    met*, shown in a line of the level-resolved page they just read.

    ``briefs`` are the briefs of units the page uses (``units.json``) that the
    learner was introduced to on an earlier day, in preference order. The first
    whose detector marks a line of today's page (its panels, as rendered at the
    learner's band) is shown on its own rule card, that line as the card's
    headline, the form in ``[…]`` (the x-ray). ``None`` when no met unit is in a
    line: nothing is shown rather than a new unit dressed as review. Reading it
    introduces nothing and credits nothing (``review``: the state machine
    stores no ``concept_id`` for it).
    """

    lines = [grammar_items.plain(text) for text in scene_sentences(*page_texts(scene_page(scenario)))]
    if not lines or not briefs:
        return None
    speakers = scene_speakers(scenario)
    language = str(scenario.control_language or "")
    for brief in briefs:
        card = brief.get("rule_card")
        if not isinstance(card, dict) or not brief.get("detectors") or brief.get("concept_id") is None:
            continue
        for text in lines:
            if not 3 <= len(text.split()) <= 24:
                continue
            bounds = grammar_items.rule_span(brief, text)
            if bounds is None:
                continue
            start, end = bounds
            marked = f"{text[:start]}[{text[start:end]}]{text[end:]}"
            speaker = speakers.get(grammar_items._fold(text))
            shown = {**card, "example": {"fr": marked}, "speaker": speaker or None, "from_scene": True}
            rule = card.get("rule") if isinstance(card.get("rule"), dict) else {}
            native = str(rule.get(language) or rule.get("en") or "")
            cost = round(
                PAGE_REVIEW_LOOK_SECONDS * multiplier
                + _reading_seconds(spt, text) * page_reading_factor(band)
                + _tokens(native) * NATIVE_SECONDS_PER_TOKEN
            )
            return PlannedStep(
                ordinal=0,
                kind=StepKind.RULE,
                estimated_seconds=max(1, cost),
                public_prompt={
                    "concept_id": int(brief["concept_id"]),
                    "title_native": str(brief.get("title_native") or ""),
                    "title_fr": str(brief.get("title_fr") or ""),
                    "rule_card": shown,
                    "scene_example_fr": marked,
                    "scene_example_speaker": speaker or None,
                    "review": True,
                },
                target=grammar_items.grammar_target(brief),
            )
    return None


def grammar_uses(items: list[PracticeItem]) -> int:
    return sum(1 for item in items if item.entry.target.kind is TargetKind.GRAMMAR)


def _same_concept_last(items: list[PracticeItem], target: TargetRef) -> bool:
    """Never the same concept back to back (WP-L3's interleaving rule)."""

    return bool(items) and target_identity(items[-1].entry.target) == target_identity(target)


def grammar_item_seconds(task: RecallTask, *, spt: float, multiplier: float) -> int:
    """A grammar item is a quick item whose cards are sentences: they are read.

    WP-128: :func:`quick_recall_seconds` now reads every item's cards, so the
    sentences are no longer added a second time here.
    """

    return quick_recall_seconds(task, spt=spt, multiplier=multiplier)


def rule_card_seconds(
    card: dict[str, Any] | None, *, spt: float, multiplier: float,
    band: str | None = None, language: str | None = None,
) -> int:
    """The Règle: thirty seconds with the card, plus reading its French.

    WP-128: with a ``band`` the card is priced by what it prints — the rule in
    the learner's language at a native pace, its French (the example, the
    pattern's rows, the contrast) at the band's prose pace — after ten seconds
    of looking at it. The walk's Timer read an A1 card in 50–85 s, not 33.
    """

    card = card or {}
    texts = [str((card.get("example") or {}).get("fr") or "")]
    contrast = card.get("contrast") or {}
    texts.extend([str(contrast.get("wrong") or ""), str(contrast.get("right") or "")])
    if not _band_key(band):
        return max(
            1, round(RULE_CARD_SECONDS * multiplier + _reading_seconds(spt, *texts) * 0.5)
        )
    texts.extend(
        str((row or {}).get("fr") or "")
        for row in ((card.get("pattern") or {}).get("rows") or [])
        if isinstance(row, dict)
    )
    rule = card.get("rule") or {}
    if isinstance(rule, dict):
        rule_text = rule.get(language or "") or next(iter(rule.values()), "")
    else:
        rule_text = rule
    french = _reading_seconds(spt, *texts) * page_reading_factor(band)
    native = _tokens(str(rule_text or "")) * NATIVE_SECONDS_PER_TOKEN
    return max(1, round(RULE_CARD_LOOK_SECONDS * multiplier + french + native))


def _unit_ids(brief: dict[str, Any]) -> set[str]:
    """Every id a scene may name the unit by: the concept id and its catalogue id."""

    return {
        str(value).strip()
        for value in (brief.get("concept_id"), brief.get("external_id"))
        if value not in (None, "") and str(value).strip()
    }


def rule_scene_example(
    brief: dict[str, Any] | None, scenario: ScenarioBrief
) -> tuple[str | None, str | None]:
    """WP-92 — a cast line of today's scene that uses the day's unit, and who says it.

    A line whose ``grammar_marks`` (the story engine's, WP-92) name the unit
    wins; otherwise the first cast line the unit's detector finds (the same
    trustworthy match the card's headline uses, :func:`grammar_items.rule_span`).
    The form is wrapped in the rule card's marks — «Je [suis allé] au marché»
    — from the mark's span or the detector's. The speaker is the cast id (the
    client draws the face and prints the name). Narration is never the
    example: the card shows a person saying the form. ``(None, None)`` when
    the scene holds none.
    """

    if not isinstance(brief, dict):
        return None, None
    ids = _unit_ids(brief)
    # The story engine measures the marks after validation and keeps them in
    # the story context (``grammar.marks``: "<panel>:<line>" → spans); a bound
    # scene's lines carry them as ``grammar_marks``. Either is read.
    story = scenario.story_context if isinstance(scenario.story_context, dict) else {}
    grammar = story.get("grammar") if isinstance(story.get("grammar"), dict) else {}
    outcome_marks = grammar.get("marks") if isinstance(grammar.get("marks"), dict) else {}
    lines: list[dict[str, Any]] = []
    for panel_index, panel in enumerate(scene_page(scenario)):
        for line_index, line in enumerate(panel.get("dialogue") or []):
            if isinstance(line, dict) and str(line.get("text_fr") or "").strip():
                marks = outcome_marks.get(f"{panel_index}:{line_index}")
                if isinstance(marks, list) and not line.get("grammar_marks"):
                    line = {**line, "grammar_marks": marks}
                lines.append(line)
    if scenario.opening_line_fr and scenario.character_id:
        lines.append({"character_id": scenario.character_id, "text_fr": scenario.opening_line_fr})

    def marked(text: str, start: int, end: int) -> str:
        return f"{text[:start]}[{text[start:end]}]{text[end:]}"

    cast = [line for line in lines if str(line.get("character_id") or "") not in ("", NARRATOR_ID)]
    for line in cast:
        marks = line.get("grammar_marks")
        if not isinstance(marks, list):
            continue
        for mark in marks:
            if not isinstance(mark, dict) or str(mark.get("unit_id") or "").strip() not in ids:
                continue
            raw = str(line["text_fr"]).strip()
            try:
                start, end = int(mark.get("start")), int(mark.get("end"))
            except (TypeError, ValueError):
                start, end = -1, -1
            if 0 <= start < end <= len(raw) and raw[start:end].strip():
                return marked(raw, start, end), str(line["character_id"])
            return _detector_marked(brief, raw) or raw, str(line["character_id"])
    for line in cast:
        text = _detector_marked(brief, str(line["text_fr"]))
        if text is not None:
            return text, str(line["character_id"])
    return None, None


def _detector_marked(brief: dict[str, Any], text: str) -> str | None:
    """``text`` with the unit's trustworthy use in ``[…]``, or ``None``."""

    plain = grammar_items.plain(" ".join(str(text or "").split()))
    try:
        found = grammar_items.rule_span(brief, plain)
    except Exception:  # noqa: BLE001 - a detector that cannot run finds nothing
        found = None
    if found is None:
        return None
    start, end = found
    return f"{plain[:start]}[{plain[start:end]}]{plain[end:]}"


def _rule_step(
    ordinal: int,
    *,
    brief: dict[str, Any],
    card: dict[str, Any],
    cost: int,
    scenario: ScenarioBrief | None = None,
) -> PlannedStep:
    example, example_speaker = (
        rule_scene_example(brief, scenario) if scenario is not None else (None, None)
    )
    return PlannedStep(
        ordinal=ordinal,
        kind=StepKind.RULE,
        estimated_seconds=cost,
        public_prompt={
            "concept_id": int(brief["concept_id"]),
            "title_native": str(brief.get("title_native") or ""),
            "title_fr": str(brief.get("title_fr") or ""),
            "rule_card": card,
            # WP-92: the form as the learner is about to meet it in the story.
            "scene_example_fr": example,
            "scene_example_speaker": example_speaker,
        },
        target=grammar_items.grammar_target(brief),
    )


#: WP-S4 — the shortest forge block worth folding into a day.
FORGE_MIN_SECONDS = 120


def forge_reserve_seconds(forge: dict[str, Any] | None) -> int:
    """The room a folded forge keeps free of quick items (0 without a forge)."""

    if not isinstance(forge, dict):
        return 0
    try:
        return max(0, int(forge.get("reserve_seconds") or 0))
    except (TypeError, ValueError):
        return 0


def _forge_step(
    ordinal: int,
    *,
    forge: dict[str, Any],
    introduction: dict[str, Any] | None,
    room: int,
) -> PlannedStep | None:
    """The folded forge's hand-off step, or None when the day leaves too little.

    Today's rule is the rule this day introduces, when it does; otherwise the
    forge picker's anchor, as the caller passed it.
    """

    try:
        ceiling = int(forge.get("max_seconds") or 0)
    except (TypeError, ValueError):
        ceiling = 0
    cost = min(room, ceiling) if ceiling > 0 else room
    if cost < FORGE_MIN_SECONDS:
        return None
    source = introduction if isinstance(introduction, dict) and introduction.get("concept_id") else forge
    concept_id = source.get("concept_id")
    return PlannedStep(
        ordinal=ordinal,
        kind=StepKind.FORGE,
        estimated_seconds=int(cost),
        public_prompt={
            "concept_id": int(concept_id) if concept_id not in (None, "") else None,
            "title_native": str(source.get("title_native") or ""),
            "title_fr": str(source.get("title_fr") or ""),
            "budget_seconds": int(cost),
        },
    )


def scene_speakers(scenario: ScenarioBrief) -> dict[str, str]:
    """Who said each sentence of the scene's dialogue (folded sentence → character id)."""

    speakers: dict[str, str] = {}
    for line in scene_lines(scenario):
        for sentence in scene_sentences(line.text_fr):
            speakers.setdefault(grammar_items._fold(grammar_items.plain(sentence)), line.character_id)
    return speakers


def _introduction_items(
    brief: dict[str, Any] | None,
    *,
    scenario: ScenarioBrief,
    sentences: list[str],
    spt: float,
    multiplier: float,
    shape: DayShape = DEFAULT_DAY_SHAPE,
) -> tuple[dict[str, Any] | None, int, list[tuple[RecallTask, int]]]:
    """The introduction's card, its cost, and its guided items with their costs."""

    if not isinstance(brief, dict) or not brief.get("concept_id"):
        return None, 0, []
    card = grammar_items.scene_rule_card(brief, sentences, speakers=scene_speakers(scenario))
    if not card:
        return None, 0, []
    guided = [
        (task, grammar_item_seconds(task, spt=spt, multiplier=multiplier))
        for task in grammar_items.guided_items(
            {**brief, "level": scenario.level_band},
            sentences=sentences,
            language=scenario.control_language,
            meanings=line_meanings(scenario),
        )
        # A «jour d'écoute» poses only what can be taken down by ear.
        if shape_allows_format(shape, task.task_type)
    ]
    if len(guided) < 2:
        # A rule with nothing to try is a lecture, not an Essai.
        return None, 0, []
    cost = rule_card_seconds(
        card, spt=spt, multiplier=multiplier,
        band=scenario.level_band, language=str(scenario.control_language or ""),
    )
    return card, cost, guided


def top_up_from_scene(
    *,
    scenario: ScenarioBrief,
    shape: DayShape,
    entries: list[SelectedTarget],
    items: list[PracticeItem],
    expected_reply: str | None,
    headroom: int,
    spt: float,
    multiplier: float,
    target_items: int | None = None,
    caps: RhythmCaps | None = None,
    avoid_sentences: set[str] | frozenset[str] = frozenset(),
) -> list[PracticeItem]:
    """WP-86 — the floor: when today's words leave the day thin, the scene
    itself poses the rest («Qui a dit ça ?», a cloze, a rebuilt line).

    Adds items after the scene only, until the day holds ``target_items``
    quick items or the budget or the cap says stop. Each item is tied to a
    word of today that its line holds; one item per (word, kind), and a word
    may come back once more than the fill allows (never for the same kind);
    «Qui a dit ça ?» schedules nothing and is not counted. Pure and deterministic, like the fill it follows.
    """

    from app.services.scene_items import floor_tasks

    caps = caps or rhythm_caps(None)
    if target_items is None:
        target_items = caps.target_items
    cap = min(practice_day_shape_rule(shape, caps.budget_seconds).max_recall, caps.max_recall)
    if len(items) >= min(target_items, cap):
        return items
    by_identity = {target_identity(entry.target): entry for entry in entries}
    uses: dict[str, int] = {}
    for item in items:
        identity = target_identity(item.entry.target)
        uses[identity] = uses.get(identity, 0) + 1
    taken: set[tuple[str, str, str]] = set()
    placed = list(items)
    for target, task in floor_tasks(
        scenario,
        [(entry.target, entry.candidate.metadata or {}) for entry in entries],
        expected_reply=expected_reply,
    ):
        if len(placed) >= min(target_items, cap):
            break
        identity = target_identity(target)
        entry = by_identity.get(identity)
        if entry is None or not shape_allows_format(shape, task.task_type):
            continue
        if scenario.level_band in {"B1", "B2", "C1", "C2"} and task.task_type not in {"transform", "short_answer", "dictation"}:
            continue
        kind = (identity, task.task_type, str(task.instruction_native))
        if kind in taken:
            continue
        if task.task_type != "who_said" and uses.get(identity, 0) > caps.uses_per_target:
            # One use beyond the fill's limit: the floor exists because the
            # pool is thin, and a rebuilt line is a different act from a pick.
            continue
        cost = quick_recall_seconds(task, spt=spt, multiplier=multiplier)
        if cost > headroom:
            continue
        slot_items = [item for item in placed if item.slot in ("mid", "post")]
        slot = "mid" if len(slot_items) % 2 == 0 else "post"
        if _repeats_the_day(task, entry, placed, slot=slot, avoid=avoid_sentences):
            continue
        position = 1 + max((item.position for item in placed if item.slot == slot), default=-1)
        taken.add(kind)
        if task.task_type != "who_said":
            uses[identity] = uses.get(identity, 0) + 1
        headroom -= cost
        placed.append(PracticeItem(slot=slot, position=position, entry=entry, task=task, cost=cost))
    return placed


def _next_position(items: list[PracticeItem], slot: str) -> int:
    return 1 + max((item.position for item in items if item.slot == slot), default=-1)


def add_listening_items(
    *,
    scenario: ScenarioBrief,
    shape: DayShape,
    entries: list[SelectedTarget],
    items: list[PracticeItem],
    expected_reply: str | None,
    headroom: int,
    spt: float,
    multiplier: float,
    caps: RhythmCaps,
    max_items: int | None = None,
    partners: list[TargetRef] | tuple[TargetRef, ...] = (),
    extra_heard: int = 0,
    avoid_sentences: set[str] | frozenset[str] = frozenset(),
) -> list[PracticeItem]:
    """WP-91 — with audio on, the day *hears* its words: listen-and-tap items
    carry a clip of the phrase, and dictations ask for lines of the scene.
    From B1 the listening floor uses written dictations rather than tapping.

    Called only when the deployment speaks (``audio_available``); a day planned
    without audio never reaches this and is exactly what it was. Budget-scaled
    and inside the day's caps: every listen-and-tap item already placed gets
    its clip; the day then holds at least :data:`LISTEN_TAP_ITEMS_BY_BUDGET`
    of them — added while the cap and the seconds allow, otherwise by re-posing
    a placed word as listen-and-tap — and one dictation, added or (at the cap)
    in place of the last item that is not already heard. Deterministic, like
    the fill it follows.
    """

    placed = list(items)
    rule = practice_day_shape_rule(shape, caps.budget_seconds)
    cap = min(caps.max_recall, rule.max_recall)
    if max_items is not None:
        cap = min(cap, max_items)
    # WP-93: a paged day from Soutenu up hears more — heard items may go past
    # the recall ceiling by ``extra_heard`` (they are input, not drills).
    cap += max(0, extra_heard)
    wanted_dictations = DICTATION_ITEMS_PER_DAY + max(0, extra_heard) // 3
    if scenario.level_band in {"B1", "B2", "C1", "C2"}:
        # Keep the listening floor as written dictations at B1, so heard words
        # also count as production instead of displacing it with recognition.
        wanted_dictations += LISTEN_TAP_ITEMS_BY_BUDGET.get(caps.budget_seconds, 1)
    room = headroom - sum(item.cost for item in placed)
    pool = [entry.target for entry in entries if _glossed(entry.target) is not None]
    pool.extend(target for target in partners if _glossed(target) is not None)

    def heard(item: PracticeItem) -> PracticeItem:
        if item.task.task_type != str(RecallFormat.LISTEN_TAP):
            return item
        line = listen_tap_line(scenario, item.task.target)
        if not line.text_fr:
            return item
        return replace(item, audio_url=line_audio_url(line.voice, line.text_fr))

    placed = [heard(item) for item in placed]

    def listen_tap_for(entry: SelectedTarget) -> RecallTask | None:
        return build_listen_tap_task(
            target=entry.target,
            pool=pool,
            optional=bool(entry.candidate.is_new),
            control_language=scenario.control_language,
        )

    # -- listen-and-tap: the day's floor of heard words ------------------------
    wanted = LISTEN_TAP_ITEMS_BY_BUDGET.get(caps.budget_seconds, 1) + max(0, extra_heard) * 2 // 3
    if scenario.level_band in {"B1", "B2", "C1", "C2"}:
        wanted = 0
    if shape_allows_format(shape, str(RecallFormat.LISTEN_TAP)):
        tapped = {
            target_identity(item.entry.target)
            for item in placed
            if item.task.task_type == str(RecallFormat.LISTEN_TAP)
        }
        uses: dict[str, int] = {}
        for item in placed:
            identity = target_identity(item.entry.target)
            uses[identity] = uses.get(identity, 0) + 1
        for entry in entries:
            count = sum(1 for item in placed if item.task.task_type == str(RecallFormat.LISTEN_TAP))
            if count >= wanted or len(placed) >= cap:
                break
            identity = target_identity(entry.target)
            if identity in tapped or uses.get(identity, 0) >= caps.uses_per_target:
                continue
            task = listen_tap_for(entry)
            if task is None:
                continue
            cost = quick_recall_seconds(task, spt=spt, multiplier=multiplier)
            if cost > room:
                continue
            # After the scene: the word is heard in the voice that said it.
            slot = "mid" if shape is DayShape.LISTENING or len(placed) % 2 == 0 else "post"
            placed.append(
                heard(
                    PracticeItem(
                        slot=slot, position=_next_position(placed, slot), entry=entry,
                        task=task, cost=cost,
                    )
                )
            )
            tapped.add(identity)
            uses[identity] = uses.get(identity, 0) + 1
            room -= cost
        # At the cap (or out of new words): re-pose placed words by ear.
        for index, item in enumerate(list(placed)):
            count = sum(1 for other in placed if other.task.task_type == str(RecallFormat.LISTEN_TAP))
            if count >= wanted:
                break
            identity = target_identity(item.entry.target)
            if (
                identity in tapped
                or item.entry.target.kind is TargetKind.GRAMMAR
                or item.task.task_type in (*LISTENING_RECALL_FORMATS, str(RecallFormat.WHO_SAID))
            ):
                continue
            task = listen_tap_for(item.entry)
            if task is None:
                continue
            cost = quick_recall_seconds(task, spt=spt, multiplier=multiplier)
            if cost - item.cost > room:
                continue
            room -= cost - item.cost
            placed[index] = heard(replace(item, task=task, cost=cost))
            tapped.add(identity)

    # -- one dictation: a short line of today's scene ---------------------------
    if not shape_allows_format(shape, str(RecallFormat.DICTATION)) or not entries:
        return placed
    limit = dictation_word_cap(scenario.level_band)
    candidates = [
        line
        for line in dictation_lines(scenario)
        if DICTATION_MIN_WORDS <= len(line.text_fr.split()) <= limit
    ]
    if not candidates:
        return placed

    def owner(line: HeardLine) -> SelectedTarget | None:
        from app.services.scene_items import contains_surface, target_surfaces

        for entry in entries:
            for surface in target_surfaces(entry.target, entry.candidate.metadata or {}):
                if contains_surface(line.text_fr, surface):
                    return entry
        return None

    # A line holding one of today's words first (its evidence lands on that
    # word); the characters before the narrator; reading order breaks ties.
    ranked = sorted(
        candidates,
        key=lambda line: (
            0 if owner(line) is not None else 1,
            1 if line.character_id == NARRATOR_ID else 0,
            candidates.index(line),
        ),
    )
    if scenario.level_band in LOW_BANDS and caps.budget_seconds > RHYTHM_FIVE_MINUTES:
        # WP-129 (owner decision: fewer replies, more items). The time the
        # shorter reply frees is not drills for their own sake: when today's
        # words are too few to fill the day, the story's own lines are heard and
        # written down — input and output in one — up to
        # :data:`THIN_DAY_EXTRA_DICTATIONS` more, inside the cap and the seconds.
        deficit = caps.target_items - len(placed)
        extra_dictations = max(0, min(THIN_DAY_EXTRA_DICTATIONS, deficit - wanted_dictations))
    else:
        extra_dictations = 0
    ranked = [
        line for line in ranked
        # WP-129: a line the rule's guided items work on is not dictated too.
        if grammar_items._fold(grammar_items.plain(line.text_fr)) not in set(avoid_sentences)
    ]
    dictated = 0
    for line in ranked:
        if dictated >= wanted_dictations + extra_dictations:
            break
        index_line = dictated
        entry = owner(line) or entries[0]
        task = build_dictation_task(
            target=entry.target, line=line, optional=True,
            control_language=scenario.control_language,
        )
        cost = quick_recall_seconds(task, spt=spt, multiplier=multiplier)
        # A line said before the reply must not be the reply.
        slot = "post" if line_spoils_reply(line.text_fr, expected_reply) else "mid"
        dictation = PracticeItem(
            slot=slot, position=_next_position(placed, slot), entry=entry, task=task,
            cost=cost, audio_url=line_audio_url(line.voice, line.text_fr),
        )
        same = next(
            (
                index for index, other in enumerate(placed)
                if grammar_items.item_sentences(task) & grammar_items.item_sentences(other.task)
            ),
            None,
        )
        if same is not None:
            # WP-129: the day already works on this line (a rebuilt line, a
            # cloze): the dictation takes that item's place rather than posing
            # the same sentence twice — or the line is left to it.
            other = placed[same]
            if other.task.task_type not in LISTENING_RECALL_FORMATS and cost - other.cost <= room:
                room -= cost - other.cost
                placed[same] = replace(
                    dictation, slot=slot,
                    position=other.position if other.slot == slot else _next_position(placed, slot),
                )
                dictated += 1
            # Else the line stays the other item's, and the next line is tried.
            continue
        if len(placed) < cap and cost <= room:
            placed.append(dictation)
            room -= cost
            dictated += 1
            continue
        if index_line >= wanted_dictations:
            # A thin day's extra line is added or not: it never displaces an item.
            break
        # At the cap or out of seconds: in place of the last item not heard.
        for index in range(len(placed) - 1, -1, -1):
            other = placed[index]
            if other.task.task_type in LISTENING_RECALL_FORMATS or other.slot == "warmup":
                continue
            if cost - other.cost > room:
                continue
            room -= cost - other.cost
            placed[index] = replace(
                dictation, slot=slot,
                position=other.position if other.slot == slot else _next_position(placed, slot),
            )
            break
        # Placed or not, this is the line the day offered: the next is not tried
        # for the same slot (the pre-WP-129 behaviour at the cap).
        dictated += 1
    return placed


def recall_met(candidate: LearningCandidate | None) -> dict[str, Any]:
    """WP-121 A.4: ``{"met": {"place_label_fr": "vu au marché d'Aligre, semaine 41"}}``
    for a card first kept in a Papier (the caller put the line in the candidate's
    ``metadata["place_label_fr"]`` from ``kept_words.place_line_fr``), else ``{}``."""

    label = str(((getattr(candidate, "metadata", None) or {}).get("place_label_fr")) or "").strip()
    return {"met": {"place_label_fr": label}} if label else {}


def _recall_step(ordinal: int, item: PracticeItem) -> PlannedStep:
    recall = item.task
    prompt: dict[str, Any] = {
        "task_type": recall.task_type,
        "instruction_native": recall.instruction_native,
        "prompt_fr": recall.prompt_fr,
        "options": [dict(option) for option in recall.options],
        "target": public_recall_target(recall.target),
        "optional": recall.optional,
        "help_available": _recall_help(recall),
        # WP-103 T3: what to produce, and what it starts from.
        "goal_native": recall.goal_native,
        "source_fr": recall.source_fr,
        **recall_met(item.entry.candidate),
    }
    if recall.task_type in LISTENING_RECALL_FORMATS:
        # WP-91: with a clip the phrase (or the dictated line) is heard, not
        # read — the prompt prints nothing French. Without one a listen-and-tap
        # item is read-and-tap, exactly as before; a dictation always has one.
        prompt["audio_url"] = item.audio_url
        if item.audio_url:
            prompt["prompt_fr"] = None
    return PlannedStep(
        ordinal=ordinal,
        kind=StepKind.RECALL,
        estimated_seconds=item.cost,
        public_prompt=prompt,
        private_task=replace(recall, estimated_seconds=item.cost),
        target=item.entry.target,
        optional=recall.optional,
        initial_status=StepStatus.PENDING,
    )


#: «Le bureau»: what one desk step is priced at when the offer names no
#: length — a Relecture is one or two sentences and the pair; the Radio is a
#: ~50 s bulletin heard, read and one dictée; the Correcteur is three lines
#: marked and the result.
DESK_SECONDS: dict[str, int] = {"relecture": 120, "radio": 150, "correcteur": 150}


def desk_offer(
    desk: str,
    *,
    title_fr: str,
    dossier_id: str | None = None,
    relecture: dict[str, Any] | None = None,
    seconds: int | None = None,
) -> dict[str, Any]:
    """The planner's ``desk`` argument: what the step will carry (all public)."""

    return {
        "desk": desk,
        "title_fr": title_fr,
        "dossier_id": dossier_id,
        "relecture": dict(relecture) if relecture else None,
        "seconds": int(seconds) if seconds else None,
    }


def _desk_step(
    desk: dict[str, Any] | None,
    *,
    shape: DayShape,
    shape_reason: str,
    room: int,
    notes: list[str],
) -> PlannedStep | None:
    """The day's one optional desk step, or ``None`` (never on a tentpole, the
    first day, the Papier day or a short day; never past the budget)."""

    if not isinstance(desk, dict):
        return None
    kind = str(desk.get("desk") or "")
    if kind not in DESK_KINDS:
        return None
    if shape not in DESK_SHAPES or shape_reason in ("season_tentpole", "first_day"):
        notes.append(f"desk {kind} not dealt on a {shape} day ({shape_reason or 'shape'})")
        return None
    if kind == "relecture" and not isinstance(desk.get("relecture"), dict):
        return None
    if kind in ("radio", "correcteur") and not desk.get("dossier_id"):
        return None
    cost = DESK_SECONDS[kind]
    if cost > room:
        notes.append(f"desk {kind} skipped: the day's budget does not hold it")
        return None
    notes.append(f"desk planned: {kind}, {cost}s")
    return PlannedStep(
        ordinal=0,
        kind=StepKind.DESK,
        estimated_seconds=cost,
        public_prompt={
            "desk": kind,
            "title_fr": str(desk.get("title_fr") or ""),
            "dossier_id": (str(desk["dossier_id"]) if desk.get("dossier_id") else None),
            "relecture": dict(desk["relecture"]) if isinstance(desk.get("relecture"), dict) else None,
            "seconds": int(desk["seconds"]) if desk.get("seconds") else None,
        },
        optional=True,
    )


def _drop_one_recall(items: list[PracticeItem]) -> list[PracticeItem] | None:
    """The day's items less one ordinary recall — the last item after the
    ending (a non-heard one first), else the last build, else the last warm-up.
    ``None`` when there is nothing to give up."""

    if not items:
        return None
    order = {"warmup": 0, "mid": 1, "post": 2}
    ranked = sorted(
        range(len(items)),
        key=lambda index: (
            order.get(items[index].slot, 0),
            0 if items[index].audio_url else 1,
            items[index].position,
        ),
    )
    drop = ranked[-1]
    return [item for index, item in enumerate(items) if index != drop]


def _plan_practice_day(
    *,
    scenario: ScenarioBrief,
    task: ResponseTask,
    outcome_key: str,
    candidates: list[LearningCandidate],
    selection: TargetSelection,
    affordances: list[str],
    reasons_by_identity: dict[str, str],
    shape: DayShape,
    shape_reason: str,
    dice: DayShapeInputs | None,
    letter: LetterOffer | None,
    chapter_recap_fr: str | None,
    audio_available: bool,
    input_mode: InputMode,
    budget_seconds: int,
    turns: int,
    spt: float,
    multiplier: float,
    scene_cost: int,
    resolution_cost: int,
    notes: list[str],
    partners: list[TargetRef] | None = None,
    introduction: dict[str, Any] | None = None,
    forge: dict[str, Any] | None = None,
    reading: dict[str, Any] | list[dict[str, Any]] | None = None,
    scene_audio: bool = False,
    desk: dict[str, Any] | None = None,
    band: str | None = None,
    story_longer: bool = False,
    practice_units: list[LearningCandidate] | None = None,
    page_review: list[dict[str, Any]] | None = None,
) -> PlannedJourney | None:
    """WP-78 — warm-ups → scene → reply → builds → a word from today → ending.

    WP-128: ``story_longer`` — the story alone is longer than the rhythm; the
    day is then the story and its rule (a flagged longer day), or ``None`` when
    there is no rule to plan, for the caller's story-alone day.

    WP-93 (W5): the scene's page ends on the question the reply answers, so
    nothing sits between them — the builds that used to come between the
    scene and the reply come after it. With an ``introduction`` (WP-L4) the
    rule card and its three or four guided items come *before* the scene
    (the reply asks for the unit, and the scene then shows it in use), and so
    does a folded forge block (WP-S4). The rule's budget is reserved first,
    and the guided items are dropped from the strongest end (transform, then
    build) before the introduction is given up.

    WP-93: on a paged scene at least :data:`INPUT_FLOOR_SHARE` of the budget
    is reading or listening — the page, the heard items and the «Lecture»
    (``reading``, Soutenu/Intensif, after the ending) — and drills never
    take that room.

    WP-L6: the same day at every rhythm, with the movements sized by
    :func:`~app.services.journey_contracts.rhythm_caps` of the budget.
    """

    caps = rhythm_caps(budget_seconds)
    forge_reserve = forge_reserve_seconds(forge)
    authored = authored_turns(scenario)
    # WP-93 «Lecture»: the long rhythms' extra pages (one on Soutenu, two on
    # Intensif), reserved before any drill, in the order offered.
    read_steps: list[PlannedStep] = []
    offers = [reading] if isinstance(reading, dict) else list(reading or [])
    core = scene_cost + respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier, band=band, authored=authored)
    for offer in offers:
        if len(read_steps) >= caps.max_reads or budget_seconds < READ_MIN_BUDGET_SECONDS:
            break
        if not isinstance(offer, dict) or str(offer.get("variant") or "") not in (
            "relecture", "coulisses"
        ):
            continue
        heard = bool(offer.get("audio_available", audio_available)) and bool(audio_available)
        cost = reading_step_seconds(
            offer, scenario, spt=spt, multiplier=multiplier, audio=heard, band=band
        )
        spent = sum(step.estimated_seconds for step in read_steps)
        if core + resolution_cost + spent + cost > budget_seconds:
            notes.append("lecture skipped: the day's budget does not hold another page")
            continue
        variant = str(offer["variant"])
        status = str(offer.get("status") or ("ready" if variant == "relecture" else "writing"))
        read_steps.append(
            PlannedStep(
                ordinal=0,
                kind=StepKind.READ,
                estimated_seconds=cost,
                public_prompt={
                    "variant": variant,
                    "title_fr": str(offer.get("title_fr") or scenario.title_fr),
                    "scene_id": (str(offer["scene_id"]) if offer.get("scene_id") else None),
                    "status": status if status in ("ready", "writing", "unavailable") else "writing",
                    "audio_available": heard,
                },
                optional=True,
            )
        )
        notes.append(f"lecture planned: {variant}, {cost}s")
    read_cost = sum(step.estimated_seconds for step in read_steps)
    # «Le bureau» (WP-121/122): one Revue desk, reserved like the «Lecture».
    desk_step = _desk_step(
        desk, shape=shape, shape_reason=shape_reason,
        room=budget_seconds - (core + resolution_cost + read_cost), notes=notes,
    )
    desk_cost = desk_step.estimated_seconds if desk_step is not None else 0
    # WP-93: the input floor. The page (and the «Lecture») count; what they
    # leave short of the floor is kept free of drills — only a heard item may
    # use it. A page-less (legacy) brief has no page to price and keeps the
    # pre-WP-93 fill.
    input_gap = 0
    if scene_page(scenario):
        floor = round(INPUT_FLOOR_SHARE * budget_seconds)
        input_gap = max(
            0, floor - scene_cost - read_cost - reply_input_seconds(task, turns=turns, spt=spt, band=band)
        )
        if input_gap:
            notes.append(f"input floor: {input_gap}s kept for reading and listening")
    entries = practice_entries(scenario, selection, affordances)
    # WP-86: the floor may lean on any word of today the scene prints — a word
    # already produced is not drilled, but its line can still be rebuilt or
    # attributed («Qui a dit ça ?»).
    floor_entries = [
        *entries,
        *(
            SelectedTarget(
                candidate=candidate,
                fit=scenario_fit(candidate.target, affordances, scenario),
                demonstrated=True,
            )
            for candidate in [
                *(entry.candidate for entry in selection.selected),
                *selection.omitted,
            ]
            if candidate_is_demonstrated(candidate)
        ),
    ]
    scene_line = _scene_line_without_spoiler(scenario)
    # WP-86: the characters' own lines are read too (the episode's panels).
    sentences = scene_sentences(
        scenario.setup_fr, scene_line, *(line.text_fr for line in scene_lines(scenario))
    )
    expected = task.suggested_response_fr
    # A sentence rebuilt *before* the reply must not be the reply.
    safe_sentences = [line for line in sentences if not line_spoils_reply(line, expected)]

    # WP-L4 «Règle» + «Essai»: the new unit's card and guided items.
    intro_card, intro_card_cost, intro_items = _introduction_items(
        introduction,
        scenario=scenario,
        sentences=safe_sentences,
        spt=spt,
        multiplier=multiplier,
        shape=shape,
    )
    if story_longer and not intro_card:
        return None
    intro_identity = (
        target_identity(grammar_items.grammar_target(introduction)) if intro_card else None
    )
    if intro_identity:
        entries = [entry for entry in entries if target_identity(entry.target) != intro_identity]

    # WP-128: a reply that asks for a unit («Réemploi» of a strong due unit, or
    # today's «Emploi») is priced a sentence longer.
    # The sentence is the unit's own model sentence (its first example), the
    # one the rule card and the hint show.
    reemploi_briefs = [
        (entry.candidate.metadata or {}).get("grammar_brief")
        for entry in reemploi_order(entries)
        if entry.target.kind is TargetKind.GRAMMAR
        and isinstance((entry.candidate.metadata or {}).get("grammar_brief"), dict)
        and ((entry.candidate.metadata or {}).get("grammar_brief") or {}).get("detectors")
        and grammar_items.review_band(
            ((entry.candidate.metadata or {}).get("grammar_brief") or {}).get("stability")
        ) == "high"
    ]
    reemploi = unit_sentence_words(reemploi_briefs[0], band) if reemploi_briefs else 0
    emploi = unit_sentence_words(introduction, band) if intro_card else 0

    # WP-129: the units a B1+ day may mix in — the due Rappel units and the
    # introduced ``practice_unit`` candidates, never today's new unit.
    unit_entries = [
        entry for entry in entries
        if entry.target.kind is TargetKind.GRAMMAR and _unit_brief(entry) is not None
    ] + [
        SelectedTarget(candidate=candidate, fit=0.0, demonstrated=False)
        for candidate in practice_units or []
        if target_identity(candidate.target) != intro_identity
    ]

    forced_intro = False

    def intro_reserve(turn_count: int) -> list[tuple[RecallTask, int]]:
        """The guided items that fit, keeping at least room for the core day."""

        if not intro_card:
            return []
        if forced_intro:
            # WP-128: a longer rule day — the card and its two first guided items.
            return list(intro_items)[:2]
        cost = respond_seconds(
            task, turns=turn_count, spt=spt, multiplier=multiplier, band=band, authored=authored,
            asks_unit=emploi
        )
        # WP-128: the input floor keeps *drills* off the reading's room; the
        # rule and its Essai are the day's grammar intake, which a deferral would
        # hand tomorrow's director again (a reprise that cannot introduce its
        # unit repeats forever), so they are not held to it.
        room = (
            budget_seconds - (scene_cost + cost + resolution_cost) - intro_card_cost
            - read_cost - desk_cost
        )
        # The rule step and its items share the day's step envelope.
        kept = list(intro_items)[: max(0, min(caps.max_recall, caps.max_steps - 5))]
        while kept and sum(item_cost for _task, item_cost in kept) > room:
            kept.pop()
        return kept if len(kept) >= 2 else []

    def attempt(turn_count: int) -> tuple[int, list[PracticeItem]]:
        cost = respond_seconds(
            task, turns=turn_count, spt=spt, multiplier=multiplier, band=band, authored=authored,
            asks_unit=(emploi if intro_reserve(turn_count) else 0) or reemploi,
        )
        # WP-S4: the folded forge keeps its room free of quick items; WP-93:
        # so do the «Lecture» and the input floor (only heard items use it).
        headroom = (
            budget_seconds - (scene_cost + cost + resolution_cost) - forge_reserve - read_cost
            - desk_cost
        )
        reserved = intro_reserve(turn_count)
        max_items: int | None = None
        target_items: int | None = None
        if reserved:
            headroom -= intro_card_cost + sum(item_cost for _task, item_cost in reserved)
            max_items = max(0, min(caps.max_recall, caps.max_steps - 5) - len(reserved))
            target_items = max(0, caps.target_items - len(reserved))
        drills = headroom - input_gap
        # WP-129: the rule's guided items already work on these sentences.
        avoid = set()
        for guided, _cost in reserved:
            avoid |= grammar_items.item_sentences(guided)
        day_key = "|".join(dice.seed_parts) if dice is not None else str(scenario.scenario_key)
        mixed = scenario.level_band in ADVANCED_BANDS and bool(unit_entries)
        word_cap = max_items
        if mixed:
            # WP-129 (owner decision 4): about half of a B1+ day is interleaved
            # practice of earlier units — the words' fill leaves it that room.
            target = ADVANCED_ITEM_TARGET.get(caps.budget_seconds, 5) - len(reserved)
            leave = max(0, target // 2)
            word_cap = leave if max_items is None else min(max_items, leave)
        filled = fill_practice_items(
            scenario=scenario,
            shape=shape,
            entries=entries,
            affordances=affordances,
            sentences=sentences,
            safe_sentences=safe_sentences,
            dice=dice,
            headroom=max(0, drills),
            spt=spt,
            multiplier=multiplier,
            partners=partners or [],
            caps=caps,
            max_items=word_cap,
            avoid_sentences=avoid,
        )
        # WP-129: a B1+ day fills its free time with mixed-unit production.
        filled = fill_advanced_practice(
            scenario=scenario,
            shape=shape,
            units=unit_entries,
            items=filled,
            headroom=max(0, drills - sum(item.cost for item in filled)),
            spt=spt,
            multiplier=multiplier,
            caps=caps,
            max_items=max_items,
            reserved=len(reserved),
            avoid_sentences=avoid,
            day_key=day_key,
        )
        # WP-86: a thin day is topped up from the scene's own lines.
        topped = top_up_from_scene(
            scenario=scenario,
            shape=shape,
            entries=floor_entries,
            items=filled,
            expected_reply=expected,
            headroom=max(0, drills - sum(item.cost for item in filled)),
            spt=spt,
            multiplier=multiplier,
            caps=caps,
            target_items=target_items,
            avoid_sentences=avoid,
        )
        if not audio_available:
            return cost, topped
        # WP-91: a deployment that speaks makes the day's listening real.
        return cost, add_listening_items(
            scenario=scenario,
            shape=shape,
            entries=entries,
            items=topped,
            expected_reply=expected,
            headroom=max(0, headroom),
            spt=spt,
            multiplier=multiplier,
            caps=caps,
            max_items=max_items,
            partners=partners or [],
            extra_heard=caps.max_heard if scene_page(scenario) else 0,
            avoid_sentences=avoid,
        )

    respond_cost, items = attempt(turns)
    min_turns = max(1, int(getattr(task, "min_turns", 0) or 0))
    if intro_card and not intro_reserve(turns) and turns > min_turns:
        # The new unit is worth the reply's second turn. WP-128: and, when the
        # band composes slowly, its third — down to the reply's minimum (one
        # exchange, or «Le choix»'s) — rather than deferring the rule again.
        fewer = next(
            (count for count in range(turns - 1, min_turns - 1, -1) if intro_reserve(count)),
            None,
        )
        if fewer is not None:
            dropped_turns = turns - fewer
            turns = fewer
            respond_cost, items = attempt(turns)
            notes.append(
                f"reply reduced by {dropped_turns} turn(s) so the new rule fits the budget"
            )
    if intro_card and not intro_reserve(turns):
        # WP-128. Even the reply's minimum leaves the rule no room: a slow band
        # on a short rhythm (A1 on Léger). Deferring would defer it every day —
        # and a reprise that cannot introduce its unit repeats forever — so the
        # day is the story and its rule, nothing else, and it is a *longer
        # day*, said before the learner starts: never a hidden expansion.
        forced_intro = True
        turns = min_turns
        read_steps, desk_step, desk_cost, read_cost = [], None, 0, 0
        forge, forge_reserve = None, 0
        respond_cost, items = attempt(turns)
        items = []
        notes.append("longer day: the new rule does not fit the rhythm; the day is the story and its rule")
    if reemploi and not intro_reserve(turns):
        # WP-130 B: the reply asks for a «Réemploi» only when it fits the day
        # with the shape's items. A slow band composes the unit's sentence in
        # every exchange (WP-128), which a ten-minute A1 day cannot hold: the
        # opportunity then goes to the coach's two-line scene, priced as an item.
        rule_now = practice_day_shape_rule(shape, budget_seconds)
        spent = scene_cost + respond_cost + resolution_cost + forge_reserve + read_cost + desk_cost
        if spent + sum(item.cost for item in items) > budget_seconds or len(items) < rule_now.min_recall:
            reemploi = 0
            respond_cost, items = attempt(turns)
            notes.append("réemploi: the reply cannot hold the unit's sentence inside the budget")
    if (
        not forced_intro
        and caps.budget_seconds <= RHYTHM_FIVE_MINUTES
        and len(items) + len(intro_reserve(turns)) < caps.target_items
        and turns > 1
        and not (intro_card and not intro_reserve(turns - 1))
    ):
        # The reply keeps its repair; it gives up its second turn so the day
        # can hold its quick items — the same trade WP-75 made for day one.
        # WP-93: only the five-minute day makes it. A longer rhythm keeps its
        # exchanges: a conversation is input and output, a drill is neither.
        shorter_cost, shorter = attempt(turns - 1)
        if len(shorter) > len(items):
            turns, respond_cost, items = turns - 1, shorter_cost, shorter
            notes.append("reply reduced to one turn so the practice items fit the budget")

    rule = practice_day_shape_rule(shape, budget_seconds)
    if len(items) < rule.min_recall and not forced_intro:
        notes.append(
            f"{shape} day downgraded to {DEFAULT_DAY_SHAPE}: "
            f"{len(items)} recall step(s), {rule.min_recall} required"
        )
        shape = DEFAULT_DAY_SHAPE
        shape_reason = "shape_needs_a_recall_step"
        if not items:
            respond_cost, items = attempt(turns)
    if desk_step is not None:
        # «Le bureau»: the desk takes one ordinary recall's place, so the day
        # keeps its step envelope. A shape that needs every item it has keeps
        # them and gives up the desk instead.
        dropped = _drop_one_recall(items)
        if dropped is not None and len(dropped) < practice_day_shape_rule(shape, budget_seconds).min_recall:
            notes.append(f"desk skipped: the {shape} day needs its {len(items)} recall item(s)")
            desk_step = None
        elif dropped is not None:
            items = dropped
            notes.append("desk: one ordinary recall item given up for it")

    # WP-129 / D7: a tentpole's review in context, after the ending — inside the
    # budget, giving up an ordinary item after the ending if it must, else not shown.
    review_step = (
        page_review_step(scenario, page_review, spt=spt, multiplier=multiplier, band=band)
        if page_review and not forced_intro and page_review_contract_ready()
        else None
    )
    if review_step is not None:
        reserved_now = intro_reserve(turns)
        spent = (
            scene_cost + respond_cost + resolution_cost + desk_cost + read_cost
            + (intro_card_cost + sum(cost for _t, cost in reserved_now) if reserved_now else 0)
        )
        while review_step is not None and spent + sum(item.cost for item in items) + review_step.estimated_seconds > budget_seconds:
            dropped = _drop_one_recall(items)
            if dropped is None or len(dropped) < practice_day_shape_rule(shape, budget_seconds).min_recall:
                notes.append("page review skipped: the day's budget does not hold it")
                review_step = None
                break
            items = dropped
            notes.append("page review: one ordinary item after the ending given up for it")
        if review_step is not None:
            notes.append(
                f"page review: {review_step.target.kind}:{review_step.target.id} in a line of the page"
                if review_step.target is not None else "page review planned"
            )
    elif page_review:
        notes.append("page review: no unit met earlier is in a line of today's page")

    practised = {target_identity(item.entry.target) for item in items}
    used_targets = list(selection.selected)
    selected_ids = {target_identity(entry.target) for entry in used_targets}
    for item in items:
        identity = target_identity(item.entry.target)
        if identity not in selected_ids:
            selected_ids.add(identity)
            used_targets.append(item.entry)
    omitted = [
        candidate
        for candidate in selection.omitted
        if target_identity(candidate.target) not in practised
    ]
    for entry in selection.selected:
        if entry.demonstrated:
            notes.append(
                f"{target_identity(entry.target)}: already produced independently, not drilled"
            )
    notes.append(
        "practice day: "
        + ", ".join(f"{item.slot}:{item.task.task_type}" for item in sorted(
            items, key=lambda item: ({"warmup": 0, "mid": 1, "post": 2}[item.slot], item.position)
        ))
    )
    primary_reason = next(
        (
            reason
            for reason in (
                reasons_by_identity.get(target_identity(entry.target)) for entry in used_targets
            )
            if reason
        ),
        None,
    )
    if primary_reason:
        notes.append(f"today's targets include {primary_reason}")

    def placed(slot: str) -> list[PracticeItem]:
        return sorted((item for item in items if item.slot == slot), key=lambda item: item.position)

    # WP-93 (W5): Rappel → Règle + Essai (+ Forge) → Scène → Réponse →
    # Bouclé → Fin (→ Lecture). Ordinals are numbered once, at the end.
    steps: list[PlannedStep] = []
    for item in placed("warmup"):
        steps.append(_recall_step(len(steps), item))
    intro_target: TargetRef | None = None
    intro_entry: SelectedTarget | None = None
    reserved = intro_reserve(turns)
    if intro_card and reserved and introduction is not None:
        intro_target = grammar_items.grammar_target(introduction)
        steps.append(
            _rule_step(
                len(steps), brief=introduction, card=intro_card, cost=intro_card_cost,
                scenario=scenario,
            )
        )
        intro_entry = SelectedTarget(
            candidate=LearningCandidate(
                target=intro_target,
                priority_score=0.0,
                due_since_days=0,
                estimated_seconds=0,
                is_new=True,
                source_item_type="grammar",
                metadata={"introduction": True},
            ),
            fit=1.0,
            demonstrated=False,
        )
        for position, (guided, guided_cost) in enumerate(reserved):
            steps.append(
                _recall_step(
                    len(steps),
                    PracticeItem(
                        slot="mid", position=-1 - position, entry=intro_entry,
                        task=guided, cost=guided_cost,
                    ),
                )
            )
        used_targets.append(intro_entry)
        notes.append(
            f"introduction: {intro_target.kind}:{intro_target.id}, rule card + "
            + ", ".join(guided.task_type for guided, _cost in reserved)
            + " (before the scene)"
        )
    elif introduction is not None:
        notes.append("introduction skipped: its rule and guided items did not fit")
    forge_at = len(steps)
    steps.append(
        PlannedStep(
            ordinal=len(steps),
            kind=StepKind.SCENE,
            estimated_seconds=scene_cost,
            public_prompt={
                "setup_fr": scenario.setup_fr,
                "setup_native": scenario.setup_native,
                "objective_native": scenario.objective_native,
                "character_line_fr": scene_line,
                "character_line_audio_url": None,
                "image_url": scenario.image_url,
                "listen_first": bool(shape is DayShape.LISTENING and audio_available),
                # An authored scene's graphic-novel page; absent when it has none.
                **({"panels": [dict(panel) for panel in scenario.panels]} if scenario.panels else {}),
            },
        )
    )

    elicited = [entry.target for entry in selection.selected if entry.is_elicitable]
    # WP-L4 «Emploi» / «Réemploi»: the reply's grammar targets — the new unit
    # first, then a strong due unit asked for as free use (no item today).
    grammar_asked: list[TargetRef] = [intro_target] if intro_target is not None else []
    # WP-130 B: a «Réemploi» is asked only when the reply was priced with it
    # (WP-128 prices one unit's sentence: today's new unit's when there is one).
    reemploi_asked = bool(reemploi) and intro_target is None
    for entry in reemploi_order(entries):
        brief = (entry.candidate.metadata or {}).get("grammar_brief")
        if len(grammar_asked) >= MAX_REPLY_GRAMMAR_TARGETS or not reemploi_asked:
            break
        if (
            entry.target.kind is TargetKind.GRAMMAR
            and isinstance(brief, dict)
            and brief.get("detectors")
            and grammar_items.review_band(brief.get("stability")) == "high"
            and target_identity(entry.target) not in {target_identity(t) for t in grammar_asked}
        ):
            grammar_asked.append(entry.target)
            if target_identity(entry.target) not in {target_identity(e.target) for e in used_targets}:
                used_targets.append(entry)
            break  # one priced «Réemploi» (WP-128 prices one unit's sentence)
    asked_ids = {target_identity(target) for target in grammar_asked}
    elicited = [
        *grammar_asked,
        *(target for target in elicited if target_identity(target) not in asked_ids),
    ]
    respond_task = replace(
        task, max_turns=turns, targets=list(elicited), estimated_seconds=respond_cost
    )
    steps.append(
        PlannedStep(
            ordinal=len(steps),
            kind=StepKind.RESPOND,
            estimated_seconds=respond_cost,
            public_prompt={
                "turn_index": 0,
                "max_turns": turns,
                "repair_allowed": bool(task.repair_allowed),
                "character_id": task.character_id,
                "character_name": task.character_name,
                "character_line_fr": task.opening_line_fr,
                "character_line_audio_url": None,
                "objective_native": task.objective_native,
                "input_modes": supported_input_modes(scenario, input_mode=input_mode),
                "targets": [target.as_public() for target in elicited],
                "help_available": _respond_help(task),
                "letter": _letter_prompt(letter) if shape is DayShape.LETTER else None,
            },
            private_task=respond_task,
        )
    )
    steps.append(
        PlannedStep(
            ordinal=len(steps),
            kind=StepKind.RESOLUTION,
            estimated_seconds=resolution_cost,
            public_prompt={
                "outcome_key": outcome_key,
                "character_line_fr": render_authored_text(
                    scenario.resolution_lines.get(outcome_key, "")
                ),
                "summary_native": render_authored_text(
                    scenario.resolution_summaries.get(outcome_key, "")
                ),
                "image_url": scenario.image_url,
                "chapter_recap_fr": (
                    (chapter_recap_fr or "").strip() or None
                    if shape is DayShape.REPRISE
                    else None
                ),
                "register_note_fr": None,
                "register_reason_native": None,
            },
        )
    )
    if review_step is not None:
        # D7: straight after the ending, while the page is fresh.
        steps.append(replace(review_step, ordinal=len(steps)))
    # WP-109 «Une seule maison»: the episode is never interrupted. The builds and
    # the word from today (WP-93 put them after the reply) follow the ending.
    for item in [*placed("mid"), *placed("post")]:
        steps.append(_recall_step(len(steps), item))
    if desk_step is not None:
        steps.append(desk_step)
    steps.extend(read_steps)

    if forge:
        # WP-S4: La Forge, folded in with the rule — before the scene, so the
        # scene's question is answered next (W5). Sized from what the rest of
        # the day leaves — never the input floor's room (WP-93: a forge is
        # drills, and a longer rhythm buys input, not more drills).
        heard = sum(
            step.estimated_seconds
            for step in steps
            if step.kind is StepKind.RECALL and (step.public_prompt or {}).get("audio_url")
        )
        room = (
            budget_seconds - sum(step.estimated_seconds for step in steps)
            - max(0, input_gap - heard)
        )
        if room < FORGE_MIN_SECONDS and not audio_available:
            # WP-129: on a day without audio no heard item can use the input
            # floor, so it stood empty while the folded forge (owner decision 3;
            # since WP-128 an extension with its own estimate) was dropped from
            # Soutenu (tests/test_forge_integration.py, the A1 café). The forge
            # may then take its *minimum* block from the floor — never more: the
            # day's input share stays WP-93's.
            whole = budget_seconds - sum(step.estimated_seconds for step in steps)
            room = min(whole, FORGE_MIN_SECONDS)
        forge_step = _forge_step(
            forge_at,
            forge=forge,
            introduction=introduction if intro_target is not None else None,
            room=room,
        )
        if forge_step is not None:
            steps.insert(forge_at, forge_step)
            notes.append(f"forge folded in: {forge_step.estimated_seconds}s")
        else:
            notes.append(f"forge skipped: {max(0, room)}s left, {FORGE_MIN_SECONDS}s needed")
    steps = [replace(step, ordinal=index) for index, step in enumerate(steps)]

    if intro_entry is not None:
        items = [
            *items,
            *(
                PracticeItem(slot="mid", position=-1, entry=intro_entry, task=guided, cost=guided_cost)
                for guided, guided_cost in reserved
            ),
        ]
    rationale = _rationale(
        selected=used_targets,
        recalls=[(item.entry, item.task, item.cost, False) for item in items],
        omitted=omitted,
        reasons=dict(selection.omission_reasons),
        candidates=candidates,
        notes=notes,
    )
    plan = PlannedJourney(
        scenario=scenario,
        steps=steps,
        estimated_active_seconds=sum(step.estimated_seconds for step in steps),
        budget_seconds=budget_seconds,
        selected_target_ids=[target_identity(entry.target) for entry in used_targets],
        omitted_candidate_ids=[target_identity(item.target) for item in omitted],
        rationale=rationale,
        day_shape=shape,
        shape_reason=shape_reason,
        practice=True,
        longer_day=forced_intro,
    )
    plan.validate()
    return plan


def graded_interactions(plan: PlannedJourney) -> int:
    """How many things the learner answers today: every recall step that is
    not skipped, plus the reply."""

    return sum(
        1
        for step in plan.steps
        if step.kind is StepKind.RESPOND
        or (step.kind is StepKind.RECALL and step.initial_status is not StepStatus.SKIPPED)
    )


#: WP-93. What share of its budget a paged day plans, before the learner has a
#: planned day at this rhythm to go by — the WP-L9 harness's audio-off floor,
#: rounded down (``tests/test_wp_l9_rhythm_harness.py`` pins that the prior never
#: promises more than the harness plans). The preview says these minutes, not
#: the rhythm's: a day promised at twenty minutes that plans eighteen is the
#: false time promise of the July audit.
EXPECTED_DAY_SHARE: dict[int, float] = {300: 0.95, 600: 0.8, 1200: 0.85, 1800: 0.85}
#: How many of the learner's latest planned days at the same budget the preview
#: reads (their median wins over the prior).
EXPECTED_DAY_SAMPLE = 7


def expected_day_seconds(budget_seconds: int, recent: list[int] | None = None) -> int:
    """WP-93: the minutes a day at this budget will honestly plan.

    The median of the learner's latest planned days at this budget when there
    are any, else :data:`EXPECTED_DAY_SHARE` of the budget; never more than
    the budget.
    """

    budget = int(budget_seconds or DEFAULT_BUDGET_SECONDS)
    samples = sorted(int(value) for value in (recent or []) if value and int(value) > 0)
    if samples:
        middle = len(samples) // 2
        median = samples[middle] if len(samples) % 2 else (samples[middle - 1] + samples[middle]) // 2
        return min(budget, median)
    fitting = [value for value in EXPECTED_DAY_SHARE if value <= budget]
    share = EXPECTED_DAY_SHARE[max(fitting)] if fitting else 1.0
    return min(budget, int(budget * share))


#: WP-128. One card of the word drill: seeing it, typing or turning it, the
#: verdict and «Weiter» (the walk's Timer: 4 s + 0.35 s a typed character +
#: reading + 1.5 s) — about nine seconds.
WORD_CARD_SECONDS = 9
#: WP-128. The drill a day offers at most (``review.tsx``: 30 due cards).
WORD_DRILL_MAX_CARDS = 30
#: WP-128. A Courrier letter: about this many words of French to read (the
#: letter and its answer back), and a reply of two and a half sentences.
LETTER_READ_TOKENS = 60
LETTER_REPLY_SENTENCES = 2.5


def word_drill_seconds(cards: int) -> int:
    """WP-128: the drill's own estimate for ``cards`` waiting cards (0: none)."""

    return max(0, min(int(cards or 0), WORD_DRILL_MAX_CARDS)) * WORD_CARD_SECONDS


def letter_seconds(band: str | None) -> int:
    """WP-128: one Courrier reply's own estimate at ``band`` — read the letter
    and its answer back as prose, compose the reply at the band's pace."""

    key = _band_key(band) or "B1"
    reading = LETTER_READ_TOKENS * reading_prior(key) * page_reading_factor(key)
    compose = LETTER_REPLY_SENTENCES * REPLY_WORDS_FLOOR[key] * compose_seconds_per_word(key)
    return round(reading + compose + 3 * RESPOND_TURN_FIXED_SECONDS)


def input_seconds(plan: PlannedJourney) -> int:
    """WP-93: the day's reading and listening — the page, the heard items (a
    recall step that carries a clip) and the «Lecture». WP-128: and the French
    the reply makes the learner read (:func:`reply_input_seconds`), as the
    planner's floor counts it."""

    total = 0
    band = _band_key(plan.scenario.level_band)
    for step in plan.steps:
        if step.kind in (StepKind.SCENE, StepKind.READ):
            total += step.estimated_seconds
        elif step.kind is StepKind.RECALL and (step.public_prompt or {}).get("audio_url"):
            total += step.estimated_seconds
        elif step.kind is StepKind.RESPOND and isinstance(step.private_task, ResponseTask):
            total += min(
                step.estimated_seconds,
                reply_input_seconds(
                    step.private_task,
                    turns=int(step.private_task.max_turns or 1),
                    spt=reading_prior(band),
                    band=band,
                ),
            )
    return total


def input_share(plan: PlannedJourney) -> float:
    """WP-93: :func:`input_seconds` as a share of the day's budget."""

    return round(input_seconds(plan) / max(1, plan.budget_seconds), 4)


def recall_count(plan: PlannedJourney) -> int:
    return sum(1 for step in plan.steps if step.kind is StepKind.RECALL)


def scene_reuse(
    scenario: ScenarioBrief, *, lemma_keys: Any = None
) -> tuple[int, int]:
    """WP-93: ``(asked, found)`` — the recycled words the director was handed
    (``recycled_lemmas``) and how many of them the page actually prints.

    Read from the draft (plan time) or the stored ``script_payload`` copy the
    story context carries. Matching is whole-word and accent-folded; pass
    ``lemma_keys`` (text → lemma keys, e.g. the :mod:`lexical_coverage`
    lemmatiser) to also count an inflected use. The planner itself stays pure
    and imports no lemmatiser.
    """

    asked = _story_words(scenario, "recycled")
    if not asked:
        return 0, 0
    from app.services.scene_items import contains_surface

    texts = page_texts(scene_page(scenario))
    texts.append(str(scenario.opening_line_fr or ""))
    keys: set[str] = set()
    if lemma_keys is not None:
        keys = {key for text in texts for key in lemma_keys(text)}
    found = sum(
        1
        for lemma in asked
        if any(contains_surface(text, lemma) for text in texts)
        or (lemma_keys is not None and set(lemma_keys(lemma)) <= keys and lemma_keys(lemma))
    )
    return len(asked), found


def _require_plannable(scenario: ScenarioBrief) -> str:
    """Refuse to plan a scene that cannot honestly end."""

    if not (scenario.setup_fr or "").strip():
        raise PlanUnavailable("scene_has_no_setup")
    if not (scenario.objective_native or "").strip():
        raise PlanUnavailable("scene_has_no_objective")
    task = scenario.response_task
    if not (task.opening_line_fr or "").strip():
        raise PlanUnavailable("response_task_has_no_opening_line")
    if not (task.objective_native or "").strip():
        raise PlanUnavailable("response_task_has_no_objective")
    outcome_key = default_outcome_key(scenario)
    if not outcome_key:
        raise PlanUnavailable("scenario_has_no_ending")
    return outcome_key


def _rationale(
    *,
    selected: list[SelectedTarget],
    recalls: list[tuple[SelectedTarget, RecallTask, int, bool]],
    omitted: list[LearningCandidate],
    reasons: dict[str, str],
    candidates: list[LearningCandidate],
    notes: list[str],
) -> str:
    """A short, deterministic, honest account of what today contains.

    Internal (it is not part of the frozen wire contract) and written in
    English for operators and tests; nothing here is rendered to a learner.
    """

    parts: list[str] = []
    if not candidates:
        parts.append(
            "no review item was due and no new anchor was offered, "
            "so today is the scene and the response only"
        )
    else:
        parts.append(
            f"{len(selected)} of {len(candidates)} candidate(s) selected; "
            f"{sum(1 for _e, _t, _c, skipped in recalls if not skipped)} recall step(s) planned"
        )
    unrelated = [
        target_identity(entry.target) for entry in selected if not entry.is_elicitable
    ]
    if unrelated:
        parts.append(
            "rehearsed but not required in the reply (no scene fit): " + ", ".join(sorted(unrelated))
        )
    if omitted:
        grouped: dict[str, list[str]] = {}
        for candidate in omitted:
            identity = target_identity(candidate.target)
            grouped.setdefault(reasons.get(identity, "not_selected"), []).append(identity)
        for reason in sorted(grouped):
            ids = sorted(grouped[reason])
            shown = ", ".join(ids[:3]) + (f" and {len(ids) - 3} more" if len(ids) > 3 else "")
            parts.append(f"{len(ids)} candidate(s) stayed due, untouched ({reason}): {shown}")
    parts.extend(notes)
    return "; ".join(parts)



def _coach_scene_task(brief: dict[str, Any]) -> RecallTask | None:
    """WP-94: the strong unit's coach mini-scene, as the learning adapter built it."""

    scene = brief.get("coach_scene")
    if not isinstance(scene, dict) or not scene.get("accepted_answers"):
        return None
    try:
        return RecallTask(target=grammar_items.grammar_target(brief), **scene)
    except (TypeError, KeyError, ValueError):
        return None

__all__ = [
    "AUDIO_PLAYBACK_SECONDS_PER_TOKEN",
    "DEFAULT_SECONDS_PER_TOKEN",
    "DEMONSTRATED_EVIDENCE_KINDS",
    "DEMONSTRATED_FLAG_KEYS",
    "ELICITATION_FIT_THRESHOLD",
    "MAX_DUE_TARGETS",
    "MAX_NEW_TARGETS",
    "MAX_SELECTED_TARGETS",
    "MIN_PACE_OBSERVATIONS",
    "PLANNER_VERSION",
    "RECALL_ANSWER_SECONDS",
    # WP-L4
    "MAX_REPLY_GRAMMAR_TARGETS",
    "RULE_CARD_SECONDS",
    "grammar_item_seconds",
    "rule_card_seconds",
    "RECALL_FEEDBACK_SECONDS",
    "REPAIR_ALLOWANCE_SECONDS",
    "RESOLUTION_BASE_SECONDS",
    "RESPOND_FEEDBACK_SECONDS",
    "RESPOND_TURN_SECONDS",
    "SCENE_BASE_SECONDS",
    "SECONDS_PER_TOKEN_BOUNDS",
    "STEP_MULTIPLIER_BOUNDS",
    "PacingProfile",
    "PlanUnavailable",
    "SelectedTarget",
    "TargetSelection",
    "build_classify_task",
    # WP-78
    "LISTENING_FILL_ORDER",
    "MATCH_PAIR_COUNT",
    "PRACTICE_FILL_ORDER",
    "practice_fill_order",
    "PRACTICE_MAX_USES_PER_TARGET",
    "PRACTICE_SLOT_FORMATS",
    "PRACTICE_TARGET_ITEMS",
    "QUICK_ANSWER_SECONDS",
    "QUICK_FEEDBACK_SECONDS",
    "PracticeItem",
    "build_listen_tap_task",
    "build_match_pairs_task",
    "build_unscramble_task",
    "fill_practice_items",
    "top_up_from_scene",
    "graded_interactions",
    "practice_entries",
    "practice_task",
    "quick_recall_seconds",
    "scene_sentences",
    "build_recall_task",
    "build_recall_task_in_format",
    "build_rotated_recall_task",
    "build_transform_task",
    "build_word_bank_task",
    "candidate_is_demonstrated",
    "merge_errata_candidates",
    "plan_because",
    "plan_target_reasons",
    "default_outcome_key",
    "plan_journey",
    "public_recall_target",
    "recall_seconds",
    "resolution_seconds",
    "respond_seconds",
    "scenario_fit",
    "scene_seconds",
    "select_plan_targets",
    "supported_input_modes",
    "target_identity",
    "target_reason",
    # WP-128
    "COMPOSE_SECONDS_PER_WORD",
    "PAGE_READING_FACTOR_BY_BAND",
    "READING_PRIOR_SECONDS_PER_TOKEN",
    "REPLY_WORDS_FLOOR",
    "WORD_CARD_SECONDS",
    "compose_seconds_per_word",
    "expected_reply_words",
    "letter_seconds",
    "page_reading_factor",
    "reading_prior",
    "authored_turns",
    "reply_input_seconds",
    "story_alone_seconds",
    "word_drill_seconds",
    # WP-93 / WP-92
    "PAGE_READING_FACTOR",
    "SCENE_LINE_HELP_SECONDS",
    "SCENE_PANEL_SECONDS",
    "TASTE_WORDS_FR",
    "EXPECTED_DAY_SHARE",
    "expected_day_seconds",
    "input_seconds",
    "input_share",
    "page_seconds",
    "page_texts",
    "reading_step_seconds",
    "recall_count",
    "rule_scene_example",
    "scene_page",
    "scene_reuse",
    "story_affordances",
    # WP-75
    "SPOILER_SAFE_OPENING_FR",
    "SPOILER_SIMILARITY",
    "guard_opening_line",
    "line_spoils_reply",
]
