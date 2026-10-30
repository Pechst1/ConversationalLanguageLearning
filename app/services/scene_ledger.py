"""The scene ledger (#145, #378): what was asked in a scene, and what was answered.

The live walk of 30 Oct 2026 had one reply. Lila answered it with a question
(«Et ce restaurant te fait peur ?»), and the scene closed under it: the question
could never be answered. The scene kept no record of what was still open.

The ledger is that record, rebuilt from the scene's own lines every turn (the
opening line, the stored exchanges, the learner's new text). Pure, no model
call, nothing invented: a question is a sentence that ends in «?», or a
learner sentence that opens like one («pourquoi tu…», «est-ce que…»), since
learners often drop the mark.

* A character's question is answered by the learner's next turn.
* A learner's question is answered by the character's next reply. The voice
  lane is told the open one (``turn_plan.learner_asked``) and answers it first.
* The scene stays open while the character's last reply still asks the learner
  something (:func:`keeps_open_for`), up to ``SCENE_QUESTION_GRACE`` exchanges
  past the planned ones.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.journey_contracts import SCENE_QUESTION_GRACE

#: A sentence ends at «.», «!», «?» or «…», never before a closing guillemet.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?![»”\"])")
#: How a French question opens when the learner left out the «?».
_INTERROGATIVE = re.compile(
    r"^(?:est[- ]ce\s+que?|est[- ]ce\s+qu['’]|pourquoi|comment|combien|quand|où|ou\s+est|"
    r"qui\s|quoi|quel(?:le)?s?\s|qu['’]est[- ]ce|que\s+(?:fais|fait|veux|veut|dis|dit|penses|pense))",
    re.IGNORECASE,
)
QUESTION_CHARS = 240


def sentences(text: Any) -> list[str]:
    return [part.strip() for part in _SENTENCE_END.split(" ".join(str(text or "").split())) if part.strip()]


def character_question(text: Any) -> str | None:
    """The last question in a character's line, or ``None``. A line that asks and
    then goes on («Tu as peur ? Moi aussi, un peu.») still asks."""

    question = next((part for part in reversed(sentences(text)) if part.rstrip("»\" ").endswith("?")), None)
    return question[:QUESTION_CHARS] if question else None


def learner_question(text: Any) -> str | None:
    """The question in the learner's turn, or ``None``: a sentence ending in «?»,
    or one that opens like a French question."""

    for part in sentences(text):
        bare = part.strip("«»\"' ")
        if bare.endswith("?") or _INTERROGATIVE.match(bare):
            return part[:QUESTION_CHARS]
    return None


def build(
    *,
    opening_line_fr: Any,
    history: list[Any] | None,
    learner_text: Any = None,
) -> dict[str, Any]:
    """The ledger of a scene so far.

    ``history`` is the stored exchanges (``{"learner", "character"}``) and
    ``learner_text`` the turn being answered now, if any. Returns
    ``{"exchanges", "asked", "open_for_learner", "learner_asked"}``:

    * ``asked``: every question, in order: ``{"by", "text_fr", "at", "answered_at"}``
      where ``at`` is the exchange it was asked in (the opening line is 0) and
      ``answered_at`` the exchange whose turn answered it, or ``None``;
    * ``open_for_learner``: the character's question still waiting for the learner;
    * ``learner_asked``: the learner's question the character has not answered yet.
    """

    exchanges = [row for row in history or [] if isinstance(row, dict)]
    asked: list[dict[str, Any]] = []
    pending_character: dict[str, Any] | None = None
    pending_learner: dict[str, Any] | None = None

    def ask(by: str, text: str, at: int) -> dict[str, Any]:
        row = {"by": by, "text_fr": text, "at": at, "answered_at": None}
        asked.append(row)
        return row

    if question := character_question(opening_line_fr):
        pending_character = ask("character", question, 0)
    turns = [(str(row.get("learner") or ""), str(row.get("character") or "")) for row in exchanges]
    if str(learner_text or "").strip():
        turns.append((str(learner_text), ""))
    for index, (learner, character) in enumerate(turns):
        if learner.strip():
            if pending_character is not None:
                pending_character["answered_at"] = index
                pending_character = None
            if question := learner_question(learner):
                pending_learner = ask("learner", question, index)
        if character.strip():
            if pending_learner is not None:
                pending_learner["answered_at"] = index
                pending_learner = None
            if question := character_question(character):
                pending_character = ask("character", question, index + 1)
    return {
        "exchanges": len(exchanges),
        "asked": asked,
        "open_for_learner": pending_character["text_fr"] if pending_character else None,
        "learner_asked": pending_learner["text_fr"] if pending_learner else None,
    }


def keeps_open_for(reply_fr: Any, *, turn_index: int, max_turns: int) -> bool:
    """#378: the character's reply asks the learner something, and the scene may
    still take the answer (at most :data:`SCENE_QUESTION_GRACE` exchanges past the
    planned ``max_turns``)."""

    if character_question(reply_fr) is None:
        return False
    return int(turn_index) + 1 < int(max_turns or 1) + SCENE_QUESTION_GRACE


def without_trailing_question(text: Any) -> str:
    """An ending that closes: the scene's last line drops a question at its end
    when something before it still stands («D'accord. Tu viens demain ?» →
    «D'accord.»). A line that is only a question comes back unchanged."""

    parts = sentences(text)
    while len(parts) > 1 and parts[-1].rstrip("»\" ").endswith("?"):
        parts.pop()
    return " ".join(parts) if parts else str(text or "")
