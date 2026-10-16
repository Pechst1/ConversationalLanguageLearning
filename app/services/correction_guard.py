"""A correction keeps the learner's meaning and lists every change it makes (#133).

The «corrected form» is what the learner copies. Live walk 2026-10-14: «Qu est-ce que c
est, jeudi a dix-huit heures ?» came back as «C'est jeudi à dix-huit heures ?» — a
different question — with only two of the changes listed. The mechanism was that the
corrected text came from the model as free text and the notes were written beside
it; nothing tied the two together. This module ties them:

* :func:`unlisted_changes` — every difference between the learner's text and the
  corrected form that no listed erratum accounts for;
* :func:`drops_question` — a question word the learner wrote that the correction
  removed (the question became another question).

Pure functions; ``missions.MissionCorrectionService._complete_corrected_answer`` falls
back to the learner's own text repaired only by the listed errata when either fires.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

_TOKEN = re.compile(r"[\w']+", re.UNICODE)

#: Interrogatives whose loss turns one question into another.
_QUESTION_WORDS = (
    "qu'est-ce",
    "qu est",
    "pourquoi",
    "comment",
    "combien",
    "quand",
    "quel",
    "quelle",
    "quels",
    "où",
    "qui",
    "quoi",
)


def _norm(text: str) -> str:
    return unicodedata.normalize(
        "NFC", str(text or "").replace("’", "'").replace("‘", "'")
    ).casefold()


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(_norm(text))


def _letters(parts: Iterable[str]) -> str:
    return "".join(ch for part in parts for ch in part if ch.isalpha())


def _covered(old: list[str], new: list[str], errata: Iterable[dict[str, Any]]) -> bool:
    old_letters, new_letters = _letters(old), _letters(new)
    for erratum in errata:
        wrong = _letters(_tokens(str(erratum.get("learner_text") or "")))
        right = _letters(_tokens(str(erratum.get("corrected_target") or "")))
        if not wrong and not right:
            continue
        if old_letters in wrong and new_letters in right:
            return True
    return False


def unlisted_changes(
    learner: str, corrected: str, errata: Iterable[dict[str, Any]]
) -> list[tuple[str, str]]:
    """``[(learner words, corrected words)]`` for every change that no erratum lists.

    Compared token by token (apostrophes kept, accents significant: «a» → «à» is a
    change); a change is listed when an erratum's wrong fragment contains the learner's
    words and its corrected fragment contains the new ones."""

    errata = [e for e in errata if isinstance(e, dict)]
    old, new = _tokens(learner), _tokens(corrected)
    out: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        if not _covered(old[i1:i2], new[j1:j2], errata):
            out.append((" ".join(old[i1:i2]), " ".join(new[j1:j2])))
    return out


def drops_question(learner: str, corrected: str) -> bool:
    """The learner asked with an interrogative the correction no longer has."""

    said, fixed = _norm(learner), _norm(corrected)

    def has(word: str, text: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text))

    for word in _QUESTION_WORDS:
        if has(word, said) and not has(word, fixed):
            # «qu est-ce» and «qu'est-ce» are the same words
            if has(word.replace("qu est", "qu'est"), fixed) or has(
                word.replace("qu'est", "qu est"), fixed
            ):
                continue
            return True
    return False
