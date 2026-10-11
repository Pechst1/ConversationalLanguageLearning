"""WP-115b — the recall ladder: a card's format follows its memory, not a counter.

The drill chose a card's format from ``proficiency_score`` (±10 per answer), so one lucky
streak put a fragile word into a harder mode and one slip pushed a solid word back. The
ladder reads the scheduler's own stability (days until recall falls to ~90 %), with
the band deciding how long a learner stays on the receptive side (Terai et al. 2021:
learners at lower levels gain more from recognising first; at B1 production pays sooner):

``recognition`` → ``production`` (the meaning → type the French) → ``audio`` (hear it →
type it) → ``cloze`` (a new sentence, the word blanked).

Two rungs sit beside the ladder:

* **the scene** — for a word kept from the story (``progress.context``), its first two
  reviews show its own line, speaker and voice with the word blanked; from the third
  review on it meets new contexts (varied encounters, Bolger et al. 2008);
* **rescue** — a leech (≥ :data:`LEECH_LAPSES` lapses) changes method instead of
  frequency: its original line when there is one, else a sentence of the catalogue, with
  the first letter and the length given (a cued recall), labelled «mot têtu».
"""

from __future__ import annotations

import re
from typing import Any

LEECH_LAPSES = 5
#: Reviews after which a story word leaves its own scene for new contexts.
SCENE_REVIEWS = 2
#: Stability (days) at which a card moves up: production, audio, cloze.
THRESHOLDS: dict[str, tuple[float, float, float]] = {
    "A1": (5.0, 14.0, 30.0),
    "A2": (3.0, 10.0, 30.0),
    "B1": (1.0, 7.0, 21.0),
    "B2": (1.0, 5.0, 14.0),
    "C1": (1.0, 4.0, 10.0),
}


def _band(level: str | None) -> str:
    code = str(level or "").strip().upper()[:2]
    if code in THRESHOLDS:
        return code
    return "C1" if code == "C2" else "A2"


_ARTICLES = {"le", "la", "les", "l'", "un", "une"}
#: An elided clitic a learner may type in front of the blanked form («j'étais»).
_ELISION_CLITICS = {"j", "l", "d", "n", "m", "t", "s", "c", "qu", "lorsqu", "puisqu", "jusqu"}
_APOSTROPHES = "'\u2018\u2019\u02bc\u02bb\u2032\uff07`\u00b4"
_WORD_CHARS = r"[^\W\d_]"


def _head(word: str) -> str:
    """The word without its article («la serrure» → «serrure»)."""

    head = str(word or "").strip()
    parts = head.split(" ", 1)
    if len(parts) == 2 and parts[0].casefold() in _ARTICLES:
        head = parts[1]
    return head


def _pattern(form: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w]){re.escape(form)}(?![\w])", re.IGNORECASE)


def blank_word(sentence: str, word: str) -> str | None:
    """``sentence`` with ``word`` (its head, without the article) replaced by a blank, or
    ``None`` when the word is not in it as written."""

    head = _head(word)
    if not head or not sentence:
        return None
    pattern = _pattern(head)
    if not pattern.search(sentence):
        return None
    return pattern.sub("_____", sentence, count=1)


def _fold(value: str) -> str:
    from app.services.answer_acceptance import fold_typography

    return fold_typography(value)


def _lemma_candidates(key: str) -> tuple[str, ...]:
    """The lemmas a running word may have (spaCy first, cached; the curated table
    after). A resolver that cannot load yields only the word itself."""

    try:
        from app.services.lexical_coverage import default_resolver

        return default_resolver().candidates(key)
    except Exception:  # pragma: no cover - a broken pipeline never costs a card
        return (key,)


def _derived_form(sentence: str, head: str) -> str | None:
    """The one inflected token of ``sentence`` whose lemma is ``head`` — ``None`` when
    there is none or more than one distinct form (an ambiguous blank is no blank)."""

    try:
        from app.services.lexical_coverage import fold, tokenize
    except Exception:  # pragma: no cover
        return None
    target = fold(head)
    if not target or " " in target:
        return None
    forms: set[str] = set()
    for token in tokenize(sentence):
        if token.key == target or target in _lemma_candidates(token.key):
            forms.add(token.key)
    return forms.pop() if len(forms) == 1 else None


