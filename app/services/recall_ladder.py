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
}


def _band(level: str | None) -> str:
    code = str(level or "").strip().upper()[:2]
    if code in THRESHOLDS:
        return code
    return "B1" if code in {"B2", "C1", "C2"} else "A2"


def blank_word(sentence: str, word: str) -> str | None:
    """``sentence`` with ``word`` (its head, without the article) replaced by a blank, or
    ``None`` when the word is not in it as written."""

    head = str(word or "").strip()
    parts = head.split(" ", 1)
    if len(parts) == 2 and parts[0].casefold() in {"le", "la", "les", "l'", "un", "une"}:
        head = parts[1]
    if not head or not sentence:
        return None
    pattern = re.compile(rf"(?<![\w]){re.escape(head)}(?![\w])", re.IGNORECASE)
    if not pattern.search(sentence):
        return None
    return pattern.sub("_____", sentence, count=1)


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
    """``{ladder, scene_cue, leech, rescue_cue}`` for a drill card (additive fields)."""

    if progress is None:
        return {"ladder": "recognition", "scene_cue": None, "leech": False, "rescue_cue": None}
    reps = int(progress.reps or 0)
    lapses = int(progress.lapses or 0)
    context = progress.context if isinstance(getattr(progress, "context", None), dict) else {}
    lemma = str(getattr(word, "word", "") or "")
    scene_line = str(context.get("sentence_fr") or "")
    scene_blank = blank_word(scene_line, lemma) if scene_line else None
    example_blank = blank_word(str(getattr(word, "example_sentence", "") or ""), lemma)
    leech = lapses >= LEECH_LAPSES
    out: dict[str, Any] = {
        "ladder": rung(
            stability=progress.stability, reps=reps, lapses=lapses, level=level, has_example=bool(example_blank)
        ),
        "scene_cue": None,
        "leech": leech,
        "rescue_cue": None,
    }
    if scene_blank and reps < SCENE_REVIEWS and not leech:
        out["ladder"] = "scene"
        out["scene_cue"] = {
            "sentence_fr": scene_blank,
            "speaker_id": context.get("speaker_id"),
            "line_key": context.get("line_key"),
        }
    if leech:
        head = lemma.split(" ", 1)[1] if " " in lemma and lemma.split(" ", 1)[0].casefold() in {"le", "la", "les", "un", "une"} else lemma
        out["ladder"] = "rescue"
        out["rescue_cue"] = {
            "sentence_fr": scene_blank or example_blank,
            "first_letter": head[:1],
            "length": len(head),
            "speaker_id": context.get("speaker_id") if scene_blank else None,
        }
    return out
