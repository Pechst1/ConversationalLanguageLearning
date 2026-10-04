"""WP-131 — the order the word drill introduces new words in.

The core list is in learning order (sub-band, then rank), and the drill took it
straight: an A1 learner met «deux … neuf», «dix … vingt», «trente … mille» on
three consecutive days, and a C1 learner a block of newspaper-corpus words
(«islamiste», «bombardement», «colonel») next to a story about a flat in Paris
(EXPERIENCE-REVIEW 2026-10-04 §2.7).

:func:`order_new_words` keeps the list's order as the backbone and adds, for one
batch (one drill session's new words):

1. **met first** — a word a story scene taught the learner (unchanged);
2. **scene relevance** — a word the season's lines use at the learner's level
   (``season_lexicon.season_words``): it will be read in context;
3. **diversity** — at most one numeral in four words, never two numerals in a
   row and never one opening the batch; corpus words that the story does not use
   at most half the batch and never more than two in a row, while curated or
   story words are available to put between them.

Selection and order only: no word leaves the list and none is added to it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NewWord:
    """One candidate, in the list's base order."""

    word_id: int
    lemma: str
    numeral: bool = False
    #: A story scene taught it to this learner (``scene_lexicon`` interaction).
    met: bool = False
    #: The season's lines use it at the learner's level.
    season: bool = False
    #: Taken from a frequency corpus (``core_lexicon.CORPUS_TAG``).
    corpus: bool = False


def max_numerals(limit: int) -> int:
    """At most one numeral in four words (at least one per batch)."""

    return max(1, limit // 4)


def max_corpus(limit: int) -> int:
    """Corpus words the story does not use: at most half a batch (rounded up)."""

    return max(1, math.ceil(limit / 2))


#: Never more than this many story-less corpus words in a row.
CORPUS_RUN = 2


def order_new_words(candidates: Sequence[NewWord], limit: int) -> list[NewWord]:
    """Up to ``limit`` words for one batch, in the order they are introduced.

    Deterministic: the same candidates give the same batch (two tabs open on the
    drill introduce the same words).
    """

    if limit <= 0:
        return []
    unique: list[NewWord] = []
    seen: set[int] = set()
    for word in candidates:
        if word.word_id not in seen:
            seen.add(word.word_id)
            unique.append(word)
    # Met words, then the story's words, then the list — each in base order.
    pool = (
        [w for w in unique if w.met]
        + [w for w in unique if not w.met and w.season]
        + [w for w in unique if not w.met and not w.season]
    )
    numerals_cap = max_numerals(limit)
    corpus_cap = max_corpus(limit)
    batch: list[NewWord] = []

    def bare_corpus(word: NewWord) -> bool:
        return word.corpus and not word.season and not word.met

    def fits(word: NewWord, *, strict_corpus: bool) -> bool:
        if word.numeral:
            if not batch or batch[-1].numeral:
                return False
            if sum(1 for w in batch if w.numeral) >= numerals_cap:
                return False
        if strict_corpus and bare_corpus(word):
            if sum(1 for w in batch if bare_corpus(w)) >= corpus_cap:
                return False
            if len(batch) >= CORPUS_RUN and all(bare_corpus(w) for w in batch[-CORPUS_RUN:]):
                return False
        return True

    while len(batch) < limit and pool:
        choice = next((w for w in pool if fits(w, strict_corpus=True)), None)
        if choice is None:
            # Only corpus words are left to fill the batch: they come, still never
            # breaking the numeral rule. Only numerals left: the batch ends short.
            choice = next((w for w in pool if fits(w, strict_corpus=False)), None)
        if choice is None:
            break
        batch.append(choice)
        pool.remove(choice)
    return batch


def longest_numeral_run(numerals: Sequence[bool]) -> int:
    """The longest run of consecutive ``True`` (numerals) in a day's new words."""

    best = run = 0
    for flag in numerals:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


__all__ = [
    "CORPUS_RUN",
    "NewWord",
    "longest_numeral_run",
    "max_corpus",
    "max_numerals",
    "order_new_words",
]
