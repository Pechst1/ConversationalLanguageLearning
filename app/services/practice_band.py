"""Practice band — which words of an answer sit above the learner's band.

One definition for the product and the walk: an item built from the story may
*show* any word of its line (with its gloss), but never makes a word above the
learner's band the answer. "Above" is the core lexicon's band more than
``slack`` (one) band over the learner's, the rule of WP-129's
:func:`app.services.practice_level.within_band` and of the walk's
``check_level`` (``tests/walk_checks.item_words_above``, which reads its bands
from :func:`word_band`).

One correction to the lexicon lookup: a regular ``-er`` verb form that is also a
noun lemma («je garde», «je signe», «Écoute !») is the verb's word as well. The
lexicon lists the noun («la garde», B2) and not the form, so «Je le garde.» read
as B2 for an A2 learner who has had «garder» since A2. The form takes the lower
of the two bands, as a participle already takes its verb's.
"""
from __future__ import annotations

import re

from app.services.grammar_items import fold_apostrophes
from app.services.practice_level import _BANDS, _word_bands

_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
#: Participles take their verb's band (``within_band``'s rule).
_PARTICIPLES = (("ées", "er"), ("és", "er"), ("ée", "er"), ("é", "er"))
#: Present and imperative endings of a regular ``-er`` verb that make a noun's
#: homograph («garde», «gardes», «gardent», «signons», «écoutez»).
_ER_FORMS = ("ent", "ons", "ez", "es", "e")


def level_rank(level: str | None) -> int:
    return _BANDS.get(str(level or "")[:2].upper(), 1)


def word_band(raw: str) -> int | None:
    """The band of one written word (``None`` when the lexicon does not know it)."""

    bands = _word_bands()
    whole = fold_apostrophes(raw).casefold()
    token = whole.split("'")[-1]
    band = bands.get(whole, bands.get(token))
    if band is None:
        return None
    for ending, infinitive in _PARTICIPLES:
        if token.endswith(ending):
            verb = bands.get(token[: -len(ending)] + infinitive)
            return min(band, verb) if verb is not None else band
    for ending in _ER_FORMS:
        if token.endswith(ending) and len(token) > len(ending) + 1:
            verb = bands.get(token[: -len(ending)] + "er")
            if verb is not None:
                return min(band, verb)
            break
    return band


def words_above(text: str | None, level: str | None, *, slack: int = 1) -> list[str]:
    """Words of ``text`` more than ``slack`` bands above ``level``, in order.

    A capitalised word after the first is a name and never counts. Without a
    level, nothing is above it.
    """

    if not level:
        return []
    limit = level_rank(level) + slack
    above: list[str] = []
    for index, raw in enumerate(_WORD.findall(str(text or ""))):
        if index and raw[:1].isupper():
            continue
        band = word_band(raw)
        if band is not None and band > limit:
            above.append(raw)
    return above


def at_band(text: str | None, level: str | None, *, slack: int = 1) -> bool:
    """May ``text`` be an answer for a learner at ``level``?"""

    return not words_above(text, level, slack=slack)


__all__ = ["at_band", "level_rank", "word_band", "words_above"]
