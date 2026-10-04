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
from dataclasses import dataclass
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
    """

    correct: bool
    exact: bool = False
    accent_slip: bool = False
    typo: bool = False
    note: str | None = None
    expected: str | None = None
    learner_word: str | None = None
    expected_word: str | None = None


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
        strict = accents == "strict" or any(_accent_strict_word(got, want) for got, want in slips)
        got, want = slips[0]
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
_NOTE_PRIORITY = {"gender": 5, "elision": 4, "accent": 3, "form": 2, "typo": 1}


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
