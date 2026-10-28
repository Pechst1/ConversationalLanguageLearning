"""EXERCISE-QA 2026-10-03 — one answer-acceptance contract for every typed answer.

Before this module the app had more than twenty private ``_normalize``/``_fold``
helpers, and they disagreed: three of them dropped «œ» outright (so a German
keyboard's «soeur» was graded wrong against «sœur», while «sur» was graded right),
one forgave a one-letter difference anywhere in the word (so «parles» passed for
«parle», «vendions» for «vendons»), and only some folded the U+2018 apostrophe iOS
inserts. This is the one place that decides what is *typography* and what is
*French*.

The contract (tested in ``tests/test_answer_acceptance.py`` against a table of
tricky answers, and run through the real graders):

* **Typography never counts.** Every apostrophe and quote variant (U+2018/U+2019,
  primes, backticks), Unicode NFC vs NFD, case, exotic spaces (NBSP, narrow NBSP),
  the French space before «? ! : ;», guillemets, hyphen variants, sentence
  punctuation, a space after an elided particle («j' aime»), and the ligatures
  «œ»/«æ» typed as «oe»/«ae».
* **Accents are lenient where the item does not test them, and reported.** A
  missing or wrong accent on a word whose accent-free spelling is not another
  French word is accepted with ``accent_slip=True`` (the feedback names it).
  Accents are **strict** where they carry grammar or meaning: the homograph pairs
  (a/à, ou/où, la/là, du/dû, sur/sûr, des/dès, mur/mûr, tache/tâche…), a final
  «-é/-ée/-és/-ées» (participle vs present: «mangé» is not «mange») and anything
  an item marks ``accents="strict"`` (a ç or é/è item).
* **Typo tolerance never accepts a different grammatical form.** At most one
  edit (insert, delete, substitute, swap), in one word of at least five letters,
  where the learner's word is not itself a French word form, and where the two
  words do not differ only by an inflectional ending («parle/parles»,
  «vendons/vendions», «petit/petite», «allé/allée» are never typos).
* **Elision is French, not typography.** «je aime» is not «j'aime» (it is
  reported as ``elision``); «j' aime» and «j’aime» are «j'aime».
* **Optional articles** only when the caller says the article is not what the item
  asks for (``article_optional=True``): the bare noun, or the noun with an
  article of the right gender, counts; a wrong-gender article does not.
* **Accepted alternatives** are the item's list plus the systematic ones the
  caller opts into: ``question_variants`` (est-ce que ↔ intonation ↔ simple
  inversion) and ``on_nous_variants`` («on va» ↔ «nous allons» for the verbs in
  the table below).
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Literal

AccentPolicy = Literal["lenient", "strict"]

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

#: Everything a keyboard, a phone or a transcription service types for «'».
_APOSTROPHES = "‘’‚‛′´`ʹʻʼʽ＇"
_DOUBLE_QUOTES = "“”„‟″«»‹›\""
_SPACES = "           　\t\r\n"
_HYPHENS = "‐‑‒–—−"
_LIGATURES = {"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"}
_ZERO_WIDTH = "​‌‍﻿­"

_TRANSLATE = str.maketrans(
    {
        **dict.fromkeys(_APOSTROPHES, "'"),
        **dict.fromkeys(_DOUBLE_QUOTES, " "),
        **dict.fromkeys(_SPACES, " "),
        **dict.fromkeys(_HYPHENS, "-"),
        **dict.fromkeys(_ZERO_WIDTH),
        **_LIGATURES,
    }
)

#: Sentence punctuation: never part of a one-line answer's French.
_PUNCTUATION = re.compile(r"[.,;:!?…()\[\]/]+")
#: «j' aime» → «j'aime»; «aujourd' hui» → «aujourd'hui».
_ELISION_SPACE = re.compile(r"'\s+")
#: «est -ce que» / «est- ce que» → «est-ce que».
_HYPHEN_SPACE = re.compile(r"\s*-\s*")


def fold_typography(value: object) -> str:
    """The answer with typography folded and accents **kept**.

    NFC, apostrophe/quote/space/hyphen variants, œ/æ spelled out, case folded,
    punctuation dropped, whitespace collapsed. «Où est l’hôtel ?» and
    «où est l'hôtel» fold to the same string; «ou est l'hotel» does not.
    """

    text = unicodedata.normalize("NFC", "" if value is None else str(value))
    text = text.translate(_TRANSLATE).casefold()
    text = _PUNCTUATION.sub(" ", text)
    text = _ELISION_SPACE.sub("'", text)
    text = _HYPHEN_SPACE.sub("-", text)
    text = " ".join(text.split())
    return text.strip("-' ")


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if not unicodedata.combining(c)))


def fold_all(value: object) -> str:
    """Typography *and* accents folded — a lookup key, never a verdict on its own."""

    return strip_accents(fold_typography(value))


# ---------------------------------------------------------------------------
# What French knows that a fold does not
# ---------------------------------------------------------------------------

#: Words whose accent-free spelling is another French word. An accent slip on one
#: of these is a different word, so it is never forgiven.
#: EXPERIENCE-REVIEW 2026-10-04: «ca» is not a word — it is how every German and
#: English keyboard types «ça», so it is a spelling slip (named, not refused). The
#: literary «çà» stays strict.
ACCENT_HOMOGRAPHS: frozenset[str] = frozenset(
    {
        "a", "à", "ou", "où", "la", "là", "du", "dû", "sur", "sûr", "sure", "sûre",
        "des", "dès", "mur", "mûr", "mure", "mûre", "tache", "tâche", "pecher",
        "pêcher", "pécher", "jeune", "jeûne", "cote", "côte", "côté", "coté",
        "roder", "rôder", "foret", "forêt", "mais", "maïs", "çà",
        "eut", "eût", "fut", "fût", "notre", "nôtre", "votre", "vôtre", "crue", "crûe",
        "age", "âge", "ai", "aï", "es", "ès", "interne", "interné", "marche", "marché",
        "peche", "pêche", "pèche", "prés", "près", "pres", "rue", "rué",
    }
)

#: Endings that make a different grammatical form of the same stem: verb person,
#: tense and mood, gender and number agreement. Two words that differ only by
#: swapping one of these for another are never a typo.
INFLECTION_ENDINGS: frozenset[str] = frozenset(
    {
        "", "e", "s", "es", "x", "t", "d", "nt", "ent", "ons", "ez", "ais", "ait",
        "ions", "iez", "aient", "ai", "as", "a", "âmes", "âtes", "èrent", "erent",
        "rai", "ras", "ra", "rons", "rez", "ront", "rais", "rait", "rions", "riez",
        "raient", "er", "ir", "re", "oir", "é", "ée", "és", "ées", "i", "ie", "is",
        "ies", "u", "ue", "us", "ues", "ant", "eons", "eais", "eait", "eant", "le", "lle", "lles", "les", "ne", "nne", "nnes", "nes", "ve", "ves", "f", "fs",
        "se", "ses", "euse", "euses", "eur", "eurs", "rice", "rices", "eux", "al", "aux",
        "ale", "ales", "ère", "ères", "ier", "iers", "ière", "ières",
    }
)

#: The articles an ``article_optional`` answer may carry, with their gender.
_ARTICLES: dict[str, str | None] = {
    "le": "m", "un": "m", "la": "f", "une": "f", "l'": None, "les": None, "des": None,
}
_ARTICLE_PREFIX = re.compile(r"^(l'|les|le|la|une|un|des)(?:\s+|(?<='))(?=\S)")

#: Particles that elide before a vowel or mute h.
_ELIDING = ("je", "me", "te", "se", "le", "la", "ne", "de", "que", "ce", "si")
_VOWEL_START = re.compile(r"^[aeiouyhàâäéèêëîïôöùûü]")


@lru_cache(maxsize=1)
def known_forms() -> frozenset[str]:
    """Every lemma and inflected form of the core lexicon, accent-folded."""

    path = Path(__file__).resolve().parents[1] / "data" / "lexical" / "fr_core_lexicon.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - a missing lexicon never breaks grading
        return frozenset()
    words: set[str] = set()
    for key in (data.get("lemmas") or {}):
        words.add(fold_all(key))
    for form, lemma in (data.get("forms") or {}).items():
        words.add(fold_all(form))
        words.add(fold_all(lemma))
    return frozenset(word for word in words if word and " " not in word)


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the grader decided, and why — enough for a feedback line.

    ``note`` names the one thing worth telling the learner when the answer was
    accepted with a slip (``accent``, ``typo``) or refused for a reason a fold
    can see (``elision``, ``gender``, ``accent``, ``form``); ``None`` otherwise.
    ``expected`` is the accepted answer the verdict was measured against, as
    authored, so a miss can always show it.

    A repair answered with only its corrected part (:func:`judge_repair`) also
    carries ``read_as``, the whole sentence the part stands for (the source with
    the part put in), and ``expected_part``, the stretch of ``expected`` the part
    answers. Both are ``None`` for an answer read as a whole sentence.
    """

    correct: bool
    exact: bool = False
    accent_slip: bool = False
    typo: bool = False
    note: str | None = None
    expected: str | None = None
    learner_word: str | None = None
    expected_word: str | None = None
    read_as: str | None = None
    expected_part: str | None = None


