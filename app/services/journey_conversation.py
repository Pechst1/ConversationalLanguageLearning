"""WP-06 — purposeful conversation and grounded story consequences.

Two responsibilities, both owned by this module and nothing else:

1. :func:`evaluate_response` grades one turn of the daily journey's *respond*
   step. It splits **communicative success** (did the learner get the practical
   thing done?) from **linguistic polish** (was the French tidy?), produces a
   natural in-character reply *before* any correction, and proposes a typed
   story consequence drawn from the learner's actual choice.
2. :func:`apply_story_outcome` writes that consequence into the **existing**
   serial ledger, exactly once, through
   :meth:`SerialThreadService.apply_journey_story_outcome`.

Deliberate boundaries
---------------------

* **No learning policy here.** Evidence classification, correction validation
  and credit belong to WP-05 (``app.services.journey_learning``). This module
  calls ``classify_observation`` / ``select_foreground_correction`` and never a
  scheduler or a credit service.
* **No new memory store.** Consequences land in ``SerialThread.state`` via the
  serial service's own relationship bounds. There is no second character
  memory, no transcript table, and no invented "Romy read your message" event.
* **Never an episode completion.** A journey is a *side scene*. It may add a
  grounded callback; it never advances ``current_episode_index``, never
  completes an episode, never moves an arc stage, and never rolls a season
  over. Stale, not-current, superseded and season-finale episodes are refused
  as anchors by the serial service's existing safeguards; the callback is still
  recorded on the thread, just without an episode reference.
* **Typed consequences only.** ``StoryOutcomeProposal.outcome_key`` must be one
  of ``ResponseTask.allowed_outcomes``. Anything else — including anything a
  model proposes — is rejected and replaced by the declared default.
* **Deterministic by default.** The grader, the reply and the outcome mapping
  are provider-free. A model may *re-dress* the reply and *propose* one of the
  declared outcome keys; it can never widen the outcome vocabulary, write into
  character memory, or invent a correction the learner's text does not support.

Reply provenance
----------------

``ResponseEvaluation`` (frozen in WP-00's ``journey_contracts``) has no field
for "was this line authored or generated", and a scripted line must never be
presented as a live model response. This module therefore stamps the provenance
into the free-text ``failure_reason`` field using a namespaced value and exposes
:func:`reply_source` to read it back. A real failure code always wins over the
provenance marker, because a failed turn carries no live reply anyway.

Turn history
------------

``history`` is a list of plain dicts, oldest first. Each entry is
``{"role": "learner" | "character", "text": str}``; ``"user"`` / ``"assistant"``
are accepted as synonyms, and ``"learner_text"`` is accepted instead of
``"text"``. Only learner entries contribute to the accumulated intents, so a
two-turn exchange ("un café" then "en terrasse") is scored as one met objective.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.journey_content import render_authored_text
from app.services.journey_contracts import (
    FALLBACK_CONTROL_LANGUAGE,
    MAX_RESPOND_TURNS,
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    Correction,
    JourneyEventName,
    ResponseEvaluation,
    ResponseTask,
    ScenarioBrief,
    StoryOutcomeProposal,
    StoryOutcomeRef,
    TaskOutcome,
    effect_source_key,
    normalize_answer_text,
)
from app.services.journey_learning import (
    answer_matches,
    classify_observation,
    correction_relevance,
    fold_for_comparison,
    is_infrastructure_failure,
    select_foreground_correction,
)
from app.services.llm_service import LLMService
from app.services.pilot_events import PilotEventService
from app.services.serial import SerialThreadService

# --------------------------------------------------------------------------
# Module constants
# --------------------------------------------------------------------------

CONVERSATION_POLICY_VERSION = "journey-conversation-v1"
STORY_OUTCOME_EFFECT = "story_outcome"

#: Provenance markers written into ``ResponseEvaluation.failure_reason``.
REPLY_SOURCE_AUTHORED = "reply_source:authored"
REPLY_SOURCE_MODEL = "reply_source:model"

MAX_REPLY_CHARS = 180
MAX_CALLBACK_WORDS = 6
MAX_MODEL_ATTEMPTS = 2

#: Outcomes that are coherent but not a warm success. They never *lower*
#: closeness — a postponement is a real answer, not a punishment.
#: Outcomes that record no success: the learner did not get the task done, so
#: they must not warm the relationship or imply the objective was met.
NEUTRAL_OUTCOMES = frozenset({"meeting_postponed", "romy_reschedules", "not_ordered"})

#: The declared fallback when a proposal names an outcome the brief does not
#: allow, or when nothing in the learner's utterance selects one. Every value
#: is still checked against ``task.allowed_outcomes`` before use.
DEFAULT_OUTCOME_BY_SCENARIO: dict[str, str] = {
    # Integration-owner fix 2026-09-05: the café default used to be
    # "served_at_counter", so a learner who never managed to order was still
    # shown Margaux serving them "what you asked for". The fallback must be the
    # honest ending; a real order still selects one of the three served outcomes.
    CapabilityKey.ORDER_AT_CAFE.value: "not_ordered",
    CapabilityKey.ARRANGE_MEETING.value: "meeting_postponed",
    # Same fix: "romy_waits_at_bar" implies Romy knows you are coming and when,
    # which only holds if the learner actually explained. "romy_reschedules"
    # ("Laisse tomber pour ce soir, on se voit demain") is the honest ending when
    # nothing got across, and is already declared NEUTRAL.
    CapabilityKey.EXPLAIN_DELAY.value: "romy_reschedules",
}


#: The plausible ending when the learner DID get the task across but named no
#: specific choice ("je suis en retard, le métro est bloqué" explains the delay
#: without saying whether Romy should wait, come, or reschedule). This is
#: deliberately separate from DEFAULT_OUTCOME_BY_SCENARIO above: conflating the two
#: is what let a learner who said nothing be shown a successful ending.
SUCCESS_DEFAULT_OUTCOME_BY_SCENARIO: dict[str, str] = {
    CapabilityKey.ORDER_AT_CAFE.value: "served_at_counter",
    CapabilityKey.ARRANGE_MEETING.value: "meeting_weekday_cafe",
    CapabilityKey.EXPLAIN_DELAY.value: "romy_waits_at_bar",
}


def success_outcome_key(task: ResponseTask, scenario_key: str) -> str | None:
    """The ending for a learner who succeeded but chose no specific option.

    Falls back to the neutral default only if the scenario declares no success
    outcome, so this can never invent one that the brief did not allow.
    """

    allowed = [str(key) for key in task.allowed_outcomes if str(key or "").strip()]
    if not allowed:
        return None
    declared = SUCCESS_DEFAULT_OUTCOME_BY_SCENARIO.get(str(scenario_key))
    if declared and declared in allowed:
        return declared
    for key in allowed:
        if key not in NEUTRAL_OUTCOMES:
            return key
    return default_outcome_key(task, scenario_key)


# --------------------------------------------------------------------------
# Text signals
# --------------------------------------------------------------------------

def _normalized(value: str | None) -> str:
    return normalize_answer_text(value)


def _padded(folded: str) -> str:
    return f" {folded} "


def _scan(folded: str, cues: dict[str, str | None]) -> list[str]:
    """Longest-cue-first phrase scan that consumes what it matches.

    Consuming matters: ``un café crème`` must produce one drink, not two, and
    ``ça marche`` must not be read as the Canal market.
    """

    working = _padded(folded)
    found: list[str] = []
    for cue in sorted(cues, key=lambda item: (-len(item), item)):
        needle = f" {cue} "
        if needle not in working:
            continue
        working = working.replace(needle, " ")
        label = cues[cue]
        if label is not None and label not in found:
            found.append(label)
    return found


def _has_any(folded: str, cues: tuple[str, ...]) -> bool:
    padded = _padded(folded)
    return any(f" {cue} " in padded for cue in cues)


_TIME_WORDS = (
    r"(?:vingt[- ]et[- ]une|vingt[- ]deux|vingt[- ]trois|dix[- ]sept|dix[- ]huit|dix[- ]neuf|"
    r"quatorze|quinze|seize|treize|douze|onze|vingt|dix|neuf|huit|sept|six|cinq|quatre|trois|"
    r"deux|une)"
)
_CLOCK_RE = re.compile(
    rf"(?:(?:vers|à|a|pour)\s+)?(?:\b{_TIME_WORDS}\s+heures?"
    r"(?:\s+(?:et\s+demie|et\s+quart|trente|quinze|moins\s+le\s+quart))?"
    r"|\b\d{1,2}\s*h(?:\s*\d{2})?\b|\b\d{1,2}\s*heures?(?:\s*\d{2})?\b|\bmidi\b|\bminuit\b)",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    rf"\bdans\s+(?:\d{{1,2}}|{_TIME_WORDS})\s*(?:minutes?|min\b|heures?)"
    r"|\bdans\s+un\s+quart\s+d['’ ]heure\b|\bdans\s+une\s+demi[- ]heure\b|\btout\s+de\s+suite\b",
    re.IGNORECASE,
)

_DRINK_CUES: dict[str, str | None] = {
    "un cafe creme": "un café crème",
    "cafe creme": "un café crème",
    "un cafe au lait": "un café au lait",
    "un chocolat chaud": "un chocolat chaud",
    "chocolat chaud": "un chocolat chaud",
    "un chocolat": "un chocolat chaud",
    "chocolat": "un chocolat chaud",
    "un cappuccino": "un cappuccino",
    "cappuccino": "un cappuccino",
    "une noisette": "une noisette",
    "noisette": "une noisette",
    "un expresso": "un expresso",
    "un espresso": "un expresso",
    "un express": "un expresso",
    "un deca": "un déca",
    "deca": "un déca",
    "une tisane": "une tisane",
    "tisane": "une tisane",
    "une infusion": "une infusion",
    "infusion": "une infusion",
    "un cafe": "un café",
    "du cafe": "un café",
    "le cafe": "un café",
    "cafe": "un café",
    "un the vert": "un thé vert",
    "un the noir": "un thé noir",
    "the vert": "un thé vert",
    "the noir": "un thé noir",
    "un the": "un thé",
    "du the": "un thé",
    "le the": "un thé",
}

_ENGLISH_DRINK_CUES: dict[str, str] = {
    "a coffee": "un café",
    "coffee": "un café",
    "a tea": "un thé",
    "tea": "un thé",
    "hot chocolate": "un chocolat chaud",
}

_CAFE_PLACE_CUES: dict[str, str | None] = {
    "en terrasse": "terrace",
    "a la terrasse": "terrace",
    "sur la terrasse": "terrace",
    "terrasse": "terrace",
    "a emporter": "takeaway",
    "pour emporter": "takeaway",
    "emporter": "takeaway",
    "dans un gobelet": "takeaway",
    "au bureau": "takeaway",
    "a la maison": "takeaway",
    "au comptoir": "counter",
    "comptoir": "counter",
    "sur place": "counter",
    "au bar": "counter",
    "en salle": "counter",
    "a l interieur": "counter",
    "interieur": "counter",
    "dedans": "counter",
    "ici": "counter",
}
_CAFE_PLACE_LABEL = {
    "terrace": "en terrasse",
    "takeaway": "à emporter",
    "counter": "au comptoir",
}
_CAFE_OUTCOME_BY_PLACE = {
    "terrace": "served_at_terrace",
    "takeaway": "takeaway",
    "counter": "served_at_counter",
}

_CAFE_EXTRA_CUES: tuple[str, ...] = (
    "un verre d eau",
    "de l eau",
    "un sucre",
    "du sucre",
    "l addition",
    "addition",
    "la carte",
    "par carte",
    "carte bancaire",
    "un croissant",
    "croissant",
    "du lait",
    "un citron",
    "aussi",
    "en plus",
    "avec ca",
    "autre chose",
    "egalement",
)

_DAY_CUES: dict[str, str | None] = {
    "lundi": "lundi",
    "mardi": "mardi",
    "mercredi": "mercredi",
    "jeudi": "jeudi",
    "vendredi": "vendredi",
    "samedi": "samedi",
    "dimanche": "dimanche",
    "le week end": "le week-end",
    "week end": "le week-end",
    "weekend": "le week-end",
    "demain": "demain",
    "apres demain": "après-demain",
}
_WEEKEND_DAYS = frozenset({"samedi", "dimanche", "le week-end"})

_MEETING_PLACE_CUES: dict[str, str | None] = {
    "ca marche": None,
    "ca me marche": None,
    "au marche": "market",
    "le marche": "market",
    "du marche": "market",
    "marche": "market",
    "au mistral": "cafe",
    "le mistral": "cafe",
    "mistral": "cafe",
    "au cafe": "cafe",
    "au bar": "cafe",
    "chez toi": "elsewhere",
    "chez moi": "elsewhere",
    "a la maison": "elsewhere",
    "a l ecole": "elsewhere",
    "au parc": "elsewhere",
    "a la station": "elsewhere",
}
_MEETING_PLACE_LABEL = {
    "market": "au marché",
    "cafe": "au Mistral",
    "elsewhere": "là où tu dis",
}

_MEETING_POSTPONE_CUES: tuple[str, ...] = (
    "la semaine prochaine",
    "semaine prochaine",
    "pas cette semaine",
    "une autre fois",
    "on remet",
    "on reporte",
    "reporter",
    "plus tard",
    "je ne peux pas",
    "je peux pas",
    "pas possible",
    "annuler",
    "on annule",
)

_LATE_CUES: tuple[str, ...] = ("retard", "en retard", "du retard", "je suis retarde")
_REASON_CUES: dict[str, str | None] = {
    "le metro": "le métro",
    "metro": "le métro",
    "la ligne": "la ligne",
    "le bus": "le bus",
    "le train": "le train",
    "greve": "la grève",
    "panne": "la panne",
    "bloque": "le blocage",
    "bloquee": "le blocage",
    "coince": "le blocage",
    "coincee": "le blocage",
    "arrete": "le blocage",
    "circulation": "la circulation",
    "embouteillage": "les embouteillages",
    "bouchon": "les embouteillages",
    "trafic": "la circulation",
    "accident": "un accident",
    "le travail": "le travail",
    "au travail": "le travail",
    "boulot": "le boulot",
    "reunion": "la réunion",
    "parce que": "ta raison",
    "a cause": "ta raison",
}

_DELAY_STATION_CUES: tuple[str, ...] = (
    "a la station",
    "viens",
    "viens me chercher",
    "rejoins moi",
    "tu viens",
    "a la gare",
    "jusqu a la station",
)
_DELAY_RESCHEDULE_CUES: tuple[str, ...] = (
    "demain",
    "on remet",
    "on annule",
    "annule",
    "laisse tomber",
    "une autre fois",
    "on reporte",
    "pas ce soir",
    "la prochaine fois",
)
_DELAY_WAIT_CUES: tuple[str, ...] = (
    "attends",
    "attends moi",
    "au bar",
    "commande",
    "patiente",
    "bouge pas",
    "reste",
)

_GREETING_CUES: tuple[str, ...] = (
    "bonjour",
    "bonsoir",
    "salut",
    "coucou",
    "madame",
    "monsieur",
    "re",
)
_POLITE_CUES: tuple[str, ...] = (
    "s il vous plait",
    "s il te plait",
    "svp",
    "merci",
    "je voudrais",
    "j aimerais",
    "pourriez vous",
    "est ce que je pourrais",
    "je pourrais",
)
_APOLOGY_CUES: tuple[str, ...] = (
    "desole",
    "desolee",
    "pardon",
    "excuse moi",
    "excusez moi",
    "je m excuse",
    "navre",
)
_CLOSING_CUES: tuple[str, ...] = (
    "vous fermez",
    "avant la fermeture",
    "vingt minutes",
    "20 minutes",
    "je fais vite",
    "vous allez fermer",
)
_ENTHUSIASM_CUES: tuple[str, ...] = (
    "avec plaisir",
    "ca me va",
    "super",
    "genial",
    "j ai hate",
    "volontiers",
    "content",
    "contente",
    "cool",
)
_CHECK_CUES: tuple[str, ...] = (
    "ca te va",
    "ca te convient",
    "ca marche pour toi",
    "tu peux",
    "tu es libre",
    "t es libre",
    "d accord",
    "ok pour toi",
)
_ALTERNATIVE_CUES: tuple[str, ...] = (
    "sinon",
    "ou alors",
    "ou bien",
    "plutot",
    "si tu preferes",
    "au pire",
)


# --------------------------------------------------------------------------
# Polarity: negation scope, correction and refusal (R-1)
# --------------------------------------------------------------------------
#
# A learner who says « je ne veux pas de café » has communicated something
# real, and the exact opposite of what a bare keyword scan reads. Three things
# must be separated before any cue is believed:
#
# * **scope** — French negation opens at ``ne`` / ``n'`` / ``pas`` / ``sans`` …
#   and runs to the end of its clause, so a cue inside that scope is a *rejected*
#   option, never a chosen one;
# * **correction** — « non, finalement… », « pas X, plutôt Y » retracts what was
#   named before the pivot and promotes what follows it;
# * **refusal** — declining the whole objective is a coherent answer. It must
#   never mint a success, and it must never be answered with "I did not catch
#   that".
#
# Three cue families are deliberately *not* polarity-scoped, because the cue
# itself carries the negation or is polarity-neutral: the postpone/reschedule
# vocabulary (« je ne peux pas », « pas ce soir », « laisse tomber »), the
# politeness/greeting/apology markers, and the delay **reasons** — « il n\'y a
# pas de métro » is a reason given, not a métro refused.

_SENTENCE_SPLIT_RE = re.compile(r"[.!?;:\n]+")
_CLAUSE_SPLIT_RE = re.compile(r",")

#: ``sans doute`` means "probably", not "without": it never opens a scope.
_NEGATION_TRIGGER_RE = re.compile(
    r"(?<![\w\'\u2019])(?:"
    r"n[\'\u2019]"
    r"|sans(?!\s+doute)(?![\w\'\u2019])"
    r"|(?:ne|pas|non|rien|jamais|aucune?|ni|nulle?)(?![\w\'\u2019])"
    r")",
    re.IGNORECASE,
)
_PIVOT_RE = re.compile(
    r"(?<![\w\'\u2019])(?:mais|plut[o\u00f4]t|finalement|en fait|par contre"
    r"|en revanche|au final)(?![\w\'\u2019])",
    re.IGNORECASE,
)

#: A comma closes a negative scope unless the next clause is an elliptical
#: continuation of it (« pas de café, ni de thé »).
_NEGATION_CONTINUATION = frozenset(
    {"ni", "de", "d", "du", "des", "ou", "aucun", "aucune", "pas", "ne", "non",
     "plus", "rien", "jamais"}
)

#: Declining the objective outright. Only consulted when nothing positive was
#: named, so « je ne veux pas de café, je prends un thé » is not a refusal.
_REFUSAL_CUES: tuple[str, ...] = (
    "je ne veux rien",
    "je veux rien",
    "je n en veux pas",
    "je ne veux pas",
    "je veux pas",
    "je ne prends rien",
    "je prends rien",
    "je ne prends pas",
    "rien merci",
    "rien pour moi",
    "non merci",
    "non rien",
    "pas envie",
    "je n ai pas envie",
    "pas aujourd hui",
    "pas maintenant",
    "pas cette fois",
    "je ne peux pas venir",
    "je ne viens pas",
    "je viens pas",
    "laisse tomber",
    "sans moi",
)

#: An alternative offered on a *later* turn adds to the earlier choice instead
#: of replacing it, so "un café" then "ou alors un thé ?" reads as the
#: ambiguity it is. Bare « ou » is excluded: it folds together with « où ».
_CROSS_TURN_ALTERNATIVE_CUES: tuple[str, ...] = (
    "sinon",
    "ou alors",
    "ou bien",
    "ou sinon",
    "au pire",
    "si tu preferes",
    "si vous preferez",
)


@dataclass(frozen=True, slots=True)
class _Span:
    """One run of text with a settled polarity."""

    raw: str
    folded: str
    positive: bool
    corrective: bool


def _span(raw: str, *, positive: bool, corrective: bool) -> _Span:
    return _Span(
        raw=raw, folded=fold_for_comparison(raw), positive=positive, corrective=corrective
    )


def _continues_negation(chunk: str) -> bool:
    tokens = fold_for_comparison(chunk).split()
    return bool(tokens) and tokens[0] in _NEGATION_CONTINUATION


def _split_on_pivots(chunk: str) -> list[tuple[str, bool]]:
    """Split one clause at its correction pivots, flagging what follows one."""

    pieces: list[tuple[str, bool]] = []
    cursor = 0
    follows = False
    for match in _PIVOT_RE.finditer(chunk):
        pieces.append((chunk[cursor : match.start()], follows))
        cursor = match.end()
        follows = True
    pieces.append((chunk[cursor:], follows))
    return [(text, flag) for text, flag in pieces if text.strip()]


def _polarity_spans(text: str) -> list[_Span]:
    """Cut one utterance into positive / negative / corrective runs."""

    spans: list[_Span] = []
    negation_seen = False
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if not sentence.strip():
            continue
        negative = False
        for index, chunk in enumerate(_CLAUSE_SPLIT_RE.split(sentence)):
            if not chunk.strip():
                continue
            if negative and not (index > 0 and _continues_negation(chunk)):
                negative = False
            for piece, follows_pivot in _split_on_pivots(chunk):
                corrective = False
                if follows_pivot and negation_seen:
                    # « …non, finalement X » / « pas Y, plutôt X »: X wins and
                    # whatever filled the same slot before the pivot is dropped.
                    negative = False
                    corrective = True
                match = _NEGATION_TRIGGER_RE.search(piece)
                if match is None:
                    spans.append(
                        _span(piece, positive=not negative, corrective=corrective)
                    )
                    continue
                negation_seen = True
                head = piece[: match.start()]
                if head.strip():
                    spans.append(
                        _span(head, positive=not negative, corrective=corrective)
                    )
                spans.append(
                    _span(piece[match.start() :], positive=False, corrective=False)
                )
                negative = True
    return [span for span in spans if span.folded]


def _scan_polarized(
    spans: list[_Span], cues: dict[str, str | None]
) -> tuple[list[str], list[str]]:
    """``(chosen, rejected)`` for one cue family across an utterance."""

    chosen: list[tuple[int, bool, list[str]]] = []
    rejected: list[str] = []

    def _reject(labels: list[str]) -> None:
        for label in labels:
            if label not in rejected:
                rejected.append(label)

    for index, span in enumerate(spans):
        found = _scan(span.folded, cues)
        if not found:
            continue
        if span.positive:
            chosen.append((index, span.corrective, found))
        else:
            _reject(found)
    corrective_index = max(
        (index for index, corrective, _ in chosen if corrective), default=None
    )
    if corrective_index is not None:
        for index, _corrective, found in chosen:
            if index < corrective_index:
                _reject(found)
        chosen = [item for item in chosen if item[0] >= corrective_index]
    labels: list[str] = []
    for _index, _corrective, found in chosen:
        for label in found:
            if label not in labels:
                labels.append(label)
    return [label for label in labels if label not in rejected], rejected


def _flag_polarized(spans: list[_Span], cues: tuple[str, ...]) -> tuple[bool, bool]:
    """``(asserted, rejected)`` for one boolean cue family."""

    asserted = any(_has_any(span.folded, cues) for span in spans if span.positive)
    denied = any(_has_any(span.folded, cues) for span in spans if not span.positive)
    return asserted, (denied and not asserted)


def _time_in(spans: list[_Span], *, positive: bool):
    for span in spans:
        if span.positive is not positive:
            continue
        clock = _CLOCK_RE.search(span.raw)
        duration = _DURATION_RE.search(span.raw)
        if clock or duration:
            return clock, (duration or clock)
    return None, None


@dataclass(frozen=True, slots=True)
class _Signals:
    """Everything the deterministic grader reads out of one utterance."""

    text: str
    folded: str
    content_tokens: int
    drinks: list[str]
    english_drinks: list[str]
    cafe_places: list[str]
    cafe_extra: bool
    days: list[str]
    weekend_day: bool
    weekday_day: bool
    meeting_places: list[str]
    postpone: bool
    clock_time: bool
    arrival_time: bool
    time_phrase: str | None
    late: bool
    reasons: list[str]
    station: bool
    reschedule: bool
    wait: bool
    greeting: bool
    polite: bool
    apology: bool
    closing: bool
    enthusiasm: bool
    checks: bool
    alternative: bool
    #: Options the learner explicitly ruled out, in this utterance or an
    #: earlier one. They drive the reply and are never chosen as a consequence.
    rejected_drinks: list[str] = field(default_factory=list)
    rejected_cafe_places: list[str] = field(default_factory=list)
    rejected_days: list[str] = field(default_factory=list)
    rejected_meeting_places: list[str] = field(default_factory=list)
    rejected_delay_options: tuple[str, ...] = ()
    rejected_late: bool = False
    rejected_time: bool = False
    #: A clear "no" rather than a garbled attempt: every option this utterance
    #: touched was ruled out and none was chosen. Drives the *reply*.
    refusal: bool = False
    #: The learner said no in words (« je ne veux rien », « pas envie »), not
    #: merely by ruling one option out. Only this may settle a neutral ending,
    #: so "not the terrace" never becomes "so, nothing then".
    explicit_refusal: bool = False
    #: This turn corrected an earlier choice (« finalement… »).
    corrected: bool = False
    #: This turn offers an alternative rather than settling one.
    offers_alternative: bool = False

    @property
    def is_substantive(self) -> bool:
        return self.content_tokens >= 2

    @property
    def has_positive_choice(self) -> bool:
        return bool(
            self.drinks
            or self.cafe_places
            or self.cafe_extra
            or self.days
            or self.meeting_places
            or self.station
            or self.wait
            or self.late
            or self.arrival_time
            or self.reasons
        )


def _signals(value: str | None) -> _Signals:
    text = _normalized(value)
    folded = fold_for_comparison(text)
    spans = _polarity_spans(text)
    positive_spans = [span for span in spans if span.positive]

    drinks, rejected_drinks = _scan_polarized(spans, _DRINK_CUES)
    # « thé » carries an accent the cue table cannot spell every way round. It is
    # added on the side of the span it was actually written in, so « ni café ni
    # thé » rejects both rather than quietly losing one.
    if not any(item.startswith("un thé") for item in drinks + rejected_drinks):
        if any("thé" in span.raw.lower() for span in positive_spans):
            drinks.append("un thé")
        elif any("thé" in span.raw.lower() for span in spans if not span.positive):
            rejected_drinks.append("un thé")
    english_drinks: list[str] = []
    for cue in sorted(_ENGLISH_DRINK_CUES, key=lambda item: (-len(item), item)):
        label = _ENGLISH_DRINK_CUES[cue]
        if label in english_drinks:
            continue
        if any(f" {cue} " in _padded(span.folded) for span in positive_spans):
            english_drinks.append(label)

    cafe_places, rejected_places = _scan_polarized(spans, _CAFE_PLACE_CUES)
    days, rejected_days = _scan_polarized(spans, _DAY_CUES)
    meeting_places, rejected_meeting = _scan_polarized(spans, _MEETING_PLACE_CUES)
    # Reasons stay unscoped on purpose: « il n\'y a pas de métro » explains the
    # delay, it does not decline one.
    reasons = _scan(folded, _REASON_CUES)

    cafe_extra, _ = _flag_polarized(spans, _CAFE_EXTRA_CUES)
    late, rejected_late = _flag_polarized(spans, _LATE_CUES)
    station, rejected_station = _flag_polarized(spans, _DELAY_STATION_CUES)
    wait, rejected_wait = _flag_polarized(spans, _DELAY_WAIT_CUES)
    clock, time_match = _time_in(spans, positive=True)
    _, negated_time = _time_in(spans, positive=False)

    rejected_delay = tuple(
        name
        for name, flag in (("station", rejected_station), ("wait", rejected_wait))
        if flag
    )
    rejected_any = bool(
        rejected_drinks
        or rejected_places
        or rejected_days
        or rejected_meeting
        or rejected_delay
        or rejected_late
    )
    positives_any = bool(
        drinks
        or cafe_places
        or cafe_extra
        or days
        or meeting_places
        or station
        or wait
        or late
        or time_match
        or reasons
    )
    said_no = _has_any(folded, _REFUSAL_CUES)
    refusal = (rejected_any or said_no) and not positives_any

    return _Signals(
        text=text,
        folded=folded,
        content_tokens=len([token for token in folded.split() if len(token) >= 2]),
        drinks=drinks,
        english_drinks=english_drinks,
        cafe_places=cafe_places,
        cafe_extra=cafe_extra,
        days=days,
        weekend_day=any(day in _WEEKEND_DAYS for day in days),
        weekday_day=any(day not in _WEEKEND_DAYS for day in days),
        meeting_places=meeting_places,
        # Postpone/reschedule cues *are* negations; scoping them would delete
        # exactly the phrase that carries the meaning.
        postpone=_has_any(folded, _MEETING_POSTPONE_CUES),
        clock_time=bool(clock),
        arrival_time=bool(time_match),
        time_phrase=time_match.group(0).strip() if time_match else None,
        late=late,
        reasons=reasons,
        station=station,
        reschedule=_has_any(folded, _DELAY_RESCHEDULE_CUES),
        wait=wait,
        greeting=_has_any(folded, _GREETING_CUES),
        polite=_has_any(folded, _POLITE_CUES),
        apology=_has_any(folded, _APOLOGY_CUES),
        closing=_has_any(folded, _CLOSING_CUES),
        enthusiasm=_has_any(folded, _ENTHUSIASM_CUES),
        checks=_has_any(folded, _CHECK_CUES),
        alternative=_has_any(folded, _ALTERNATIVE_CUES),
        rejected_drinks=rejected_drinks,
        rejected_cafe_places=rejected_places,
        rejected_days=rejected_days,
        rejected_meeting_places=rejected_meeting,
        rejected_delay_options=rejected_delay,
        rejected_late=rejected_late,
        rejected_time=bool(negated_time) and not time_match,
        refusal=refusal,
        explicit_refusal=said_no and not positives_any,
        corrected=any(span.corrective for span in spans),
        offers_alternative=_has_any(folded, _CROSS_TURN_ALTERNATIVE_CUES),
    )


#: ``(slot, rejected slot)`` pairs folded across turns.
_CHOICE_SLOTS: tuple[tuple[str, str | None], ...] = (
    ("drinks", "rejected_drinks"),
    ("cafe_places", "rejected_cafe_places"),
    ("days", "rejected_days"),
    ("meeting_places", "rejected_meeting_places"),
    ("english_drinks", None),
    ("reasons", None),
)


def _merge_signals(current: _Signals, previous: list[_Signals]) -> _Signals:
    """Accumulate signals across the learner\'s turns as a running choice.

    A two-turn exchange ("un café" then "en terrasse") is one met objective, so
    intents accumulate. Each turn then *settles* the slots it names and *clears*
    the ones it rejects, so "finalement, pas en terrasse" removes yesterday\'s
    terrace instead of leaving it standing. A turn that offers an alternative
    ("ou alors un thé ?") adds to the standing choice rather than replacing it,
    which is how a cross-turn ambiguity stays visible to the grader.
    """

    if not previous:
        return current
    ordered = [*previous, current]

    slots: dict[str, list[str]] = {name: [] for name, _ in _CHOICE_SLOTS}
    rejected: dict[str, list[str]] = {name: [] for name, _ in _CHOICE_SLOTS}
    late = station = wait = arrival = clock = False
    time_phrase: str | None = None

    for item in ordered:
        for name, rejected_name in _CHOICE_SLOTS:
            chosen = list(getattr(item, name))
            if chosen:
                slots[name] = (
                    list(dict.fromkeys(slots[name] + chosen))
                    if item.offers_alternative
                    else chosen
                )
            denied = list(getattr(item, rejected_name)) if rejected_name else []
            if denied:
                rejected[name] = list(dict.fromkeys(rejected[name] + denied))
                slots[name] = [value for value in slots[name] if value not in denied]
        if item.late:
            late = True
        elif item.rejected_late:
            late = False
        if item.station:
            station = True
        elif "station" in item.rejected_delay_options:
            station = False
        if item.wait:
            wait = True
        elif "wait" in item.rejected_delay_options:
            wait = False
        if item.arrival_time:
            arrival, clock, time_phrase = True, item.clock_time, item.time_phrase
        elif item.rejected_time:
            arrival, clock, time_phrase = False, False, None

    def any_flag(attr: str) -> bool:
        return any(bool(getattr(item, attr)) for item in ordered)

    days = slots["days"]
    merged_positive = bool(
        slots["drinks"]
        or slots["cafe_places"]
        or days
        or slots["meeting_places"]
        or slots["reasons"]
        or station
        or wait
        or late
        or arrival
        or any_flag("cafe_extra")
    )
    return _Signals(
        text=current.text,
        folded=current.folded,
        content_tokens=max(item.content_tokens for item in ordered),
        drinks=slots["drinks"],
        english_drinks=slots["english_drinks"],
        cafe_places=slots["cafe_places"],
        cafe_extra=any_flag("cafe_extra"),
        days=days,
        weekend_day=any(day in _WEEKEND_DAYS for day in days),
        weekday_day=any(day not in _WEEKEND_DAYS for day in days),
        meeting_places=slots["meeting_places"],
        postpone=any_flag("postpone"),
        clock_time=clock,
        arrival_time=arrival,
        time_phrase=time_phrase,
        late=late,
        reasons=slots["reasons"],
        station=station,
        reschedule=any_flag("reschedule"),
        wait=wait,
        greeting=any_flag("greeting"),
        polite=any_flag("polite"),
        apology=any_flag("apology"),
        closing=any_flag("closing"),
        enthusiasm=any_flag("enthusiasm"),
        checks=any_flag("checks"),
        alternative=any_flag("alternative"),
        rejected_drinks=rejected["drinks"],
        rejected_cafe_places=rejected["cafe_places"],
        rejected_days=rejected["days"],
        rejected_meeting_places=rejected["meeting_places"],
        rejected_delay_options=tuple(
            dict.fromkeys(
                option
                for item in ordered
                for option in item.rejected_delay_options
                if not (option == "station" and station)
                and not (option == "wait" and wait)
            )
        ),
        rejected_late=not late and any_flag("rejected_late"),
        rejected_time=not arrival and any_flag("rejected_time"),
        refusal=current.refusal and not merged_positive,
        explicit_refusal=current.explicit_refusal and not merged_positive,
        corrected=any_flag("corrected"),
        offers_alternative=current.offers_alternative,
    )


# --------------------------------------------------------------------------
# Intents
# --------------------------------------------------------------------------

_INTENT_TESTS = {
    "name_a_hot_drink": lambda s: bool(s.drinks),
    "state_where_you_will_drink_it": lambda s: bool(s.cafe_places),
    "add_one_extra_request": lambda s: s.cafe_extra,
    "greet_margaux": lambda s: s.greeting,
    "greet_lila": lambda s: s.greeting,
    "use_a_polite_marker": lambda s: s.polite,
    "acknowledge_closing_time": lambda s: s.closing,
    "name_a_day": lambda s: bool(s.days),
    "propose_a_day": lambda s: bool(s.days),
    "name_a_meeting_place": lambda s: bool(s.meeting_places),
    "propose_a_time": lambda s: s.clock_time,
    "say_you_are_happy_to_come": lambda s: s.enthusiasm,
    "check_it_suits_lila": lambda s: s.checks,
    "offer_an_alternative": lambda s: s.alternative,
    "say_you_are_late": lambda s: s.late,
    "give_the_reason": lambda s: bool(s.reasons),
    "give_a_new_arrival_time": lambda s: s.arrival_time,
    "apologize": lambda s: s.apology,
    "say_roughly_when_you_arrive": lambda s: s.arrival_time,
    "propose_what_romy_should_do": lambda s: s.station or s.reschedule or s.wait,
}


def satisfied_intents(intents: list[str], signals: _Signals) -> list[str]:
    """The subset of ``intents`` this utterance demonstrates."""

    return [name for name in intents if _INTENT_TESTS.get(name, _unknown_intent)(signals)]


def _unknown_intent(signals: _Signals) -> bool:
    """An intent this module has no detector for is not a hidden failure."""

    return signals.is_substantive


# --------------------------------------------------------------------------
# Turn budget
# --------------------------------------------------------------------------

def normal_turns(task: ResponseTask) -> int:
    return max(1, min(int(task.max_turns or MAX_RESPOND_TURNS), MAX_RESPOND_TURNS))


def turn_budget(task: ResponseTask) -> int:
    """Normal turns plus at most one optional repair. Text and voice alike."""

    return normal_turns(task) + (1 if task.repair_allowed else 0)


def remaining_turns(task: ResponseTask, turn_index: int) -> int:
    return max(0, turn_budget(task) - max(0, int(turn_index)) - 1)


def is_repair_turn(task: ResponseTask, turn_index: int) -> bool:
    return task.repair_allowed and int(turn_index) >= normal_turns(task)


# --------------------------------------------------------------------------
# Outcome mapping
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _OutcomeChoice:
    key: str | None
    categories: tuple[str, ...]
    conflict: str | None = None


def _cafe_outcome(signals: _Signals) -> _OutcomeChoice:
    categories = tuple(dict.fromkeys(signals.cafe_places))
    if len(categories) >= 2 or len(dict.fromkeys(signals.drinks)) >= 2:
        return _OutcomeChoice(key=None, categories=categories, conflict="ambiguous_choice")
    if signals.explicit_refusal:
        # A learner who declines is not a learner who failed to speak: the
        # honest, declared ending is "nothing was ordered". It is NEUTRAL, so
        # it warms nothing and claims no success.
        return _OutcomeChoice(key="not_ordered", categories=())
    if categories:
        return _OutcomeChoice(
            key=_CAFE_OUTCOME_BY_PLACE.get(categories[0]), categories=categories
        )
    return _OutcomeChoice(key=None, categories=())


def _meeting_outcome(signals: _Signals) -> _OutcomeChoice:
    categories = tuple(dict.fromkeys(signals.meeting_places))
    if signals.explicit_refusal and not (signals.days or categories):
        return _OutcomeChoice(key="meeting_postponed", categories=())
    if signals.postpone and not (signals.days or categories):
        return _OutcomeChoice(key="meeting_postponed", categories=categories)
    if len(categories) >= 2:
        return _OutcomeChoice(key=None, categories=categories, conflict="ambiguous_choice")
    if signals.postpone and (signals.days or categories):
        return _OutcomeChoice(key=None, categories=categories, conflict="ambiguous_choice")
    if "market" in categories and signals.weekday_day and not signals.weekend_day:
        # Grounded in the scene's required facts: the Canal market opens only at
        # the weekend, so a weekday market plan cannot simply be granted.
        return _OutcomeChoice(
            key="meeting_postponed", categories=categories, conflict="market_is_weekend_only"
        )
    if signals.weekend_day or "market" in categories:
        return _OutcomeChoice(key="meeting_saturday_market", categories=categories)
    if categories or signals.days:
        return _OutcomeChoice(key="meeting_weekday_cafe", categories=categories)
    return _OutcomeChoice(key=None, categories=())


def _delay_outcome(signals: _Signals) -> _OutcomeChoice:
    flags = [
        ("station", signals.station),
        ("reschedule", signals.reschedule),
        ("wait", signals.wait),
    ]
    chosen = [name for name, value in flags if value]
    if len(chosen) >= 2:
        return _OutcomeChoice(key=None, categories=tuple(chosen), conflict="ambiguous_choice")
    if signals.explicit_refusal and not chosen:
        # "Je n'ai pas envie de venir": Romy reschedules. NEUTRAL, so the
        # evening is not booked as a success.
        return _OutcomeChoice(key="romy_reschedules", categories=("reschedule",))
    if signals.rejected_delay_options and not chosen:
        # One option ruled out and none chosen. Romy asks; nothing is settled.
        return _OutcomeChoice(key=None, categories=())
    if signals.station:
        return _OutcomeChoice(key="romy_meets_at_station", categories=("station",))
    if signals.reschedule:
        return _OutcomeChoice(key="romy_reschedules", categories=("reschedule",))
    if signals.wait or signals.arrival_time:
        return _OutcomeChoice(key="romy_waits_at_bar", categories=("wait",))
    return _OutcomeChoice(key=None, categories=())


_OUTCOME_MAPPERS = {
    CapabilityKey.ORDER_AT_CAFE.value: _cafe_outcome,
    CapabilityKey.ARRANGE_MEETING.value: _meeting_outcome,
    CapabilityKey.EXPLAIN_DELAY.value: _delay_outcome,
}


def default_outcome_key(task: ResponseTask, scenario_key: str) -> str | None:
    """The declared fallback outcome, always inside ``allowed_outcomes``."""

    allowed = [str(key) for key in task.allowed_outcomes if str(key or "").strip()]
    if not allowed:
        return None
    declared = DEFAULT_OUTCOME_BY_SCENARIO.get(str(scenario_key))
    if declared and declared in allowed:
        return declared
    return allowed[0]


def coerce_outcome_key(
    candidate: str | None, *, task: ResponseTask, scenario_key: str
) -> str | None:
    """Typed consequences only: an undeclared key never reaches the story."""

    allowed = {str(key) for key in task.allowed_outcomes if str(key or "").strip()}
    value = str(candidate or "").strip()
    if value and value in allowed:
        return value
    if value:
        logger.warning(
            "journey_conversation_rejected_outcome_key",
            scenario_key=str(scenario_key),
            proposed=value,
            allowed=sorted(allowed),
        )
    return default_outcome_key(task, scenario_key)


# --------------------------------------------------------------------------
# Authored replies
# --------------------------------------------------------------------------

_VOUS_VIOLATIONS = (" tu ", " toi ", " ton ", " ta ", " tes ", " t es ")
_TU_VIOLATIONS = (" vous ", " votre ", " vos ")
_NEUTRAL_REPLY = "Très bien, je note."


def _register_ok(reply: str, register: str) -> bool:
    folded = _padded(fold_for_comparison(reply))
    violations = _VOUS_VIOLATIONS if register == "vous" else _TU_VIOLATIONS
    return not any(token in folded for token in violations)


def _capitalize(value: str) -> str:
    return value[:1].upper() + value[1:] if value else value


#: The three drinks and the three places Margaux can actually offer. Used to
#: answer a rejection with the options that are *left* instead of repeating the
#: one the learner just turned down.
_CAFE_DRINK_MENU: tuple[str, ...] = ("un café", "un thé", "un chocolat chaud")
_CAFE_PLACE_MENU: tuple[str, ...] = ("au comptoir", "en terrasse", "à emporter")
_MEETING_PLACE_MENU: tuple[str, ...] = ("au marché", "au Mistral")


def _without_article(label: str) -> str:
    for article in ("un ", "une ", "du ", "de la ", "le ", "la "):
        if label.startswith(article):
            return label[len(article) :]
    return label


def _remaining(menu: tuple[str, ...], rejected: list[str]) -> list[str]:
    ruled_out = set(rejected)
    return [item for item in menu if item not in ruled_out]


def _rejected_place_labels(signals: _Signals) -> list[str]:
    """Café place *categories* the learner ruled out, as spoken labels."""

    return [
        _CAFE_PLACE_LABEL[category]
        for category in signals.rejected_cafe_places
        if category in _CAFE_PLACE_LABEL
    ]


def _cafe_rejection_head(signals: _Signals) -> str | None:
    """« pas de café », « pas en terrasse » — what the learner ruled out."""

    bits: list[str] = []
    if signals.rejected_drinks and not signals.drinks:
        bits.append(f"pas de {_without_article(signals.rejected_drinks[0])}")
    if signals.rejected_cafe_places and not signals.cafe_places:
        label = _CAFE_PLACE_LABEL.get(signals.rejected_cafe_places[0])
        if label:
            bits.append(f"pas {label}")
    if not bits:
        return None
    return f"D'accord, {' et '.join(bits)}."


def _cafe_reply(signals: _Signals, choice: _OutcomeChoice, met: bool) -> str:
    drink = _capitalize(signals.drinks[0]) if signals.drinks else None
    if choice.conflict == "ambiguous_choice":
        if len(dict.fromkeys(signals.drinks)) >= 2:
            options = list(dict.fromkeys(signals.drinks))[:2]
            return f"Alors, {options[0]} ou {options[1]} ? Dites-moi."
        labels = [_CAFE_PLACE_LABEL[cat] for cat in choice.categories[:2]]
        return f"Alors, c'est {labels[0]} ou {labels[1]} ?"
    place = _CAFE_PLACE_LABEL.get(choice.categories[0]) if choice.categories else None
    if met and drink and place:
        tail = {
            "en terrasse": "Je vous apporte ça, la terrasse est couverte.",
            "à emporter": "Je vous mets ça dans un gobelet.",
            "au comptoir": "Je vous prépare ça tout de suite.",
        }[place]
        extra = " Et je note votre demande." if signals.cafe_extra else ""
        return f"{drink} {place}, très bien. {tail}{extra}"
    if drink and place:
        return f"{drink} {place}, c'est noté. Il vous faut autre chose avec ?"
    head = _cafe_rejection_head(signals)
    if drink:
        options = _remaining(_CAFE_PLACE_MENU, _rejected_place_labels(signals))
        if head and len(options) >= 2:
            return f"{drink}, très bien. {head} C'est {options[0]} ou {options[1]} ?"
        return f"{drink}, très bien. Vous vous installez au comptoir, en terrasse, ou c'est à emporter ?"
    if place:
        options = _remaining(_CAFE_DRINK_MENU, signals.rejected_drinks)
        if head and len(options) >= 2:
            return f"{head} {_capitalize(place)}, donc. {_capitalize(options[0])} ou {options[1]} ?"
        return f"D'accord, {place}. Et je vous sers quoi ? Un café, un thé, un chocolat chaud ?"
    if head:
        # The learner said no to something specific. Offering it back would be
        # contradicting them; offer what is left instead.
        options = _remaining(_CAFE_DRINK_MENU, signals.rejected_drinks)
        if len(options) >= 2:
            return f"{head} Je vous sers {options[0]} ou {options[1]} ?"
        return f"{head} Qu'est-ce que je vous sers, alors ?"
    if signals.refusal:
        return "Très bien, pas de souci. Je suis là si vous changez d'avis."
    if signals.english_drinks:
        return (
            "Ah, en français s'il vous plaît. Un café, un thé, un chocolat chaud ?"
        )
    return "Pardon, je n'ai pas bien saisi. Qu'est-ce que je vous sers ?"


def _meeting_reply(signals: _Signals, choice: _OutcomeChoice, met: bool) -> str:
    day = signals.days[0] if signals.days else None
    place = _MEETING_PLACE_LABEL.get(choice.categories[0]) if choice.categories else None
    if choice.conflict == "market_is_weekend_only":
        return "Ah, le marché n'ouvre que le week-end. Samedi, ou plutôt au Mistral en semaine ?"
    if choice.conflict == "ambiguous_choice":
        if len(choice.categories) >= 2:
            labels = [_MEETING_PLACE_LABEL[cat] for cat in choice.categories[:2]]
            return f"Alors, {labels[0]} ou {labels[1]} ? Décide, les deux me vont."
        return "Attends, on se voit ou on remet ? Dis-moi."
    if choice.key == "meeting_postponed" and not day:
        return "Bon, pas cette semaine alors. On se rappelle."
    if met and day and place:
        when = f"{day} {signals.time_phrase}" if signals.time_phrase else day
        return f"{_capitalize(when)} {place}, ça marche. Je note."
    if day and place:
        return f"{_capitalize(day)} {place}, ok. Vers quelle heure ?"
    if day:
        options = _remaining(_MEETING_PLACE_MENU, [
            _MEETING_PLACE_LABEL[category]
            for category in signals.rejected_meeting_places
            if category in _MEETING_PLACE_LABEL
        ])
        if len(options) == 1:
            return f"{_capitalize(day)}, d'accord. {_capitalize(options[0])}, alors ?"
        return f"{_capitalize(day)}, d'accord. Et on se retrouve où ? Au marché ou au Mistral ?"
    if place:
        return f"{_capitalize(place)}, ça me va. Et quel jour ? Le marché n'ouvre que le week-end."
    if signals.rejected_days:
        return f"Pas {signals.rejected_days[0]}, ok. Tu peux quel jour, alors ?"
    if signals.rejected_meeting_places:
        options = _remaining(_MEETING_PLACE_MENU, [
            _MEETING_PLACE_LABEL[category]
            for category in signals.rejected_meeting_places
            if category in _MEETING_PLACE_LABEL
        ])
        if len(options) == 1:
            return f"Bon, pas là-bas. {_capitalize(options[0])} alors, et quel jour ?"
    return "Attends, j'ai pas suivi. Tu peux quel jour, et on se retrouve où ?"


def _delay_reply(signals: _Signals, choice: _OutcomeChoice, met: bool) -> str:
    reason = signals.reasons[0] if signals.reasons else None
    if choice.conflict == "ambiguous_choice":
        return "Alors je t'attends ou je viens à la station ? Choisis."
    if signals.rejected_delay_options and not (
        signals.station or signals.wait or signals.reschedule
    ):
        return "Bon, alors je fais quoi ? Je t'attends ou je viens te chercher ?"
    if met or choice.key:
        if choice.key == "romy_meets_at_station":
            return "Bouge pas, je viens te chercher à la station."
        if choice.key == "romy_reschedules":
            return "Ok, laisse tomber pour ce soir. On se voit demain."
        if signals.time_phrase:
            head = f"{_capitalize(reason)}, d'accord." if reason else "D'accord."
            return f"{head} {_capitalize(signals.time_phrase)}, ça va. Je t'attends au bar."
        head = f"{_capitalize(reason)}, encore." if reason else "Bon."
        return f"{head} Je commande un truc et je t'attends au bar."
    if signals.rejected_late and not signals.late:
        return "Ah, tu n'es pas en retard ? Alors tu arrives quand ?"
    if signals.late and not reason:
        return "En retard, ok. Mais qu'est-ce qui se passe ?"
    if reason and not signals.late:
        return f"{_capitalize(reason)}, d'accord. Donc tu arrives quand ?"
    if signals.late and reason:
        return f"{_capitalize(reason)}, ok. Tu arrives vers quelle heure ?"
    return "Attends, j'ai rien compris. Qu'est-ce qui se passe ?"


_REPLY_BUILDERS = {
    CapabilityKey.ORDER_AT_CAFE.value: _cafe_reply,
    CapabilityKey.ARRANGE_MEETING.value: _meeting_reply,
    CapabilityKey.EXPLAIN_DELAY.value: _delay_reply,
}


def _authored_reply(
    *, scenario_key: str, register: str, signals: _Signals, choice: _OutcomeChoice, met: bool
) -> str:
    builder = _REPLY_BUILDERS.get(str(scenario_key))
    if builder is None:
        return _NEUTRAL_REPLY
    reply = " ".join(builder(signals, choice, met).split())[:MAX_REPLY_CHARS]
    if not _register_ok(reply, register):
        logger.warning(
            "journey_conversation_reply_register_violation",
            scenario_key=str(scenario_key),
            register=register,
        )
        return _NEUTRAL_REPLY
    return reply


# --------------------------------------------------------------------------
# Deterministic corrections
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _CorrectionRule:
    pattern: re.Pattern[str]
    replacement: str
    note_native: str
    register: str | None = None


_CORRECTION_RULES: tuple[_CorrectionRule, ...] = (
    _CorrectionRule(
        pattern=re.compile(r"\bje prend\b", re.IGNORECASE),
        replacement="je prends",
        note_native="With je, prendre ends in -s: je prends.",
    ),
    _CorrectionRule(
        pattern=re.compile(r"\bje voudrai\b(?!s)", re.IGNORECASE),
        replacement="je voudrais",
        note_native="The polite form is je voudrais, with an -s.",
    ),
    _CorrectionRule(
        pattern=re.compile(r"\bje peut\b", re.IGNORECASE),
        replacement="je peux",
        note_native="With je, pouvoir is peux, not peut.",
    ),
    _CorrectionRule(
        pattern=re.compile(r"\bvous avet\b", re.IGNORECASE),
        replacement="vous avez",
        note_native="With vous, avoir is avez.",
    ),
    _CorrectionRule(
        pattern=re.compile(r"\bje suis en retarde\b", re.IGNORECASE),
        replacement="je suis en retard",
        note_native="The noun is retard, with no final -e.",
    ),
    _CorrectionRule(
        pattern=re.compile(r"\btu peux\b", re.IGNORECASE),
        replacement="vous pouvez",
        note_native="Margaux still uses vous with you here, so use vous pouvez.",
        register="vous",
    ),
    _CorrectionRule(
        # The span deliberately excludes the apostrophe: a quoted span must
        # survive verbatim in the raw answer as well as the normalized one, and
        # iOS types U+2019 there.
        pattern=re.compile(r"\bte pla[iî]t\b", re.IGNORECASE),
        replacement="vous plaît",
        note_native="This scene stays on vous, so it is s'il vous plaît.",
        register="vous",
    ),
)


def _preserve_case(span: str, replacement: str) -> str:
    if span[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _rule_corrections(text: str, register: str) -> list[Correction]:
    found: list[Correction] = []
    for rule in _CORRECTION_RULES:
        if rule.register is not None and rule.register != register:
            continue
        match = rule.pattern.search(text)
        if not match:
            continue
        span = match.group(0)
        found.append(
            Correction(
                span_fr=span,
                corrected_fr=_preserve_case(span, rule.replacement),
                note_native=rule.note_native,
            )
        )
    return found


def _english_drink_corrections(text: str, signals: _Signals) -> list[Correction]:
    found: list[Correction] = []
    seen: set[str] = set()
    for cue in sorted(_ENGLISH_DRINK_CUES, key=lambda item: (-len(item), item)):
        label = _ENGLISH_DRINK_CUES[cue]
        if label not in signals.english_drinks or label in seen:
            continue
        match = re.search(rf"\b{re.escape(cue)}\b", text, re.IGNORECASE)
        if match:
            seen.add(label)
            found.append(
                Correction(
                    span_fr=match.group(0),
                    corrected_fr=label,
                    note_native="Order in French: name the drink the French way.",
                )
            )
    return found


def _scene_fact_corrections(
    *, scenario_key: str, text: str, choice: _OutcomeChoice
) -> list[Correction]:
    if scenario_key != CapabilityKey.ARRANGE_MEETING.value:
        return []
    if choice.conflict != "market_is_weekend_only":
        return []
    match = re.search(r"\b(lundi|mardi|mercredi|jeudi|vendredi)\b", text, re.IGNORECASE)
    if not match:
        return []
    return [
        Correction(
            span_fr=match.group(0),
            corrected_fr=_preserve_case(match.group(0), "samedi"),
            note_native="The Canal market only opens at the weekend.",
        )
    ]


# --------------------------------------------------------------------------
# Callback facts
# --------------------------------------------------------------------------

def build_callback_fact(*, scenario_key: str, signals: _Signals, outcome_key: str) -> str | None:
    """A short, grounded fact — never the learner's raw sentence."""

    key = str(scenario_key)
    parts: list[str] = []
    if key == CapabilityKey.ORDER_AT_CAFE.value:
        if signals.drinks:
            parts.append(signals.drinks[0])
        place = {
            "served_at_terrace": "en terrasse",
            "takeaway": "à emporter",
            "served_at_counter": "au comptoir",
        }.get(outcome_key)
        if place:
            parts.append(place)
    elif key == CapabilityKey.ARRANGE_MEETING.value:
        if outcome_key == "meeting_postponed":
            parts.append("rendez-vous reporté")
        else:
            if signals.days:
                parts.append(signals.days[0])
            place = "au marché" if outcome_key == "meeting_saturday_market" else "au Mistral"
            parts.append(place)
    elif key == CapabilityKey.EXPLAIN_DELAY.value:
        if signals.reasons:
            parts.append(signals.reasons[0])
        parts.append(
            {
                "romy_waits_at_bar": "Romy attend au bar",
                "romy_reschedules": "reporté à demain",
                "romy_meets_at_station": "Romy vient à la station",
            }.get(outcome_key, "")
        )
    phrase = " ".join(part for part in parts if part).strip()
    words = phrase.split()
    if not words:
        return None
    return " ".join(words[:MAX_CALLBACK_WORDS])


