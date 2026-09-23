"""WP-L7 — the level as syllabus coverage of a sub-band.

The level a learner is shown is the sub-band they are working through
(A1.1 … B2.2). A band is *covered* when three things are true:

* **units held** — at least :data:`UNITS_HELD_SHARE` (85 %) of the band's
  grammar units are held (:func:`held_unit_ids`: WP-L4's «Tenue»);
* **words known** — at least :data:`WORDS_KNOWN_SHARE` (80 %) of the band's core
  words are known: a card for the lemma with retrievability ≥
  :data:`WORD_KNOWN_RETRIEVABILITY` (0.85), seen at least twice and not in
  relearning;
* **the checkpoint** — the band's «épreuve» is passed
  (:mod:`app.services.level_checkpoint`). Coverage of the first two makes the
  learner *ready* for it.

Which units belong to a band:

* catalogue **v2** (``ATELIER_GRAMMAR_CATALOG_VERSION=v2``): the unit's own
  ``sub_band`` tag;
* catalogue **v1** (no sub-bands): the concepts of the band's CEFR level (A1,
  A2 …), split in two halves by teaching order (``difficulty_order``, then id);
  the first half is ``.1``, the rest ``.2``.

The band's words are the core lexicon's lemmas tagged with that ``sub_band``
(``app/data/lexical/fr_core_lexicon.json``), minus the closed-class words
(articles, pronouns, determiners, prepositions, conjunctions): those are taught
by the grammar units and rarely have a card of their own, so counting them
would put 80 % out of reach for a learner who knows every one of them.

Read-only. Nothing here writes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.db.models.progress import UserVocabularyProgress
from app.db.models.vocabulary import VocabularyWord

#: The sub-bands the level walks, lowest first (mirrors ``cefr_progress.CEFR_LEVELS``).
SUB_BANDS: tuple[str, ...] = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2")

UNITS_HELD_SHARE = 0.85
WORDS_KNOWN_SHARE = 0.80
WORD_KNOWN_RETRIEVABILITY = 0.85
#: A word counts as known only after its second successful sighting: a card
#: reviewed a minute ago has a retrievability of 1.0 whether it was learned or
#: just shown.
WORD_KNOWN_MIN_REPS = 2
_WORD_UNSETTLED_STATES = frozenset({"new", "learning", "relearning", "relearn", "learn"})

#: How the percent shown beside the band («A1.1 · 60 %») is made up: the two
#: coverage criteria, each capped at its threshold, and the checkpoint. Coverage
#: without the épreuve therefore reads 90 %, never 100 %.
PERCENT_WEIGHT_UNITS = 0.45
PERCENT_WEIGHT_WORDS = 0.45
PERCENT_WEIGHT_CHECKPOINT = 0.10

#: Closed-class words: taught through the grammar units, not word cards.
CLOSED_CLASS_WORDS: frozenset[str] = frozenset(
    {
        # articles, partitives, contractions
        "le", "la", "les", "l'", "un", "une", "des", "de", "d'", "du", "au", "aux",
        # subject / object / stressed / reflexive pronouns
        "je", "j'", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
        "me", "m'", "te", "t'", "se", "s'", "moi", "toi", "lui", "leur", "leurs", "eux",
        "y", "en",
        # possessives
        "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre", "nos", "votre", "vos",
        # demonstratives
        "ce", "c'", "cet", "cette", "ces", "ça", "cela", "ceci", "celui", "celle", "ceux", "celles",
        # relatives / interrogatives
        "que", "qu'", "qui", "quoi", "dont", "lequel", "laquelle", "lesquels", "lesquelles",
        "quel", "quelle", "quels", "quelles",
        # prepositions
        "à", "dans", "sur", "sous", "avec", "sans", "pour", "par", "chez", "entre", "vers",
        "contre", "depuis", "pendant",
        # conjunctions and negation
        "et", "ou", "mais", "donc", "or", "ni", "car", "si", "ne", "n'", "pas", "comme", "quand",
    }
)


# ---------------------------------------------------------------------------
# Bands
# ---------------------------------------------------------------------------


def band_index(band: str | None) -> int:
    try:
        return SUB_BANDS.index(str(band or "A1.1"))
    except ValueError:
        return 0


def band_level(band: str) -> str:
    """``"A1.2"`` → ``"A1"``."""

    return str(band or "A1.1")[:2].upper()


def next_band(band: str | None) -> str | None:
    index = band_index(band)
    return SUB_BANDS[index + 1] if index + 1 < len(SUB_BANDS) else None


# ---------------------------------------------------------------------------
# Units per band
# ---------------------------------------------------------------------------


def _is_french(concept: GrammarConcept) -> bool:
    return str(getattr(concept, "language", "") or "fr").strip().casefold().startswith(("fr", "français"))


def band_unit_ids(db: Session, band: str) -> list[int]:
    """The active grammar units (concept ids) of one sub-band, in teaching order."""

    from app.services.grammar_catalog import (
        FRENCH_CORE_CATALOG_V2_VERSION,
        active_catalog_version,
        concept_sub_band,
    )

    concepts = (
        db.query(GrammarConcept)
        .filter(GrammarConcept.active.is_(True))
        .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
        .all()
    )
    concepts = [concept for concept in concepts if _is_french(concept)]
    if active_catalog_version() == FRENCH_CORE_CATALOG_V2_VERSION:
        return [concept.id for concept in concepts if concept_sub_band(concept) == band]
    # v1: the band's CEFR level, halved by teaching order.
    level = band_level(band)
    in_level = [
        concept
        for concept in concepts
        if str(concept.level or "").strip().upper()[:2] == level and not concept_sub_band(concept)
    ]
    half = math.ceil(len(in_level) / 2)
    part = in_level[:half] if band.endswith(".1") else in_level[half:]
    return [concept.id for concept in part]


def held_unit_ids(db: Session, user: Any, *, now: datetime | None = None) -> set[int]:
    """The grammar units this learner *holds* («Tenue», §2.4).

    WP-L4's rule (:func:`app.services.concept_life.held_concept_ids`): correct
    free use on two days at least 7 days apart plus a correct spaced item at
    least 14 days after the introduction. ``held_at`` is written the first time
    that is true and never cleared, so a lapse makes a unit fragile (it comes
    back through the scheduler) without uncovering its band.
    """

    from app.services.concept_life import held_concept_ids

    return held_concept_ids(db, user.id)


# ---------------------------------------------------------------------------
# Words per band
# ---------------------------------------------------------------------------


@lru_cache(maxsize=16)
def band_words(band: str) -> frozenset[str]:
    """The band's core lemmas (folded), closed-class words excluded."""

    from app.services.lexical_coverage import load_lexicon

    lexicon = load_lexicon()
    return frozenset(
        lemma
        for lemma, entry in lexicon.lemmas.items()
        if str(entry.get("sub_band") or "") == band and lemma not in CLOSED_CLASS_WORDS
    )


