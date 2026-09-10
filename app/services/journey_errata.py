"""WP-24: tomorrow's scene, chosen from yesterday's mistakes.

The cascade errata → due → generation prompt existed before this module, but
nothing *deliberately* picked the day's learning targets from the learner's due
errata: the planner ranked whatever WP-05 happened to hand it, and a mistake
made on Tuesday reached Thursday's scene only by luck.

This module is the deliberate half. It reads the learner's due errata through
:class:`~app.services.error_memory.ErrorMemoryService` — the same queue Le Relevé
and the Cahier read, never a second one — ranks a small set, and returns them as
``ErrataTarget``s the planner can merge into its candidates.

Three things it deliberately does not do:

* It does not schedule anything. Reading the queue must not move a due date;
  only a graded repair does that (``ErrorMemoryService.review_error``).
* It does not return more than a handful. The planner already caps the day at
  two due targets; ranking a hundred would only produce a longer rejection list.
* It never returns a mastered erratum. That is the whole point of the exit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.user import User
from app.services.error_memory import (
    ERROR_STATE_MASTERED,
    ERROR_STATE_REPAIRING,
    ErrorMemoryService,
    normalize_error_state,
    serialize_error_memory,
)
from app.services.journey_contracts import LearningCandidate, TargetKind, TargetRef

#: How many errata targets the planner is ever offered. The planner keeps at
#: most two due targets; three leaves it one to reject on scene fit.
DEFAULT_TARGET_LIMIT = 3

#: Machine-readable reason stamped on a planner target that exists because of a
#: recorded mistake. Read by the because-line and by telemetry.
REASON_PREFIX = "erratum"

#: Ranking weights. A recurrence outranks a first offence, an overdue item
#: outranks a fresh one, and a repair already in progress outranks an untouched
#: one — finishing a repair is worth more than opening another.
_STATE_WEIGHT = {ERROR_STATE_REPAIRING: 1.0, "open": 0.6}


def reason_for(error_id: Any) -> str:
    """The `target_reason` string for one erratum: ``"erratum:<id>"``."""

    return f"{REASON_PREFIX}:{error_id}"


def parse_reason(reason: str | None) -> str | None:
    """The erratum id inside a ``target_reason``, or None if it is not one."""

    text = str(reason or "")
    if not text.startswith(f"{REASON_PREFIX}:"):
        return None
    return text.split(":", 1)[1] or None


@dataclass(frozen=True, slots=True)
class ErrataTarget:
    """One ranked mistake, ready to be a learning target for today's scene."""

    error_id: str
    memory_key: str | None
    concept_id: int | None
    #: The learner's own wrong wording and the correction, e.g. "une homme".
    example_learner: str | None
    example_correct: str | None
    #: The stored explanation, in the learner's own language.
    why: str | None
    label: str
    review_mode: str
    state: str
    occurrences: int
    lapses: int
    overdue_days: int
    priority: float
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        return reason_for(self.error_id)

    @property
    def example(self) -> str | None:
        """``"une homme → un homme"`` when both halves exist."""

        if self.example_learner and self.example_correct:
            return f"{self.example_learner} → {self.example_correct}"
        return self.example_correct or self.example_learner

    def as_candidate(self) -> LearningCandidate:
        """The planner's view of this erratum.

        ``is_new`` is False: an erratum is by definition something the learner
        has already met. ``metadata`` carries the reason so the planner can
        stamp it on whatever step the target ends up in.
        """

        return LearningCandidate(
            target=TargetRef(
                kind=TargetKind.ERROR,
                id=self.error_id,
                label_fr=self.label,
                label_native=self.why,
            ),
            priority_score=self.priority,
            due_since_days=self.overdue_days,
            estimated_seconds=45,
            is_new=False,
            relevance=min(1.0, 0.5 + self.priority / 20.0),
            source_item_type="user_error",
            metadata={
                "target_reason": self.reason,
                "erratum_id": self.error_id,
                "erratum_state": self.state,
                "erratum_label": self.label,
                "erratum_example": self.example,
                "erratum_why": self.why,
                "concept_id": self.concept_id,
                "memory_key": self.memory_key,
            },
        )

    def as_because(self) -> dict[str, Any]:
        """What Home needs to say the scene exists because of a past mistake.

        Structured, never a rendered sentence: the French copy lives in the
        component that prints it, next to the rest of the learner-facing copy.
        """

        return {
            "kind": REASON_PREFIX,
            "reason": self.reason,
            "label": self.label,
            "example": self.example,
        }


