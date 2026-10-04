"""WP-129 — is a practice sentence at the learner's level?

A catalogue sentence is written for its unit's own band; a B1+ practice item on
an earlier unit (a contrast, a free sentence's model) stays at the learner's
level. Kept out of :mod:`app.services.grammar_items`, which stays pure (no I/O):
the planner hands the check to the item builders as a predicate.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.grammar_items import fold_apostrophes

_BANDS = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


@lru_cache(maxsize=1)
def _word_bands() -> dict[str, int]:
    """Each French word's band in the core lexicon (a form takes its lemma's)."""

    path = Path(__file__).resolve().parents[1] / "data" / "lexical" / "fr_core_lexicon.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    bands: dict[str, int] = {}
    for lemma, entry in (data.get("lemmas") or {}).items():
        if isinstance(entry, dict) and " " not in lemma:
            band = _BANDS.get(str(entry.get("band") or "")[:2].upper(), 1)
            bands[lemma.casefold()] = min(band, bands.get(lemma.casefold(), band))
    lemma_band = dict(bands)
    for form, lemma in (data.get("forms") or {}).items():
        band = lemma_band.get(str(lemma).casefold())
        if band is not None:
            bands[form.casefold()] = min(band, bands.get(form.casefold(), band))
    return bands


def within_band(text: str | None, level: str | None, *, slack: int = 1) -> bool:
    """WP-129: is every word of ``text`` at most ``slack`` bands above ``level``?

    A catalogue sentence written for a unit's own band may hold a word a B1
    learner has not met; a practice item of an earlier unit stays at the
    learner's level. A capitalised word after the first is a name.
    """

    if not level:
        return True
    bands = _word_bands()
    limit = _BANDS.get(str(level)[:2].upper(), 1) + slack
    for index, raw in enumerate(re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", str(text or ""))):
        if index and raw[:1].isupper():
            continue
        whole = fold_apostrophes(raw).casefold()
        token = whole.split("'")[-1]
        band = bands.get(whole, bands.get(token))
        for ending, infinitive in (("ées", "er"), ("és", "er"), ("ée", "er"), ("é", "er")):
            if band is not None and token.endswith(ending):
                verb = bands.get(token[: -len(ending)] + infinitive)
                band = min(band, verb) if verb is not None else band
                break
        if band is not None and band > limit:
            return False
    return True




__all__ = ["within_band"]