# --------------------------------------------------------------------------
# Optional model layer (never widens the outcome vocabulary)
# --------------------------------------------------------------------------

_MODEL_SYSTEM_PROMPT = (
    "You voice one character in a short French practice scene for a beginner. "
    "Reply in French, in character, in at most two short sentences. "
    "Never break character, never teach, never correct the learner in the reply. "
    "Return only JSON."
)

_MODEL_USER_TEMPLATE = """Character: {character_name} ({character_id}) at {location_name}.
Register with the learner: {register} (never switch).
Practical objective: {objective_native}
Scene facts that must stay true:
{required_facts}
Allowed outcome keys (choose exactly one, copy it verbatim):
{allowed_outcomes}
The deterministic grader already decided:
  task_outcome = {task_outcome}
  outcome_key = {outcome_key}
Learner's latest message: {learner_text}

Return JSON: {{"reply_fr": "...", "outcome_key": "..."}}
Do not invent an outcome key. Do not add any other field."""


def _conversation_llm() -> LLMService | None:
    if not settings.ATELIER_LLM_ENABLED:
        return None
    try:
        return LLMService()
    except ValueError:
        return None


def _record_event(
    db: Session,
    event_type: str,
    *,
    user_id: UUID | None,
    scenario_key: str,
    payload: dict[str, Any],
    cost_usd: float = 0.0,
) -> None:
    try:
        PilotEventService(db).record(
            event_type,
            user_id=user_id,
            entity_type="daily_journey_conversation",
            entity_id=scenario_key,
            payload=payload,
            cost_usd=cost_usd,
        )
    except Exception as exc:  # pragma: no cover - instrumentation never breaks a turn
        logger.warning("journey conversation event {} not recorded: {}", event_type, exc)


