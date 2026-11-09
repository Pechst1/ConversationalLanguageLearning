"""One verdict shape for every surface that judges what a learner wrote (#174, #250, #333).

Pure: no database and no model. Drills, La Forge, the scene, Le Courrier and the Journal
each grew their own way of saying «was this checked?». The learner could not tell «you
were right» from «nothing looked at it», and a failed check moved levels and minted gold.

The rules the shape holds, whoever builds one:

1. ``right`` comes only from the key or a model. Rules can add fixes, never a verdict: a
   failed call with rule fixes is ``not_checked``, ``checked_by: rules``.
2. :attr:`Verdict.counts` is the one thing a level, gold or a token may read.
3. ``corrected`` is built from ``edits``, so no screen can print a change it doesn't list.
4. «No mistakes» needs ``call: ok``, no edits, and rules that agree.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Outcome(StrEnum):
    RIGHT = "right"
    PARTLY = "partly"
    NOT_YET = "not_yet"
    NOT_CHECKED = "not_checked"


class CheckedBy(StrEnum):
    KEY = "key"
    MODEL = "model"
    RULES = "rules"
    NONE = "none"


class Call(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    FAILED = "failed"
    PENDING = "pending"
    NOT_CALLED = "not_called"


class Failure(StrEnum):
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_OUTPUT = "invalid_output"
    NO_MODEL = "no_model"
    NO_CHECK_TARGET = "no_check_target"


@dataclass(frozen=True, slots=True)
class Edit:
    """One listed change: ``span`` at ``start``..``end`` of the learner's text becomes ``replacement``."""

    span: str
    start: int
    end: int
    replacement: str
    note: str = ""
    by: str = "model"
    rule_id: str | None = None


@dataclass(frozen=True, slots=True)
class Verdict:
    """Build one with :func:`make_verdict`, which applies the rules above."""

    outcome: Outcome
    checked_by: CheckedBy
    call: Call
    failure: Failure | None = None
    retryable: bool = False
    edits: tuple[Edit, ...] = ()
    corrected: str | None = None

    @property
    def counts(self) -> bool:
        """Whether this may move a level, mint gold or mint a token."""

        if self.outcome is Outcome.NOT_CHECKED:
            return False
        if self.checked_by is CheckedBy.KEY:
            return True
        return self.checked_by is CheckedBy.MODEL and self.call is Call.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "checked_by": self.checked_by.value,
            "call": self.call.value,
            "failure": self.failure.value if self.failure else None,
            "retryable": self.retryable,
            "edits": [
                {
                    "span": edit.span,
                    "start": edit.start,
                    "end": edit.end,
                    "replacement": edit.replacement,
                    "note": edit.note,
                    "by": edit.by,
                    "rule_id": edit.rule_id,
                }
                for edit in self.edits
            ],
            "corrected": self.corrected,
            "counts": self.counts,
        }


def _span_pattern(span: str) -> re.Pattern[str]:
    """The span as whole words, whichever apostrophe it was quoted with."""

    body = "".join("['’]" if char in "'’" else re.escape(char) for char in span)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)


def locate_edits(text: str, proposed: Iterable[dict[str, Any]]) -> tuple[Edit, ...]:
    """The proposed changes whose span is really in ``text``, in reading order, none overlapping.

    Each row holds ``span`` and ``replacement``, and may hold ``note``, ``by`` and
    ``rule_id``. An edit naming words the learner did not write has nothing to change,
    so it is left out rather than printed.
    """

    taken: list[tuple[int, int]] = []
    edits: list[Edit] = []
    for row in proposed:
        span = str(row.get("span") or "")
        replacement = str(row.get("replacement") or "")
        if not span.strip() or span.strip() == replacement.strip():
            continue
        for match in _span_pattern(span).finditer(text):
            start, end = match.span()
            if all(end <= left or start >= right for left, right in taken):
                taken.append((start, end))
                edits.append(
                    Edit(
                        span=text[start:end],
                        start=start,
                        end=end,
                        replacement=replacement,
                        note=str(row.get("note") or ""),
                        by=str(row.get("by") or "model"),
                        rule_id=row.get("rule_id") or None,
                    )
                )
                break
    return tuple(sorted(edits, key=lambda edit: edit.start))


def apply_edits(text: str, edits: Iterable[Edit]) -> str:
    """``text`` with ``edits`` made, and nothing else changed."""

    out = text
    for edit in sorted(edits, key=lambda item: item.start, reverse=True):
        out = out[: edit.start] + edit.replacement + out[edit.end :]
    return out


def make_verdict(
    *,
    outcome: Outcome,
    checked_by: CheckedBy,
    call: Call,
    text: str = "",
    proposed: Iterable[dict[str, Any]] = (),
    failure: Failure | None = None,
    retryable: bool = False,
) -> Verdict:
    """A verdict that holds the module's rules, whatever the caller read from a stored row."""

    edits = locate_edits(text, proposed)
    settled = checked_by is CheckedBy.KEY or (checked_by is CheckedBy.MODEL and call is Call.OK)
    if not settled:
        outcome = Outcome.NOT_CHECKED
        if checked_by is CheckedBy.MODEL:
            checked_by = CheckedBy.NONE
        if edits:
            checked_by = CheckedBy.RULES
        elif checked_by is CheckedBy.RULES:
            checked_by = CheckedBy.NONE
    return Verdict(
        outcome=outcome,
        checked_by=checked_by,
        call=call,
        failure=None if settled else failure,
        retryable=retryable and not settled and call in {Call.FAILED, Call.EMPTY},
        edits=edits,
        corrected=apply_edits(text, edits) if edits else None,
    )


__all__ = [
    "Call",
    "CheckedBy",
    "Edit",
    "Failure",
    "Outcome",
    "Verdict",
    "apply_edits",
    "locate_edits",
    "make_verdict",
]