def lemmas_of_card(word: VocabularyWord) -> set[str]:
    """Core-lexicon lemmas a card teaches («le chien» → {"le", "chien"})."""

    from app.services.lexical_coverage import load_lexicon, tokenize

    lexicon = load_lexicon()
    found: set[str] = set()
    for surface in (getattr(word, "normalized_word", None), getattr(word, "word", None)):
        for token in tokenize(str(surface or "")):
            key = token.key
            if key in lexicon.lemmas:
                found.add(key)
            elif key in lexicon.forms:
                found.add(lexicon.forms[key])
    return found


def word_retrievability(progress: UserVocabularyProgress, *, now: datetime) -> float | None:
    from app.services.vocabulary_coverage import _retrievability

    return _retrievability(progress, now=now)


def is_word_known(progress: UserVocabularyProgress, *, now: datetime) -> bool:
    """Retrievability ≥ 0.85 on a settled card seen at least twice.

    A legacy row with no memory (imported, no stability) counts when it was
    marked mastered — the same evidence the old counters trusted.
    """

    state = str(getattr(progress, "state", "") or "").lower()
    phase = str(getattr(progress, "phase", "") or "").lower()
    retrievability = word_retrievability(progress, now=now)
    if retrievability is None:
        return bool(progress.mastered_date or state in {"mastered", "gemeistert"})
    if int(progress.reps or 0) < WORD_KNOWN_MIN_REPS:
        return False
    if state in _WORD_UNSETTLED_STATES or phase in {"learn", "relearn"}:
        return False
    return retrievability >= WORD_KNOWN_RETRIEVABILITY