def _damerau_one(left: str, right: str) -> int | None:
    """The index in ``right`` of the single edit that turns ``left`` into it, else None."""

    if left == right:
        return None
    if abs(len(left) - len(right)) > 1:
        return None
    prefix = 0
    while prefix < min(len(left), len(right)) and left[prefix] == right[prefix]:
        prefix += 1
    if len(left) == len(right):
        if left[prefix + 1:] == right[prefix + 1:]:
            return prefix  # substitution
        if (
            prefix + 1 < len(left)
            and left[prefix] == right[prefix + 1]
            and left[prefix + 1] == right[prefix]
            and left[prefix + 2:] == right[prefix + 2:]
        ):
            return prefix  # transposition
        return None
    if len(left) < len(right):
        return prefix if left[prefix:] == right[prefix + 1:] else None
    return prefix if left[prefix + 1:] == right[prefix:] else None


def _inflection_change(learner: str, target: str) -> bool:
    """Do the two words differ only by an inflectional ending on a shared stem?"""

    prefix = 0
    while prefix < min(len(learner), len(target)) and learner[prefix] == target[prefix]:
        prefix += 1
    # Back off into the stem so «parle|s» and «vend|ons/ions» both split on the ending.
    for cut in range(prefix, max(prefix - 3, 1) - 1, -1):
        if learner[cut:] in INFLECTION_ENDINGS and target[cut:] in INFLECTION_ENDINGS:
            return True
    return False


def is_typo_of(learner_word: str, target_word: str) -> bool:
    """One slip of the finger on one word — never another form, never another word.

    Both words are compared accent-folded (accents are judged separately).
    """

    learner = strip_accents(learner_word)
    target = strip_accents(target_word)
    if learner == target or len(target) < 5 or "'" in target or "-" in target:
        return False
    if _damerau_one(learner, target) is None:
        return False
    if _inflection_change(learner, target):
        return False
    if learner in known_forms():
        return False
    return True


def _accent_strict_word(learner_word: str, target_word: str) -> bool:
    """Is this accent difference grammar or meaning, not spelling?

    Strict for the homographs (a/à, ou/où …) and for a verb's «-é» ending: the
    participle against the present or the infinitive («mangé»/«mange»,
    «allée»/«allee»). «cle» for «clé» or «tres» for «très» is spelling.
    """

    if learner_word in ACCENT_HOMOGRAPHS or target_word in ACCENT_HOMOGRAPHS:
        return True
    lemmas = known_lemmas()
    for word in (target_word, learner_word):
        for ending in ("ées", "és", "ée", "é"):
            if word.endswith(ending) and strip_accents(word[: -len(ending)]) + "er" in lemmas:
                # EXPERIENCE-REVIEW 2026-10-04: strict only when the slip is *in* the
                # «-é» ending; «diné» for «dîné» has the participle right.
                other = learner_word if word is target_word else target_word
                if other.endswith(ending):
                    return False
                return True
    return False