def _overdue_days(error: UserError, now: datetime) -> int:
    due = error.next_review_date
    if due is None:
        return 0
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return max(0, (now.astimezone(UTC) - due.astimezone(UTC)).days)


def _priority(*, state: str, occurrences: int, lapses: int, overdue_days: int, severity: int) -> float:
    """A small, explainable score. Every term is bounded so none can dominate."""

    return round(
        4.0 * _STATE_WEIGHT.get(state, 0.4)
        + 1.5 * min(lapses, 6)
        + 1.0 * min(max(occurrences - 1, 0), 6)
        + 0.5 * min(overdue_days, 14)
        + 0.5 * max(0, min(severity, 4)),
        4,
    )


def build_errata_target(error: UserError, *, now: datetime | None = None) -> ErrataTarget | None:
    """One stored mistake as a ranked target, or None if it must not be one."""

    state = normalize_error_state(error.state)
    if state == ERROR_STATE_MASTERED:
        return None
    payload = serialize_error_memory(error)
    label = str(payload.get("display_label") or "").strip()
    if not label:
        return None
    now = now or datetime.now(UTC)
    metadata = error.error_metadata or {}
    severity = int(metadata.get("severity") or 2) if isinstance(metadata, dict) else 2
    overdue = _overdue_days(error, now)
    occurrences = int(error.occurrences or 1)
    lapses = int(error.lapses or 0)
    return ErrataTarget(
        error_id=str(error.id),
        memory_key=error.memory_key,
        concept_id=error.concept_id,
        example_learner=error.original_text,
        example_correct=error.correction,
        why=error.why_wrong or error.context_snippet,
        label=label,
        review_mode=str(error.review_mode or "grammar"),
        state=state,
        occurrences=occurrences,
        lapses=lapses,
        overdue_days=overdue,
        priority=_priority(
            state=state,
            occurrences=occurrences,
            lapses=lapses,
            overdue_days=overdue,
            severity=severity,
        ),
        payload=payload,
    )


def rank_errata_targets(
    errors: list[UserError], *, limit: int = DEFAULT_TARGET_LIMIT, now: datetime | None = None
) -> list[ErrataTarget]:
    """Rank stored mistakes, best first, one per concept-or-memory key.

    Deduplication is by concept where a concept is known and by memory key
    otherwise: three gender slips on three different nouns are one lesson, and
    filling the day with all three would crowd out everything else.
    """

    now = now or datetime.now(UTC)
    built = [target for target in (build_errata_target(error, now=now) for error in errors) if target]
    built.sort(key=lambda target: (-target.priority, -target.overdue_days, target.error_id))
    seen: set[str] = set()
    ranked: list[ErrataTarget] = []
    for target in built:
        group = (
            f"concept:{target.concept_id}"
            if target.concept_id
            else f"key:{target.memory_key or target.error_id}"
        )
        if group in seen:
            continue
        seen.add(group)
        ranked.append(target)
        if len(ranked) >= max(1, limit):
            break
    return ranked


def errata_targets_for_user(
    db: Session,
    user: User,
    *,
    limit: int = DEFAULT_TARGET_LIMIT,
    now: datetime | None = None,
) -> list[ErrataTarget]:
    """The learner's ranked errata targets. Reads the queue; changes nothing."""

    records = ErrorMemoryService(db).due_error_records(user, limit=max(limit * 6, 12))
    return rank_errata_targets(records, limit=limit, now=now)


def errata_candidates_for_user(
    db: Session,
    user: User,
    *,
    limit: int = DEFAULT_TARGET_LIMIT,
    now: datetime | None = None,
) -> list[LearningCandidate]:
    """The same targets as planner candidates, for a caller that only wants those."""

    return [target.as_candidate() for target in errata_targets_for_user(db, user, limit=limit, now=now)]


__all__ = [
    "DEFAULT_TARGET_LIMIT",
    "REASON_PREFIX",
    "ErrataTarget",
    "build_errata_target",
    "errata_candidates_for_user",
    "errata_targets_for_user",
    "parse_reason",
    "rank_errata_targets",
    "reason_for",
]
