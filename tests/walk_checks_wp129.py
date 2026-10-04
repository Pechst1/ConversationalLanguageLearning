"""WP-129 — life-walk invariants for practice volume, one sentence per item, and D7.

Each function takes one life record of :mod:`tests.experience_walk` (``record["days"]``
with ``day["journey"]["events"]``, every event ``{"step": {"kind", "prompt"}, "key": …}``)
and returns problems as strings, like :func:`tests.walk_checks.check_life`.

* :func:`check_b1_practice` — a B1/B2/C1 life's ordinary days hold, on average,
  at least :data:`B1_MIN_MEAN_ITEMS` practice items, and at least
  :data:`B1_MIN_INTERLEAVED_SHARE` of them are *interleaved*: a grammar item on a
  unit other than that day's new one (owner decision 4: «8–10 items, about half
  interleaved» is the design target; these floors catch a regression to the
  pre-WP-129 three-transform day, not a shortfall against the target).
* :func:`check_one_sentence_one_item` — no two items of one day work on the same
  French sentence (the line printed to work on, or the answer).
* :func:`check_page_review_is_a_met_unit` — a tentpole's review in context
  (a ``rule`` step with ``review``) comes after the ending, and its unit was met
  on an earlier day (a rule read, or an item on it).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

ADVANCED = ("b1", "b2", "c1")
#: The pre-WP-129 B1 lives held 2.9–3.1 items a day; with WP-129 an average
#: B1 life holds 5.5 (8–12 on a day without a new rule, 3–4 on a rule day,
#: whose reply and guided items fill the budget).
B1_MIN_MEAN_ITEMS = 5.0
B1_MIN_INTERLEAVED_SHARE = 0.30


def _who(record: dict[str, Any]) -> str:
    return f"{record.get('persona')} {record.get('quality')}"


def _fold(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[’ʼ‘]", "'", re.sub(r"[\[\]{}]", "", text))
    return " ".join(re.sub(r"[^0-9a-z'\s]+", " ", text).split())


def _events(day: dict[str, Any]) -> list[dict[str, Any]]:
    return list(((day.get("journey") or {}).get("events")) or [])


def _step(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    step = event.get("step") or {}
    return str(step.get("kind") or ""), dict(step.get("prompt") or {})


def _recalls(day: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in _events(day) if _step(event)[0] == "recall"]


def _intro(day: dict[str, Any]) -> str | None:
    for event in _events(day):
        kind, prompt = _step(event)
        if kind == "rule" and not prompt.get("review"):
            return str(prompt.get("concept_id"))
    return None


def _grammar_unit(event: dict[str, Any]) -> str | None:
    target = _step(event)[1].get("target") or {}
    return str(target.get("id")) if isinstance(target, dict) and target.get("kind") == "grammar" else None


def check_b1_practice(record: dict[str, Any]) -> list[str]:
    if not str(record.get("persona") or "").startswith(ADVANCED):
        return []
    items = interleaved = days = 0
    for day in record.get("days") or []:
        if not _events(day) or (day.get("time_budget") or {}).get("longer_day"):
            continue
        days += 1
        intro = _intro(day)
        recalls = _recalls(day)
        items += len(recalls)
        interleaved += sum(1 for event in recalls if _grammar_unit(event) not in (None, intro))
    if not days:
        return []
    problems: list[str] = []
    mean = items / days
    if mean < B1_MIN_MEAN_ITEMS:
        problems.append(f"{_who(record)}: {mean:.1f} practice items a day (at least {B1_MIN_MEAN_ITEMS:.0f})")
    share = interleaved / items if items else 0.0
    if share < B1_MIN_INTERLEAVED_SHARE:
        problems.append(
            f"{_who(record)}: {share:.0%} of practice items interleaved (at least {B1_MIN_INTERLEAVED_SHARE:.0%})"
        )
    return problems


def _sentences(event: dict[str, Any]) -> set[str]:
    _kind, prompt = _step(event)
    key = event.get("key") or {}
    out: set[str] = set()
    for text in (prompt.get("prompt_fr"), prompt.get("source_fr"), key.get("solution_fr")):
        folded = _fold(text)
        if len(folded.split()) >= 3:
            out.add(folded)
    return out


def check_one_sentence_one_item(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for day in record.get("days") or []:
        seen: dict[str, str] = {}
        for event in _recalls(day):
            task_type = str(_step(event)[1].get("task_type") or "")
            for sentence in _sentences(event):
                if sentence in seen:
                    problems.append(
                        f"{_who(record)} day {day.get('day')}: «{sentence}» in a {seen[sentence]} and a {task_type}"
                    )
                seen.setdefault(sentence, task_type)
    return problems


def check_page_review_is_a_met_unit(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    met: set[str] = set()
    for day in record.get("days") or []:
        events = _events(day)
        ended = False
        for event in events:
            kind, prompt = _step(event)
            if kind == "resolution":
                ended = True
            if kind == "rule" and prompt.get("review"):
                unit = str(prompt.get("concept_id"))
                if unit not in met:
                    problems.append(f"{_who(record)} day {day.get('day')}: the page review shows unit {unit}, not met before")
                if not ended:
                    problems.append(f"{_who(record)} day {day.get('day')}: the page review comes before the ending")
        for event in events:
            kind, prompt = _step(event)
            if kind == "rule" and not prompt.get("review"):
                met.add(str(prompt.get("concept_id")))
            unit = _grammar_unit(event)
            if unit is not None:
                met.add(unit)
    return problems


def check_life_wp129(record: dict[str, Any]) -> list[str]:
    return [
        *check_b1_practice(record),
        *check_one_sentence_one_item(record),
        *check_page_review_is_a_met_unit(record),
    ]


def practice_summary(record: dict[str, Any]) -> dict[str, float]:
    """Mean items a day and the interleaved share, for the report (any band)."""

    items = interleaved = days = 0
    for day in record.get("days") or []:
        if not _events(day):
            continue
        days += 1
        intro = _intro(day)
        recalls = _recalls(day)
        items += len(recalls)
        interleaved += sum(1 for event in recalls if _grammar_unit(event) not in (None, intro))
    return {
        "items_per_day": items / days if days else 0.0,
        "interleaved_share": interleaved / items if items else 0.0,
    }


__all__ = [
    "B1_MIN_INTERLEAVED_SHARE",
    "B1_MIN_MEAN_ITEMS",
    "check_b1_practice",
    "check_life_wp129",
    "check_one_sentence_one_item",
    "check_page_review_is_a_met_unit",
    "practice_summary",
]
