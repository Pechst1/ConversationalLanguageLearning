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
    recall_goal,
    DEFAULT_BUDGET_SECONDS,
    DEFAULT_DAY_SHAPE,
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
    day_shape_rule,
    normalize_answer_text,
    practice_day_shape_rule,
    rhythm_caps,
)
from app.services.journey_day_shapes import (
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
#: A measured pace outside this band is a measurement artefact, not a learner.
SECONDS_PER_TOKEN_BOUNDS = (0.30, 0.70)
#: A measured per-step multiplier is clamped here too. Beyond 1.35 the honest
#: answer is a shorter plan, not a longer estimate.
STEP_MULTIPLIER_BOUNDS = (0.80, 1.35)
#: How many measured days a pace profile needs before it is trusted at all.
#: Under this threshold the bounded defaults are used verbatim. WP-L6: three
#: measured days (was five journeys), the point at which the planner is fed
#: the learner's own pace instead of the priors.
MIN_PACE_OBSERVATIONS = 3

#: Orientation, looking at the art, deciding to begin.
SCENE_BASE_SECONDS = 12
#: WP-93 «Price the input». A page is priced by what is on it: each panel is
#: looked at (its art, then «Suivant»), each line of narration or dialogue may
#: send the learner to a word's help, and the French itself is read at a
#: learner's pace — story text in the target language, not a mixed prompt, so
#: the reading pace is scaled by :data:`PAGE_READING_FACTOR` (0.45 × 2 = 0.9 s
#: a word ≈ 67 words a minute, an A1–A2 reader of L2 prose). A painted panel
#: is looked at before it is read: eight seconds.
SCENE_PANEL_SECONDS = 8
SCENE_LINE_HELP_SECONDS = 2
PAGE_READING_FACTOR = 2.0
#: WP-93 (W5/W11). What the landing page's taste («Romy», then «Commandez un
#: café.») already taught, as in ``web-frontend/lib/onboarding-taste.ts``: the
#: learner answered «Bonjour !» / «Merci !» to Romy and built «Un café, s'il vous
#: plaît» for Margaux. Day 1 never drills them again. Kept in sync by hand: the
#: taste is authored client-side and has no server copy.
TASTE_WORDS_FR: tuple[str, ...] = ("un café", "s'il vous plaît", "bonjour", "merci")
#: Reading the ending, the summary, and closing the day.
RESOLUTION_BASE_SECONDS = 45
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
#: WP-L4 «Réemploi»: at most this many grammar units are asked for in the
#: reply, the day's new unit included (§2.4: ≤ 2 per day).
MAX_REPLY_GRAMMAR_TARGETS = 2

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
    "en": 'It is {count} word(s) long and starts with "{initial}".',
    "de": 'Es ist {count} Wort/Wörter lang und beginnt mit „{initial}“.',
    "fr": "C'est {count} mot(s) et ça commence par « {initial} ».",
}

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
_CLASSIFY_GENDER_LABELS: dict[str, tuple[str, str]] = {
    "en": ("masculine", "feminine"),
    "de": ("maskulin", "feminin"),
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
    "de": 'Sag dasselbe mit "{pronoun}": ändere "{span}".',
    "fr": "Dites la même chose avec « {pronoun} » : changez « {span} ».",
}
_TRANSFORM_HINT: dict[str, str] = {
    "en": 'Only the part with "{span}" changes.',
    "de": 'Nur der Teil mit "{span}" ändert sich.',
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
    "en": "It is {count} word(s) long.",
    "de": "Es sind {count} Wort/Wörter.",
    "fr": "C'est {count} mot(s).",
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

    seconds_per_token: float = DEFAULT_SECONDS_PER_TOKEN
    step_multiplier: float = 1.0
    observations: int = 0

    @property
    def is_trusted(self) -> bool:
        return self.observations >= MIN_PACE_OBSERVATIONS

    def effective_seconds_per_token(self) -> float:
        if not self.is_trusted:
            return DEFAULT_SECONDS_PER_TOKEN
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


def _distractors(target: TargetRef, affordances: list[str], limit: int = 2) -> list[str]:
    """Scene phrases that are plausible here but are not the answer."""

    label = _fold(target.label_fr)
    pool: list[str] = []
    for phrase in affordances:
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
    words = (target.label_fr or "").split()
    initial = words[0][:1] if words and words[0] else "?"
    return _localized(_HINT_TEMPLATE, control_language).format(
        count=len(words) or 1, initial=initial
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
    distractors = _distractors(target, affordances)
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
        options = [
            {"id": "cls_" + _digest(target.id, "masculin")[:8], "text_fr": "masculin"},
            {"id": "cls_" + _digest(target.id, "feminin")[:8], "text_fr": "féminin"},
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

    taken_fr = {_fold(target.label_fr)}
    taken_gloss = {_fold(_glossed(target))}
    partners: list[TargetRef] = []
    ranked = sorted(pool, key=lambda item: _digest(target.id, "partner", target_identity(item)))
    for item in ranked:
        gloss = _glossed(item)
        if gloss is None or target_identity(item) == target_identity(target):
            continue
        if _fold(item.label_fr) in taken_fr or _fold(gloss) in taken_gloss:
            continue
        taken_fr.add(_fold(item.label_fr))
        taken_gloss.add(_fold(gloss))
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
    tokens = chosen.split()
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
        hint_native=_localized(_DICTATION_HINT, control_language).format(count=words),
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
    texts: list[str], *, panels: int, spt: float, multiplier: float, audio: bool
) -> float:
    """WP-93: looking at ``panels`` panels, reading ``texts`` at a learner's
    pace with a word's help now and then, and — when the deployment speaks —
    hearing every line once."""

    orientation = SCENE_PANEL_SECONDS * panels + SCENE_LINE_HELP_SECONDS * len(texts)
    reading = _reading_seconds(spt, *texts) * PAGE_READING_FACTOR
    playback = _tokens(*texts) * AUDIO_PLAYBACK_SECONDS_PER_TOKEN if audio else 0.0
    return orientation * multiplier + reading + playback


def scene_seconds(
    scenario: ScenarioBrief, *, spt: float, multiplier: float, audio: bool = False
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
    panels = scene_page(scenario)
    if not panels:
        reading += _reading_seconds(spt, scenario.opening_line_fr)
        return max(1, round(SCENE_BASE_SECONDS * multiplier + reading))
    texts = page_texts(panels)
    opening = " ".join(str(scenario.opening_line_fr or "").split())
    if opening and not any(_fold(opening) in _fold(text) for text in texts):
        texts.append(opening)
    page = page_seconds(texts, panels=len(panels), spt=spt, multiplier=multiplier, audio=audio)
    return max(1, round(SCENE_BASE_SECONDS * multiplier + reading + page))


def reading_step_seconds(
    reading: dict[str, Any], scenario: ScenarioBrief, *, spt: float, multiplier: float,
    audio: bool,
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
            + page_seconds(texts, panels=panels, spt=spt, multiplier=multiplier, audio=heard)
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
    reading = _reading_seconds(spt, task.instruction_native, task.prompt_fr)
    if task.task_type == str(RecallFormat.DICTATION):
        # WP-91: heard twice, then typed — priced per word of the line.
        words = _tokens(task.solution_fr)
        fixed += words * (2 * AUDIO_PLAYBACK_SECONDS_PER_TOKEN + DICTATION_TYPING_SECONDS_PER_WORD)
    return max(1, round(fixed * multiplier + reading))


def respond_seconds(task: ResponseTask, *, turns: int, spt: float, multiplier: float) -> int:
    """WP-03's authored envelope, floored by an explicit bottom-up model.

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
    fixed = RESPOND_TURN_SECONDS * turns + RESPOND_FEEDBACK_SECONDS + repair
    bottom_up = fixed * multiplier + reading
    authored = float(task.estimated_seconds or 0)
    dropped = max(0, (task.max_turns or MAX_RESPOND_TURNS) - turns)
    authored = max(0.0, authored - RESPOND_TURN_SECONDS * dropped) * multiplier
    return max(1, round(max(authored, bottom_up)))


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
) -> PlannedJourney:
    """Build today's immutable plan.

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
    profile = pace or PacingProfile()
    spt = profile.effective_seconds_per_token()
    multiplier = profile.effective_step_multiplier()
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
    # WP-93: the page is heard as well as read when the deployment speaks —
    # priced from Régulier up; the five-minute day reads it (its audio is a
    # replay the learner may take, not a cost the day promises).
    scene_audio = bool(audio_available) and budget_seconds > RHYTHM_FIVE_MINUTES
    scene_cost = scene_seconds(scenario, spt=spt, multiplier=multiplier, audio=scene_audio)
    resolution_cost = resolution_seconds(scenario, outcome_key, spt=spt, multiplier=multiplier)
    respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
    while scene_cost + respond_cost + resolution_cost > budget_seconds and turns > 1:
        turns -= 1
        respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
        notes.append("response reduced to one turn to keep the plan inside the budget")
    if scene_cost + respond_cost + resolution_cost > budget_seconds and scene_audio:
        # The lines' audio is a replay the learner may skip; a five-minute day
        # that cannot also hold it is priced as read.
        scene_audio = False
        scene_cost = scene_seconds(scenario, spt=spt, multiplier=multiplier)
        notes.append("scene priced without its audio to keep the plan inside the budget")
    if scene_cost + respond_cost + resolution_cost > budget_seconds and (
        spt != DEFAULT_SECONDS_PER_TOKEN or multiplier != 1.0
    ):
        # A measured pace this slow cannot fit a scene that still has a real
        # ending. The plan stays whole and the estimate falls back to the base
        # pace rather than silently deleting the objective or the resolution.
        spt = DEFAULT_SECONDS_PER_TOKEN
        multiplier = 1.0
        scene_cost = scene_seconds(scenario, spt=spt, multiplier=multiplier, audio=scene_audio)
        resolution_cost = resolution_seconds(scenario, outcome_key, spt=spt, multiplier=multiplier)
        respond_cost = respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
        notes.append("measured pace set aside to the base pace: the core plan did not fit")
    if scene_cost + respond_cost + resolution_cost > budget_seconds:
        # Scene, response and resolution are not removable (CONTRACTS §3). If
        # they cannot fit even at the base pace the content is too long to be a
        # five-minute journey, and saying so beats shipping a false promise.
        raise PlanUnavailable("scene_exceeds_budget")

    if practice and not first_day and practice_day_shape_rule(shape, budget_seconds).max_recall > 0:
        return _plan_practice_day(
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
        )

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
        and turns > 1
        and dropped
        and not any(not skipped for _e, _t, _c, skipped in recalls)
    ):
        # WP-93: a page priced by its panels can leave a five-minute day no
        # room for a single recall; the reply gives up its second turn (it
        # keeps its repair) — the trade WP-75 made for day one.
        shorter = respond_seconds(task, turns=turns - 1, spt=spt, multiplier=multiplier)
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
) -> list[str]:
    declared = PRACTICE_SLOT_FORMATS[slot]
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
) -> list[PracticeItem]:
    """Place the day's quick items inside ``headroom`` seconds.

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
                task = grammar_items.review_item(
                    {**brief, "level": scenario.level_band},
                    sentences=list(safe_sentences),
                    language=scenario.control_language,
                    day_key=day_key,
                    meanings=line_meanings(scenario),
                )
                if task is None and grammar_items.review_band(brief.get("stability")) == "high":
                    # WP-94: past 10 days of stability the Rappel is the coach's
                    # mini-scene — free use elicited, not hoped for in the reply.
                    # Built by the learning adapter (``coach_scene`` on the brief).
                    task = _coach_scene_task(brief)
                if task is None or not shape_allows_format(shape, task.task_type):
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


def grammar_uses(items: list[PracticeItem]) -> int:
    return sum(1 for item in items if item.entry.target.kind is TargetKind.GRAMMAR)


def _same_concept_last(items: list[PracticeItem], target: TargetRef) -> bool:
    """Never the same concept back to back (WP-L3's interleaving rule)."""

    return bool(items) and target_identity(items[-1].entry.target) == target_identity(target)


def grammar_item_seconds(task: RecallTask, *, spt: float, multiplier: float) -> int:
    """A grammar item is a quick item whose cards are sentences: they are read."""

    reading = _reading_seconds(spt, *(str(option.get("text_fr") or "") for option in task.options)) \
        if task.task_type == "choice" else 0.0
    return max(1, round(quick_recall_seconds(task, spt=spt, multiplier=multiplier) + reading))


def rule_card_seconds(card: dict[str, Any] | None, *, spt: float, multiplier: float) -> int:
    """The Règle: thirty seconds with the card, plus reading its French."""

    card = card or {}
    texts = [str((card.get("example") or {}).get("fr") or "")]
    contrast = card.get("contrast") or {}
    texts.extend([str(contrast.get("wrong") or ""), str(contrast.get("right") or "")])
    return max(1, round(RULE_CARD_SECONDS * multiplier + _reading_seconds(spt, *texts) * 0.5))


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
    return card, rule_card_seconds(card, spt=spt, multiplier=multiplier), guided


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
    for line in ranked[:wanted_dictations]:
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
        if len(placed) < cap and cost <= room:
            placed.append(dictation)
            room -= cost
            continue
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
    return placed


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
) -> PlannedJourney:
    """WP-78 — warm-ups → scene → reply → builds → a word from today → ending.

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
    # WP-93 «Lecture»: the long rhythms' extra pages (one on Soutenu, two on
    # Intensif), reserved before any drill, in the order offered.
    read_steps: list[PlannedStep] = []
    offers = [reading] if isinstance(reading, dict) else list(reading or [])
    core = scene_cost + respond_seconds(task, turns=turns, spt=spt, multiplier=multiplier)
    for offer in offers:
        if len(read_steps) >= caps.max_reads or budget_seconds < READ_MIN_BUDGET_SECONDS:
            break
        if not isinstance(offer, dict) or str(offer.get("variant") or "") not in (
            "relecture", "coulisses"
        ):
            continue
        heard = bool(offer.get("audio_available", audio_available)) and bool(audio_available)
        cost = reading_step_seconds(offer, scenario, spt=spt, multiplier=multiplier, audio=heard)
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
    # WP-93: the input floor. The page (and the «Lecture») count; what they
    # leave short of the floor is kept free of drills — only a heard item may
    # use it. A page-less (legacy) brief has no page to price and keeps the
    # pre-WP-93 fill.
    input_gap = 0
    if scene_page(scenario):
        floor = round(INPUT_FLOOR_SHARE * budget_seconds)
        input_gap = max(0, floor - scene_cost - read_cost)
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
    intro_identity = (
        target_identity(grammar_items.grammar_target(introduction)) if intro_card else None
    )
    if intro_identity:
        entries = [entry for entry in entries if target_identity(entry.target) != intro_identity]

    def intro_reserve(turn_count: int) -> list[tuple[RecallTask, int]]:
        """The guided items that fit, keeping at least room for the core day."""

        if not intro_card:
            return []
        cost = respond_seconds(task, turns=turn_count, spt=spt, multiplier=multiplier)
        room = (
            budget_seconds - (scene_cost + cost + resolution_cost) - intro_card_cost
            - read_cost - input_gap
        )
        # The rule step and its items share the day's step envelope.
        kept = list(intro_items)[: max(0, min(caps.max_recall, caps.max_steps - 5))]
        while kept and sum(item_cost for _task, item_cost in kept) > room:
            kept.pop()
        return kept if len(kept) >= 2 else []

    def attempt(turn_count: int) -> tuple[int, list[PracticeItem]]:
        cost = respond_seconds(task, turns=turn_count, spt=spt, multiplier=multiplier)
        # WP-S4: the folded forge keeps its room free of quick items; WP-93:
        # so do the «Lecture» and the input floor (only heard items use it).
        headroom = (
            budget_seconds - (scene_cost + cost + resolution_cost) - forge_reserve - read_cost
        )
        reserved = intro_reserve(turn_count)
        max_items: int | None = None
        target_items: int | None = None
        if reserved:
            headroom -= intro_card_cost + sum(item_cost for _task, item_cost in reserved)
            max_items = max(0, min(caps.max_recall, caps.max_steps - 5) - len(reserved))
            target_items = max(0, caps.target_items - len(reserved))
        drills = headroom - input_gap
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
            max_items=max_items,
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
        )

    respond_cost, items = attempt(turns)
    if intro_card and not intro_reserve(turns) and turns > 1 and intro_reserve(turns - 1):
        # The new unit is worth the reply's second turn.
        turns -= 1
        respond_cost, items = attempt(turns)
        notes.append("reply reduced to one turn so the new rule fits the budget")
    if (
        caps.budget_seconds <= RHYTHM_FIVE_MINUTES
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
    if len(items) < rule.min_recall:
        notes.append(
            f"{shape} day downgraded to {DEFAULT_DAY_SHAPE}: "
            f"{len(items)} recall step(s), {rule.min_recall} required"
        )
        shape = DEFAULT_DAY_SHAPE
        shape_reason = "shape_needs_a_recall_step"
        if not items:
            respond_cost, items = attempt(turns)

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
    for entry in entries:
        brief = (entry.candidate.metadata or {}).get("grammar_brief")
        if len(grammar_asked) >= MAX_REPLY_GRAMMAR_TARGETS:
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
    # WP-109 «Une seule maison»: the episode is never interrupted. The builds and
    # the word from today (WP-93 put them after the reply) follow the ending.
    for item in [*placed("mid"), *placed("post")]:
        steps.append(_recall_step(len(steps), item))
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


def input_seconds(plan: PlannedJourney) -> int:
    """WP-93: the day's reading and listening — the page, the heard items (a
    recall step that carries a clip) and the «Lecture»."""

    total = 0
    for step in plan.steps:
        if step.kind in (StepKind.SCENE, StepKind.READ):
            total += step.estimated_seconds
        elif step.kind is StepKind.RECALL and (step.public_prompt or {}).get("audio_url"):
            total += step.estimated_seconds
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
