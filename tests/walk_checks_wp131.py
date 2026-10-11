"""WP-131 walk checks over a life record (``tests/experience_walk.py``).

* :func:`check_new_word_swing` — an *average* learner's daily new words do not
  swing on noise. Before WP-131 the intake throttle halved intake at a cliff (80 %
  review accuracy, release at 85 %), so a learner reviewing at about 78–82 % got
  8 new words one day and 3 the next (or 237 vs 143 over two runs of the same
  life). The threshold: a drill session introduces at most 8; the journey's
  reservation moves the drill's share by up to the Régulier journey share (4);
  the graded throttle moves it by about one word per 5 accuracy points. A change
  of :data:`SWING_LIMIT` (5) or more between two consecutive played days is the
  halving signature (8 → 3), not that ordinary variation.
* :func:`check_numeral_runs` — no day introduces four or more numerals in a row
  (the A1 list used to hand out «deux … neuf», «dix … vingt» on consecutive days).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

#: A day-to-day change in new words this large is a throttle flip, not noise.
SWING_LIMIT = 5
#: Days 1–2 are onboarding and placement: a placed learner's first drill differs.
SETTLED_FROM_DAY = 3
#: Four numerals in a row is a block, not a mix.
NUMERAL_RUN_LIMIT = 4


def day_new_words(day: dict[str, Any]) -> list[str] | None:
    """The drill's new words of a day, in the order shown; ``None`` with no drill."""

    drill = day.get("drill")
    if not isinstance(drill, dict) or "cards" not in drill:
        return None
    return [str(card.get("word") or "") for card in drill.get("cards") or [] if card.get("new")]


def check_new_word_swing(record: dict[str, Any]) -> list[str]:
    if record.get("quality") != "average":
        return []
    problems: list[str] = []
    previous: tuple[int, int] | None = None
    for day in record.get("days") or []:
        number = int(day.get("day") or 0)
        words = day_new_words(day)
        if words is None or number < SETTLED_FROM_DAY:
            previous = None if words is None else previous
            continue
        count = len(words)
        if previous is not None and previous[0] == number - 1 and abs(count - previous[1]) >= SWING_LIMIT:
            problems.append(
                f"{record.get('persona')} {record.get('quality')} day {number}: new words swung "
                f"{previous[1]} → {count} (≥ {SWING_LIMIT}; the throttle flips on noise)"
            )
        previous = (number, count)
    return problems


@lru_cache(maxsize=1)
def _numerals() -> frozenset[str]:
    from app.services.lexical_coverage import fold, load_lexicon

    return frozenset(
        fold(lemma)
        for lemma, entry in load_lexicon().lemmas.items()
        if entry.get("numeral") or entry.get("pos") == "number"
    )


def is_numeral(word: str) -> bool:
    from app.services.lexical_coverage import fold

    return fold(word) in _numerals()


def check_numeral_runs(record: dict[str, Any]) -> list[str]:
    from app.services.word_order import longest_numeral_run

    problems: list[str] = []
    for day in record.get("days") or []:
        words = day_new_words(day) or []
        run = longest_numeral_run([is_numeral(word) for word in words])
        if run >= NUMERAL_RUN_LIMIT:
            problems.append(
                f"{record.get('persona')} {record.get('quality')} day {day.get('day')}: {run} numerals in a row "
                f"among the day's new words ({', '.join(words)})"
            )
    return problems


def check_life_wp131(record: dict[str, Any]) -> list[str]:
    return check_new_word_swing(record) + check_numeral_runs(record)


__all__ = [
    "NUMERAL_RUN_LIMIT",
    "SWING_LIMIT",
    "check_life_wp131",
    "check_new_word_swing",
    "check_numeral_runs",
    "day_new_words",
    "is_numeral",
]