def scene_form(sentence: str, lemma: str, stored: str | None = None) -> dict[str, Any] | None:
    """The in-context card for a kept word (owner decision 2026-10-08).

    A cloze can only be answered with the form that fits the line, so the blank is the
    word **as it appeared in the line** («Vous venez d'où ?» → «venez») and that form
    is the answer; the lemma is the hint. The form is the one stored at keeping time,
    else the lemma itself when the line has it as written, else the one token of the
    line whose lemma it is. ``None`` when no single occurrence can be blanked — a
    broken blank (none, or the answer still visible elsewhere in the line) is never
    shown.

    Returns ``{sentence_fr, expected_fr, hint_fr, accepted}``: the blanked line, the
    form to type (lower-cased unless the lemma is capitalised), the lemma's head when
    the form differs from it (else ``None``), and the answers the grader accepts (the
    form, and the form with its elided clitic, «j'étais»).
    """

    line = str(sentence or "")
    head = _head(lemma)
    if not line or not head:
        return None
    candidates: list[str] = []
    stored_head = _head(stored or "")
    if stored_head:
        candidates.append(stored_head)
    candidates.append(head)
    for candidate in candidates:
        matches = list(_pattern(candidate).finditer(line))
        if len(matches) == 1:
            match = matches[0]
            break
        if len(matches) > 1 and candidate == stored_head:
            return None
    else:
        derived = _derived_form(line, head)
        matches = list(_pattern(derived).finditer(line)) if derived else []
        if len(matches) != 1:
            return None
        match = matches[0]
    form = match.group(0)
    expected = form if any(ch.isupper() for ch in head) else form.lower()
    inflected = _fold(expected) != _fold(head)
    accepted = [expected]
    before = line[: match.start()]
    if before and before[-1] in _APOSTROPHES:
        clitic = re.search(rf"({_WORD_CHARS}+)$", before[:-1])
        if clitic and clitic.group(1).casefold() in _ELISION_CLITICS:
            accepted.append(f"{clitic.group(1).lower()}'{expected}")
    return {
        "sentence_fr": line[: match.start()] + "_____" + line[match.end():],
        "expected_fr": expected,
        "hint_fr": head if inflected else None,
        "accepted": accepted,
    }


def rung(
    *,
    stability: float | None,
    reps: int | None,
    lapses: int | None,
    level: str | None,
    has_example: bool,
) -> str:
    """The ladder's rung for one card: recognition, production, audio or cloze."""

    if not reps:
        return "recognition"
    production, audio, cloze = THRESHOLDS[_band(level)]
    held = float(stability or 0.0)
    if held >= cloze and has_example:
        return "cloze"
    if held >= audio:
        return "audio"
    if held >= production:
        return "production"
    return "recognition"


def card_ladder(progress: Any, word: Any, *, level: str | None) -> dict[str, Any]:
    """``{ladder, scene_cue, leech, rescue_cue}`` for a drill card (additive fields).

    The scene (and a rescue drawn from the word's own line) blanks the word as it was
    in the line and expects that form (:func:`scene_form`); its cue carries
    ``expected_fr`` and, when the form is inflected, ``hint_fr`` (the lemma). The card,
    its evidence and its schedule stay the lemma's.
    """

    if progress is None:
        return {"ladder": "recognition", "scene_cue": None, "leech": False, "rescue_cue": None}
    reps = int(progress.reps or 0)
    lapses = int(progress.lapses or 0)
    leech = lapses >= LEECH_LAPSES
    lemma = str(getattr(word, "word", "") or "")
    example_blank = blank_word(str(getattr(word, "example_sentence", "") or ""), lemma)
    out: dict[str, Any] = {
        "ladder": rung(
            stability=progress.stability, reps=reps, lapses=lapses, level=level, has_example=bool(example_blank)
        ),
        "scene_cue": None,
        "leech": leech,
        "rescue_cue": None,
    }
    in_line = in_line_card(progress, word) if (leech or reps < SCENE_REVIEWS) else None
    context = progress.context if isinstance(getattr(progress, "context", None), dict) else {}
    if in_line and not leech:
        out["ladder"] = "scene"
        out["scene_cue"] = {
            "sentence_fr": in_line["sentence_fr"],
            "speaker_id": context.get("speaker_id"),
            "line_key": context.get("line_key"),
            "expected_fr": in_line["expected_fr"],
            "hint_fr": in_line["hint_fr"],
        }
    if leech:
        head = in_line["expected_fr"] if in_line else _head(lemma)
        out["ladder"] = "rescue"
        out["rescue_cue"] = {
            "sentence_fr": in_line["sentence_fr"] if in_line else example_blank,
            "first_letter": head[:1],
            "length": len(head),
            "speaker_id": context.get("speaker_id") if in_line else None,
            "expected_fr": in_line["expected_fr"] if in_line else None,
            "hint_fr": in_line["hint_fr"] if in_line else None,
        }
    return out


def in_line_card(progress: Any, word: Any) -> dict[str, Any] | None:
    """The kept word's own line, blanked at the form it had there (or ``None``)."""

    context = progress.context if isinstance(getattr(progress, "context", None), dict) else {}
    line = str(context.get("sentence_fr") or "")
    if not line:
        return None
    return scene_form(line, str(getattr(word, "word", "") or ""), str(context.get("surface_fr") or "") or None)


def in_line_answer(progress: Any, word: Any) -> dict[str, Any] | None:
    """What a ``cloze``-format review of this card is graded against when the card on
    screen was its own line at an inflected form: ``{expected_fr, hint_fr, accepted}``.
    ``None`` when the card was graded by the lemma (no line, a form equal to the lemma,
    or a card past its scene reviews and not a leech) — the drill's own rule, re-read
    on the server so the client's expected answer is never trusted."""

    ladder = card_ladder(progress, word, level=None)
    cue = ladder.get("scene_cue") if ladder["ladder"] == "scene" else ladder.get("rescue_cue")
    if ladder["ladder"] not in {"scene", "rescue"} or not cue or not cue.get("hint_fr"):
        return None
    return in_line_card(progress, word)
