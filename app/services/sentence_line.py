"""Text the learner reads is cut on a sentence, never on a character count; notes are not text.

Two small, pure rules the story engine and the archive share (night shift 2026-10-21):

* **Whole sentences.** ``_one_line(text, 120)`` cut «… Alors, tu gardes l'appartement…» to
  «… Alors,…» and filed it under a chapter for months (#268). :func:`whole_sentences`
  keeps the sentences that fit and never a fragment; :func:`question_line` keeps the
  sentence that actually asks the question; :func:`drop_cut_tail` repairs a line an
  older version already cut.
* **No planning notes.** The director's scratch note reached a reader caption
  (#263). :func:`is_planning_note` names the shapes a note takes («(!)», «40 × 1 000 €»,
  «M. M. :», «NB :») that a line of narration never has. The reader keeps a mirror of
  it for scenes stored before the guard (``web-frontend/components/feuilleton/reader/planning-note.ts``).
"""

from __future__ import annotations

import re

#: A sentence ends on . ! ? … (a closing quote or bracket may follow) and the next one opens
#: on a capital, an opening quote or a digit.
_BOUNDARY = re.compile(
    r"(?:(?<=[.!?…])|(?<=[.!?…][\"»”)]))(?<!\bM\.)(?<!\bMM\.)(?<!\bDr\.)(?<!\bSt\.)(?<!\bMlle\.)"
    r"\s+(?=[A-ZÀ-ÖØ-Þ«\"“(\d])"
)
#: A line that ends on a closed sentence.
_CLOSED = re.compile(r"[.!?»\"”)]$")
#: «À suivre…» ends on an ellipsis on purpose: it is a whole phrase.
_DELIBERATE_ELLIPSIS = re.compile(r"(?:^|[.!?]\s+)À suivre\s*…$", re.IGNORECASE)


def _flat(text: object) -> str:
    return " ".join(str(text or "").split())


def sentences(text: object) -> list[str]:
    flat = _flat(text)
    return [part.strip() for part in _BOUNDARY.split(flat) if part.strip()] if flat else []


def _word_cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def whole_sentences(text: object, limit: int, *, hard_cap: int | None = None) -> str:
    """The longest run of whole opening sentences within ``limit`` characters.

    A first sentence longer than ``limit`` is kept whole up to ``hard_cap`` (default twice
    the limit) rather than cut; only past that is it cut at a word with an ellipsis."""

    flat = _flat(text)
    if len(flat) <= limit:
        return flat
    kept = ""
    for sentence in sentences(flat):
        candidate = f"{kept} {sentence}".strip()
        if len(candidate) > limit:
            break
        kept = candidate
    if kept:
        return kept
    first = (sentences(flat) or [flat])[0]
    return _word_cut(first, hard_cap or limit * 2)


def question_line(text: object, limit: int) -> str:
    """The sentence that asks the question (the last one ending in «?»), whole; else the
    opening sentences that fit. A chapter's question is its last sentence, not its first."""

    flat = _flat(text)
    if len(flat) <= limit:
        return flat
    asking = [sentence for sentence in sentences(flat) if sentence.endswith("?")]
    if asking:
        return whole_sentences(asking[-1], limit)
    return whole_sentences(flat, limit)


def drop_cut_tail(text: object) -> str:
    """A stored line that an older cut left ending mid-sentence («… Alors,…»), without the
    fragment. A whole line, and a deliberate «À suivre…», are returned as they were."""

    flat = _flat(text)
    if not flat.endswith("…") or _DELIBERATE_ELLIPSIS.search(flat):
        return flat
    parts = sentences(flat)
    if not parts:
        return flat
    stem = parts[-1][:-1].rstrip()
    # The last piece ends in «…» after no closed sentence: an older cut left it.
    return " ".join(parts[:-1]) if not _CLOSED.search(stem) else flat


_AMOUNT = re.compile(r"\d[\d\s  .,]*\s*[×✕]\s*\d")
_INITIALS_TAG = re.compile(r"(?:\b[A-ZÀ-ÖØ-Þ]\.\s?){2,}:")
_LABEL = re.compile(r"^\s*(?:note|nb|n\.b\.|todo|plan|idée|idee|rappel)\s*[:\-–—]", re.IGNORECASE)
_FLAG = re.compile(r"\((?:!|\?|!!|\?\?)\)")


def is_planning_note(text: object) -> bool:
    """True for a line that is the author's note about the scene, not a line of it."""

    flat = _flat(text)
    if not flat:
        return False
    return bool(_FLAG.search(flat) or _AMOUNT.search(flat) or _INITIALS_TAG.search(flat) or _LABEL.search(flat))
