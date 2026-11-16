"""The scene ledger (#145, #378): what was said in a scene, and where that leaves it.

The live walk of 30 Oct 2026 had one reply. Lila answered it with a question
(«Et ce restaurant te fait peur ?»), and the scene closed under it: the question
could never be answered. The scene kept no record of what was still open.

The ledger is that record, rebuilt from the scene's own lines every turn (the
opening line, the stored exchanges, the learner's new text). Pure, no model
call, nothing invented: a question is a sentence that ends in «?», or a
learner sentence that opens like one («pourquoi tu…», «est-ce que…»), since
learners often drop the mark.

* A character's question is answered by the learner's next turn, unless that
  turn only asks a question of its own.
* A learner's question is answered by the character's next reply. The voice
  lane is told the open one (``turn_plan.learner_asked``) and answers it first.
* The scene stays open while the character's last reply still asks the learner
  something (:func:`keeps_open_for`), up to ``SCENE_QUESTION_GRACE`` exchanges
  past the planned ones.

#145 asks for more than questions: the walks show characters answering for the
learner, joining a refusal of their own proposal and quoting words nobody wrote.
So the ledger also keeps what each turn did (``turns``, ``last_turn``), what a
character put to the learner for agreement and how it was received (``stands``),
what the learner established in their own words (``established``), what the scene
leaves open (``still_open``) and who may speak (``in_the_room``).

Reading a learner's turn is deliberately modest. :func:`read_turn` looks at how
the turn opens and says ``other`` whenever it is unsure, so that nothing here can
misjudge a sentence it does not understand; when a model has read the turn, its
reading (``heard["intent"]``) wins. The ledger states what is known. It refuses
nothing: the writers read it, and the few checks that compare a line against it
live with the lanes.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services import story_memory
from app.services.journey_contracts import SCENE_QUESTION_GRACE

#: A sentence ends at «.», «!», «?» or «…», never before a closing guillemet.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?![»”\"])")
#: How a French question opens when the learner left out the «?».
_INTERROGATIVE = re.compile(
    r"^(?:est[- ]ce\s+que?|est[- ]ce\s+qu['’]|pourquoi|comment|combien|quand|où|ou\s+est|"
    r"qui\s|quoi|quel(?:le)?s?\s|qu['’]est[- ]ce|que\s+(?:fais|fait|veux|veut|dis|dit|penses|pense))",
    re.IGNORECASE,
)
#: «Pourquoi pas ?» opens like a question and says yes.
_SOFT_YES_QUESTION = re.compile(r"^pourquoi\s+pas\b", re.IGNORECASE)
QUESTION_CHARS = 240

#: What a learner's turn did. ``question`` is a turn that asks without saying yes or
#: no; a «non» that also asks stays ``no`` and carries the question in ``asks``.
INTENTS = ("yes", "no", "question", "other")

#: Words a learner says before getting to the point (folded: no accents, no apostrophes).
_OPENERS = re.compile(
    r"^(?:(?:euh+|heu+|hum+|hmm+|ah|oh|eh|ben|bah|bon|alors|eh bien|bonjour|salut|coucou|"
    r"merci|desole|desolee|pardon|mais|ecoute|ecoutez)\s+)+"
)
#: A refusal, by how the turn opens. «Moi non plus» and «non seulement» refuse nothing.
_READS_NO = re.compile(
    r"^(?:non\b(?!\s+(?:plus|seulement)\b)|nan\b|nope\b|nein\b|no\b|jamais\b|"
    r"pas\s+(?:du\s+tout|question|vraiment|maintenant|d\s?accord|possible)\b|surtout\s+pas\b|"
    r"(?:absolument|certainement|evidemment)\s+pas\b|bien\s+sur\s+que\s+non\b|"
    r"hors\s+de\s+question\b|sans\s+facon\b|"
    r"je\s+(?:ne\s+)?(?:suis\s+pas\s+d\s?accord|peux\s+pas|veux\s+pas|pense\s+pas|crois\s+pas)\b|"
    r"je\s+(?:ne\s+)?prefere\s+(?:ne\s+)?pas\b|je\s+refuse\b|"
    r"je\s+(?:pense|crois|dirais)\s+que\s+non\b)"
)
#: An acceptance, by how the turn opens. «Oui et non» says neither.
_READS_YES = re.compile(
    r"^(?:oui\b(?!\s+et\s+non\b)|ouais\b|ouaip\b|ja\b|yes\b|ok\b|okay\b|d\s?accord\b|"
    r"bien\s+sur\b|bien\s+entendu\b|evidemment\b|absolument\b|exactement\b|certainement\b|"
    r"tout\s+a\s+fait\b|volontiers\b|avec\s+plaisir\b|pourquoi\s+pas\b|"
    r"je\s+suis\s+d\s?accord\b|je\s+(?:pense|crois|dirais)\s+que\s+oui\b)"
)
#: «Si» says yes only on its own: «Si, je veux», not «Si tu veux».
_READS_SI = re.compile(r"^\W*(?:mais\s+)?si\s*(?:[,.!…]|$)", re.IGNORECASE)
#: The word thrown back as a question («Oui ?», «Non ?», «Ah bon ?»): no answer yet.
_ASKED_BACK = re.compile(r"^\W*(?:ah\s+)?(?:oui|non|ouais|si|bon)\s*\?", re.IGNORECASE)
#: Words that make a question ask for something, not for a yes or a no (folded text).
_ASKS_FOR_A_THING = re.compile(
    r"\b(?:qui|quoi|quel|quelle|quels|quelles|lequel|laquelle|ou|comment|combien|pourquoi|quand)\b"
    r"|\bqu\s?est\s+ce\b"
)
#: A question that goes on with the learner («Et toi ?», «Alors ?»): it wants more than a yes.
_ASKS_TO_GO_ON = re.compile(r"^(?:et|alors|donc)\b")
#: A question that asks the learner to agree («Vous êtes d'accord, non ?», «ça vous
#: va ?»): what stands before it is the character's proposal. A tag on a fact («Il fait
#: beau, n'est-ce pas ?») proposes nothing.
_AGREEMENT_ASK = re.compile(
    r"d['’ ]?accord|[cç]a\s+(?:te|vous)\s+va|[cç]a\s+marche|on\s+fait\s+comme\s+[cç]a",
    re.IGNORECASE,
)
_STANCE = {"no": "refused", "yes": "agreed"}


def _folded(text: Any) -> str:
    """No accents, no case, no punctuation: «Non… je ne suis pas daccord» reads the same
    however a phone or a beginner typed it."""

    bare = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^\w\s]", " ", bare.casefold()).split())


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
        if _SOFT_YES_QUESTION.match(bare):
            continue
        if bare.endswith("?") or _INTERROGATIVE.match(bare):
            return part[:QUESTION_CHARS]
    return None


def _yes_or_no(text: Any) -> str | None:
    """``yes`` or ``no`` when the turn opens with one, else ``None``. «Oui ?» opens with
    a question, not an answer."""

    if _ASKED_BACK.match(str(text or "")):
        return None
    folded = _OPENERS.sub("", _folded(text))
    if _READS_NO.match(folded):
        return "no"
    if _READS_YES.match(folded) or _READS_SI.match(str(text or "")):
        return "yes"
    return None


def asks_yes_or_no(text: Any) -> bool:
    """Whether a line's question is answered by a yes or a no («Tu sais ça ?», «C'est
    vrai ?»): no question of the line asks for a thing, and the last one is no «A ou
    B ?» choice, nor a bare name called out («Odile ?»)."""

    questions = [part for part in sentences(text) if part.rstrip("»\" ").endswith("?")]
    if not questions:
        return False
    folded = [_folded(question) for question in questions]
    if " oui ou non" in f" {folded[-1]}":
        return True
    if any(_ASKS_FOR_A_THING.search(question) for question in folded):
        return False
    last = re.sub(r"\best\s+ce\s+qu(?:e)?\s+", "", folded[-1])
    if " ou " in f" {last} " or _ASKS_TO_GO_ON.match(last):
        return False
    return len(last.split()) >= 2


def for_writer(ledger: Any) -> dict[str, Any]:
    """The part of a scene's record the reply prompts explain; the rest is for the
    surfaces that close the scene."""

    ledger = ledger if isinstance(ledger, dict) else {}
    return {key: ledger.get(key) for key in ("exchanges", "asked", "last_turn", "stands", "established")}


def read_turn(text: Any, *, heard: Any = None) -> dict[str, Any]:
    """What a learner's turn did: ``{"intent", "asks", "read_by"}``.

    A model's reading of the turn (``heard["intent"]``, kept with the exchange) wins;
    otherwise the words are read by how they open, and anything unclear is ``other``.
    ``asks`` is the learner's question, whatever else the turn did."""

    asks = learner_question(text)
    reading = heard.get("intent") if isinstance(heard, dict) else None
    if reading in INTENTS:
        return {"intent": reading, "asks": asks, "read_by": "voice"}
    intent = _yes_or_no(text) or ("question" if asks else "other")
    return {"intent": intent, "asks": asks, "read_by": "words"}


