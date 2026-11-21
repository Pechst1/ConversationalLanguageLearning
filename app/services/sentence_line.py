"""Text the learner reads is cut on a sentence, never on a character count; notes are not text.

Small, pure rules the story engine, the archive and the device share (night shift 2026-10-21):

* **One sentence splitter.** :func:`sentences` is the one way a text is cut into sentences
  (#896): a quotation the sentence carries on after, a hesitation that runs on and a chain
  of alternatives stay whole. ``web-frontend/lib/sentence-split.ts`` mirrors it, and
  ``tests/fixtures/sentence_split_cases.json`` pins both.
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

#: Titles whose full stop ends no sentence («la lampe de M. Marchand», «Mme. Odile»): the one
#: list every cut of a French text shares (#398). One capital and a stop («J. Dupont») is an
#: initial, and ends no sentence either.
TITLE_ABBREVIATIONS = (
    "M", "MM", "Mme", "Mmes", "Mlle", "Mlles", "Dr", "Pr", "Me", "Mgr", "St", "Ste", "Mr", "Mrs", "Ms",
)
_INITIAL = "[A-ZÀ-ÖØ-Þ]"
_TITLE = rf"(?:{'|'.join(TITLE_ABBREVIATIONS)}|{_INITIAL})\."
#: Lookbehinds, each of fixed width, that keep a cut from falling after a title or an initial.
NOT_AFTER_TITLE = "".join(rf"(?<!\b{title}\.)" for title in TITLE_ABBREVIATIONS) + rf"(?<!\b{_INITIAL}\.)"
_TITLE_WORD = re.compile(_TITLE)
#: What is left of a sentence cut at its title («Sur le toit, la lampe de M.»), or a signature.
_STOPS_AT_TITLE = re.compile(rf"(?<![^\s(«\"“'’—–-]){_TITLE}[\s»\"”)]*$")

#: The looser cut a scene line is looked up by: after any . ! ? … that is no title's.
_LOOSE_BOUNDARY = re.compile(r"(?<=[.!?…])" + NOT_AFTER_TITLE + r"\s+")
#: A line that ends on a closed sentence.
_CLOSED = re.compile(r"[.!?»\"”)]$")
#: «À suivre…» ends on an ellipsis on purpose: it is a whole phrase.
_DELIBERATE_ELLIPSIS = re.compile(r"(?:^|[.!?]\s+)À suivre\s*…$", re.IGNORECASE)


# ---------------------------------------------------------------------------------------
# The one sentence splitter (#896). Every surface that cuts a text into sentences, on the
# server and on the device, reads it the same way: ``web-frontend/lib/sentence-split.ts``
# is its mirror, and ``tests/fixtures/sentence_split_cases.json`` pins both. It is a scan,
# not one regex, so the device runs the same steps without lookbehind (older iOS).
#
# A sentence ends on . ! ? … that is no title's or initial's (one closing mark may follow,
# or a French-spaced « »»), before a word that opens a new one: a capital, a digit, an
# opening quote or bracket, a dash. Three things a «?» or a «.» there does not end:
#   * a quotation the sentence carries on after («„Tu est française, Margaux ?“ stimmt
#     nicht; …», #893): what is inside it is one piece of the sentence that quotes it;
#   * a hesitation that runs on in small letters («déjà… le groupe qui …», #849);
#   * a chain of alternatives («Tu prends l'appartement pour toi ? Pour toi et les
#     autres ? Ou tu dis au revoir à tout ça ?», #827): a run of questions is one only
#     when it ends on a question that opens on «Ou» («Or», «Oder»). The questions inside
#     that run that open on «Pour», «Et»… join it as part of the run, never alone: «Alors,
#     quel jour ? Et on se retrouve où ?» is two questions (review of #900).
# ---------------------------------------------------------------------------------------

_STOPS = ".!?…"
#: The one closing mark a stop may carry before the space («?“ stimmt», «brille.»»).
_CLOSERS = "\"»”“’)]›"
#: Where a quotation opens, and what closes it: «“» closes a German «„» and opens an
#: English quotation; «"» opens and closes.
_QUOTE_PAIRS = {"«": "»", "„": "“”", "“": "”", "‹": "›", '"': '"'}
#: What a new sentence opens on.
_OPENS = re.compile(r"[A-ZÀ-ÖØ-Þ0-9«\"“„(\[—–]")
#: The word only a later alternative opens on: «Ou …?» is never a question of its own, and
#: it alone closes a chain (fr, en, de: notes come in all three).
ALTERNATIVE_WORDS = frozenset({"ou", "or", "oder"})
#: The words a question inside a chain may open on («Pour toi et les autres ?»). They link
#: a question to the one before it only on the way to an «Ou …?»: on their own, «Et on se
#: retrouve où ?» and «Pour quel motif ?» are questions of their own.
LINK_WORDS = frozenset({"et", "pour", "ni", "and", "for", "nor", "und", "für"})
CHAIN_WORDS = ALTERNATIVE_WORDS | LINK_WORDS
_FIRST_WORD = re.compile(r"[^\W\d_]+")
_LEADING_MARKS = "«“„\"'‘’([—–- "


def _flat(text: object) -> str:
    return " ".join(str(text or "").split())


def _quotation_spans(flat: str) -> list[tuple[int, int]]:
    """Each quotation that opens and closes again, as (open, close) indexes."""

    spans: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for index, char in enumerate(flat):
        if stack and char in stack[-1][0]:
            spans.append((stack.pop()[1], index))
        elif char in _QUOTE_PAIRS:
            stack.append((_QUOTE_PAIRS[char], index))
    return spans


def _carried_on(flat: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The quotations their sentence carries on after: what follows the closing mark is
    no new sentence and not the end of the text («“ stimmt nicht», «”.», «» demande»)."""

    kept = []
    for start, end in spans:
        rest = flat[end + 1 :].lstrip()
        if rest and not _OPENS.match(rest):
            kept.append((start, end))
    return kept


