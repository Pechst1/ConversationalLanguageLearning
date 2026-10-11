"""Le lexique de base — the core French list (A1 → C1) as drillable catalogue rows.

The content audit of 2026-10-03 found the 2,682-lemma core lexicon was never
loaded into ``vocabulary_words``: the drill introduced only ``is_anki_card`` rows,
so a learner without an imported deck had no planned source of new words at all,
while the level gate asked for 80 % of each sub-band's word list on a card.

This module mirrors ``app/data/lexical/fr_core_lexicon.json`` (v3: ~6,900 lemmas
A1.1 … C1.2, with POS, gender and en/de glosses) into shared catalogue rows:

* one row per non-numeral lemma, ``deck_name`` :data:`CORE_DECK`, no direction
  (the learner's own card is the ``user_vocabulary_progress`` row);
* ``frequency_rank`` is the learning order (sub-band, then the lexicon's rank),
  so the drill's rank ordering introduces the list in sequence;
* ``difficulty_level`` is the band (A1 = 1 … C1 = 5) and ``topic_tags`` carry the
  band and sub-band, which is how the drill starts a learner at their own band;
* ``card_id`` holds the marker of the lexicon build the row was written from, so
  :func:`ensure_core_lexicon` is one count query once the table is current.

Compound numerals are not seeded: numbers are taught by the NUMBERS units.
"""

from __future__ import annotations

import hashlib
import threading
from functools import lru_cache
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.vocabulary import VocabularyWord
from app.services.lexical_coverage import BAND_ORDER, LEXICON_PATH, fold, load_lexicon

CORE_DECK = "Lexique de base"
CORE_TAG = "core_lexicon"
#: WP-131: a lemma the list took from a frequency corpus (``source: anki_rank``,
#: most of B2–C1: «sénateur», «islamiste», «bombardement») rather than from a
#: curated theme. The drill interleaves these with curated and story words
#: instead of introducing them in uncontextualised blocks (app/services/word_order).
CORPUS_TAG = "core_corpus"
#: Bumped when the row fields change shape, so deployed catalogues re-sync once.
FIELDS_VERSION = "f2"
LANGUAGE = "fr"

_lock = threading.Lock()


def core_marker() -> str:
    """``core:<version>:<sha8>`` of the lexicon file the rows should mirror (≤ 50 chars)."""

    try:
        mtime_ns = LEXICON_PATH.stat().st_mtime_ns
    except OSError:  # pragma: no cover - a missing file seeds nothing
        mtime_ns = 0
    return _marker(mtime_ns)


@lru_cache(maxsize=4)
def _marker(mtime_ns: int) -> str:
    try:
        digest = hashlib.sha256(LEXICON_PATH.read_bytes()).hexdigest()[:8]
    except OSError:  # pragma: no cover
        digest = "missing"
    return f"core:{load_lexicon().version}:{digest}:{FIELDS_VERSION}"[:50]


def band_level(band: str | None) -> int:
    """A1 = 1 … C1 = 5 (C2 = 6); unreadable is 1."""

    raw = str(band or "").upper()[:2]
    return BAND_ORDER.index(raw) + 1 if raw in BAND_ORDER else 1


SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")


def _entries() -> list[tuple[str, dict[str, Any]]]:
    """Non-numeral lemmas in learning order: sub-band first, then the list's rank."""

    def order(item: tuple[str, dict[str, Any]]) -> tuple[int, int, str]:
        lemma, entry = item
        sub_band = str(entry.get("sub_band") or "")
        return (SUB_BANDS.index(sub_band) if sub_band in SUB_BANDS else len(SUB_BANDS),
                int(entry.get("rank") or 0), lemma)

    return sorted(
        (
            (lemma, entry)
            for lemma, entry in load_lexicon().lemmas.items()
            if not entry.get("numeral") and lemma.strip()
        ),
        key=order,
    )


@lru_cache(maxsize=4)
def _entry_count(marker: str) -> int:
    return len(_entries())


def _fields(lemma: str, entry: dict[str, Any], marker: str, position: int) -> dict[str, Any]:
    gloss = entry.get("gloss") if isinstance(entry.get("gloss"), dict) else {}
    tags = [CORE_TAG, str(entry.get("band") or ""), str(entry.get("sub_band") or "")]
    if entry.get("register"):
        tags.append(f"register:{entry['register']}")
    if entry.get("source") == "anki_rank":
        tags.append(CORPUS_TAG)
    return {
        "word": lemma,
        "normalized_word": fold(lemma),
        "part_of_speech": entry.get("pos"),
        "gender": entry.get("gender") if entry.get("gender") in {"m", "f", "mf"} else None,
        # Learning order (sub-band, then rank), so the drill's rank ordering
        # introduces A1.1 before A1.2; not a corpus frequency.
        "frequency_rank": position,
        "english_translation": (gloss.get("en") or None),
        "german_translation": (gloss.get("de") or None),
        "difficulty_level": band_level(entry.get("band")),
        "topic_tags": [tag for tag in tags if tag],
        "deck_name": CORE_DECK,
        "card_id": marker,
        "is_anki_card": False,
        "direction": None,
    }


def sync_core_lexicon(db: Session) -> int:
    """Upsert the core rows from the lexicon file; returns the rows written. Idempotent."""

    marker = core_marker()
    existing = {
        row.normalized_word: row
        for row in db.scalars(
            select(VocabularyWord).where(
                VocabularyWord.language == LANGUAGE,
                VocabularyWord.deck_name == CORE_DECK,
            )
        )
    }
    written = 0
    for position, (lemma, entry) in enumerate(_entries(), start=1):
        fields = _fields(lemma, entry, marker, position)
        row = existing.get(fields["normalized_word"])
        if row is None:
            db.add(VocabularyWord(language=LANGUAGE, **fields))
            written += 1
            continue
        changed = False
        for name, value in fields.items():
            if getattr(row, name) != value:
                setattr(row, name, value)
                changed = True
        written += int(changed)
    db.flush()
    return written


def ensure_core_lexicon(db: Session) -> None:
    """The core rows mirror the current lexicon build: one count query once current.

    No per-process memo: a request that rolls back takes its sync with it, and
    the next caller simply syncs again.
    """

    marker = core_marker()
    current = int(
        db.scalar(
            select(func.count(VocabularyWord.id)).where(
                VocabularyWord.deck_name == CORE_DECK,
                VocabularyWord.card_id == marker,
            )
        )
        or 0
    )
    if current >= _entry_count(marker):
        return
    with _lock:
        try:
            with db.begin_nested():
                written = sync_core_lexicon(db)
            logger.info("core lexicon synced: {} rows written ({})", written, marker)
        except Exception:  # noqa: BLE001 - a word list never costs the request
            logger.exception("core lexicon sync failed")


__all__ = [
    "CORE_DECK",
    "CORE_TAG",
    "CORPUS_TAG",
    "band_level",
    "core_marker",
    "ensure_core_lexicon",
    "sync_core_lexicon",
]
