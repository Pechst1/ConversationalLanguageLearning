"""The facts a learner states in a reply: dates and numbers, and the reason given (#379, #145).

A line written before the learner spoke (a task's scripted example) can say the
opposite of what they just said: on the 30 Oct walk the learner answered «le deux
decembre, parce que je suis fatigue de Berlin» and was offered «Je rentre le 19
décembre, parce que je reste pour la fête.» to say aloud as theirs.

Pure, no model call. :func:`contradicts` is deliberately narrow: it only speaks when
the learner stated a kind of fact (a number, a month, a reason) and the line states
that kind differently. A reply with no such facts vetoes nothing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_UNITS = {
    "zero": 0, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
    "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60,
}
#: «un» and «une» are the article far more often than the number: never read as one.
_MULTIPLIERS = {"cent": 100, "cents": 100, "mille": 1000}
_MONTHS = frozenset(
    "janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre".split()
)
_REASON = re.compile(r"\b(?:parce qu'|parce que|puisque|puisqu'|car)\s*(.*)$")
#: Words that carry no reason: a reason is compared by what it is about.
_LIGHT = frozenset(
    "parce puisque pour avec dans mais suis fais est sont etre avoir tres trop aussi encore alors donc "
    "cette comme moins plus bien beaucoup que qui quoi leur nous vous elle elles ils".split()
)


def fold(text: Any) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).casefold()
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.replace("’", "'").replace("-", " ").split())


def _tokens(text: Any) -> list[str]:
    return re.findall(r"\d+|[a-z']+", fold(text))


def numbers_of(text: Any) -> frozenset[int]:
    """Every number in the text, digits or words («deux», «dix-neuf», «quatre-vingts»)."""

    found: set[int] = set()
    run: list[str] = []

    def flush() -> None:
        if not run:
            return
        total, current = 0, 0
        for word in run:
            if word == "et":
                continue
            if word in _MULTIPLIERS:
                current = (current or 1) * _MULTIPLIERS[word]
                total, current = total + current, 0
            elif word == "vingt" and current == 4:
                current = 80
            elif word == "vingts":
                current = (current or 1) * 20
            else:
                current += _UNITS.get(word, 1)
        found.add(total + current)
        run.clear()

    for piece in _tokens(text):
        if piece.isdigit():
            flush()
            found.add(int(piece))
        elif (
            piece in _UNITS
            or piece in _MULTIPLIERS
            or piece == "vingts"
            or (piece == "et" and run)
            or (piece == "un" and run and run[-1] == "et")
        ):
            run.append(piece)
        else:
            flush()
    flush()
    return frozenset(found)


def months_of(text: Any) -> frozenset[str]:
    return frozenset(token for token in _tokens(text) if token in _MONTHS)


def reason_of(text: Any) -> frozenset[str]:
    """What the reason given («parce que …») is about, as word stems; empty when none."""

    match = _REASON.search(fold(text))
    if not match:
        return frozenset()
    words = re.findall(r"[a-z]+", match.group(1))
    return frozenset(word[:5] for word in words if len(word) >= 4 and word not in _LIGHT)


def contradicts(learner_text: Any, line: Any) -> bool:
    """Does ``line`` state a date, number or reason that is not the learner's own?

    A kind of fact the learner did not state never counts against the line."""

    said_numbers = numbers_of(learner_text)
    if said_numbers and numbers_of(line) != said_numbers:
        return True
    said_months = months_of(learner_text)
    if said_months and months_of(line) != said_months:
        return True
    said_reason = reason_of(learner_text)
    if said_reason and not (said_reason & reason_of(line)):
        return True
    return False