def known_lemmas(db: Session, user: Any, *, now: datetime | None = None) -> set[str]:
    """Every core lemma for which the learner holds a known card."""

    now = now or datetime.now(UTC)
    rows = (
        db.query(UserVocabularyProgress, VocabularyWord)
        .join(VocabularyWord, UserVocabularyProgress.word_id == VocabularyWord.id)
        .filter(UserVocabularyProgress.user_id == user.id)
        .all()
    )
    known: set[str] = set()
    for progress, word in rows:
        if is_word_known(progress, now=now):
            known |= lemmas_of_card(word)
    return known


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BandCoverage:
    band: str
    units_held: int
    units_total: int
    words_known: int
    words_total: int
    checkpoint_passed: bool = False
    unit_ids: tuple[int, ...] = field(default=(), repr=False)

    @property
    def units_required(self) -> int:
        return math.ceil(self.units_total * UNITS_HELD_SHARE) if self.units_total else 0

    @property
    def words_required(self) -> int:
        return math.ceil(self.words_total * WORDS_KNOWN_SHARE) if self.words_total else 0

    @property
    def units_met(self) -> bool:
        # A band without units (no catalogue seeded) cannot be claimed covered.
        return self.units_total > 0 and self.units_held >= self.units_required

    @property
    def words_met(self) -> bool:
        # The core lexicon stops at B1: a B2 band has no word list, so its
        # coverage is the grammar units (and the épreuve) alone.
        return self.words_total == 0 or self.words_known >= self.words_required

    @property
    def coverage_met(self) -> bool:
        return self.units_met and self.words_met

    @property
    def percent(self) -> int:
        """0–100 for «A1.1 · 60 %». 90 at full coverage; 100 once the épreuve is passed."""

        parts: list[tuple[float, float]] = []
        if self.units_total:
            parts.append((PERCENT_WEIGHT_UNITS, min(1.0, self.units_held / max(1, self.units_required))))
        if self.words_total:
            parts.append((PERCENT_WEIGHT_WORDS, min(1.0, self.words_known / max(1, self.words_required))))
        if not parts:
            return 100 if self.checkpoint_passed else 0
        weight = sum(w for w, _ in parts)
        share = sum(w * v for w, v in parts) / weight * (1.0 - PERCENT_WEIGHT_CHECKPOINT)
        if self.checkpoint_passed:
            share += PERCENT_WEIGHT_CHECKPOINT
        return max(0, min(100, int(math.floor(share * 100 + 1e-9))))

    def as_dict(self) -> dict[str, Any]:
        return {
            "band": self.band,
            "percent": self.percent,
            "label": f"{self.band} · {self.percent} %",
            "units": {
                "held": self.units_held,
                "total": self.units_total,
                "required": self.units_required,
                "met": self.units_met,
            },
            "words": {
                "known": self.words_known,
                "total": self.words_total,
                "required": self.words_required,
                "met": self.words_met,
            },
            "coverage_met": self.coverage_met,
            "rule": {
                "units_held_share": UNITS_HELD_SHARE,
                "words_known_share": WORDS_KNOWN_SHARE,
                "word_retrievability": WORD_KNOWN_RETRIEVABILITY,
                "held_rule": "wp-l4-tenue",
            },
        }


def band_coverage(
    db: Session,
    user: Any,
    band: str,
    *,
    now: datetime | None = None,
    held: set[int] | None = None,
    known: set[str] | None = None,
    checkpoint_passed: bool = False,
) -> BandCoverage:
    now = now or datetime.now(UTC)
    unit_ids = band_unit_ids(db, band)
    held = held if held is not None else held_unit_ids(db, user, now=now)
    words = band_words(band)
    known = known if known is not None else known_lemmas(db, user, now=now)
    return BandCoverage(
        band=band,
        units_held=len(held & set(unit_ids)),
        units_total=len(unit_ids),
        words_known=len(known & words),
        words_total=len(words),
        checkpoint_passed=checkpoint_passed,
        unit_ids=tuple(unit_ids),
    )


__all__ = [
    "CLOSED_CLASS_WORDS",
    "SUB_BANDS",
    "UNITS_HELD_SHARE",
    "WORDS_KNOWN_SHARE",
    "WORD_KNOWN_RETRIEVABILITY",
    "BandCoverage",
    "band_coverage",
    "band_index",
    "band_unit_ids",
    "band_words",
    "held_unit_ids",
    "is_word_known",
    "known_lemmas",
    "lemmas_of_card",
    "next_band",
]
