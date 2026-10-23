"""La Forge's drills: how an item is posed, and the recommender that picks one.

A rung says *what* a learner proves about a rule (recognise … free use); a
*drill* says *how* the item is posed. The owner's overhaul (2026-10-18: more
varied, more fun, more personal, faster learning) gives several rungs more
than one drill, so a séance never plays the same twice and each learner gets
the drill their own mistakes call for:

============== ================================ ==================================
rung           drills                           the item it poses
============== ================================ ==================================
recognise      ``choice``                       a fill: pick the form
discriminate   ``judge`` · ``rafale``           a classify; a burst of four
build          ``tiles`` · ``dictation`` ·      a word bank, read or heard; a
               ``typed``                        fill whose form is typed
transform      ``spot`` · ``mine`` ·            a repair: tap the wrong word; the
               ``rewrite``                      learner's own saved mistake; retype
produce        ``write``                        a sentence
free use       ``scene``                        the coach's two-line scene
============== ================================ ==================================

Grading never changes with the drill: a drill is presentation over items the
séance already grades by key (a typed fill is a fill, a dictation is a word
bank, a spot and a mine are repairs). Only the burst grades four judgements in
one attempt (its ``exercise_id`` ends in ``id+id+id+id``).

**The recommender** (:func:`rank_drills`) scores every drill of the slot's rung:

* the learner's own mistakes (:func:`learner_signal`, their saved errors of the
  last weeks, read as kinds by :func:`error_kind`): an accent slip calls for
  typing, a wrong form for spotting or typing, a word-order slip for tiles or
  dictation, a missing word for a rewrite, a missed judgement for a burst;
* the rule's momentum in this séance: after a miss (or on a reprise) the
  scaffolded drill, after two right in a row a stretch;
* variety: never the drill just served, fewer repeats;
* the learner's own sentences: a saved mistake of this rule comes back as
  «Ta phrase» (at most :data:`MINE_PER_SEANCE` per séance).

Deterministic for one séance (a hash breaks ties), so a resumed séance agrees
with itself.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from app.core.forge import OUTCOME_CORRECT, Rung, clamp_rung
from app.services.answer_acceptance import fold_typography, is_real_correction, strip_accents

DRILL_CHOICE = "choice"
DRILL_JUDGE = "judge"
DRILL_RAFALE = "rafale"
DRILL_TILES = "tiles"
DRILL_DICTATION = "dictation"
DRILL_TYPED = "typed"
DRILL_SPOT = "spot"
DRILL_MINE = "mine"
DRILL_REWRITE = "rewrite"
DRILL_WRITE = "write"
DRILL_SCENE = "scene"

#: Each rung's drills, the canonical (scaffolded) one first.
DRILLS_BY_RUNG: dict[Rung, tuple[str, ...]] = {
    Rung.RECOGNISE: (DRILL_CHOICE,),
    Rung.DISCRIMINATE: (DRILL_JUDGE, DRILL_RAFALE),
    Rung.BUILD: (DRILL_TILES, DRILL_DICTATION, DRILL_TYPED),
    Rung.TRANSFORM: (DRILL_SPOT, DRILL_MINE, DRILL_REWRITE),
    Rung.PRODUCE: (DRILL_WRITE,),
    Rung.FREE_USE: (DRILL_SCENE,),
}
ALL_DRILLS = frozenset(drill for drills in DRILLS_BY_RUNG.values() for drill in drills)

#: Where a drill's item lives in the exercise set: ``(round, mode)``.
DRILL_POOL: dict[str, tuple[str, str]] = {
    DRILL_CHOICE: ("recognize", "fill"),
    DRILL_JUDGE: ("recognize", "classify"),
    DRILL_RAFALE: ("recognize", "classify"),
    DRILL_TILES: ("recognize", "word_bank"),
    DRILL_DICTATION: ("recognize", "word_bank"),
    DRILL_TYPED: ("recognize", "fill"),
    DRILL_SPOT: ("transform", "rewrite"),
    DRILL_MINE: ("transform", "rewrite"),
    DRILL_REWRITE: ("transform", "rewrite"),
    DRILL_WRITE: ("sentence", "sentence"),
    DRILL_SCENE: ("conversation", "conversation"),
}

#: The drill that holds a learner's hand on its rung, and the ones that stretch.
SCAFFOLDED = frozenset({DRILL_CHOICE, DRILL_JUDGE, DRILL_TILES, DRILL_SPOT})
STRETCH = frozenset({DRILL_RAFALE, DRILL_DICTATION, DRILL_TYPED, DRILL_REWRITE})

#: A burst is four judgements in one go.
RAFALE_SIZE = 4
#: The learner's own sentences, at most this many per séance.
MINE_PER_SEANCE = 2
#: A typed form is short: a word or three, never a clause.
TYPED_MAX_WORDS = 3
TYPED_MAX_CHARS = 32
#: A dictation is a sentence one hears in one go.
DICTATION_MIN_WORDS = 3
DICTATION_MAX_WORDS = 14
#: A mistake one can spot is a word or three; longer is a rewrite.
SPOT_MAX_WORDS = 3
#: An own sentence worth bringing back: a line, not a word and not a paragraph.
MINE_MIN_WORDS = 2
MINE_MAX_WORDS = 14

# ---------------------------------------------------------------------------
# What kind of mistake a saved error is
# ---------------------------------------------------------------------------

KIND_ACCENT = "accent"
KIND_FORM = "form"
KIND_ORDER = "order"
KIND_MISSING = "missing"
KIND_EXTRA = "extra"
KIND_WORD = "word"
KIND_JUDGE = "judge"
ERROR_KINDS = (KIND_ACCENT, KIND_FORM, KIND_ORDER, KIND_MISSING, KIND_EXTRA, KIND_WORD, KIND_JUDGE)

#: Below this share of words in common, a "correction" is another answer
#: altogether (a learner who tapped two tiles), not a slip to learn from.
MIN_LOCAL_RATIO = 0.34

#: The grammar's own small words: articles, pronouns, the auxiliaries' forms,
#: prepositions, negation. Swapping one for another is a wrong form (à/au,
#: avait/était, le/la), never a vocabulary slip.
GRAMMAR_WORDS = frozenset(
    {
        # articles, determiners, partitives
        "le", "la", "les", "l'", "un", "une", "des", "du", "de", "d'", "au", "aux",
        "ce", "cet", "cette", "ces", "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
        "notre", "nos", "votre", "vos", "leur", "leurs",
        # pronouns
        "je", "j'", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "me", "m'", "te",
        "t'", "se", "s'", "lui", "y", "en", "moi", "toi", "eux", "qui", "que", "qu'", "dont", "où",
        # être and avoir
        "suis", "es", "est", "sommes", "êtes", "sont", "étais", "était", "étions", "étiez",
        "étaient", "serai", "seras", "sera", "serons", "serez", "seront", "serais", "serait",
        "serions", "seriez", "seraient", "sois", "soit", "soyons", "soyez", "soient", "été",
        "ai", "as", "a", "avons", "avez", "ont", "avais", "avait", "avions", "aviez", "avaient",
        "aurai", "auras", "aura", "aurons", "aurez", "auront", "aurais", "aurait", "aurions",
        "auriez", "auraient", "aie", "aies", "ait", "ayons", "ayez", "aient", "eu",
        # prepositions, negation, small links
        "à", "dans", "sur", "sous", "pour", "par", "avec", "chez", "sans", "depuis",
        "pendant", "ne", "n'", "pas", "plus", "jamais", "rien", "personne", "si",
    }
)


def _same_stem(left: str, right: str) -> bool:
    """Two spellings of one word: another ending, an accent, an agreement."""

    bare_left, bare_right = strip_accents(left), strip_accents(right)
    if bare_left == bare_right:
        return True
    common = len(os.path.commonprefix([bare_left, bare_right]))
    return common >= 3 and common >= min(len(bare_left), len(bare_right)) - 3


def _unelided(words: Sequence[str]) -> list[str]:
    """«j'ai» → «j'», «ai»: an elided pair is two grammar words, not one new word."""

    out: list[str] = []
    for word in words:
        head, mark, tail = word.partition("'")
        if mark and head and tail and f"{head}'" in GRAMMAR_WORDS:
            out.extend((f"{head}'", tail))
        else:
            out.append(word)
    return out


def _is_form_change(left: Sequence[str], right: Sequence[str]) -> bool:
    if not left or not right:
        return False
    left, right = _unelided(left), _unelided(right)
    if all(word in GRAMMAR_WORDS for word in (*left, *right)):
        return True
    if len(left) != len(right):
        return False
    return all(
        _same_stem(a, b) or (a in GRAMMAR_WORDS and b in GRAMMAR_WORDS)
        for a, b in zip(left, right, strict=True)
    )


def error_kind(learner: Any, corrected: Any) -> str | None:
    """What kind of slip one saved error is, from its two halves.

    ``accent`` (the same words, only accents differ), ``order`` (the same
    words in another order), ``missing`` / ``extra`` (a word left out / one
    too many), ``form`` (another form of the same word, or one grammar word
    for another: avait/était, le/la), ``word`` (another word). ``None`` when
    there is nothing to read: a side is missing, nothing changed, or the
    "correction" is another answer altogether (a few tiles tapped at random).
    """

    left = fold_typography(learner)
    right = fold_typography(corrected)
    if not left or not right or left == right:
        return None
    if strip_accents(left) == strip_accents(right):
        return KIND_ACCENT
    words_left, words_right = left.split(), right.split()
    if len(words_left) > 1 and sorted(words_left) == sorted(words_right):
        return KIND_ORDER
    matcher = SequenceMatcher(a=words_left, b=words_right, autojunk=False)
    if max(len(words_left), len(words_right)) >= 3 and matcher.ratio() < MIN_LOCAL_RATIO:
        return None
    changes = [op for op in matcher.get_opcodes() if op[0] != "equal"]
    tags = {op[0] for op in changes}
    if tags == {"insert"}:
        return KIND_MISSING
    if tags == {"delete"}:
        return KIND_EXTRA
    pairs = [
        (words_left[i1:i2], words_right[j1:j2])
        for tag, i1, i2, j1, j2 in changes
        if tag == "replace"
    ]
    if pairs and all(_is_form_change(a, b) for a, b in pairs):
        return KIND_FORM
    return KIND_WORD


# ---------------------------------------------------------------------------
# The learner's signal
# ---------------------------------------------------------------------------

#: A saved error's weight halves every this many days.
SIGNAL_HALF_LIFE_DAYS = 14.0
#: The look-back of the signal, and how many errors it reads at most.
SIGNAL_WINDOW_DAYS = 60
SIGNAL_MAX_ERRORS = 150
#: This much weighted evidence makes the signal fully trusted.
SIGNAL_FULL_WEIGHT = 4.0


@dataclass(frozen=True, slots=True)
class LearnerSignal:
    """What kinds of mistakes a learner makes lately, as shares of one."""

    kinds: Mapping[str, float] = field(default_factory=dict)
    #: How much the shares can be trusted, 0 … 1 (a single slip is a hint).
    weight: float = 0.0

    @classmethod
    def from_mistakes(cls, mistakes: Iterable[tuple[Any, Any, float]]) -> LearnerSignal:
        """``(learner, corrected, weight)`` rows → the signal."""

        totals: dict[str, float] = {}
        for learner, corrected, weight in mistakes:
            kind = error_kind(learner, corrected)
            if kind is None or weight <= 0:
                continue
            totals[kind] = totals.get(kind, 0.0) + float(weight)
        total = sum(totals.values())
        if total <= 0:
            return cls()
        return cls(
            kinds={kind: value / total for kind, value in totals.items()},
            weight=min(1.0, total / SIGNAL_FULL_WEIGHT),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"kinds": {kind: round(share, 3) for kind, share in self.kinds.items()}, "weight": round(self.weight, 3)}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def learner_signal(db: Any, user: Any, *, now: datetime | None = None) -> LearnerSignal:
    """The learner's saved errors of the last weeks, read as kinds of slip.

    Recent errors weigh more (half-life :data:`SIGNAL_HALF_LIFE_DAYS`), a
    repeated one more (up to three occurrences), a mastered one little.
    """

    from app.db.models.error import UserError

    now = _aware(now) or datetime.now(UTC)
    since = now - timedelta(days=SIGNAL_WINDOW_DAYS)
    try:
        rows = (
            db.query(
                UserError.original_text,
                UserError.correction,
                UserError.occurrences,
                UserError.state,
                UserError.updated_at,
                UserError.created_at,
            )
            .filter(UserError.user_id == user.id, UserError.updated_at >= since)
            .order_by(UserError.updated_at.desc())
            .limit(SIGNAL_MAX_ERRORS)
            .all()
        )
    except Exception:  # pragma: no cover - a signal never blocks a séance
        return LearnerSignal()
    mistakes: list[tuple[Any, Any, float]] = []
    for learner, corrected, occurrences, state, updated_at, created_at in rows:
        stamp = _aware(updated_at) or _aware(created_at) or now
        age_days = max(0.0, (now - stamp).total_seconds() / 86400.0)
        weight = min(max(int(occurrences or 1), 1), 3) * 0.5 ** (age_days / SIGNAL_HALF_LIFE_DAYS)
        if str(state or "") == "mastered":
            weight *= 0.3
        mistakes.append((learner, corrected, weight))
    return LearnerSignal.from_mistakes(mistakes)


# ---------------------------------------------------------------------------
# Which items a drill can pose
# ---------------------------------------------------------------------------


def _is_judgement(item: Mapping[str, Any]) -> bool:
    from app.services.item_bank import _is_judgement as bank_is_judgement

    return bank_is_judgement(dict(item))


def fold_key(text: Any) -> str:
    """A line as a comparison key: typography folded, accents kept."""

    return fold_typography(text)


def _words(text: Any) -> list[str]:
    return fold_key(text).split()


def typed_fits(item: Mapping[str, Any]) -> bool:
    """A fill whose form is short enough to type (a word or three)."""

    answer = str(item.get("correct_answer") or "").strip()
    prompt = str(item.get("prompt") or "")
    if not answer or "___" not in prompt or _is_judgement(item):
        return False
    return 1 <= len(answer.split()) <= TYPED_MAX_WORDS and len(answer) <= TYPED_MAX_CHARS


def dictation_fits(item: Mapping[str, Any]) -> bool:
    """A word bank whose sentence can be heard and built in one go."""

    answer = item.get("correct_answer")
    tokens = item.get("answer_tokens")
    if not answer or not isinstance(tokens, list):
        return False
    return DICTATION_MIN_WORDS <= len(_words(answer)) <= DICTATION_MAX_WORDS


def spot_window(source: Any, expected: Any) -> tuple[int, int] | None:
    """``(start, end)`` of the words to fix in ``source``, or ``None``.

    A spot needs one stretch of one to :data:`SPOT_MAX_WORDS` words that is
    wrong (a missing word has nothing to tap: that is a rewrite).
    """

    wrong, right = _words(source), _words(expected)
    if not wrong or not right or wrong == right:
        return None
    limit = min(len(wrong), len(right))
    head = 0
    while head < limit and wrong[head] == right[head]:
        head += 1
    tail = 0
    while tail < limit - head and wrong[-1 - tail] == right[-1 - tail]:
        tail += 1
    span = len(wrong) - head - tail
    fixed = len(right) - head - tail
    if span < 1 or span > SPOT_MAX_WORDS or fixed > SPOT_MAX_WORDS + 1:
        return None
    return head, head + span


def fix_words(source: Any, expected: Any) -> int:
    """How many words of ``source`` the learner has to touch (``0``: not a spot).

    One wrong stretch can hold several words («nous sommes cherchés» for «nous
    avons cherché»: a wrong auxiliary and the agreement it dragged along). The
    item carries the number, so the card says it instead of promising «the one
    mistake» (#300).
    """

    window = spot_window(source, expected)
    return 0 if window is None else window[1] - window[0]


#: An authored transform that changes a right sentence into another (a tense, a
#: negation): there is no mistake in it to find.
REWRITE_KINDS = frozenset({"directed_rewrite", "contrast_rewrite"})


def is_repair(item: Mapping[str, Any]) -> bool:
    """A sentence with a mistake in it, not a right one to change into another."""

    kind = str(item.get("type") or "")
    if kind in REWRITE_KINDS:
        return False
    return kind == "repair_rewrite" or bool(item.get("source_fr") or item.get("wrong_span"))


def spot_fits(item: Mapping[str, Any]) -> bool:
    if not is_repair(item):
        return False
    return spot_window(item.get("source_fr") or item.get("source"), item.get("expected_answer")) is not None


def judgement_fits(item: Mapping[str, Any]) -> bool:
    return _is_judgement(item)


def mine_fits(learner: Any, corrected: Any) -> bool:
    """A saved error worth posing as «Ta phrase»: a real, local slip in a line."""

    if not is_real_correction(learner, corrected):
        return False
    left, right = _words(learner), _words(corrected)
    if not (MINE_MIN_WORDS <= len(left) <= MINE_MAX_WORDS and MINE_MIN_WORDS <= len(right) <= MINE_MAX_WORDS + 2):
        return False
    return error_kind(learner, corrected) is not None


#: A drill's own condition on an item of its pool (``None``: any item).
DRILL_FITS: dict[str, Any] = {
    DRILL_TYPED: typed_fits,
    DRILL_DICTATION: dictation_fits,
    DRILL_SPOT: spot_fits,
    DRILL_RAFALE: judgement_fits,
}


def item_fits(drill: str | None, item: Mapping[str, Any]) -> bool:
    """Can ``drill`` pose this item? A learner's own sentence is only ever «mine»."""

    if not isinstance(item, Mapping):
        return False
    personal = bool(item.get("personal"))
    if drill == DRILL_MINE:
        return personal
    if personal:
        return False
    check = DRILL_FITS.get(str(drill or ""))
    return True if check is None else bool(check(item))


def canonical_drill(rung: int) -> str:
    return DRILLS_BY_RUNG[Rung(clamp_rung(rung))][0]


def drill_of_item(rung: int, item: Mapping[str, Any] | None, round_name: str | None = None) -> str:
    """The drill an item served without the recommender is posed as."""

    if isinstance(item, Mapping) and item.get("personal"):
        return DRILL_MINE
    if round_name == "transform" or Rung(clamp_rung(rung)) == Rung.TRANSFORM:
        return DRILL_SPOT if isinstance(item, Mapping) and spot_fits(item) else DRILL_REWRITE
    return canonical_drill(rung)


# ---------------------------------------------------------------------------
# The recommender
# ---------------------------------------------------------------------------

#: Every drill's own pull, before the learner is read.
BASE_SCORE: dict[str, float] = {
    DRILL_CHOICE: 1.0,
    DRILL_JUDGE: 1.0,
    DRILL_RAFALE: 0.7,
    DRILL_TILES: 1.0,
    DRILL_DICTATION: 0.75,
    DRILL_TYPED: 0.8,
    DRILL_SPOT: 1.1,
    DRILL_MINE: 0.0,
    DRILL_REWRITE: 0.2,
    DRILL_WRITE: 1.0,
    DRILL_SCENE: 1.0,
}

#: Which drills train which kind of slip (0 … 2).
AFFINITY: dict[str, dict[str, float]] = {
    KIND_ACCENT: {DRILL_TYPED: 2.0, DRILL_DICTATION: 1.0, DRILL_REWRITE: 0.5},
    KIND_FORM: {DRILL_SPOT: 1.5, DRILL_TYPED: 1.5, DRILL_CHOICE: 1.0, DRILL_RAFALE: 0.5},
    KIND_ORDER: {DRILL_TILES: 2.0, DRILL_DICTATION: 1.5},
    KIND_MISSING: {DRILL_REWRITE: 1.5, DRILL_TILES: 1.0, DRILL_DICTATION: 0.5},
    KIND_EXTRA: {DRILL_RAFALE: 1.5, DRILL_JUDGE: 1.0, DRILL_SPOT: 1.0},
    KIND_WORD: {DRILL_CHOICE: 1.0, DRILL_JUDGE: 0.5, DRILL_TYPED: 0.5},
    KIND_JUDGE: {DRILL_RAFALE: 2.0, DRILL_JUDGE: 1.0},
}

AFFINITY_SCALE = 1.0
MOMENTUM_AFTER_MISS = 1.5
MOMENTUM_STRETCH_PENALTY = 0.8
MOMENTUM_AFTER_STREAK = 1.0
VARIETY_LAST = 2.0
VARIETY_REPEAT = 0.35
MINE_BONUS = 2.4
#: The séance's own missed judgements read as this much «judge» signal each.
SEANCE_JUDGE_MISS = 0.6


def _tie(seed: str, drill: str) -> float:
    digest = hashlib.sha256(f"{seed}:{drill}".encode()).digest()
    return digest[0] / 255.0 * 0.05


def _rule_momentum(history: Sequence[Mapping[str, Any]], concept_id: int) -> tuple[bool, int]:
    """``(missed_last, streak)`` of one rule in this séance (checked answers only)."""

    entries = [
        entry for entry in history
        if int(entry.get("concept_id", -1)) == int(concept_id) and entry.get("checked")
    ]
    if not entries:
        return False, 0
    missed_last = entries[-1].get("outcome") != OUTCOME_CORRECT
    streak = 0
    for entry in reversed(entries):
        if entry.get("outcome") != OUTCOME_CORRECT:
            break
        streak += 1
    return missed_last, streak


def drill_scores(
    *,
    rung: int,
    concept_id: int,
    history: Sequence[Mapping[str, Any]] = (),
    signal: LearnerSignal | None = None,
    reprise: bool = False,
    mine_ready: bool = False,
    seed: str = "",
) -> dict[str, float]:
    """Each drill of the rung with its score (a drill that cannot be posed is left out)."""

    signal = signal or LearnerSignal()
    drills = DRILLS_BY_RUNG[Rung(clamp_rung(rung))]
    served = [str(entry.get("drill") or "") for entry in history if entry.get("drill")]
    last = served[-1] if served else None
    mine_served = served.count(DRILL_MINE)
    missed_last, streak = _rule_momentum(history, concept_id)
    missed_last = missed_last or reprise
    judge_misses = sum(
        1 for entry in history
        if entry.get("drill") in {DRILL_JUDGE, DRILL_RAFALE} and entry.get("checked")
        and entry.get("outcome") != OUTCOME_CORRECT
    )
    kinds = dict(signal.kinds)
    weight = signal.weight
    if judge_misses:
        # The séance's own misses add to the long-term reading.
        extra = SEANCE_JUDGE_MISS * judge_misses
        total = weight + extra
        kinds = {kind: share * weight / total for kind, share in kinds.items()}
        kinds[KIND_JUDGE] = kinds.get(KIND_JUDGE, 0.0) + extra / total
        weight = min(1.0, total)
    scores: dict[str, float] = {}
    for drill in drills:
        if drill == DRILL_MINE and (not mine_ready or mine_served >= MINE_PER_SEANCE or last == DRILL_MINE):
            continue
        score = BASE_SCORE.get(drill, 0.0)
        score += AFFINITY_SCALE * weight * sum(
            share * AFFINITY.get(kind, {}).get(drill, 0.0) for kind, share in kinds.items()
        )
        if missed_last:
            if drill in SCAFFOLDED:
                score += MOMENTUM_AFTER_MISS
            elif drill in STRETCH:
                score -= MOMENTUM_STRETCH_PENALTY
        elif streak >= 2 and drill in STRETCH:
            score += MOMENTUM_AFTER_STREAK
        if drill == last:
            score -= VARIETY_LAST
        score -= VARIETY_REPEAT * served.count(drill)
        if drill == DRILL_MINE:
            score += MINE_BONUS
        scores[drill] = round(score + _tie(seed, drill), 4)
    return scores


def rank_drills(
    *,
    rung: int,
    concept_id: int,
    history: Sequence[Mapping[str, Any]] = (),
    signal: LearnerSignal | None = None,
    reprise: bool = False,
    mine_ready: bool = False,
    seed: str = "",
) -> list[str]:
    """The rung's drills, best first (see the module docstring)."""

    scores = drill_scores(
        rung=rung,
        concept_id=concept_id,
        history=history,
        signal=signal,
        reprise=reprise,
        mine_ready=mine_ready,
        seed=seed,
    )
    return sorted(scores, key=lambda drill: (-scores[drill], drill))


__all__ = [
    "AFFINITY",
    "ALL_DRILLS",
    "DRILLS_BY_RUNG",
    "DRILL_CHOICE",
    "DRILL_DICTATION",
    "DRILL_JUDGE",
    "DRILL_MINE",
    "DRILL_POOL",
    "DRILL_RAFALE",
    "DRILL_REWRITE",
    "DRILL_SCENE",
    "DRILL_SPOT",
    "DRILL_TILES",
    "DRILL_TYPED",
    "DRILL_WRITE",
    "ERROR_KINDS",
    "MINE_PER_SEANCE",
    "RAFALE_SIZE",
    "LearnerSignal",
    "canonical_drill",
    "dictation_fits",
    "drill_of_item",
    "drill_scores",
    "error_kind",
    "fix_words",
    "fold_key",
    "is_repair",
    "item_fits",
    "learner_signal",
    "mine_fits",
    "rank_drills",
    "spot_fits",
    "spot_window",
    "typed_fits",
]