def _ends_here(left: str) -> bool:
    """Whether the text before a space closes a sentence: a stop, then at most one closing
    mark or a French-spaced «»» («Margaux ? »»), and not a title's or an initial's stop."""

    stem = left
    if stem.endswith(" »"):
        stem = stem[:-2]
    elif stem and stem[-1] in _CLOSERS:
        stem = stem[:-1]
    if not stem or stem[-1] not in _STOPS:
        return False
    return not _TITLE_WORD.fullmatch(stem.rsplit(" ", 1)[-1].lstrip(_LEADING_MARKS))


def asks(sentence: object) -> bool:
    """Whether a sentence asks: it ends on «?», a closing mark may follow."""

    return str(sentence or "").rstrip(_CLOSERS + " \u00a0\u202f").endswith("?")


def _first_word(sentence: str) -> str:
    found = _FIRST_WORD.match(sentence.lstrip(_LEADING_MARKS))
    return found.group(0).lower() if found else ""


def _chained(pieces: list[str]) -> list[str]:
    """Each chain of alternatives as one sentence: a question that opens on «Ou» takes back
    the questions before it while each one it reaches opens on a chain word, and the one
    question the chain starts from. Nothing joins without an «Ou …?» to close it."""

    joined: list[str] = []
    for piece in pieces:
        start = len(joined)
        if asks(piece) and _first_word(piece) in ALTERNATIVE_WORDS:
            head = piece
            while start > 0 and asks(joined[start - 1]) and _first_word(head) in CHAIN_WORDS:
                start -= 1
                head = joined[start]
        joined[start:] = [" ".join([*joined[start:], piece])]
    return joined


def sentences(text: object) -> list[str]:
    """``text`` as its sentences, the one way every surface reads them (#896)."""

    flat = _flat(text)
    if not flat:
        return []
    inside = _carried_on(flat, _quotation_spans(flat))
    pieces: list[str] = []
    start = 0
    for index, char in enumerate(flat):
        if char != " " or not 0 < index < len(flat) - 1:
            continue
        if not _OPENS.match(flat[index + 1]) or not _ends_here(flat[:index]):
            continue
        if any(opened < index < closed for opened, closed in inside):
            continue
        pieces.append(flat[start:index])
        start = index + 1
    pieces.append(flat[start:])
    return _chained([piece.strip() for piece in pieces if piece.strip()])


def cut_sentences(text: object) -> list[str]:
    """``text`` cut after every . ! ? … that is no title's or initial's, each piece as it was
    stored, so a caller can look a word up in it (#398: «Sur le toit, la lampe de M.» was the
    sentence of «lampe»). Unlike :func:`sentences`, the next piece need not open on a capital."""

    return [part for part in _LOOSE_BOUNDARY.split(str(text or "")) if part.strip()]


def ends_sentence(word: str) -> bool:
    """Whether a word, as a text is cut on its spaces, closes a sentence: «brille.» and «pas ?»
    do; a title or an initial («M.», «Mme.», «J.») does not (#398)."""

    bare = str(word or "").strip("«»“”\"„()[]")
    if not bare or bare[-1] not in ".!?…":
        return False
    return not _TITLE_WORD.fullmatch(bare)


def stops_at_title(text: object) -> bool:
    """Whether a text stops on a title or an initial («Sur le toit, la lampe de M.», «— M.»):
    the rest of a sentence cut at its abbreviation, or a signature, never a sentence a drill
    may pose (#398)."""

    return bool(_STOPS_AT_TITLE.search(str(text or "").strip()))


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
    """The question the text asks (its last asking sentence), whole; else the opening
    sentences that fit. A chapter's question is its last sentence, not its first.

    A chain of alternatives is one sentence to :func:`sentences`, so it is never cut to its
    last alternative («Ou tu dis au revoir à tout ça ?», #827); the questions right before
    it that lead into it («Alors, qu'est-ce que tu fais ?») come along while they fit."""

    flat = _flat(text)
    if len(flat) <= limit:
        return flat
    parts = sentences(flat)
    asking = [index for index, sentence in enumerate(parts) if asks(sentence)]
    if not asking:
        return whole_sentences(flat, limit)
    start = asking[-1]
    line = parts[start]
    if len(line) > limit:
        return whole_sentences(line, limit)
    while start > 0 and asks(parts[start - 1]) and len(f"{parts[start - 1]} {line}") <= limit:
        start -= 1
        line = f"{parts[start]} {line}"
    if _first_word(line) in ALTERNATIVE_WORDS:
        # «Ou …?» after a statement offers that statement's other way: both, or nothing.
        lead = f"{parts[start - 1]} {line}" if start > 0 else ""
        return lead if lead and len(lead) <= limit else ""
    return line


def drop_cut_tail(text: object) -> str:
    """A stored line that an older cut left ending mid-sentence («… Alors,…»), without the
    fragment. A whole line, and a deliberate «À suivre…», are returned as they were.

    An older :func:`question_line` filed a chain of alternatives as its last one alone («Ou
    tu dis au revoir à tout ça ?», #827): a lone question opening on «Ou» is all fragment.
    Any other whole question («Et si … ?», «Mais qui … ?», «Pour qui … ?») is kept."""

    flat = _flat(text)
    if _first_word(flat) in ALTERNATIVE_WORDS and len(sentences(flat)) == 1 and asks(flat):
        return ""
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