@lru_cache(maxsize=1)
def known_lemmas() -> frozenset[str]:
    """The core lexicon's lemmas, accent-folded (``manger``, ``aller`` …)."""

    path = Path(__file__).resolve().parents[1] / "data" / "lexical" / "fr_core_lexicon.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return frozenset()
    return frozenset(fold_all(lemma) for lemma in (data.get("lemmas") or {}))


def _strip_article(text: str) -> tuple[str | None, str]:
    match = _ARTICLE_PREFIX.match(text)
    if not match:
        return None, text
    return match.group(1), text[match.end():].strip()


def _elision_slip(learner_tokens: list[str], target_tokens: list[str]) -> bool:
    """«je aime» for «j'aime», «le arbre» for «l'arbre»."""

    expanded: list[str] = []
    for token in target_tokens:
        if "'" in token:
            head, _, tail = token.partition("'")
            if tail and len(head) <= 4:
                full = {"j": "je", "m": "me", "t": "te", "s": "se", "l": "le", "n": "ne", "d": "de", "c": "ce", "qu": "que"}.get(head)
                if full:
                    expanded.append(full)
                    expanded.append(tail)
                    continue
        expanded.append(token)
    if expanded == target_tokens:
        return False
    learner = [strip_accents(token) for token in learner_tokens]
    target = [strip_accents(token) for token in expanded]
    if learner == target:
        return True
    # «la arbre» for «l'arbre»: the particle may be either gender's article.
    if len(learner) == len(target):
        swapped = ["le" if (word == "la" and other == "le") else word for word, other in zip(learner, target, strict=True)]
        return swapped == target
    return False


def _compare(
    learner: str,
    target: str,
    *,
    accents: AccentPolicy,
    typo: bool,
) -> Verdict:
    """One learner answer against one accepted answer, both typography-folded."""

    if learner == target:
        return Verdict(correct=True, exact=True)
    if learner.count("'") < target.count("'"):
        # «s il vous plait» for «s'il vous plaît»: the apostrophe typed as a space
        # is typography. («je aime» is not: the particle's letters differ.)
        spaced_learner = " ".join(learner.replace("'", " ").split())
        spaced_target = " ".join(target.replace("'", " ").split())
        if spaced_learner.split() and len(spaced_learner.split()) == len(spaced_target.split()):
            spaced = _compare(spaced_learner, spaced_target, accents=accents, typo=typo)
            if spaced.correct:
                return spaced
    learner_tokens = learner.split()
    target_tokens = target.split()
    if strip_accents(learner) == strip_accents(target) and len(learner_tokens) == len(target_tokens):
        slips = [
            (got, want)
            for got, want in zip(learner_tokens, target_tokens, strict=True)
            if got != want
        ]
        strict_slips = [(got, want) for got, want in slips if _accent_strict_word(got, want)]
        strict = accents == "strict" or bool(strict_slips)
        # A refusal names the accent that refuses it: «la» for «là» in «il a ete la»,
        # not the forgiven «ete».
        got, want = (strict_slips or slips)[0]
        return Verdict(
            correct=not strict,
            accent_slip=True,
            note="accent",
            learner_word=got,
            expected_word=want,
        )
    if len(learner_tokens) == len(target_tokens):
        differing = [
            (got, want)
            for got, want in zip(learner_tokens, target_tokens, strict=True)
            if strip_accents(got) != strip_accents(want)
        ]
        if len(differing) == 1:
            got, want = differing[0]
            if typo and is_typo_of(got, want):
                accent_words = [
                    (g, w) for g, w in zip(learner_tokens, target_tokens, strict=True)
                    if g != w and strip_accents(g) == strip_accents(w)
                ]
                strict_accent = accents == "strict" or any(_accent_strict_word(g, w) for g, w in accent_words)
                return Verdict(
                    correct=not strict_accent,
                    typo=True,
                    accent_slip=bool(accent_words),
                    note="typo",
                    learner_word=got,
                    expected_word=want,
                )
            note = "form" if _inflection_change(strip_accents(got), strip_accents(want)) else None
            return Verdict(correct=False, note=note, learner_word=got, expected_word=want)
    if _elision_slip(learner_tokens, target_tokens):
        return Verdict(correct=False, note="elision")
    return Verdict(correct=False)


def _gender_of(noun: str) -> str | None:
    """The noun's gender from the core lexicon, when it is known."""

    entry = _lemma_genders().get(strip_accents(noun))
    return entry


@lru_cache(maxsize=1)
def _lemma_genders() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "data" / "lexical" / "fr_core_lexicon.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover
        return {}
    out: dict[str, str] = {}
    for lemma, entry in (data.get("lemmas") or {}).items():
        gender = (entry or {}).get("gender") if isinstance(entry, dict) else None
        if gender in {"m", "f"}:
            out.setdefault(strip_accents(fold_typography(lemma)), gender)
    return out


def judge(
    answer: object,
    accepted: Iterable[object],
    *,
    accents: AccentPolicy = "lenient",
    typo: bool = True,
    article_optional: bool = False,
    alternatives: Iterable[object] = (),
) -> Verdict:
    """Grade one typed answer against the item's accepted answers.

    Returns the best verdict over every accepted answer (an exact hit beats a
    slip; a slip beats a miss; among misses the most informative note wins).
    """

    learner = fold_typography(answer)
    candidates = [str(item) for item in [*accepted, *alternatives] if item and str(item).strip()]
    if not learner or not candidates:
        return Verdict(correct=False, expected=candidates[0] if candidates else None)
    best: Verdict | None = None
    for candidate in candidates:
        target = fold_typography(candidate)
        if not target:
            continue
        verdicts = [_compare(learner, target, accents=accents, typo=typo)]
        if article_optional:
            want_article, want_noun = _strip_article(target)
            got_article, got_noun = _strip_article(learner)
            if want_article is not None or got_article is not None:
                gender_ok = True
                miss_note = "gender"
                if got_article is not None:
                    got_gender = _ARTICLES.get(got_article)
                    want_gender = _ARTICLES.get(want_article) if want_article else None
                    want_gender = want_gender or _gender_of(want_noun)
                    if got_gender and want_gender and got_gender != want_gender:
                        gender_ok = False
                    # «l'» only before a vowel; «le/la» never before one.
                    if got_article == "l'" and not _VOWEL_START.match(got_noun):
                        gender_ok = False
                    if got_article in {"le", "la"} and _VOWEL_START.match(got_noun) and not got_noun.startswith("h"):
                        gender_ok = False
                        miss_note = "elision"
                bare = _compare(got_noun, want_noun, accents=accents, typo=typo)
                if bare.correct and not gender_ok:
                    bare = Verdict(correct=False, note=miss_note)
                verdicts.append(bare)
        for verdict in verdicts:
            verdict = Verdict(
                correct=verdict.correct,
                exact=verdict.exact,
                accent_slip=verdict.accent_slip,
                typo=verdict.typo,
                note=verdict.note,
                expected=candidate,
                learner_word=verdict.learner_word,
                expected_word=verdict.expected_word,
            )
            if best is None or _rank(verdict) > _rank(best):
                best = verdict
    return best or Verdict(correct=False, expected=candidates[0])


