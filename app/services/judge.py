"""Package V stage 2: the one judge. Every verdict a learner sees is built here.

Before, nine adapters in :mod:`app.services.verdicts` each built a verdict from their own
surface's stored payload, so a change to one adapter quietly re-judged that surface's
history. Now an adapter only *reads*: it turns what a surface stored (or just produced)
into a :class:`Reading`, the evidence. :func:`judge` turns evidence into the verdict, in
fixed stages, the first that settles winning:

1. **normalise** the learner's text (``answer_acceptance.fold_typography``);
2. **key**: the task's accepted answers and listed variants (``answer_acceptance.judge``),
   or the surface's own key reading (a drill, an authored scene, a Forge accept-list);
3. **memo**: a confirmed answer to this keyed item (:mod:`app.services.answer_memo`),
   asked through ``memos`` before any model call (:func:`consult`);
4. **rules**: add edits, never a verdict;
5. **model**: its reading, with every edit located in the learner's own words;
6. **variant gate**: no edit turns one accepted spelling into another
   (:func:`app.services.spelling_variants.is_variant_edit`).

:func:`judge_version` names the judge: a hash of the rule set, the readers, this file and
the corrector model ids. A ledger record (:mod:`app.services.verdict_ledger`) stores it,
so a replay can tell which judge decided what.

Pure but for the memo: ``memos`` is the one door to the database, and only when a caller
passes it. The model call itself stays in each surface's corrector, which asks
:func:`consult` first: when the key or a confirmed memo settles the answer, the corrector
makes no call. What a model answered reaches the judge as the reading's ``by=model``
evidence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.verdict import Call, CheckedBy, Failure, Outcome, Verdict, make_verdict

__all__ = ["STAGES", "MemoLookup", "Reading", "Ruling", "Task", "consult", "judge", "judge_version", "settled_by"]

#: The stages, in the order they run. A record names the one that settled it.
STAGES = ("normalise", "key", "memo", "rules", "model", "variant_gate")

_APP = Path(__file__).resolve().parents[1]
#: What the verdict depends on besides the stored evidence: the rules, the readers, the judge.
_RULE_FILES = (
    "core/verdict.py",
    "services/judge.py",
    "services/verdicts.py",
    "services/correction_contract.py",
    "services/spelling_variants.py",
    "services/answer_acceptance.py",
    "services/answer_memo.py",
)
#: The models whose answers the readers turn into evidence.
_MODEL_SETTINGS = (
    "ATELIER_CORRECTION_LLM_MODEL",
    "OPENAI_ERROR_DETECTION_MODEL",
    "OPENAI_MISSION_FAST_MODEL",
    "OPENAI_MODEL",
)


@dataclass(frozen=True, slots=True)
class Task:
    """What the answer was for. ``accepted``: the key and its listed variants, when there is one."""

    surface: str
    accepted: tuple[str, ...] = ()
    item: str | None = None


@dataclass(frozen=True, slots=True)
class Reading:
    """The evidence a surface holds about one answer. No verdict: the judge makes that.

    ``by`` is who produced ``outcome``: the surface's key, a model, or nobody (``none``).
    ``call`` is the model call's state. ``proposed`` are the edits as the surface stored
    them (``span``, ``replacement``, ``note``, ``by``, ``rule_id``).
    """

    outcome: Outcome = Outcome.NOT_CHECKED
    by: CheckedBy = CheckedBy.NONE
    call: Call = Call.NOT_CALLED
    failure: Failure | None = None
    retryable: bool = False
    proposed: tuple[Mapping[str, Any], ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "by": self.by.value,
            "call": self.call.value,
            "failure": self.failure.value if self.failure else None,
            "retryable": self.retryable,
            "proposed": [dict(row) for row in self.proposed],
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Reading:
        failure = value.get("failure")
        return cls(
            outcome=Outcome(value.get("outcome") or Outcome.NOT_CHECKED.value),
            by=CheckedBy(value.get("by") or CheckedBy.NONE.value),
            call=Call(value.get("call") or Call.NOT_CALLED.value),
            failure=Failure(failure) if failure else None,
            retryable=bool(value.get("retryable")),
            proposed=tuple(dict(row) for row in value.get("proposed") or []),
        )


@lru_cache(maxsize=1)
def judge_version() -> str:
    """A short hash of what decides a verdict: the rule files and the corrector model ids."""

    from app.config import settings

    digest = hashlib.sha256()
    for relative in _RULE_FILES:
        digest.update(relative.encode())
        digest.update((_APP / relative).read_bytes())
    for name in _MODEL_SETTINGS:
        digest.update(f"{name}={getattr(settings, name, '')}".encode())
    return digest.hexdigest()[:16]


def _normalise(answer: object) -> str:
    from app.services.answer_acceptance import fold_typography

    return fold_typography(answer)


def _by_key(task: Task, normalised: str) -> bool:
    if not task.accepted or not normalised:
        return False
    from app.services.answer_acceptance import judge as accept

    return bool(accept(normalised, task.accepted).correct)


class MemoLookup(Protocol):
    """What the memo stage asks: the confirmed memo for this item and answer, if any."""

    def lookup(self, task: Task, normalised: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class Ruling:
    """What settled an answer before any model call: the ``key`` or a ``memo``."""

    verdict: Verdict
    stage: str
    memo: Any = None


def _memo_reading(memo: Any) -> Reading:
    """A confirmed memo reads like the key: settled, no call, its verified edits kept."""

    return Reading(
        outcome=Outcome(memo.outcome),
        by=CheckedBy.KEY,
        call=Call.NOT_CALLED,
        proposed=tuple(dict(row, by="key") for row in (memo.edits or [])),
    )


def _memo(task: Task, normalised: str, memos: MemoLookup | None) -> Any:
    if memos is None or not task.item or not normalised:
        return None
    return memos.lookup(task, normalised)


def _gated(proposed: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Stage 6: an edit between two accepted spellings corrects nothing."""

    from app.services.spelling_variants import is_variant_edit

    return [row for row in proposed if not is_variant_edit(row.get("span"), row.get("replacement"))]


