"""Does the learner's text contain this target word? One answer, in one place.

#236 / #146. The Courrier told a learner «vendre · used» for «Je préfère
vendredi»: the story engine marked a target as produced when the model said so
and the target's label was a *substring* of the reply, and «vendre» is the first
six letters of «vendredi». The test was written twice (living_story,
story_lanes) and a third time as a stem prefix (story_service), each a little
different, none of them a word.

A target is used when the learner wrote that **word**: a whole token, in any
accent or case, or one of its real inflections (the verb conjugated, the noun or
adjective in the plural or feminine). Never a longer word that merely starts or
ends the same way. Callers ask :func:`target_occurs_in`; nothing else in
``app/`` should compare a target to learner text with ``in`` or ``startswith``
(``tests/test_story_target_match.py`` holds that line).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_TOKEN = re.compile(r"[a-z0-9]+")
_APOSTROPHES = re.compile(r"[‘’‛′´`]")

#: A leading article or clitic is not part of the word being asked for.
_LEADING = frozenset({"le", "la", "les", "un", "une", "des", "du", "de", "l", "se", "s", "d", "ne", "n"})

#: Endings that can follow a regular verb's stem, by infinitive group. They only
#: ever complete the *whole* token, so a long word cannot match by a short stem.
_VERB_ENDINGS = {
    "er": (
        "er", "e", "es", "ons", "ez", "ent", "ais", "ait", "ions", "iez", "aient", "ant",
        "erai", "eras", "era", "erons", "erez", "eront", "erais", "erait", "erions", "eriez", "eraient",
        "e", "ee", "es", "ees", "ai", "as", "a", "asse", "assent",
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


#: Forms of avoir and être as they stand in front of a participle (folded).
_AUXILIARY_FORMS = frozenset(
    {"ai", "as", "a", "avons", "avez", "ont", "suis", "es", "est", "sommes", "etes", "sont"}
)
_AUXILIARY_LEMMAS = frozenset({"avoir", "etre"})
#: The verbs whose real forms are one or two letters long (a, ai, as, es, va).
_SHORT_FORM_VERBS = frozenset({"avoir", "etre", "aller"})
#: A form built from a stem and an ending must have at least this many letters.
_MIN_DERIVED_FORM = 3


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
        stem = word[:-2]
        # The table synthesises a conjugation for any word ending in -er/-ir/-re
        # (the noun «aire» "conjugates" to «ai»); a form of one or two letters is
        # trusted only for the few verbs that really have one.
        table = {
            form for form in _irregular_forms(word) if len(form) >= _MIN_DERIVED_FORM or word in _SHORT_FORM_VERBS
        }
        # A regular ending on a very short stem is not a form of the verb:
        # «etre» would give «et» (the word «and»). Short forms must come from the table.
        forms.update(
            form
            for form in (f"{stem}{ending}" for ending in _VERB_ENDINGS[word[-2:]])
            if len(form) >= _MIN_DERIVED_FORM or form in table
        )
        forms.update(table)
    return frozenset(forms)


def _irregular_forms(word: str) -> set[str]:
    """The conjugation table's forms for an irregular verb (être, aller, prendre...).

    Only the verb's own forms: a compound cell («j'ai vendu», «nous sommes allés»)
    contributes its participle, never the auxiliary in front of it, or every verb
    would be "used" by «J'ai faim». The verb avoir / être keeps its own forms.
    """

    try:
        from app.services.conjugation import canonicalize_lemma, fallback_conjugation_table
    except Exception:  # pragma: no cover - the table is an extra, never a requirement
        return set()
    found: set[str] = set()
    try:
        table = fallback_conjugation_table(canonicalize_lemma(word))
    except Exception:  # pragma: no cover
        return found
    own_auxiliary = word in _AUXILIARY_LEMMAS or fold(canonicalize_lemma(word)) in _AUXILIARY_LEMMAS
    for row in table.values():
        for cell in row.values():
            cell_tokens = tokens(cell)
            if not own_auxiliary:
                while len(cell_tokens) > 1 and cell_tokens[0] in _AUXILIARY_FORMS:
                    cell_tokens = cell_tokens[1:]
            found.update(cell_tokens)
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