def _parse_model_reply(
    content: str, *, task: ResponseTask, scenario_key: str, register: str
) -> tuple[str, str | None] | None:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    try:
        payload = json.loads(text)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    # A model may propose a reply and one declared outcome key. Anything else it
    # tries to write — an arbitrary memory field, a new outcome key, a
    # relationship delta — is dropped here and never reaches the story.
    extras = set(payload) - {"reply_fr", "outcome_key"}
    if extras:
        logger.warning(
            "journey_conversation_model_extra_fields",
            scenario_key=str(scenario_key),
            fields=sorted(str(item) for item in extras),
        )
        return None
    reply = payload.get("reply_fr")
    if not isinstance(reply, str) or not reply.strip():
        return None
    reply = " ".join(reply.split())
    if len(reply) > MAX_REPLY_CHARS or not _register_ok(reply, register):
        return None
    proposed = payload.get("outcome_key")
    if proposed is not None and not isinstance(proposed, str):
        return None
    allowed = {str(key) for key in task.allowed_outcomes}
    if proposed and str(proposed) not in allowed:
        logger.warning(
            "journey_conversation_model_rejected_outcome",
            scenario_key=str(scenario_key),
            proposed=str(proposed),
        )
        return None
    return reply, (str(proposed) if proposed else None)


