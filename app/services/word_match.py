"""Does the learner's text contain this target word? One answer, in one place.

#236 / #146. The Courrier told a learner «vendre · used» for «Je préfère
vendredi»: «vendre» is the first six letters of «vendredi», and the code that
asked «did the learner write this word?» compared strings with ``in`` or
``startswith``. It was written three times in the backend (living_story,
story_lanes, story_service's stem prefix) and once in the browser (the word
ribbon in pages/missions.tsx), each a little different and none of them a word.

A target is used when the learner wrote that **word**: a whole token, in any
accent or case, or one of its real inflections (the verb conjugated, the noun or
adjective in the plural or feminine). Never a longer word that merely starts or
ends the same way, and never a different word that happens to be a form of
another verb (the auxiliary «ai» in «j'ai vendu» is not «vendre»).

Callers ask :func:`target_occurs_in`; nothing else in ``app/`` should compare a
target to learner text with ``in`` or ``startswith``
(``tests/test_story_target_match.py`` holds that line). The browser keeps the
same rule in ``web-frontend/lib/word-match.ts``.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_TOKEN = re.compile(r"[a-z0-9]+")
_APOSTROPHES = re.compile(r"[‘’‛′´`]")

#: A leading article or clitic is not part of the word being asked for.
_LEADING = frozenset({"le", "la", "les", "un", "une", "des", "du", "de", "l", "se", "s", "d", "ne", "n"})

#: The shortest spelling a *derived* form may have. «être» + the «re» ending
#: with nothing after it would otherwise give «et»: a word of its own.
_MIN_DERIVED = 3

#: Endings that can follow a regular verb's stem, by infinitive group. They only
#: ever complete the *whole* token, so a long word cannot match by a short stem.
_VERB_ENDINGS = {
    "er": (
        "er", "e", "es", "ons", "ez", "ent", "ais", "ait", "ions", "iez", "aient", "ant",
        "erai", "eras", "era", "erons", "erez", "eront", "erais", "erait", "erions", "eriez", "eraient",
        "ee", "ees", "ai", "as", "a", "asse", "assent",
    ),
    "ir": (
        "ir", "is", "it", "issons", "issez", "issent", "issais", "issait", "issions", "issiez",
        "issaient", "issant", "i", "ie", "ies", "irai", "iras", "ira", "irons", "irez", "iront",
        "irais", "irait", "irions", "iriez", "iraient", "isse", "isses",
    ),
    "re": (
        "re", "", "s", "t", "ons", "ez", "ent", "ais", "ait", "ions", "iez", "aient", "ant",
        "rai", "ras", "ra", "rons", "rez", "ront", "rais", "rait", "rions", "riez", "raient",
        "u", "ue", "us", "ues", "e", "es",
    ),
}


def fold(text: object) -> str:
    """Lower case, no accents, one kind of apostrophe."""

    decomposed = unicodedata.normalize("NFKD", _APOSTROPHES.sub("'", str(text or "")).lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokens(text: object) -> list[str]:
    """The words of ``text``, folded: ``l'eau`` is ``l`` and ``eau``."""

    return _TOKEN.findall(fold(text))


@lru_cache(maxsize=2048)
def _forms(word: str) -> frozenset[str]:
    """Every folded spelling of one folded word that counts as the word."""

    forms = {word, f"{word}s", f"{word}x", f"{word}e", f"{word}es"}
    if word.endswith("al") and len(word) > 3:
        forms.add(f"{word[:-2]}aux")
    if len(word) > 3 and word[-2:] in _VERB_ENDINGS:
        irregular = _irregular_forms(word)
        forms.update(irregular)
        if not irregular:
            stem = word[:-2]
            forms.update(
                form
                for form in (f"{stem}{ending}" for ending in _VERB_ENDINGS[word[-2:]])
                if len(form) >= _MIN_DERIVED
            )
    return frozenset(forms)


def _irregular_forms(word: str) -> set[str]:
    """The verb's own forms from the conjugation table, for an irregular verb.

    Only the verb itself: a compound cell («j'ai vendu», «il est venu») adds its
    participle, never the auxiliary, or every verb would count as used whenever
    the learner wrote «j'ai» (#236 review). Empty for a regular verb.
    """

    try:
        from app.services.conjugation import (
            canonicalize_lemma,
            fallback_conjugation_table,
            is_irregular_verb,
        )
    except Exception:  # pragma: no cover - the table is an extra, never a requirement
        return set()
    try:
        lemma = canonicalize_lemma(word)
        if not is_irregular_verb(lemma):
            return set()
        table = fallback_conjugation_table(lemma)
    except Exception:  # pragma: no cover
        return set()
    found: set[str] = set()
    for tense, row in table.items():
        for cell in row.values():
            words = tokens(cell)
            if tense == "passe_compose":
                words = words[-1:]
            # «dû» folds to the article «du»: left out, it is not the verb's mark.
            found.update(token for token in words if token not in _LEADING)
    found.add(word)
    return found


def _wanted(label: object) -> list[str]:
    words = tokens(label)
    while len(words) > 1 and words[0] in _LEADING:
        words = words[1:]
    return words


def target_occurs_in(label: object, text: object) -> bool:
    """Whether ``text`` contains the target ``label`` as a word.

    ``label`` is a vocabulary entry («vendre», «la bouillotte», «avoir besoin de»)
    or a short phrase. The first word may be inflected; the others must be the
    words themselves. A label with no words, or a text with none, never matches.
    """

    wanted = _wanted(label)
    seen = tokens(text)
    if not wanted or not seen:
        return False
    head = _forms(wanted[0]) if len(wanted) > 1 or wanted[0] not in _LEADING else frozenset(wanted)
    for start, word in enumerate(seen):
        if word not in head:
            continue
        if seen[start + 1 : start + len(wanted)] == wanted[1:]:
            return True
    return False


__all__ = ["fold", "target_occurs_in", "tokens"]