# ---------------------------------------------------------------------------
# A repair answered with its corrected part
# ---------------------------------------------------------------------------


def _repair_bounds(source: list[str], target: list[str]) -> tuple[int, int]:
    """Words the wrong and the right sentence share at the start and at the end."""

    limit = min(len(source), len(target))
    head = 0
    while head < limit and source[head] == target[head]:
        head += 1
    tail = 0
    while tail < limit - head and source[-1 - tail] == target[-1 - tail]:
        tail += 1
    return head, tail


def repair_readings(answer: object, source: object, target: object) -> list[tuple[str, str, int]]:
    """Every whole sentence a repair answer may stand for (owner request 2026-10-17).

    «des chaises vert» → «des chaises vertes»: retyping the sentence to fix one
    word is slow, so the learner may write only the part they corrected («vertes»),
    with as much of the unchanged words around it as they like («chaises vertes»),
    or the whole sentence. Each reading puts the answer in place of the stretch of
    ``source`` that differs from ``target`` (widened by the context the learner
    may have typed) and returns ``(sentence, target_part, context_words)``. A
    reading is only right when the whole sentence it makes is ``target``, so a
    part is accepted exactly when it holds the whole correction.
    """

    learner = fold_typography(answer).split()
    wrong = fold_typography(source).split()
    right = fold_typography(target).split()
    if not learner or not wrong or not right or wrong == right:
        return []
    head, tail = _repair_bounds(wrong, right)
    readings: list[tuple[str, str, int]] = []
    for before in range(head + 1):
        for after in range(tail + 1):
            sentence = [*wrong[: head - before], *learner, *wrong[len(wrong) - tail + after :]]
            part = right[head - before : len(right) - tail + after]
            readings.append((" ".join(sentence), " ".join(part), before + after))
    return readings


def _aligned_reading(answer: object, source: object, target: object) -> tuple[str, str] | None:
    """The reading whose context words are the ones the learner actually typed.

    A wrong part («verts», «rouge») is shown against the part it stands for
    («vertes»), not against the whole sentence."""

    learner = fold_typography(answer).split()
    wrong = fold_typography(source).split()
    right = fold_typography(target).split()
    if not learner or len(learner) >= len(wrong):
        return None
    head, tail = _repair_bounds(wrong, right)
    before = 0
    for count in range(min(head, len(learner)), 0, -1):
        if [strip_accents(w) for w in learner[:count]] == [strip_accents(w) for w in wrong[head - count : head]]:
            before = count
            break
    after = 0
    for count in range(min(tail, len(learner) - before), 0, -1):
        start = len(wrong) - tail
        if [strip_accents(w) for w in learner[-count:]] == [strip_accents(w) for w in wrong[start : start + count]]:
            after = count
            break
    sentence = [*wrong[: head - before], *learner, *wrong[len(wrong) - tail + after :]]
    part = right[head - before : len(right) - tail + after]
    if not part:
        return None
    return " ".join(sentence), " ".join(part)


def _repair_rank(verdict: Verdict) -> tuple[int, int, int, int]:
    """:func:`_rank`, except that among misses only the note counts: a part
    refused for a grammar accent («a» for «à») says so."""

    if verdict.correct:
        return _rank(verdict)
    return (0, 0, 0, _NOTE_PRIORITY.get(verdict.note or "", 0))


def judge_repair(
    answer: object,
    source: object,
    accepted: Iterable[object],
    *,
    accents: AccentPolicy = "lenient",
    typo: bool = True,
    article_optional: bool = False,
) -> Verdict:
    """A «correct this sentence» answer: the whole sentence, or only the corrected part.

    The whole-sentence verdict is :func:`judge`'s. A shorter answer is read in
    place in ``source`` (:func:`repair_readings`) and that sentence is judged by the
    same contract, so typography, accents and typos count exactly as they do for
    a whole sentence. A verdict reached through a part carries ``read_as`` and
    ``expected_part``; so does a miss written as a part, for the correction line.
    """

    keys = [str(item) for item in accepted if item and str(item).strip()]
    best = judge(answer, keys, accents=accents, typo=typo, article_optional=article_optional)
    if best.exact or not str(source or "").strip():
        return best
    whole = len(fold_typography(answer).split()) >= len(fold_typography(source).split())
    for key in keys:
        for sentence, part, _context in repair_readings(answer, source, key):
            if fold_typography(sentence) == fold_typography(answer):
                continue
            verdict = judge(sentence, [key], accents=accents, typo=typo, article_optional=article_optional)
            if _repair_rank(verdict) > _repair_rank(best):
                best = replace(verdict, read_as=sentence, expected_part=part)
    if best.correct or whole or best.read_as is not None:
        return best
    expected = best.expected or (keys[0] if keys else None)
    aligned = _aligned_reading(answer, source, expected) if expected else None
    if aligned is None:
        return best
    return replace(best, read_as=aligned[0], expected_part=aligned[1])


