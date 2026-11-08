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
* #591: a character who puts a proposal to the learner and asks for agreement
  («L'appartement paie d'abord mon grand-père. Vous êtes d'accord, non ?») has
  taken a position. ``stands`` keeps it with the learner's stance on it (agrees,
  disagrees); the reply may not join a refusal of it (:func:`position_flip`).
"""

from __future__ import annotations

import re
import unicodedata
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
#: A question that asks the learner to agree («Vous êtes d'accord, non ?», «n'est-ce
#: pas ?», «ça vous va ?»): the sentence before it is the character's proposal.
_AGREEMENT_ASK = re.compile(
    r"d['’ ]?accord|n['’]est[- ]ce pas|pas vrai|[cç]a (?:te|vous) va", re.IGNORECASE
)
#: How a learner's turn opens when it refuses or accepts a proposal (folded: no
#: accents, no apostrophes; «daccord» as often as «d'accord»).
_DISAGREES = re.compile(r"^(?:non|nan|nope)\b|\bpas d ?accord\b|\bje refuse\b|\bje ne veux pas\b")
_AGREES = re.compile(r"^(?:oui|ouais|si|bien sur|volontiers|avec plaisir)\b|^d ?accord\b|\bje suis d ?accord\b")


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


def _fold(text: Any) -> str:
    bare = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", bare.casefold()).split())


def character_proposal(text: Any) -> str | None:
    """The proposal a character's line puts to the learner for agreement, or ``None``:
    the sentences before a question that asks «d'accord ?» («L'appartement paie
    d'abord mon grand-père.»); the question itself when nothing precedes it."""

    parts = sentences(text)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].rstrip("»\" ").endswith("?") and _AGREEMENT_ASK.search(parts[index]):
            before = " ".join(parts[:index]).strip()
            return (before or parts[index])[:QUESTION_CHARS]
    return None


def learner_stance(text: Any) -> str | None:
    """``"disagrees"`` / ``"agrees"`` when the learner's turn refuses or accepts what
    was put to them, else ``None``. A turn that opens with «non» or says «pas d'accord»
    refuses, whatever else it adds."""

    folded = _fold(text)
    if _DISAGREES.search(folded):
        return "disagrees"
    if _AGREES.search(folded):
        return "agrees"
    return None


#: What a reply says when it joins a refusal («non plus», «ni moi», «moi aussi, je ne
#: …») or declares itself agreed with a learner who refused (folded text).
_JOINS_REFUSAL = re.compile(
    r"\bnon plus\b|\bni moi\b|\bmoi aussi\b[^.!?]*\b(?:pas|non|jamais)\b|"
    r"\b(?:nous sommes|on est) d ?accord\b|\bje suis d ?accord avec (?:vous|toi)\b"
)


def position_flip(reply_fr: Any, ledger: dict[str, Any]) -> dict[str, Any] | None:
    """#591: the stand this reply gives up, or ``None``. Fires only on the stand the
    learner has just refused (the one the turn being answered, at index ``exchanges``,
    answers): a reply that says «non plus» or «moi aussi, je ne suis pas d'accord» to a
    refusal of the character's own proposal takes the learner's side against itself."""

    current = int(ledger.get("exchanges") or 0)
    for stand in ledger.get("stands") or []:
        if stand.get("learner_stance") == "disagrees" and stand.get("at") == current:
            if _JOINS_REFUSAL.search(_fold(reply_fr)):
                return stand
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
    ``{"exchanges", "asked", "open_for_learner", "learner_asked", "stands"}``:

    * ``asked``: every question, in order: ``{"by", "text_fr", "at", "answered_at"}``
      where ``at`` is the exchange it was asked in (the opening line is 0) and
      ``answered_at`` the exchange whose turn answered it, or ``None``;
    * ``open_for_learner``: the character's question still waiting for the learner;
    * ``learner_asked``: the learner's question the character has not answered yet;
    * ``stands`` (#591): each proposal the character put to the learner for agreement,
      ``{"by", "text_fr", "at", "learner_stance"}``: ``at`` is the turn that answers it
      (the opening line is 0), ``learner_stance`` is ``"agrees"``, ``"disagrees"`` or
      ``None`` while unanswered or unclear.
    """

    exchanges = [row for row in history or [] if isinstance(row, dict)]
    asked: list[dict[str, Any]] = []
    stands: list[dict[str, Any]] = []
    pending_stand: dict[str, Any] | None = None
    pending_character: dict[str, Any] | None = None
    pending_learner: dict[str, Any] | None = None

    def ask(by: str, text: str, at: int) -> dict[str, Any]:
        row = {"by": by, "text_fr": text, "at": at, "answered_at": None}
        asked.append(row)
        return row

    def stand(text: str, at: int) -> dict[str, Any]:
        row = {"by": "character", "text_fr": text, "at": at, "learner_stance": None}
        stands.append(row)
        return row

    if question := character_question(opening_line_fr):
        pending_character = ask("character", question, 0)
    if proposal := character_proposal(opening_line_fr):
        pending_stand = stand(proposal, 0)
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
            if pending_stand is not None:
                pending_stand["learner_stance"] = learner_stance(learner)
                pending_stand = None
        if character.strip():
            if pending_learner is not None:
                pending_learner["answered_at"] = index
                pending_learner = None
            if question := character_question(character):
                pending_character = ask("character", question, index + 1)
            if proposal := character_proposal(character):
                pending_stand = stand(proposal, index + 1)
    return {
        "exchanges": len(exchanges),
        "asked": asked,
        "open_for_learner": pending_character["text_fr"] if pending_character else None,
        "learner_asked": pending_learner["text_fr"] if pending_learner else None,
        "stands": stands,
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