def character_proposal(text: Any) -> str | None:
    """What a character's line puts to the learner for agreement, or ``None``: the
    sentences before a question that asks «d'accord ?», or that question itself when
    it carries the proposal («On partage la pizza, d'accord ?»)."""

    parts = sentences(text)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index].rstrip("»\" ").endswith("?") and _AGREEMENT_ASK.search(parts[index]):
            return (" ".join(parts[:index]).strip() or parts[index])[:QUESTION_CHARS]
    return None


def room_of(scene: Any) -> list[str]:
    """Who may speak in a scene: its character and everyone its page gives a line,
    each once, in order of appearance."""

    if not isinstance(scene, dict):
        return []
    people = [scene.get("character_id")]
    for panel in scene.get("panels") or []:
        for line in (panel.get("dialogue") or []) if isinstance(panel, dict) else []:
            if isinstance(line, dict):
                people.append(line.get("character_id"))
    return list(dict.fromkeys(str(person) for person in people if person))


def _established(exchanges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the learner established in their own words. A fact stays only with a quote
    copied from the reply it came from; a later fact on the same key replaces it."""

    facts: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(exchanges):
        heard = row.get("heard") if isinstance(row.get("heard"), dict) else {}
        for fact in story_memory.grounded_facts(heard.get("learned") or [], [row.get("learner") or ""]):
            facts[fact.key] = {
                "key": fact.key,
                "fact_fr": fact.fact_fr,
                "quote": fact.quote,
                "at": index,
                **({"value": fact.value} if fact.value else {}),
            }
    return list(facts.values())


def on_screen(step: Any) -> dict[str, list[dict[str, Any]]]:
    """What a scene's step showed the learner, and only that: each exchange's words and the
    facts the record holds from them. A step's private record also holds the rubric and the
    accepted answers. A journal that scored against those would be grading the learner's
    memory of a hidden document, so a reader outside the writers comes through here."""

    private = getattr(step, "private_task", None)
    private = private if isinstance(private, dict) else {}
    turns: list[dict[str, Any]] = []
    for row in private.get("turns") or []:
        if not isinstance(row, dict):
            continue
        correction = row.get("correction") if isinstance(row.get("correction"), dict) else {}
        turns.append(
            {
                "learner": str(row.get("learner") or ""),
                "character": str(row.get("character") or ""),
                "corrected_fr": str(correction.get("corrected_fr") or ""),
                "stock_exit": bool(row.get("stock_exit")),
            }
        )
    ledger = private.get("ledger") if isinstance(private.get("ledger"), dict) else {}
    established = [fact for fact in ledger.get("established") or [] if isinstance(fact, dict)]
    return {"turns": turns, "established": established}


def build(
    *,
    opening_line_fr: Any,
    history: list[Any] | None,
    learner_text: Any = None,
    in_the_room: list[Any] | None = None,
) -> dict[str, Any]:
    """The ledger of a scene so far.

    ``history`` is the stored exchanges (``{"learner", "character", "heard"?}``),
    ``learner_text`` the turn being answered now, if any, and ``in_the_room`` who may
    speak (:func:`room_of`). Returns:

    * ``exchanges``: how many exchanges are stored;
    * ``asked``: every question, in order: ``{"by", "text_fr", "at", "answered_at"}``
      where ``at`` is the exchange it was asked in (the opening line is 0) and
      ``answered_at`` the exchange whose turn answered it, or ``None``;
    * ``open_for_learner``: the character's question still waiting for the learner;
    * ``learner_asked``: the learner's question the character has not answered yet;
    * ``turns``: each learner turn read (:func:`read_turn`), with ``at`` and ``refuses``,
      the proposal or question a «no» turned down;
    * ``last_turn``: the latest of ``turns``, or ``None`` before the learner has spoken;
    * ``stands``: what a character put to the learner for agreement: ``{"by", "text_fr",
      "at", "stance"}``, where ``at`` is the turn that answers it and ``stance`` is
      ``refused``, ``agreed`` or ``None`` while unanswered or unclear;
    * ``established``: what the learner established (:func:`_established`);
    * ``still_open``: every question nobody has answered, and every refused proposal;
    * ``in_the_room``: who may speak; empty when the caller does not know.
    """

    from app.services import scene_record

    if not scene_record.enabled():
        return _main_build(opening_line_fr=opening_line_fr, history=history, learner_text=learner_text)
    exchanges = [row for row in history or [] if isinstance(row, dict)]
    asked: list[dict[str, Any]] = []
    stands: list[dict[str, Any]] = []
    read: list[dict[str, Any]] = []
    pending_character: dict[str, Any] | None = None
    pending_learner: dict[str, Any] | None = None
    pending_stand: dict[str, Any] | None = None

    def ask(by: str, text: str, at: int) -> dict[str, Any]:
        row = {"by": by, "text_fr": text, "at": at, "answered_at": None}
        asked.append(row)
        return row

    def propose(text: str, at: int) -> dict[str, Any]:
        row = {"by": "character", "text_fr": text, "at": at, "stance": None}
        stands.append(row)
        return row

    if question := character_question(opening_line_fr):
        pending_character = ask("character", question, 0)
    if proposal := character_proposal(opening_line_fr):
        pending_stand = propose(proposal, 0)
    turns = [(str(row.get("learner") or ""), str(row.get("character") or ""), row.get("heard")) for row in exchanges]
    if str(learner_text or "").strip():
        turns.append((str(learner_text), "", None))
    for index, (learner, character, heard) in enumerate(turns):
        if learner.strip():
            reading = read_turn(learner, heard=heard)
            refuses = None
            if reading["intent"] == "no":
                on_the_table = pending_stand or pending_character
                refuses = on_the_table["text_fr"] if on_the_table else None
            read.append({"at": index, **reading, "refuses": refuses})
            if pending_stand is not None:
                pending_stand["stance"] = _STANCE.get(reading["intent"])
                pending_stand = None
            # A turn that only asks has not answered: the character replies, and may come
            # back to what they asked (Margaux: «Ça va. Et la lettre, tu l'as vue ?»).
            if pending_character is not None and reading["intent"] != "question":
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
            if proposal := character_proposal(character):
                pending_stand = propose(proposal, index + 1)
    return {
        "exchanges": len(exchanges),
        "asked": asked,
        "open_for_learner": pending_character["text_fr"] if pending_character else None,
        "learner_asked": pending_learner["text_fr"] if pending_learner else None,
        "turns": read,
        "last_turn": read[-1] if read else None,
        "stands": stands,
        "established": _established(exchanges),
        "still_open": [
            *({"by": row["by"], "text_fr": row["text_fr"], "at": row["at"], "kind": "question"}
              for row in asked if row["answered_at"] is None),
            *({"by": row["by"], "text_fr": row["text_fr"], "at": row["at"], "kind": "refused_proposal"}
              for row in stands if row["stance"] == "refused"),
        ],
        "in_the_room": [str(person) for person in in_the_room or [] if person],
    }


def _main_learner_question(text: Any) -> str | None:
    """``STORY_SCENE_RECORD`` off: main's reading of a learner question («Pourquoi pas ?»
    still counts as one)."""

    for part in sentences(text):
        bare = part.strip("«»\"' ")
        if bare.endswith("?") or _INTERROGATIVE.match(bare):
            return part[:QUESTION_CHARS]
    return None


def _main_build(*, opening_line_fr: Any, history: list[Any] | None, learner_text: Any = None) -> dict[str, Any]:
    """``STORY_SCENE_RECORD`` off: main's ledger, questions only (#378). Any learner turn
    answers the character's question, a question back included."""

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
            if question := _main_learner_question(learner):
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


