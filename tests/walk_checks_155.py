"""#155 — a recall item cut from a line of today's page is that line's speaker's.

The walk of 21 Oct (b1, day 1) wrote «Complète la phrase de la scène» over Marin's
line «…Vous allez vraiment … l'appartement d'Odile ?», drew Gus beside it and
cheered «Gus te sourit»: the item took its face from the day's character, not
from the line. This check reads what the learner reads: the page the scene step
drew (its lines and who says them) and each recall item's prompt. An item whose
French is a character's line of that page (whole, one of its sentences, or the
line with a gap cut out of it) must name that person in ``prompt.speaker``, with
the cast's short name; «Qui a dit ça ?» must name nobody, since the face would be
its answer. Items that are not cut from a line are not judged.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

#: The gap a cloze leaves in its line.
_GAP = re.compile(r"_{2,}|…|\.{3}")
#: Picks show their line in the prompt; their answer may be another card's line.
_PICKS = frozenset({"choice", "classify", "listen_tap", "match_pairs", "who_said"})


def _words(text: Any) -> list[str]:
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = re.sub(r"[’ʼ‘]", "'", folded)
    return re.sub(r"[^0-9a-z'\s]+", " ", folded).split()


def _sentences(text: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?…])\s+", " ".join(text.split())) if part]


def page_lines(transcript: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """``(speaker id, folded words)`` for each character line of the day's page and
    each of its sentences, in reading order. The narration is nobody's line."""

    lines: list[tuple[str, list[str]]] = []
    for event in transcript.get("events") or []:
        for panel in event.get("page") or []:
            for line in panel.get("dialogue") or []:
                speaker = str((line or {}).get("character_id") or "")
                text = str((line or {}).get("text_fr") or "")
                if not speaker or speaker == "narrator" or not text.strip():
                    continue
                lines.append((speaker, _words(text)))
                lines.extend((speaker, _words(sentence)) for sentence in _sentences(text))
    return [(speaker, words) for speaker, words in lines if words]


def _cut_from(text: Any, lines: list[tuple[str, list[str]]]) -> str | None:
    """Whose line ``text`` is: the same words, or the line with one gap (≤ 4 words) cut out."""

    raw = str(text or "")
    parts = [_words(part) for part in _GAP.split(raw)]
    parts = [part for part in parts if part]
    if sum(len(part) for part in parts) < 3:
        return None
    if not _GAP.search(raw):
        return next((speaker for speaker, words in lines if words == parts[0]), None)
    for speaker, words in lines:
        start, found = 0, True
        for part in parts:
            at = next((i for i in range(start, len(words) - len(part) + 1) if words[i:i + len(part)] == part), None)
            if at is None:
                found = False
                break
            start = at + len(part)
        if found and len(words) - sum(len(part) for part in parts) <= 4:
            return speaker
    return None


def check_recall_speakers(transcript: dict[str, Any]) -> list[str]:
    from app.services.cast_registry import display_name, resolve_id

    lines = page_lines(transcript)
    problems: list[str] = []
    for index, event in enumerate(transcript.get("events") or []):
        step = event.get("step") or {}
        if step.get("kind") != "recall":
            continue
        prompt = step.get("prompt") or {}
        speaker = prompt.get("speaker") or {}
        task_type = prompt.get("task_type")
        label = f"{transcript.get('persona')} day {transcript.get('day')} [{index}:recall:{task_type}]"
        if task_type == "who_said":
            if speaker:
                problems.append(f"{label}: «Qui a dit ça ?» shows its answer's face ({speaker.get('id')})")
            continue
        key = event.get("key") or {}
        shown = [prompt.get("source_fr"), prompt.get("prompt_fr")]
        rebuilt = [] if task_type in _PICKS else [key.get("solution_fr"), *(key.get("accepted_answers") or [])[:1]]
        owner = next((who for who in (_cut_from(text, lines) for text in [*shown, *rebuilt]) if who), None)
        if owner is None:
            continue
        expected = resolve_id(owner) or owner
        got = resolve_id(speaker.get("id")) or speaker.get("id")
        if got != expected:
            problems.append(
                f"{label}: cut from {owner}'s line but asked by {speaker.get('id') or 'the day’s character'}"
            )
        elif display_name(expected) and speaker.get("name") != display_name(expected):
            problems.append(
                f"{label}: {owner}'s line is named «{speaker.get('name')}», not «{display_name(expected)}»"
            )
    return problems
