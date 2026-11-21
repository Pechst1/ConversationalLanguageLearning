"""What a character says when no model could write the reply (WP-58, #518, #145).

Live walk 4 Nov. The learner wrote «Mon voisin a un dinosaure dans le jardin. Il mange la
lettre !» and got «Attends, on m'appelle — je reviens vers toi très vite, promis.», then
«Margaux doit partir avant de répondre … your words are noted». Every reply that failed
read the same, whoever spoke and whatever was said, and it ended the scene.

The words here react to what kind of thing the learner said (the ledger's own reading of
the reply), in the person's register. They never cut the learner's sentence to build a line:
that put bad French in a character's mouth (#545). A reply is quoted whole, on the closing
line only, when it needed no correction. Nothing is promised and no fact is invented, and
nothing in here says a gender, because neither the learner's nor Camille's is fixed.

No line asks anything: the ledger would hold it as the character's open question, and the
next page would be captioned with it.

This is the fallback, so the writing can be plain, but it is not one line: a person keeps
their own opener, and the sentence varies with what was written.
"""

from __future__ import annotations

import zlib
from typing import Any

from app.services.learner_facts import looks_misspelled, reads_as_sentence
from app.services.scene_ledger import read_turn

#: A person says their own one, every time.
_OPENERS = ("Hm.", "Bon.", "Ah.", "Tiens.", "Oh.")

_REACTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "no": {
        "tu": ("D'accord, je note ton non.", "Si c'est non, c'est non.", "D'accord. Pas ça, alors."),
        "vous": ("D'accord, je note votre non.", "Si c'est non, c'est non.", "D'accord. Pas ça, alors."),
    },
    "yes": {
        "tu": ("D'accord, c'est noté.", "Très bien, c'est dit.", "Alors c'est dit."),
        "vous": ("D'accord, c'est noté.", "Très bien, c'est dit.", "Alors c'est dit."),
    },
    "question": {
        "tu": (
            "Bonne question. Je n'ai pas encore la réponse.",
            "Ça, je ne sais pas encore. Laisse-moi y penser.",
            "Ça, je ne peux pas te le dire tout de suite.",
        ),
        "vous": (
            "Bonne question. Je n'ai pas encore la réponse.",
            "Ça, je ne sais pas encore. Laissez-moi y penser.",
            "Ça, je ne peux pas vous le dire tout de suite.",
        ),
    },
    "other": {
        "tu": ("Attends, je réfléchis à ce que tu dis.", "Je ne m'attendais pas à ça.", "Je t'écoute. Continue."),
        "vous": (
            "Attendez, je réfléchis à ce que vous dites.",
            "Je ne m'attendais pas à ça.",
            "Je vous écoute. Continuez.",
        ),
    },
}

_ENDINGS: dict[str, dict[str, str]] = {
    "no": {"tu": "Ton non, je l'ai entendu. On en reparle.", "vous": "Votre non, je l'ai entendu. On en reparle."},
    "yes": {"tu": "Ton oui, je le garde. On en reparle.", "vous": "Votre oui, je le garde. On en reparle."},
    "question": {
        "tu": "Ta question, je ne l'oublie pas. On en reparle.",
        "vous": "Votre question, je ne l'oublie pas. On en reparle.",
    },
    "other": {
        "tu": "Ce que tu m'as dit, je le garde. On en reparle.",
        "vous": "Ce que vous m'avez dit, je le garde. On en reparle.",
    },
}

#: A quote on the closing line is the whole reply, so a long one is left out, not cut.
_QUOTE_WORDS = 14


def _intent(learner_text: Any) -> str:
    intent = str(read_turn(learner_text).get("intent") or "other")
    return intent if intent in _REACTIONS else "other"


def _register(register: Any) -> str:
    return "tu" if register == "tu" else "vous"


def reaction(*, character_id: Any, learner_text: Any, register: Any) -> str:
    """The character's reply, in their register. The same reply reads the same on a retry."""

    seed = zlib.crc32(f"{character_id}|{learner_text}".encode())
    opener = _OPENERS[zlib.crc32(str(character_id or "").encode()) % len(_OPENERS)]
    lines = _REACTIONS[_intent(learner_text)][_register(register)]
    return f"{opener} {lines[seed % len(lines)]}"


def ending(*, learner_text: Any, register: Any, clean: bool = False) -> str:
    """The scene's closing line, first person, a statement. ``clean``: the reply was read and
    needed no correction, so it may be quoted, whole."""

    closing = _ENDINGS[_intent(learner_text)][_register(register)]
    said = " ".join(str(learner_text or "").split())
    if clean and reads_as_sentence(said) and not looks_misspelled(said) and len(said.split()) <= _QUOTE_WORDS:
        return f"« {said} » {closing}"
    return closing


__all__ = ["ending", "reaction"]