def judge_in_line(answer: object, accepted: Iterable[object], *, lemma: object) -> Verdict:
    """A blank in a line, answered (owner decision 2026-10-08).

    A cloze can only be answered with the form that fits the line: «Vous ___ d'où ?»
    takes «venez», and «venir» there is wrong French. The accepted forms are graded by
    the one contract (:func:`judge`: typography folded, accents lenient-but-named, a
    typo forgiven only when it is not another form). An answer that is the lemma
    itself is refused with ``note="line_form"``: the line needs the form.
    """

    forms = [str(item) for item in accepted if item and str(item).strip()]
    verdict = judge(answer, forms)
    if verdict.correct:
        return verdict
    if judge(answer, [lemma], typo=False, article_optional=True).correct:
        return Verdict(
            correct=False,
            note="line_form",
            expected=forms[0] if forms else None,
            expected_word=forms[0] if forms else None,
            learner_word=fold_typography(answer),
        )
    return verdict


#: QA-CLOSE (owner decision c): units whose rule *is* the spelling — accents are
#: strict on every item («mangeons», «commençons», «achète», «préfère»).
ACCENT_STRICT_UNITS: frozenset[str] = frozenset({"FR2_A12_ER_SPELLING"})


def accent_policy(
    *,
    unit: object = None,
    item: dict | None = None,
    target: object = None,
    others: Iterable[object] = (),
) -> AccentPolicy:
    """Strict when the item tests the accent, lenient otherwise.

    The item tests the accent when its unit is a spelling unit
    (:data:`ACCENT_STRICT_UNITS`), when it says so (``accents: "strict"``), or when
    one of ``others`` (its options, its source sentence, its traps) differs from the
    key by accents alone — that difference is the whole question.
    """

    external_id = str(getattr(unit, "external_id", unit) or "")
    if external_id in ACCENT_STRICT_UNITS:
        return "strict"
    if isinstance(item, dict) and str(item.get("accents") or "") == "strict":
        return "strict"
    key = fold_typography(target)
    if key:
        for other in others:
            folded = fold_typography(other)
            if folded and folded != key and strip_accents(folded) == strip_accents(key):
                return "strict"
    return "lenient"


#: Among misses, the note that tells the learner the most wins.
_NOTE_PRIORITY = {"line_form": 6, "gender": 5, "elision": 4, "accent": 3, "form": 2, "typo": 1}


def _rank(verdict: Verdict) -> tuple[int, int, int, int]:
    return (
        int(verdict.correct),
        int(verdict.exact),
        int(not verdict.accent_slip and not verdict.typo),
        _NOTE_PRIORITY.get(verdict.note or "", 0),
    )


# ---------------------------------------------------------------------------
# Systematic alternatives (opt-in)
# ---------------------------------------------------------------------------

_SUBJECTS = ("je", "j'", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles")
_INVERTIBLE = ("tu", "il", "elle", "on", "nous", "vous", "ils", "elles")


def question_variants(sentence: str) -> list[str]:
    """The same yes/no question in its other registers.

    «Est-ce que tu viens ?» ↔ «Tu viens ?» ↔ «Viens-tu ?»; «Il a faim ?» ↔
    «A-t-il faim ?». Only simple «pronoun verb …» questions are rewritten; a
    sentence this cannot read safely returns ``[]`` (no guessed alternatives).
    """

    text = fold_typography(sentence)
    variants: set[str] = set()
    body = text
    if body.startswith("est-ce qu'"):
        body = body[len("est-ce qu'"):]
    elif body.startswith("est-ce que "):
        body = body[len("est-ce que "):]
    words = body.split()
    if len(words) < 2 or words[0] not in _INVERTIBLE:
        return []
    pronoun, verb, rest = words[0], words[1], words[2:]
    if pronoun in {"ne", "n'"} or verb in {"ne", "pas"} or verb.startswith("n'"):
        return []
    variants.add(" ".join([pronoun, verb, *rest]))
    vowel = f"{pronoun[0]}" in "aeiou"
    joiner = "-t-" if verb[-1] in "ae" and pronoun in {"il", "elle", "on"} and vowel else "-"
    variants.add(" ".join([f"{verb}{joiner}{pronoun}", *rest]))
    starts_vowel = bool(_VOWEL_START.match(pronoun))
    variants.add(("est-ce qu'" if starts_vowel else "est-ce que ") + " ".join([pronoun, verb, *rest]))
    variants.discard(text)
    return sorted(variants)


#: «on» + 3rd singular ↔ «nous» + 1st plural, for the verbs an A1–A2 item uses.
_ON_NOUS: dict[str, str] = {
    "va": "allons", "est": "sommes", "a": "avons", "fait": "faisons", "peut": "pouvons",
    "veut": "voulons", "doit": "devons", "prend": "prenons", "vient": "venons",
    "sait": "savons", "dit": "disons", "voit": "voyons", "part": "partons",
    "sort": "sortons", "met": "mettons", "lit": "lisons", "écrit": "écrivons",
    "boit": "buvons", "mange": "mangeons", "commence": "commençons",
}


def on_nous_variants(sentence: str) -> list[str]:
    """«On va au marché» ↔ «Nous allons au marché» (regular -er verbs and the table)."""

    text = fold_typography(sentence)
    words = text.split()
    out: list[str] = []
    for index in range(len(words) - 1):
        pronoun, verb = words[index], words[index + 1]
        if pronoun == "on":
            plural = _ON_NOUS.get(verb)
            if plural is None and verb.endswith("e") and len(verb) > 3:
                plural = verb[:-1] + ("eons" if verb.endswith("ge") else "ons")
            if plural:
                out.append(" ".join([*words[:index], "nous", plural, *words[index + 2:]]))
        elif pronoun == "nous":
            singular = next((sg for sg, pl in _ON_NOUS.items() if pl == verb), None)
            if singular is None and verb.endswith("ons") and len(verb) > 5:
                singular = verb[:-4] + "e" if verb.endswith("eons") else verb[:-3] + "e"
            if singular:
                out.append(" ".join([*words[:index], "on", singular, *words[index + 2:]]))
    return out


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

#: One short «why» per verdict note, in the learner's language.
NOTE_COPY: dict[str, dict[str, str]] = {
    "accent_ok": {
        "en": "Right — watch the accent: «{expected_word}».",
        "de": "Richtig — achte auf den Akzent: «{expected_word}».",
        "fr": "Juste — attention à l'accent : « {expected_word} ».",
    },
    "typo_ok": {
        "en": "Right — small typo: «{expected_word}».",
        "de": "Richtig — kleiner Tippfehler: «{expected_word}».",
        "fr": "Juste — petite faute de frappe : « {expected_word} ».",
    },
    "accent": {
        "en": "Here the accent changes the word: «{expected_word}», not «{learner_word}».",
        "de": "Hier ändert der Akzent das Wort: «{expected_word}», nicht «{learner_word}».",
        "fr": "Ici, l'accent change le mot : « {expected_word} », pas « {learner_word} ».",
    },
    "form": {
        "en": "Same word, different form: «{expected_word}», not «{learner_word}».",
        "de": "Richtiges Wort, falsche Form: «{expected_word}», nicht «{learner_word}».",
        "fr": "Bon mot, autre forme : « {expected_word} », pas « {learner_word} ».",
    },
    "elision": {
        "en": "Before a vowel the little word loses its e: j'aime, l'ami.",
        "de": "Vor einem Vokal fällt das e des kleinen Wortes weg: j'aime, l'ami.",
        "fr": "Devant une voyelle, le petit mot perd son e : j'aime, l'ami.",
    },
    "line_form": {
        "en": "Right word — the line needs the form «{expected_word}».",
        "de": "Richtiges Wort — der Satz braucht die Form «{expected_word}».",
        "fr": "Bon mot — la phrase demande la forme « {expected_word} ».",
    },
    "gender": {
        "en": "The noun is right, the article's gender is not.",
        "de": "Das Nomen stimmt, das Geschlecht des Artikels nicht.",
        "fr": "Le nom est juste, le genre de l'article ne l'est pas.",
    },
}


def feedback_note(verdict: Verdict, language: str | None) -> str | None:
    """The one-line «why» for a verdict, in the learner's language, or ``None``."""

    if verdict.note is None:
        return None
    key = verdict.note
    if verdict.correct and key in {"accent", "typo"}:
        key = f"{key}_ok"
    elif verdict.correct:
        return None
    table = NOTE_COPY.get(key)
    if table is None:
        return None
    lang = str(language or "en")[:2].lower()
    template = table.get(lang) or table["en"]
    return template.format(
        expected_word=verdict.expected_word or verdict.expected or "",
        learner_word=verdict.learner_word or "",
    )


#: Agency walk run 3 (2026-10-12): «mais sans mon nom» was "corrected" to «mais pas
#: mon nom» and saved as a fix. Each pair is two correct ways to say the same thing
#: where the learner wrote one; swapping one for the other is a preference, not a fix.
EQUIVALENT_WORD_SWAPS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"sans", "pas"}),
    }
)

