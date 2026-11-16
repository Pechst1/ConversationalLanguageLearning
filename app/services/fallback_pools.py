"""Where La Forge's fallback sets take their material from: the concept itself.

#447 / #448 / #146. The fallback set is what a learner gets when no reviewed or
generated set exists for the day's rule. Its rows used to be filed by a *family*
(``infer_grammar_profile(...).key``: «preposition», «pronoun_choice»…), so every
unit of a family served the same hand-written rows and the same string tricks:

* «Pour, sans, avant de + infinitif» got the place-preposition rows («Il habite
  à cette rue» → «dans»), and «Deux pronoms ensemble» got single-pronoun swaps;
* a word bank's wrong tiles were ``token + "s"`` («prêters», «peuxs») and a fixed
  «autrement»; a fill item blanked the first word of four letters, whatever the rule.

The structural flaw is that nothing asked *the concept* whether a row practises it.
The concept does know: every unit carries a detector (the pattern that recognises
its form in free text), authored ✗/✓ pairs and anchor sentences. This module is
the one place that asks:

* a row is served under a concept only when the concept's detector recognises the
  form in it (:func:`rule_hit`), so a family's row can no longer be filed under a
  unit it does not practise;
* a blank is a word *inside* the detector's span, so it is a word the rule decides
  (:func:`fill_candidates`);
* a wrong option is a real French word: the form the unit's own ✗ sentences use,
  else a word of the family's closed pool, and never an invented form
  (:func:`is_real_form`), nor one that still satisfies the detector in the blank.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from app.services.lexical_coverage import fold, load_lexicon, tokenize

#: A word, apostrophes and hyphens split: «m'en» is «m» + «en», so the blank can be «en».
LETTERS = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+")
_ALPHA = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]")
_SEPARATORS = re.compile(r"\s*[;|]\s*")

#: The closed pools of real function words a family chooses between. A wrong option
#: comes from here (or from the unit's own ✗ sentences), never from a string trick.
FAMILY_POOLS: dict[str, tuple[str, ...]] = {
    "pronoun_choice": ("y", "en", "lui", "leur", "le", "la", "les", "me", "te", "nous", "vous", "se"),
    "relative_pronoun": ("qui", "que", "où", "dont", "quoi"),
    "determiner": ("le", "la", "les", "un", "une", "des", "du", "de", "ce", "cette", "ces", "mon", "ma", "mes"),
    "preposition": ("à", "de", "en", "dans", "chez", "sur", "par", "avec", "pour", "sans", "depuis", "pendant"),
    "comparison": ("plus", "moins", "aussi", "autant", "que", "mieux"),
    "article_after_negation": ("de", "du", "des", "un", "une", "la"),
}

#: Real words that fit no rule: the last resort for a bank that has nothing better, so
#: a set is never short. Which one an item gets depends on the item (never one word
#: in every bank, as «autrement» was).
NEUTRAL_POOL: tuple[str, ...] = (
    "soudain", "déjà", "souvent", "hier", "demain", "toujours", "vraiment", "ensuite", "encore", "bientôt",
)


def split_sentences(value: str | None) -> list[str]:
    """The sentences of a ``|``- or ``;``-separated catalogue field, ``->`` right sides only."""

    out: list[str] = []
    for part in _SEPARATORS.split(str(value or "")):
        cleaned = re.sub(r"\s+", " ", re.split(r"\s*->\s*", part)[-1]).strip()
        if cleaned:
            out.append(cleaned)
    return out


def concept_sentences(concept: Any, *, wrong: bool = True) -> list[str]:
    """Every French sentence the concept itself authors: anchors, examples, its rule
    card's examples and both sides of its ✗/✓ pairs (``wrong=False``: the ✓ side only)."""

    from app.services.grammar_items import plain
    from app.services.grammar_units import contrast_pairs
    from app.services.rule_cards import rule_card_for

    sentences = [
        *split_sentences(getattr(concept, "anchor_examples", None)),
        *split_sentences(getattr(concept, "examples", None)),
    ]
    card = rule_card_for(getattr(concept, "external_id", None)) or {}
    for row in [card.get("example") or {}, *(card.get("examples") or [])]:
        if isinstance(row, dict) and row.get("fr"):
            sentences.append(plain(str(row["fr"])))
    for pair in contrast_pairs(concept):
        sentences.extend([pair["right"], pair["wrong"]] if wrong else [pair["right"]])
    out: list[str] = []
    for sentence in sentences:
        if sentence and sentence not in out:
            out.append(sentence)
    return out


def material_words(sentences: Iterable[str]) -> set[str]:
    """Every word (folded, whole and in pieces) of the given authored sentences."""

    words: set[str] = set()
    for sentence in sentences:
        for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿŒœ]+)*", str(sentence)):
            words.add(fold(token))
        words.update(fold(piece) for piece in LETTERS.findall(str(sentence)))
    return words