def _model_reply(
    db: Session,
    *,
    user: User,
    scenario: ScenarioBrief,
    task: ResponseTask,
    register: str,
    required_facts: list[str],
    learner_text: str,
    task_outcome: TaskOutcome,
    outcome_key: str | None,
) -> tuple[str, str | None] | None:
    llm = _conversation_llm()
    if llm is None:
        return None
    prompt = _MODEL_USER_TEMPLATE.format(
        character_name=task.character_name,
        character_id=task.character_id,
        location_name=scenario.location_name,
        register=register,
        objective_native=task.objective_native,
        required_facts="\n".join(f"- {fact}" for fact in required_facts) or "- (none)",
        allowed_outcomes="\n".join(f"- {key}" for key in task.allowed_outcomes) or "- (none)",
        task_outcome=str(task_outcome),
        outcome_key=outcome_key or "(none yet)",
        learner_text=learner_text,
    )
    for attempt in range(1, MAX_MODEL_ATTEMPTS + 1):
        try:
            result = llm.generate_chat_completion(
                [{"role": "user", "content": prompt}],
                system_prompt=_MODEL_SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=300,
            )
        except Exception as exc:  # noqa: BLE001 - a provider failure falls back, never raises
            _record_event(
                db,
                JourneyEventName.PROVIDER_FAILED,
                user_id=user.id,
                scenario_key=str(scenario.scenario_key),
                payload={"attempt": attempt, "error": exc.__class__.__name__},
            )
            continue
        parsed = _parse_model_reply(
            result.content, task=task, scenario_key=str(scenario.scenario_key), register=register
        )
        if parsed is None:
            continue
        _reply, proposed = parsed
        if proposed is not None and outcome_key is not None and proposed != outcome_key:
            # R-2: the key is declared, but it is not the one the learner's own
            # words grounded. Reply and consequence are validated *together* —
            # keeping the right key while showing the reply that belongs to the
            # wrong one would still tell the learner they got something they
            # never asked for. Retry once inside the same bounded budget, then
            # fall back to the authored line.
            _record_event(
                db,
                JourneyEventName.GENERATION_FALLBACK,
                user_id=user.id,
                scenario_key=str(scenario.scenario_key),
                payload={
                    "attempt": attempt,
                    "stage": "conversation_reply",
                    "reason": "outcome_conflicts_with_learner_choice",
                    "grounded": outcome_key,
                    "proposed": proposed,
                },
            )
            logger.warning(
                "journey_conversation_model_conflicting_outcome",
                scenario_key=str(scenario.scenario_key),
                grounded=outcome_key,
                proposed=proposed,
            )
            continue
        return parsed
    _record_event(
        db,
        JourneyEventName.GENERATION_FALLBACK,
        user_id=user.id,
        scenario_key=str(scenario.scenario_key),
        payload={"attempts": MAX_MODEL_ATTEMPTS, "stage": "conversation_reply"},
    )
    return None