_NUMBER = re.compile(r"\d")
#: A capitalised word after the start of a sentence: a name, in French.
_MID_NAME = re.compile(r"(?<=[\w,;:…'’] )([A-ZÀ-Ý][\w'’-]+)")


def brings_in_new(text: str, known: str) -> bool:
    """Whether a line holds a number or a name that nothing in the scene holds."""

    folded = _folded(known)
    if _NUMBER.search(text) and not all(digit in known for digit in re.findall(r"\d+", text)):
        return True
    return any(_folded(name) not in folded for name in _MID_NAME.findall(text))


def keeps_open_for(reply_fr: Any, *, turn_index: int, max_turns: int) -> bool:
    """#378: the character's reply asks the learner something, and the scene may
    still take the answer (at most :data:`SCENE_QUESTION_GRACE` exchanges past the
    planned ``max_turns``)."""

    if character_question(reply_fr) is None:
        return False
    return int(turn_index) + 1 < int(max_turns or 1) + SCENE_QUESTION_GRACE


#: The caption under the input, in the learner's language: what the character asks now.
_CAPTION_ASKS = {
    "en": "{name} asks: «{question}»",
    "de": "{name} fragt: «{question}»",
    "fr": "{name} demande : «{question}»",
}
#: …and when her latest turn asks nothing: the opening task no longer fits, so say
#: only what is true (the scene goes on) rather than keep a stale task.
_CAPTION_GOES_ON = {
    "en": "Keep the conversation going with {name}.",
    "de": "Führe das Gespräch mit {name} weiter.",
    "fr": "Continue la conversation avec {name}.",
}