def is_real_form(word: str, material: set[str] | None = None) -> bool:
    """Is ``word`` French: a word of the concept's own sentences, else one the vendored
    lexicon knows (as a lemma, an inflected form or a fixed expression)?"""

    if not _ALPHA.search(word or ""):
        return True  # punctuation is not a word
    if material and fold(word) in material:
        return True
    lexicon = load_lexicon()
    keys = [token.key for token in tokenize(word)]
    return bool(keys) and all(key in lexicon.lemmas or key in lexicon.forms or key in lexicon.atomic for key in keys)


# --------------------------------------------------------------------------- #
# The concept's own detector
# --------------------------------------------------------------------------- #


def patterns(concept: Any) -> list[str]:
    from app.services.grammar_units import regex_patterns, unit_detectors

    try:
        return regex_patterns(unit_detectors(concept))
    except Exception:  # pragma: no cover - a catalogue read must never fail a set
        return []


def rule_spans(concept: Any, sentence: str) -> list[tuple[int, int]]:
    """Where the concept's detector recognises its form in ``sentence``."""

    from app.services.grammar_units import detector_spans

    found = patterns(concept)
    return detector_spans(found, sentence) if found else []


def rule_hit(concept: Any, sentence: str) -> bool:
    return bool(rule_spans(concept, sentence))


def has_detector(concept: Any) -> bool:
    return bool(patterns(concept))


# --------------------------------------------------------------------------- #
# What the unit's own ✗ sentences get wrong
# --------------------------------------------------------------------------- #


def _words(sentence: str) -> list[str]:
    return [piece.lower() for piece in LETTERS.findall(sentence)]


