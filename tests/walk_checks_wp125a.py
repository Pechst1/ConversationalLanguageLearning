"""WP-125A walk check — a letter's unused suggested word is not a language error.

Runs over a life record from `tests/experience_walk.py` (the ``courrier`` entry of
each day). Owner decision 6 (2026-10-04): a suggested word the learner did not
use must not become a repair, a missing target, or a lower verdict / outcome.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _fold(text: Any) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _uses(reply: str, word: Any) -> bool:
    folded = _fold(word)
    return bool(folded) and f" {folded} " in f" {_fold(reply)} "


def _is_vocabulary(item: dict[str, Any]) -> bool:
    marker = f"{item.get('error_category') or ''} {item.get('task_error_type') or ''}".lower()
    return bool(item.get("linked_word_id")) or "vocab" in marker


def check_letter_omissions(record: dict[str, Any]) -> list[str]:
    """No letter whose only shortfall is an unused suggested word is partial or carries a repair."""

    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    for day in record.get("days") or []:
        label = f"{who} day {day.get('day')}"
        for letter in (day.get("courrier") or {}).get("letters") or []:
            reply = str(letter.get("reply") or "")
            if not reply:
                continue
            unused = [w for w in letter.get("target_vocabulary") or [] if w and not _uses(reply, w)]
            if not unused:
                continue
            correction = letter.get("correction") or {}
            errata = [item for item in correction.get("errata") or [] if isinstance(item, dict)]
            title = letter.get("title")
            for item in errata:
                if str(item.get("task_error_type") or "") == "vocabulary_missing_target":
                    problems.append(
                        f"{label}: an unused suggested word became a repair in {title!r}: {item.get('display_label')!r}"
                    )
            for target in correction.get("missing_targets") or []:
                if isinstance(target, dict) and str(target.get("external_id") or "").startswith("VOCAB_"):
                    problems.append(f"{label}: an unused suggested word is a missing target in {title!r}: {target.get('label')!r}")
            communicative = [
                item
                for item in correction.get("objective_progress") or []
                if isinstance(item, dict) and not str(item.get("id") or "").startswith("vocabulary_")
            ]
            language_errata = [
                item for item in errata
                if not _is_vocabulary(item) and str(item.get("task_error_type") or "") != "task_compliance"
            ]
            only_shortfall = (
                bool(communicative)
                and all(item.get("met") and item.get("assessed") is not False for item in communicative)
                and not language_errata
            )
            if not only_shortfall:
                continue
            if correction.get("verdict") in {"partial", "needs_revision"}:
                problems.append(
                    f"{label}: {title!r} is {correction.get('verdict')!r} only because {unused!r} went unused"
                )
            outcome = (letter.get("recap") or {}).get("outcome")
            if outcome and outcome != "kept":
                problems.append(f"{label}: {title!r} ends {outcome!r} only because {unused!r} went unused")
    return problems


__all__ = ["check_letter_omissions"]