def settled_by(task: Task, answer: object, reading: Reading | None, *, memos: MemoLookup | None = None) -> str:
    """The stage that settles this answer, or ``none`` when nothing does."""

    normalised = _normalise(answer)
    if _by_key(task, normalised) or (reading is not None and reading.by is CheckedBy.KEY):
        return "key"
    if _memo(task, normalised, memos) is not None:
        return "memo"
    if reading is not None and reading.by is CheckedBy.MODEL and reading.call is Call.OK:
        return "model"
    return "none"


def consult(task: Task, answer: object, *, memos: MemoLookup | None = None) -> Ruling | None:
    """Stages 1 to 3 alone: what settles ``answer`` before any model is asked.

    A corrector calls this first. ``None`` means the model is needed; a ruling means it
    is not, and ``ruling.memo`` holds what the surface stores for a memo's answer.
    """

    text = "" if answer is None else str(answer)
    normalised = _normalise(text)
    if _by_key(task, normalised):
        return Ruling(make_verdict(outcome=Outcome.RIGHT, checked_by=CheckedBy.KEY, call=Call.NOT_CALLED), "key")
    memo = _memo(task, normalised, memos)
    if memo is None:
        return None
    reading = _memo_reading(memo)
    verdict = make_verdict(
        outcome=reading.outcome,
        checked_by=reading.by,
        call=reading.call,
        text=text,
        proposed=_gated(reading.proposed),
    )
    return Ruling(verdict, "memo", memo)


def judge(
    task: Task,
    answer: object,
    *,
    reading: Reading | None = None,
    user: Any = None,  # noqa: ARG001 - the appeal (stage 5) is per learner
    memos: MemoLookup | None = None,
) -> Verdict:
    """The verdict on ``answer`` for ``task``, from the surface's ``reading``.

    ``memos`` lets stage 3 read the confirmed memos (:mod:`app.services.answer_memo`).
    """

    text = "" if answer is None else str(answer)
    reading = reading or Reading()
    normalised = _normalise(text)  # stage 1

    # Stage 2: the key settles, and only the key's own fixes are shown with it.
    if _by_key(task, normalised):
        return make_verdict(outcome=Outcome.RIGHT, checked_by=CheckedBy.KEY, call=Call.NOT_CALLED)
    memo = _memo(task, normalised, memos)  # stage 3
    if memo is not None:
        reading = _memo_reading(memo)

    # Stages 4 and 5: rule edits and model edits are evidence; make_verdict keeps only those
    # whose words are in the learner's text, and only a key or an answered call settles.
    # Stage 6: the variant gate drops an edit between two accepted spellings.
    proposed = _gated(reading.proposed)
    return make_verdict(
        outcome=reading.outcome,
        checked_by=reading.by,
        call=reading.call,
        text=text,
        proposed=proposed,
        failure=reading.failure,
        retryable=reading.retryable,
    )