def slips(concept: Any) -> list[tuple[tuple[str, ...], tuple[str, ...], str]]:
    """``(right words, wrong words, right sentence)`` for every place a ✗ sentence of the
    unit differs from its ✓: «sans dire» / «sans disant», «pour» / «pour à»."""

    from app.services.grammar_units import contrast_pairs

    out: list[tuple[tuple[str, ...], tuple[str, ...], str]] = []
    for pair in contrast_pairs(concept):
        right, wrong = _words(pair["right"]), _words(pair["wrong"])
        matcher = SequenceMatcher(a=right, b=wrong, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in {"replace", "insert"} and j2 > j1:
                out.append((tuple(right[i1:i2]), tuple(wrong[j1:j2]), pair["right"]))
    return out


def _stable_index(seed: str, size: int) -> int:
    return sum(ord(char) * (index + 1) for index, char in enumerate(seed)) % max(size, 1)


def distractor_candidates(
    concept: Any,
    sentence: str,
    answer: str,
    *,
    family: str,
    extra: Iterable[str] = (),
) -> list[str]:
    """Candidate wrong words for ``answer`` in ``sentence``, best first, unfiltered.

    The unit's own slips for that word, then the slips of its other ✗ sentences (those
    closest to this sentence first), then the family's pool. ``extra`` goes first: a
    caller's own rule-bound forms (a verb's other tense)."""

    sentence_words = set(_words(sentence))
    answer_key = answer.lower()
    found = slips(concept)
    own = [wrong for right, wrongs, _ in found if answer_key in right for wrong in wrongs]
    # Slips about a word this very sentence has (its «dire» → «disant»), then the family's
    # pool, then the unit's other slips: a slip about a word that is not here is a poor
    # wrong option for this line.
    here = [
        wrong
        for right, wrongs, _ in found
        if right and set(right) <= sentence_words
        for wrong in wrongs
    ]
    rest = [wrong for _, wrongs, _ in found for wrong in wrongs]
    return [*extra, *own, *here, *FAMILY_POOLS.get(family, ()), *rest]


def pick_distractors(
    candidates: Iterable[str],
    *,
    answer_words: Iterable[str],
    material: set[str],
    limit: int = 2,
    allow: Any = None,
    seed: str = "",
    pad: bool = True,
    strict: bool = True,
) -> list[str]:
    """The first ``limit`` real, distinct words that are not the answer.

    ``allow`` is an extra test (the blank's detector check, waived when ``strict`` is
    off). When the unit and the family offer fewer than ``limit``, real neutral words
    make up the number (unless ``pad`` is off)."""

    banned = {fold(word) for word in answer_words}
    out: list[str] = []

    def take(word: str, *, check: bool) -> None:
        key = fold(word)
        if not key or key in banned or key in {fold(existing) for existing in out}:
            return
        if not is_real_form(word, material):
            return
        if check and strict and allow is not None and not allow(word):
            return
        out.append(word)

    for word in candidates:
        take(word, check=True)
        if len(out) >= limit:
            return out[:limit]
    if not pad:
        return out
    start = _stable_index(seed, len(NEUTRAL_POOL))
    for offset in range(len(NEUTRAL_POOL)):
        take(NEUTRAL_POOL[(start + offset) % len(NEUTRAL_POOL)], check=True)
        if len(out) >= limit:
            break
    return out[:limit]


# --------------------------------------------------------------------------- #
# Fill items: the blank is a word the rule decides
# --------------------------------------------------------------------------- #


def _inside(word: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(start <= word[0] and word[1] <= end for start, end in spans)


def _overlaps(word: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(word[0] < end and start < word[1] for start, end in spans)


def blank_is_decided_by_rule(concept: Any, prompt: str, answer: str) -> bool:
    """Does the detector's span, in the finished sentence, cover the blank's word?"""

    match = re.search(r"_{2,}", prompt)
    if not match:
        return False
    filled = prompt[: match.start()] + answer + prompt[match.end():]
    return _overlaps((match.start(), match.start() + len(answer)), rule_spans(concept, filled))


def row_serves(concept: Any, prompt: str, answer: str, choices: Iterable[str], material: set[str]) -> bool:
    """May a hand-written fill row be served under ``concept``?

    Only if every option is a real word and, when the concept has a detector, the detector
    covers the blank and no wrong option still shows the form there. A family's row is
    otherwise filed under units it does not practise."""

    if not all(is_real_form(choice, material) for choice in choices):
        return False
    if not has_detector(concept):
        return True
    match = re.search(r"_{2,}", prompt)
    if match is None or not blank_is_decided_by_rule(concept, prompt, answer):
        return False
    for choice in choices:
        if choice == answer:
            continue
        changed = prompt[: match.start()] + choice + prompt[match.end():]
        if _overlaps((match.start(), match.start() + len(choice)), rule_spans(concept, changed)):
            return False
    return True


def fill_from_sentence(
    concept: Any,
    sentence: str,
    *,
    family: str,
    material: set[str],
    seed: str,
) -> dict[str, Any] | None:
    """``{prompt, answer, distractors}`` blanking a word the rule decides, or ``None``.

    The blank is a word inside the detector's span in ``sentence``. A word that also
    stands elsewhere in the sentence is skipped (the line would show its answer), and a
    wrong option must be real and must break the rule in the blank: put into the line,
    the detector no longer recognises the form there («Tu peux me la prêter» still
    would, so «la» is never offered for «le»)."""

    spans = rule_spans(concept, sentence)
    if not spans and not has_detector(concept):
        # A concept the catalogue has no detector for (none of the seeded units): the
        # family's own words decide, else any word of the line. There is no rule to hold
        # the blank to, so this is the only place the blank is not checked against one.
        pool_words = set(FAMILY_POOLS.get(family, ()))
        spans = [(m.start(), m.end()) for m in LETTERS.finditer(sentence) if m.group().lower() in pool_words]
        spans = spans or [(0, len(sentence))]
    if not spans:
        return None
    found = slips(concept)
    slip_words = {word for right, _, _ in found for word in right}
    pool = set(FAMILY_POOLS.get(family, ()))
    words = [(m.start(), m.end(), m.group()) for m in LETTERS.finditer(sentence)]
    inside = [
        (start, end, word)
        for start, end, word in words
        if _inside((start, end), spans) and (len(word) >= 2 or word.lower() in pool)
    ]
    # The words the unit's own slips are about first, then the family's pool, then the rest.
    inside.sort(key=lambda row: (row[2].lower() not in slip_words, row[2].lower() not in pool))
    inside = [
        row for row in inside if sum(1 for _, _, other in words if other.lower() == row[2].lower()) == 1
    ]
    # First a word that has two real rule-breaking wrong options of its own; only then
    # the best word padded with neutral real words, so a set is never short.
    # Last, a detector that covers the line whatever the blank holds (a whole «si» clause)
    # cannot tell a wrong option from the right one: the options are then only real words.
    for pad, strict in ((False, True), (True, True), (True, False)):
        for start, end, word in inside:
            built = _blank(
                concept, sentence, start, end, word,
                family=family, material=material, seed=seed, pad=pad, strict=strict,
            )
            if built:
                return built
    return None


def _blank(
    concept: Any,
    sentence: str,
    start: int,
    end: int,
    word: str,
    *,
    family: str,
    material: set[str],
    seed: str,
    pad: bool,
    strict: bool,
) -> dict[str, Any] | None:
    def breaks_rule(candidate: str) -> bool:
        shown = candidate.capitalize() if word[:1].isupper() else candidate
        changed = sentence[:start] + shown + sentence[end:]
        return not _overlaps((start, start + len(shown)), rule_spans(concept, changed))

    distractors = pick_distractors(
        distractor_candidates(concept, sentence, word, family=family),
        answer_words=[word],
        material=material,
        allow=breaks_rule,
        seed=seed,
        pad=pad,
        strict=strict,
    )
    if len(distractors) < 2:
        return None
    return {
        "prompt": sentence[:start] + "____" + sentence[end:],
        "answer": word,
        "distractors": [d.capitalize() if word[:1].isupper() else d for d in distractors],
    }