# --------------------------------------------------------------------------
# Public helpers
# --------------------------------------------------------------------------

def reply_source(evaluation: ResponseEvaluation) -> str:
    """``"authored" | "model" | "none"`` for the reply on this evaluation.

    The frozen ``ResponseEvaluation`` has no provenance field, so the marker
    travels in ``failure_reason``. A scripted line must never be shown as a live
    model response, so the caller can and should read this.
    """

    marker = str(evaluation.failure_reason or "")
    if marker == REPLY_SOURCE_MODEL:
        return "model"
    if marker == REPLY_SOURCE_AUTHORED:
        return "authored"
    return "none"


def story_outcome_source_key(journey_id: UUID | str) -> str:
    """The one idempotency key for a journey's story consequence."""

    return effect_source_key(journey_id=journey_id, effect=STORY_OUTCOME_EFFECT)


def unscored_response_evaluation(
    *, assistance: AssistanceLevel, reason: str
) -> ResponseEvaluation:
    """An infrastructure failure: no turn consumed, no lapse, no mutation."""

    return ResponseEvaluation(
        outcome=TaskOutcome.UNSCORED,
        assistance=assistance,
        observations=[],
        character_reply_fr=None,
        correction=None,
        consequence=None,
        needs_repair=False,
        turn_consumed=False,
        pending=True,
        failure_reason=reason,
    )


