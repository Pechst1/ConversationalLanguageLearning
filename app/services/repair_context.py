"""The sentence a saved slip sat in (#278).

An erratum used to keep only the wrong fragment, «sommer». A repair drill built
from it later had nothing but that word to print: no sentence, no rule, nothing a
learner who has forgotten the slip could tell what is asked from. Whoever saves a
slip now also saves the sentence around it (``context_fr``), found here, and the
planner prints that sentence with the slip marked.

Pure functions over strings; nothing here reads a database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

#: A gap in a printed sentence: «Nous ____ contents.» or «Nous … contents.»
_BLANK = re.compile(r"_{2,}|…|\.{3}")


def clean_text(value: object) -> str:
    """``value`` as one line of single-spaced text."""

    return " ".join(str(value or "").split())


_clean = clean_text


def find_slip(sentence: object, slip: object) -> re.Match[str] | None:
    """Where ``slip`` stands in ``sentence`` as whole words, any case, or ``None``."""

    text, wanted = _clean(sentence), _clean(slip)
    if not text or not wanted:
        return None
    return re.search(r"(?<![\w'’-])" + re.escape(wanted) + r"(?![\w-])", text, re.IGNORECASE)


def fill_blank(prompt: object, word: object) -> str | None:
    """``prompt`` with its first gap filled by ``word``, or ``None`` when it has no gap."""

    text, filler = _clean(prompt), _clean(word)
    if not text or not filler:
        return None
    filled, count = _BLANK.subn(lambda _match: filler, text, count=1)
    return filled if count else None


def context_sentence(*, slip: object, answer: object = None, prompt: object = None) -> str | None:
    """The sentence the learner's wrong fragment ``slip`` sat in, or ``None``.

    * the learner's own answer, when it is longer than the slip and holds it;
    * else the item's printed gap filled with what the learner put there;
    * else the printed sentence itself, when it holds the slip («correct this»).

    ``None`` when the slip stands alone: nothing more is known, and nothing is made up.
    """

    wanted = _clean(slip)
    if not wanted:
        return None
    said = _clean(answer)
    if said and len(said.split()) > len(wanted.split()) and find_slip(said, wanted):
        return said
    filled = fill_blank(prompt, said or wanted)
    if filled and find_slip(filled, wanted):
        return filled
    shown = _clean(prompt)
    if shown and len(shown.split()) > len(wanted.split()) and not _BLANK.search(shown) and find_slip(shown, wanted):
        return shown
    return None


def corrected_sentence(sentence: object, slip: object, fix: object) -> str | None:
    """``sentence`` with ``slip`` replaced by ``fix``, or ``None`` when it is not in it."""

    text = _clean(sentence)
    match = find_slip(text, slip)
    replacement = _clean(fix)
    if match is None or not replacement:
        return None
    return text[: match.start()] + replacement + text[match.end() :]


@dataclass(frozen=True, slots=True)
class RepairContext:
    """What a repair card knows beyond the wrong fragment: the sentence it sat in
    and the title of the rule it broke. Either may be missing."""

    sentence: str | None = None
    rule: str | None = None


def repair_context_of(metadata: dict[str, Any] | None) -> RepairContext | None:
    """The context a candidate's metadata carries (``erratum_context`` / ``erratum_rule``)."""

    data = metadata or {}
    sentence = _clean(data.get("erratum_context")) or None
    rule = _clean(data.get("erratum_rule")) or None
    return RepairContext(sentence=sentence, rule=rule) if sentence or rule else None
