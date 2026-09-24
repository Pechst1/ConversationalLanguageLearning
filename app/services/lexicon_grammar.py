"""WP-84 — a French word's part of speech and gender, from the core lexicon.

Two curated sources, no guessing:

* ``app/data/lexical/fr_core_lexicon.json`` — the 139 nouns WP-S2 annotated
  with ``pos`` / ``gender``;
* ``app/data/lexical/fr_core_pos.json`` — every other lemma of the lexicon,
  hand-classified by ``scripts/build_lexicon_pos.py`` (1,149 nouns with their
  gender, verbs, adjectives, adverbs, function words, numbers).

A card's surface is read the way a learner wrote it: «le frère», «la clé»,
«l'hiver» and «frère» all find ``frère``. The stored card wins wherever it has
a value; the lexicon only fills what the card lacks (and replaces the suffix
heuristic, which printed «frère», «hiver», «notre» as verbs).
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

POS_PATH = Path(__file__).resolve().parents[1] / "data" / "lexical" / "fr_core_pos.json"

_ARTICLES = ("le ", "la ", "les ", "un ", "une ", "des ", "l'", "l’", "du ", "de la ", "de l'")


def _fold(value: str) -> str:
    return unicodedata.normalize("NFC", str(value or "").strip().lower()).replace("’", "'")


@lru_cache(maxsize=1)
def lexicon_grammar_table() -> dict[str, dict[str, str]]:
    """``lemma → {pos, gender?}`` for the whole core lexicon."""

    from app.services.lexical_coverage import LEXICON_PATH

    table: dict[str, dict[str, str]] = {}
    try:
        payload = json.loads(POS_PATH.read_text(encoding="utf-8"))
        for lemma, entry in (payload.get("lemmas") or {}).items():
            table[_fold(lemma)] = {k: str(v) for k, v in entry.items() if v}
    except (OSError, ValueError):  # pragma: no cover - a missing file annotates nothing
        pass
    try:
        lexicon = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))
        for lemma, entry in (lexicon.get("lemmas") or {}).items():
            if entry.get("pos"):
                row = {"pos": str(entry["pos"])}
                if entry.get("gender"):
                    row["gender"] = str(entry["gender"])
                table[_fold(lemma)] = row
    except (OSError, ValueError):  # pragma: no cover
        pass
    return table


def lemma_key(surface: Any) -> str:
    """«La clé» → «clé», «l'hiver» → «hiver»; anything else folded as is."""

    text = _fold(str(surface or ""))
    for article in _ARTICLES:
        if text.startswith(article) and len(text) > len(article):
            return text[len(article):].strip()
    return text


def lexicon_entry(surface: Any) -> dict[str, str] | None:
    table = lexicon_grammar_table()
    key = lemma_key(surface)
    return table.get(key) or table.get(_fold(str(surface or "")))


def lexicon_pos(surface: Any) -> str:
    entry = lexicon_entry(surface)
    return entry.get("pos", "") if entry else ""


def lexicon_gender(surface: Any) -> str | None:
    """``m`` / ``f`` for a noun the lexicon knows; ``None`` otherwise (and for
    an epicene noun, which has no one article)."""

    entry = lexicon_entry(surface)
    if not entry or entry.get("pos") != "noun":
        return None
    gender = entry.get("gender")
    return gender if gender in {"m", "f"} else None


def word_grammar(word: Any) -> tuple[str | None, str | None]:
    """``(part_of_speech, gender)`` for a card: stored values first, then the
    lexicon for a French card. The gender is only given to a noun."""

    pos = getattr(word, "part_of_speech", None) or None
    gender = getattr(word, "gender", None) or None
    language = str(getattr(word, "language", None) or "fr").lower()
    if language != "fr":
        return pos, gender
    surface = getattr(word, "word", None) or getattr(word, "normalized_word", None)
    if not pos:
        pos = lexicon_pos(surface) or None
    if not gender and str(pos or "").lower() in {"noun", "nom", "n"}:
        gender = lexicon_gender(surface)
    return pos, gender


__all__ = [
    "lemma_key",
    "lexicon_entry",
    "lexicon_gender",
    "lexicon_grammar_table",
    "lexicon_pos",
    "word_grammar",
]