# --------------------------------------------------------------------------
# Endings that name what the learner actually chose (WP-12 defect D-2)
# --------------------------------------------------------------------------

#: Native glosses for every drink the café grader can recognise, so the recap
#: names the drink the learner ordered in their own language. German glosses are
#: accusative objects ("Margaux hat dir *einen Tee* serviert").
_DRINK_NATIVE: dict[str, dict[str, str]] = {
    "un café": {"en": "coffee", "de": "einen Kaffee", "fr": "un café"},
    "un café crème": {"en": "café crème", "de": "einen Milchkaffee", "fr": "un café crème"},
    "un café au lait": {
        "en": "café au lait", "de": "einen Milchkaffee", "fr": "un café au lait",
    },
    "un chocolat chaud": {
        "en": "hot chocolate", "de": "eine heiße Schokolade", "fr": "un chocolat chaud",
    },
    "un cappuccino": {"en": "cappuccino", "de": "einen Cappuccino", "fr": "un cappuccino"},
    "une noisette": {"en": "noisette", "de": "eine Noisette", "fr": "une noisette"},
    "un expresso": {"en": "espresso", "de": "einen Espresso", "fr": "un expresso"},
    "un déca": {"en": "decaf", "de": "einen entkoffeinierten Kaffee", "fr": "un déca"},
    "une tisane": {"en": "herbal tea", "de": "einen Kräutertee", "fr": "une tisane"},
    "une infusion": {"en": "herbal tea", "de": "einen Kräutertee", "fr": "une infusion"},
    "un thé": {"en": "tea", "de": "einen Tee", "fr": "un thé"},
    "un thé vert": {"en": "green tea", "de": "einen grünen Tee", "fr": "un thé vert"},
    "un thé noir": {"en": "black tea", "de": "einen schwarzen Tee", "fr": "un thé noir"},
}