_SWAP_WORDS = re.compile(r"[\w']+")


def is_preference_swap(learner: object, corrected: object) -> bool:
    """A "correction" that changes nothing wrong: a yes/no question moved to another
    register («Vous êtes disponible ?» → «Êtes-vous disponible ?»), or one word
    swapped for its correct equivalent (:data:`EQUIVALENT_WORD_SWAPS`)."""

    left = fold_typography(learner).strip(" ?!.")
    right = fold_typography(corrected).strip(" ?!.")
    if not left or not right or left.casefold() == right.casefold():
        return False
    if right in question_variants(left) or left in question_variants(right):
        return True
    a = _SWAP_WORDS.findall(left.casefold())
    b = _SWAP_WORDS.findall(right.casefold())
    if len(a) != len(b):
        return False
    changed = [frozenset({x, y}) for x, y in zip(a, b, strict=True) if x != y]
    return len(changed) == 1 and changed[0] in EQUIVALENT_WORD_SWAPS


def is_real_correction(learner: object, corrected: object) -> bool:
    """#174/#93: whether a "correction" changes anything that is wrong.

    The one guard every saved error passes (``ErrorMemoryService.record_erratum``):
    a correction that only changes typography (case, apostrophes, spacing, a final
    full stop; accents are kept, they can be the error) or swaps one right form for
    another (:func:`is_preference_swap`) is not an error and is never drilled. When
    either side is missing there is nothing to compare, and the correction stands.
    """

    left = fold_typography(learner)
    right = fold_typography(corrected)
    if not left or not right:
        return True
    if left == right:
        return False
    return not is_preference_swap(learner, corrected)


# ---------------------------------------------------------------------------
# #193: a correction must be about the sentence the learner actually wrote
# ---------------------------------------------------------------------------
#
# Live walk 2026-10-17: «Ma grand-mère est mort» was answered with «est → es»,
# explained as «after 'tu' you must use 'es'». There is no «tu» in the sentence and
# «Ma grand-mère est» is right. The tutor and the scene turn take the correction
# (span, replacement, note) as model-written free text, and «copy the span from the
# learner's text» was only a sentence in the prompt: nothing in code compared the
# correction with the sentence it judges (the same flaw as #174, a verdict not tied to
# the sentence). `correction_is_grounded` is that comparison; a correction that fails
# it is dropped, never shown, never saved as an erratum.
#
# The rule is deliberately one-sided. It drops a correction only when it can PROVE it
# wrong from the sentence: the quoted span is not there, the note cites a subject that
# is not there, or the «before» form is already right for the subject in front of it
# (or the replacement is wrong for that subject). Whenever the subject cannot be read
# from the sentence the correction stands: #201 dropped genuine fixes («Marie et moi
# suis → sommes», «Toi est → es») by demanding a bare pronoun next to the span.

_PERSON_FORMS: dict[str, frozenset[str]] = {
    "1sg": frozenset({"suis", "ai", "vais"}),
    "2sg": frozenset({"es", "as", "vas"}),
    "3sg": frozenset({"est", "a", "va"}),
    "1pl": frozenset({"sommes", "avons", "allons"}),
    "2pl": frozenset({"êtes", "avez", "allez"}),
    "3pl": frozenset({"sont", "ont", "vont"}),
}
#: A conjugated form of être/avoir/aller -> the persons it is right for.
_FORM_PERSONS: dict[str, frozenset[str]] = {}
for _person, _forms in _PERSON_FORMS.items():
    for _form in _forms:
        _FORM_PERSONS[_form] = _FORM_PERSONS.get(_form, frozenset()) | {_person}