def turn_caption(reply_fr: Any, *, speaker: Any, language: Any = None) -> str | None:
    """#500: the caption under the scene's input for the turn the character just spoke.

    The prompt's ``objective_native`` is written once, for the *opening* question,
    and a later turn carried it over unchanged: Lila had moved on to the next
    question and the caption still named the first. A caption is a property of
    the turn, so it is derived from the character's latest reply every time: the
    question she asks now (quoted, so nothing is translated or invented), or a
    neutral line when she asks nothing. ``None`` for a reply with no text: the
    caller keeps whatever it had.
    """

    if not str(reply_fr or "").strip():
        return None
    name = str(speaker or "").strip() or "…"
    code = str(language or "").strip().lower()
    code = code if code in _CAPTION_ASKS else "en"
    question = character_question(reply_fr)
    if question is None:
        return _CAPTION_GOES_ON[code].format(name=name)
    return _CAPTION_ASKS[code].format(name=name, question=question)


def without_trailing_question(text: Any) -> str:
    """An ending that closes: the scene's last line drops a question at its end
    when something before it still stands («D'accord. Tu viens demain ?» →
    «D'accord.»). A line that is only a question comes back unchanged."""

    parts = sentences(text)
    while len(parts) > 1 and parts[-1].rstrip("»\" ").endswith("?"):
        parts.pop()
    return " ".join(parts) if parts else str(text or "")