#: The A2 café ending may only claim an extra request when one was made.
_CAFE_EXTRA_FR = ", avec ce que vous avez demandé"
_CAFE_EXTRA_NATIVE: dict[str, str] = {
    "en": " and brought the extra thing you asked for",
    "de": " und deine zusätzliche Bitte erfüllt",
    "fr": " et a ajouté ce que tu avais demandé",
}

#: Native adverbials for the days the meeting grader can recognise, carrying the
#: preposition the language needs ("on Saturday", "am Samstag", "samedi").
_DAY_NATIVE: dict[str, dict[str, str]] = {
    "lundi": {"en": "on Monday", "de": "am Montag", "fr": "lundi"},
    "mardi": {"en": "on Tuesday", "de": "am Dienstag", "fr": "mardi"},
    "mercredi": {"en": "on Wednesday", "de": "am Mittwoch", "fr": "mercredi"},
    "jeudi": {"en": "on Thursday", "de": "am Donnerstag", "fr": "jeudi"},
    "vendredi": {"en": "on Friday", "de": "am Freitag", "fr": "vendredi"},
    "samedi": {"en": "on Saturday", "de": "am Samstag", "fr": "samedi"},
    "dimanche": {"en": "on Sunday", "de": "am Sonntag", "fr": "dimanche"},
    "le week-end": {"en": "at the weekend", "de": "am Wochenende", "fr": "le week-end"},
    "demain": {"en": "tomorrow", "de": "morgen", "fr": "demain"},
    "après-demain": {
        "en": "the day after tomorrow", "de": "übermorgen", "fr": "après-demain",
    },
}


def _signals_for_texts(learner_texts: list[str] | None) -> _Signals | None:
    """Merge everything the learner said this turn-set, newest turn winning."""

    texts = [str(item) for item in (learner_texts or []) if str(item or "").strip()]
    if not texts:
        return None
    return _merge_signals(
        _signals(texts[-1]), [_signals(item) for item in texts[:-1]]
    )


def _native(table: dict[str, dict[str, str]], key: str, language: str) -> str:
    entry = table.get(key) or {}
    return entry.get(language) or entry.get("en") or ""


def resolution_slots(
    scenario: ScenarioBrief,
    outcome_key: str,
    *,
    learner_texts: list[str] | None = None,
) -> dict[str, str]:
    """The details an authored ending may name, taken from what was actually said.

    Empty when nothing identifiable was said: :func:`render_authored_text` then
    falls back to the authored wording that names no drink and no day, which is
    the whole point — an ending must never invent a choice the learner did not
    make (WP-12 defect D-2).
    """

    signals = _signals_for_texts(learner_texts)
    if signals is None:
        return {}
    language = str(scenario.control_language or FALLBACK_CONTROL_LANGUAGE)
    key = str(scenario.scenario_key)
    slots: dict[str, str] = {}
    if key == CapabilityKey.ORDER_AT_CAFE.value:
        if signals.drinks:
            drink = signals.drinks[0]
            slots["drink"] = drink
            slots["drink_cap"] = _capitalize(drink)
            slots["drink_native"] = _native(_DRINK_NATIVE, drink, language)
        if signals.cafe_extra and str(outcome_key) != "not_ordered":
            slots["extra"] = _CAFE_EXTRA_FR
            slots["extra_native"] = _CAFE_EXTRA_NATIVE.get(
                language, _CAFE_EXTRA_NATIVE["en"]
            )
    elif key == CapabilityKey.ARRANGE_MEETING.value:
        if signals.days and str(outcome_key) != "meeting_postponed":
            day = signals.days[0]
            slots["day"] = day
            slots["day_cap"] = _capitalize(day)
            slots["day_native"] = _native(_DAY_NATIVE, day, language)
    return {name: value for name, value in slots.items() if value}


def resolution_line(
    scenario: ScenarioBrief,
    outcome_key: str,
    *,
    learner_texts: list[str] | None = None,
) -> str | None:
    """The ending line, rendered for what this learner actually did."""

    template = scenario.resolution_lines.get(outcome_key)
    if template is None:
        return None
    return render_authored_text(
        template,
        resolution_slots(scenario, outcome_key, learner_texts=learner_texts),
    )


def resolution_summary(
    scenario: ScenarioBrief,
    outcome_key: str,
    *,
    learner_texts: list[str] | None = None,
) -> str | None:
    """The native recap of the ending, rendered the same way as the line."""

    template = scenario.resolution_summaries.get(outcome_key)
    if template is None:
        return None
    return render_authored_text(
        template,
        resolution_slots(scenario, outcome_key, learner_texts=learner_texts),
    )


# --------------------------------------------------------------------------
# 1. evaluate_response
# --------------------------------------------------------------------------

def _learner_history_texts(history: list[dict] | None) -> list[str]:
    """The learner's own previous utterances, oldest first.

    Three shapes are accepted so the caller does not have to reshape its own
    transcript: ``{"role": "learner"|"user", "text": ...}``, an explicit
    ``{"learner_text": ...}``, and the turn-pair form WP-02 persists,
    ``{"learner": ..., "character": ...}``.
    """

    texts: list[str] = []
    for entry in history or []:
        if not isinstance(entry, dict):
            continue
        text = entry.get("learner") or entry.get("learner_text")
        if text is None:
            role = str(entry.get("role") or "learner").lower()
            if role not in {"learner", "user"}:
                continue
            text = entry.get("text")
        if isinstance(text, str) and text.strip():
            texts.append(text)
    return texts


def _scene_register(scenario: ScenarioBrief) -> str:
    from app.services.journey_content import scenario_content_rules

    rules = scenario_content_rules(
        scenario.scenario_key,
        level_band=scenario.level_band,
        content_version=scenario.content_version,
    )
    return rules.register if rules is not None else "vous"


def _scene_required_facts(scenario: ScenarioBrief) -> list[str]:
    from app.services.journey_content import scenario_required_facts

    return scenario_required_facts(
        scenario.scenario_key,
        level_band=scenario.level_band,
        content_version=scenario.content_version,
    )


def _grade(required: list[str], hit: list[str]) -> TaskOutcome:
    known = [name for name in required if name in _INTENT_TESTS]
    if not known:
        return TaskOutcome.MET if hit else TaskOutcome.NOT_YET
    hits = len([name for name in hit if name in known])
    if hits >= len(known):
        return TaskOutcome.MET
    if hits >= max(1, len(known) - 1):
        return TaskOutcome.PARTIALLY_MET
    return TaskOutcome.NOT_YET