_SUBJECT_PRONOUNS: dict[str, str] = {
    "je": "1sg",
    "j": "1sg",
    "tu": "2sg",
    "il": "3sg",
    "on": "3sg",
    "ce": "3sg",
    "c": "3sg",
    "ça": "3sg",
    "nous": "1pl",
    "vous": "2pl",
    "ils": "3pl",
    "elles": "3pl",
}
_DISJUNCTIVE = {"moi": "1sg", "toi": "2sg", "lui": "3sg", "eux": "3pl"}
#: Words between a subject and its verb that do not change who the subject is.
_BETWEEN = frozenset({"ne", "n", "y", "en", "toujours", "déjà", "aussi", "vraiment", "bien", "jamais"})
_PLURAL_DETERMINERS = frozenset(
    {"les", "mes", "tes", "ses", "nos", "vos", "leurs", "des", "ces", "plusieurs", "deux", "trois", "quatre", "cinq"}
)
_SINGULAR_DETERMINERS = frozenset(
    {"le", "la", "l", "un", "une", "mon", "ma", "ton", "ta", "son", "sa", "notre", "votre", "leur", "cet", "cette"}
)
_PREPOSITIONS = frozenset({"pour", "avec", "chez", "à", "de", "d", "sans", "sur", "sous", "par", "contre", "comme"})
#: A person's subject marker: the replacement «suis» needs a «je» (or «moi») in the clause.
_PERSON_MARKERS: dict[str, frozenset[str]] = {
    "1sg": frozenset({"je", "j", "moi"}),
    "2sg": frozenset({"tu", "toi"}),
    "1pl": frozenset({"nous", "moi"}),
    "2pl": frozenset({"vous", "toi", "tu"}),
}
#: «after 'tu'», «avec je», «with vous», «nach tu»: a note that hangs its rule on a subject.
_CITED_SUBJECT = re.compile(
    r"\b(?:after|with|following|nach|mit|avec|apr[eè]s|derri[eè]re)\s+[«'‘’\"“]?\s*"
    r"(je|j|tu|il|elle|on|nous|vous|ils|elles)\b",
    re.IGNORECASE,
)
_CITED_EQUIVALENTS: dict[str, frozenset[str]] = {
    "je": frozenset({"je", "j", "moi"}),
    "j": frozenset({"je", "j", "moi"}),
    "tu": frozenset({"tu", "toi"}),
}
_CLAUSE_TOKEN = re.compile(r"[^\W_]+(?:-[^\W_]+)*|[.,;:!?…()]")


def _clause_tokens(value: object) -> list[str]:
    """Words and clause-ending punctuation, lower-cased, elisions split («j'ai» ->
    «j», «ai»). Unlike :func:`fold_typography` the punctuation stays: a subject two
    sentences back is not the subject of this verb."""

    text = unicodedata.normalize("NFC", "" if value is None else str(value)).translate(_TRANSLATE)
    return _CLAUSE_TOKEN.findall(text.casefold())


def _is_word(token: str) -> bool:
    return token[:1].isalnum()


def _find_spans(tokens: list[str], span: list[str]) -> list[list[int]]:
    """Every place the words of ``span`` stand in ``tokens`` (punctuation ignored), as
    the token index of each of its words."""

    if not span:
        return []
    positions = [i for i, token in enumerate(tokens) if _is_word(token)]
    words = [tokens[i] for i in positions]
    return [
        positions[index : index + len(span)]
        for index in range(len(words) - len(span) + 1)
        if words[index : index + len(span)] == span
    ]


def _clause_before(tokens: list[str], index: int) -> list[str]:
    """The words of the clause in front of ``tokens[index]`` (stops at punctuation)."""

    before: list[str] = []
    for token in reversed(tokens[:index]):
        if not _is_word(token):
            break
        before.append(token)
    before.reverse()
    return before


