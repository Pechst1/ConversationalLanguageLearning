"""What counts as «something that happened» in a story recap line.

ROOT CAUSE #145/#539/#597. ``story_outcome.callback_fr`` is the story's *hook*: the
line that opens tomorrow. Most of the time it states something that happened, but
two authored lines travel in the same field and say nothing about the scene: the
exit stub written when the actor could not answer («Margaux a dû partir avant de
répondre.») and a season page's closing caption («Deux clés pour la même porte. À
suivre…»). Nothing marked which kind a callback was, so each reader that printed it
as «what happened» had to know, and the Journal (#539) knew while the next day's
«Bisher» line (#597) did not.

The rule lives here, once. A reader that presents the hook, the event summary or the
chronicle line as a fact of the scene takes it through :func:`scene_fact`; a reader
that only carries the field from one record to another (the hook of the episode, the
ledger of the serial) leaves it alone. ``tests/test_bisher_closing_filler.py`` lists
the readers and fails when one is added without the rule.
"""

from __future__ import annotations

import re
from typing import Any

_TO_BE_CONTINUED = re.compile(r"\bà\s+suivre\b", re.IGNORECASE)
_EXIT_STUB = re.compile(
    r"^(?:\S+\s+){1,5}?(?:a répondu,?\s+puis\s+)?(?:a|doit)\s+(?:dû\s+)?partir"
    r"(?:\s+avant\s+de\s+répondre)?\s*[.…]*$",
    re.IGNORECASE,
)


def is_closing_filler(text: Any) -> bool:
    """Whether a recap line is a closing caption or an exit stub, not an event."""
    line = " ".join(str(text or "").split())
    if not line:
        return False
    return bool(_TO_BE_CONTINUED.search(line) or _EXIT_STUB.match(line))


def scene_fact(*candidates: Any, fallback: Any = "") -> str:
    """The first candidate that states something that happened, else ``fallback``.

    Candidates are tried in order («the callback, else the resolution»); a closing
    caption or an exit stub is skipped, never returned. ``fallback`` is what the
    scene itself established (its title), and is returned as it is: it is the
    caller's own line, not a hook.
    """

    for candidate in candidates:
        line = " ".join(str(candidate or "").split())
        if line and not is_closing_filler(line):
            return line
    return " ".join(str(fallback or "").split())


__all__ = ["is_closing_filler", "scene_fact"]