def _observations_for(
    *,
    task: ResponseTask,
    answer: AttemptAnswer,
    text: str,
    assistance: AssistanceLevel,
    correction: Correction | None,
) -> list[Any]:
    observations = []
    for target in task.targets:
        used = answer_matches(text, [target.label_fr])
        if used:
            observations.append(
                classify_observation(
                    target=target,
                    opportunity="open_production",
                    is_correct=True,
                    assistance=assistance,
                    modality=answer.mode,
                    elicited=True,
                    learner_text=text,
                )
            )
            continue
        # The learner met the objective another way. A response task never
        # obliges one specific word, so an unused target is not a lapse
        # (CONTRACTS §7) — unless a validated correction shows they reached for
        # it and got the form wrong.
        attempted = correction is not None and correction_relevance(correction, [target]) > 0
        observation = classify_observation(
            target=target,
            opportunity="open_production",
            is_correct=False,
            assistance=assistance,
            modality=answer.mode,
            elicited=attempted,
            learner_text=text,
            corrected_text=correction.corrected_fr if attempted and correction else None,
        )
        if observation is not None:
            observations.append(observation)
    return [item for item in observations if item is not None]


def evaluate_response(
    db: Session,
    *,
    user: User,
    scenario: ScenarioBrief,
    task: ResponseTask,
    answer: AttemptAnswer,
    turn_index: int,
    assistance: AssistanceLevel,
    history: list[dict] | None = None,
) -> ResponseEvaluation:
    """Grade one bounded turn of the purposeful response step.

    Communicative success is decided from the declared intents, never from an
    exact string match: an understandable paraphrase with a form error is a met
    objective plus one optional correction, not a failed one. The character
    reply is produced first; the correction is an addition to it.
    """

    if scenario.story_context:
        from app.services.living_story import evaluate_turn
        return evaluate_turn(db, user=user, scenario=scenario, task=task, answer=answer, turn_index=turn_index, assistance=assistance, history=history)

    scenario_key = str(scenario.scenario_key)

    if is_infrastructure_failure(answer):
        # Microphone, transcription or a mid-turn timeout. The learner keeps
        # their answer and their turn, and nothing is booked against them.
        return unscored_response_evaluation(
            assistance=assistance, reason="voice_transcription_unavailable"
        )
    if answer.is_blank:
        return unscored_response_evaluation(assistance=assistance, reason="empty_answer")

    text = _normalized(answer.text)
    register = _scene_register(scenario)
    current = _signals(text)
    previous = [_signals(item) for item in _learner_history_texts(history)]
    combined = _merge_signals(current, previous)

    mapper = _OUTCOME_MAPPERS.get(scenario_key)
    choice = mapper(combined) if mapper else _OutcomeChoice(key=None, categories=())

    required = [str(item) for item in task.required_intents]
    optional = [str(item) for item in task.optional_intents]
    hit = satisfied_intents(required + optional, combined)
    outcome = _grade(required, hit)

    # Material ambiguity — two conflicting choices in one turn, or a plan that
    # contradicts a scene fact — blocks the consequence but not the
    # conversation: the character asks which one, and the learner keeps a turn.
    blocked = choice.conflict is not None
    if blocked and outcome is TaskOutcome.MET:
        outcome = TaskOutcome.PARTIALLY_MET

    over_budget = remaining_turns(task, turn_index) <= 0
    needs_repair = outcome is not TaskOutcome.MET and not over_budget

    candidates = [
        *_rule_corrections(text, register),
        *_english_drink_corrections(text, current),
        *_scene_fact_corrections(scenario_key=scenario_key, text=text, choice=choice),
    ]
    # WP-05 owns validation: a span the learner never wrote, a no-op, or a
    # re-punctuation is rejected before it can be shown or booked.
    correction, _background = select_foreground_correction(
        user=user, learner_text=text, candidates=candidates, targets=task.targets
    )

    reply = _authored_reply(
        scenario_key=scenario_key,
        register=register,
        signals=combined,
        choice=choice,
        met=outcome is TaskOutcome.MET,
    )
    provenance = REPLY_SOURCE_AUTHORED

    # No consequence while a repair is still owed. After that: a choice the
    # learner actually made always lands, even when the objective was not met —
    # declining a meeting is a real answer. The *declared default* only lands
    # when something got across; an utterance that communicated nothing resolves
    # through the plan's authored ending without warming the relationship.
    resolved_key: str | None = None
    if not needs_repair:
        if choice.key is not None:
            resolved_key = coerce_outcome_key(choice.key, task=task, scenario_key=scenario_key)
        elif outcome is not TaskOutcome.NOT_YET:
            # The learner got the task across but named no specific option: show a
            # success ending, not the neutral "nothing happened" one.
            resolved_key = coerce_outcome_key(
                success_outcome_key(task, scenario_key), task=task, scenario_key=scenario_key
            )

    generated = _model_reply(
        db,
        user=user,
        scenario=scenario,
        task=task,
        register=register,
        required_facts=_scene_required_facts(scenario),
        learner_text=text,
        task_outcome=outcome,
        outcome_key=resolved_key,
    )
    if generated is not None:
        generated_reply, proposed = generated
        if proposed is None or proposed == resolved_key:
            reply = generated_reply
            provenance = REPLY_SOURCE_MODEL

    consequence: StoryOutcomeProposal | None = None
    if resolved_key is not None:
        consequence = StoryOutcomeProposal(
            outcome_key=resolved_key,
            callback_fr=build_callback_fact(
                scenario_key=scenario_key, signals=combined, outcome_key=resolved_key
            ),
            character_id=task.character_id or scenario.character_id,
        )

    observations = _observations_for(
        task=task, answer=answer, text=text, assistance=assistance, correction=correction
    )

    return ResponseEvaluation(
        outcome=outcome,
        assistance=assistance,
        observations=observations,
        character_reply_fr=reply,
        correction=correction,
        consequence=consequence,
        needs_repair=needs_repair,
        turn_consumed=not over_budget,
        pending=False,
        failure_reason=provenance,
    )


# --------------------------------------------------------------------------
# 2. apply_story_outcome
# --------------------------------------------------------------------------

def _thread_for(db: Session, *, user: User, scenario: ScenarioBrief) -> SerialThread | None:
    if scenario.is_authored_fallback or not scenario.serial_thread_id:
        return None
    try:
        thread_id = UUID(str(scenario.serial_thread_id))
    except (TypeError, ValueError):
        return None
    thread = db.get(SerialThread, thread_id)
    if thread is None or thread.user_id != user.id or thread.status != "active":
        return None
    return thread


def _canonical_character(
    service: SerialThreadService,
    thread: SerialThread,
    *,
    proposed: str | None,
    scenario: ScenarioBrief,
) -> str | None:
    """Only a character that already exists in this thread's world bible.

    Character memory is not an open key space: a proposal naming someone the
    world bible has never heard of falls back to the scene's own canonical
    character, and never mints a new relationship entry.
    """

    for candidate in (proposed, scenario.character_id):
        name = str(candidate or "").strip()
        if not name:
            continue
        if service._cast_member(thread, name) is not None:  # noqa: SLF001 - same package
            return name
        logger.warning(
            "journey_conversation_unknown_character",
            proposed=name,
            thread_id=str(thread.id),
        )
    return None


def apply_story_outcome(
    db: Session,
    *,
    user: User,
    journey_id: UUID,
    scenario: ScenarioBrief,
    proposal: StoryOutcomeProposal,
    source_key: str,
) -> StoryOutcomeRef:
    """Write the accepted consequence into the existing serial ledger, once.

    Never commits — the daily-journey state machine owns the transaction. The
    outcome key is re-checked against the brief here as well as at proposal
    time, so a replayed or hand-built proposal cannot smuggle an undeclared key
    into character memory.
    """

    expected_prefix = f"journey:{journey_id}:"
    if not str(source_key or "").startswith(expected_prefix):
        raise ValueError(
            f"story outcome source key {source_key!r} does not belong to journey {journey_id}"
        )

    task = scenario.response_task
    outcome_key = coerce_outcome_key(
        proposal.outcome_key, task=task, scenario_key=str(scenario.scenario_key)
    )
    if outcome_key is None:
        return StoryOutcomeRef(
            applied=False, outcome_key=str(proposal.outcome_key or ""), callback_fr=None
        )

    thread = _thread_for(db, user=user, scenario=scenario)
    if thread is None:
        # A purely authored side scene is not part of the serial ledger. It
        # still resolves the journey; it simply writes nothing to the story.
        return StoryOutcomeRef(
            applied=False,
            outcome_key=outcome_key,
            serial_thread_id=None,
            serial_episode_id=None,
            callback_fr=proposal.callback_fr,
        )

    service = SerialThreadService(db)
    character_id = _canonical_character(
        service, thread, proposed=proposal.character_id, scenario=scenario
    )
    if character_id is None:
        return StoryOutcomeRef(
            applied=False,
            outcome_key=outcome_key,
            serial_thread_id=str(thread.id),
            serial_episode_id=None,
            callback_fr=proposal.callback_fr,
        )

    summary = resolution_summary(scenario, outcome_key) or resolution_line(
        scenario, outcome_key
    )
    result = service.apply_journey_story_outcome(
        thread,
        source_key=source_key,
        outcome_key=outcome_key,
        character_id=character_id,
        summary=summary,
        callback=proposal.callback_fr,
        episode_id=scenario.serial_episode_id,
        success=outcome_key not in NEUTRAL_OUTCOMES,
        beat_line=f"Daily journey · {scenario.title_fr}. Outcome: {summary or outcome_key}",
    )
    return StoryOutcomeRef(
        applied=bool(result.get("applied")),
        outcome_key=str(result.get("outcome_key") or outcome_key),
        serial_thread_id=str(thread.id),
        serial_episode_id=result.get("episode_id"),
        callback_fr=result.get("callback"),
        already_applied=bool(result.get("already_applied")),
    )


__all__ = [
    "CONVERSATION_POLICY_VERSION",
    "NEUTRAL_OUTCOMES",
    "REPLY_SOURCE_AUTHORED",
    "REPLY_SOURCE_MODEL",
    "STORY_OUTCOME_EFFECT",
    "apply_story_outcome",
    "build_callback_fact",
    "coerce_outcome_key",
    "default_outcome_key",
    "evaluate_response",
    "is_repair_turn",
    "normal_turns",
    "remaining_turns",
    "reply_source",
    "render_authored_text",
    "resolution_line",
    "resolution_slots",
    "resolution_summary",
    "satisfied_intents",
    "story_outcome_source_key",
    "turn_budget",
    "unscored_response_evaluation",
]