#: Object pronouns that sit between a subject and its verb («je lui ai», «il nous a»).
_OBJECT_CLITICS = frozenset(
    {"me", "m", "te", "t", "se", "s", "lui", "leur", "nous", "vous", "le", "la", "l", "les", "moi", "toi"}
)
_CLITIC_SUBJECTS = frozenset({"je", "j", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles"})


def _subject_before_clitics(before: list[str]) -> str | None:
    """«Je lui a», «il nous ont», «je vous est»: the pronoun right before the verb is
    its object, and the subject stands in front of it. Returns that subject's person,
    ``""`` when the subject pronoun is there but its person cannot be told («Marie et
    elle lui…»), or ``None`` when the words before the verb are not object clitics
    after a subject pronoun (then the caller reads them as usual: «nous sommes»,
    «Marie et moi suis»)."""

    index = len(before) - 1
    skipped = 0
    while index >= 0 and (before[index] in _OBJECT_CLITICS or before[index] in _BETWEEN):
        if before[index] in _OBJECT_CLITICS:
            skipped += 1
        index -= 1
        if index >= 0 and before[index] in _CLITIC_SUBJECTS and skipped:
            subject = before[index]
            if subject == "elle" and index > 0 and before[index - 1] == "et":
                return ""
            return "3sg" if subject == "elle" else _SUBJECT_PRONOUNS[subject]
    return None


def _subject_person(before: list[str]) -> str | None:
    """Who the subject right before a verb is («1sg», «3pl»…), or ``None`` when the
    sentence does not say (a noun phrase it cannot read, a coordination of unknown
    people). Only a subject read with confidence may prove a form right or wrong."""

    before = list(before)
    while before and before[-1] in _BETWEEN:
        before.pop()
    if not before:
        return None
    clitic_subject = _subject_before_clitics(before)
    if clitic_subject is not None:
        return clitic_subject or None
    word, rest = before[-1], before[:-1]
    if word in _SUBJECT_PRONOUNS:
        return _SUBJECT_PRONOUNS[word]
    if word == "elle":
        # «Marie et elle sont» is plural; «… et elle est» may start a new clause.
        return None if rest and rest[-1] == "et" else "3sg"
    if word in _DISJUNCTIVE:
        if rest and rest[-1] in _PREPOSITIONS:
            return None  # «pour moi est…»: not a subject
        if rest and rest[-1] == "et":
            other = rest[-2] if len(rest) >= 2 else ""
            if word == "moi" or other in {"moi", "nous", "je", "j"}:
                return "1pl"
            if word == "toi" or other in {"toi", "tu", "vous"}:
                return "2pl"
            return "3pl"
        return _DISJUNCTIVE[word]
    # A noun phrase: only read when a determiner shows its number and no «et» can make
    # it a coordination («Marie et Anna est» is plural; «ma sœur et mon frère» too).
    if word in _PREPOSITIONS or word in {"et", "que", "qui", "où", "mais", "ou", "si", "quand", "pas"}:
        return None
    window = before[-4:]
    if "et" in window[:-1]:
        return None
    if any(token in {"de", "d", "du", "des"} for token in window[:-1]):
        # «La maison de mes parents sont»: the determiner seen may be the complement's,
        # not the head noun's.
        return None
    if any(token in _PLURAL_DETERMINERS for token in window[:-1]):
        return "3pl"
    if any(token in _SINGULAR_DETERMINERS for token in window[:-1]) and not word.endswith(("s", "x")):
        return "3sg"
    return None


def _word_swap(span_tokens: list[str], corrected_tokens: list[str]) -> tuple[int, str, str] | None:
    """When the correction changes exactly one word of the span, ``(position, before,
    after)``."""

    if len(span_tokens) != len(corrected_tokens):
        return None
    changed = [i for i, (a, b) in enumerate(zip(span_tokens, corrected_tokens, strict=True)) if a != b]
    if len(changed) != 1:
        return None
    i = changed[0]
    return i, span_tokens[i], corrected_tokens[i]


def correction_is_grounded(
    learner_text: object,
    span: object,
    corrected: object,
    note: object = None,
) -> bool:
    """Whether a proposed correction is about what the learner wrote.

    * the quoted ``span`` is found, word for word, in ``learner_text``;
    * a subject the note leans on («after 'tu'») appears in the sentence;
    * when the correction changes a single être/avoir/aller form, that form is
      wrong for the subject in front of it and the replacement is right for it.
      A subject the sentence does not make clear never rejects.
    """

    text_tokens = _clause_tokens(learner_text)
    span_words = [t for t in _clause_tokens(span) if _is_word(t)]
    places = _find_spans(text_tokens, span_words)
    if not places:
        return False
    present = {t for t in text_tokens if _is_word(t)}
    for match in _CITED_SUBJECT.finditer(str(note or "")):
        cited = match.group(1).casefold()
        if not (_CITED_EQUIVALENTS.get(cited, frozenset({cited})) & present):
            return False
    swap = _word_swap(span_words, [t for t in _clause_tokens(corrected) if _is_word(t)])
    if swap is None:
        return True
    position, old, new = swap
    old_persons, new_persons = _FORM_PERSONS.get(old), _FORM_PERSONS.get(new)
    if old_persons is None or new_persons is None:
        return True
    # The span may stand twice («Elle est là. Toi est gentil.»): one place where the
    # correction holds is enough.
    return any(
        _swap_holds(_clause_before(text_tokens, place[position]), old_persons, new_persons)
        for place in places
    )


def _swap_holds(before: list[str], old_persons: frozenset[str], new_persons: frozenset[str]) -> bool:
    person = _subject_person(before)
    if person is not None:
        return person not in old_persons and person in new_persons
    # Subject unreadable: a first/second-person replacement still needs its pronoun
    # somewhere in the clause («est → es» with no «tu» or «toi» in it was the #193 bug).
    if not any(p in {"3sg", "3pl"} for p in new_persons):
        wanted = frozenset().union(*(_PERSON_MARKERS.get(p, frozenset()) for p in new_persons))
        return bool(wanted & set(before))
    return True


_BE_FOR_HAVE = re.compile(
    r"\bje suis (froid|faim|soif|peur|sommeil)\b(?: (\w+)(?: (\w+))?)?", re.IGNORECASE
)
#: «Je suis froid avec elle», «… et distant», «… de nature» are French: «froid» then
#: describes the person. It is the slip only when nothing follows, a time or place
#: does («Je suis froid ici»), or a new clause starts («Je suis froid et un peu triste»).
_COLD_THEN_SETTING = frozenset({"ici", "aujourd", "maintenant", "ce", "cette", "car", "parce", "quand", "depuis"})
_COLD_THEN_CLAUSE = frozenset(
    {"je", "j", "il", "elle", "on", "nous", "vous", "un", "une", "ma", "mon", "mes", "le", "la", "les", "ça", "c"}
)
_SLIP_NOTE = {
    "en": "In French you «have» cold, hunger or thirst: j'ai {word}, not je suis {word}.",
    "de": "Auf Französisch «hat» man Kälte, Hunger oder Durst: j'ai {word}, nicht je suis {word}.",
    "fr": "En français on « a » froid, faim ou soif : j'ai {word}, pas je suis {word}.",
}


def _cold_is_temperature(next_word: str | None, after: str | None) -> bool:
    following = (next_word or "").casefold()
    if not following or following in _COLD_THEN_SETTING:
        return True
    return following in {"et", "mais"} and (after or "").casefold() in _COLD_THEN_CLAUSE


def known_slip(learner_text: object, language: str | None = "en") -> tuple[str, str, str] | None:
    """A slip the app can name without a model: «Je suis froid» -> «J'ai froid»
    (French says «avoir froid», not «être froid»). Returns ``(span, fix, note)``, the
    note in the learner's language. Unambiguous cases only: «je suis froid avec elle»
    and «je suis chaud pour ça» are valid French and never match."""

    text = " ".join(str(learner_text or "").replace("’", "'").split())
    for match in _BE_FOR_HAVE.finditer(text):
        word = match.group(1).casefold()
        if word == "froid" and not _cold_is_temperature(match.group(2), match.group(3)):
            continue
        span = " ".join(match.group(0).split(" ")[:3])
        fix = f"j'ai {word}"
        if span[:1].isupper():
            fix = fix[:1].upper() + fix[1:]
        table = _SLIP_NOTE.get(str(language or "en")[:2].lower()) or _SLIP_NOTE["en"]
        return span, fix, table.format(word=word)
    return None

