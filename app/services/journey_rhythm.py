"""WP-L6 — the learner's rhythm: how many minutes the day is.

The rhythm is stored in ``users.daily_goal_minutes`` (5 / 10 / 20 / 30), the
column the legacy Atelier already reads its budget from, so there is one
number for «how long is my practice» and not two that drift apart
(WORK-PACKAGES-2026-09-23-learning §2.2: «``daily_goal_minutes`` becomes the
rhythm»). A stored value that predates the rhythm (the old presets 15 / 60, or
anything typed into the free field) is read through :func:`rhythm_for_minutes`
and is never rewritten behind the learner's back.

Pure: no database, no I/O.
"""
from __future__ import annotations

from typing import Literal

from app.services.journey_contracts import RHYTHM_BUDGETS, rhythm_caps

Rhythm = Literal["leger", "regulier", "soutenu", "intensif"]
RHYTHMS: tuple[Rhythm, ...] = ("leger", "regulier", "soutenu", "intensif")
DEFAULT_RHYTHM: Rhythm = "regulier"

RHYTHM_MINUTES: dict[Rhythm, int] = {
    "leger": 5,
    "regulier": 10,
    "soutenu": 20,
    "intensif": 30,
}
RHYTHM_BUDGET_SECONDS: dict[Rhythm, int] = dict(zip(RHYTHMS, RHYTHM_BUDGETS, strict=True))
DEFAULT_RHYTHM_MINUTES = RHYTHM_MINUTES[DEFAULT_RHYTHM]


def rhythm_for_minutes(minutes: int | None) -> Rhythm:
    """Map a stored ``daily_goal_minutes`` onto a rhythm.

    ≤ 7 Léger, ≤ 14 Régulier, ≤ 25 Soutenu, else Intensif. Nothing stored
    (a row older than the column's default) is the default rhythm.
    """

    if minutes is None:
        return DEFAULT_RHYTHM
    value = int(minutes)
    if value <= 0:
        return DEFAULT_RHYTHM
    if value <= 7:
        return "leger"
    if value <= 14:
        return "regulier"
    if value <= 25:
        return "soutenu"
    return "intensif"


def rhythm_of(user: object) -> Rhythm:
    return rhythm_for_minutes(getattr(user, "daily_goal_minutes", None))


def budget_seconds_for(user: object) -> int:
    """Today's journey budget for this learner: their rhythm's minutes."""

    return RHYTHM_BUDGET_SECONDS[rhythm_of(user)]


def rhythm_for_budget(budget_seconds: int | None) -> Rhythm:
    caps = rhythm_caps(budget_seconds)
    for rhythm, seconds in RHYTHM_BUDGET_SECONDS.items():
        if seconds == caps.budget_seconds:
            return rhythm
    return DEFAULT_RHYTHM  # pragma: no cover - every caps row is a rhythm


def candidate_limit_for(budget_seconds: int | None) -> int:
    """How many candidates a practice day at this budget asks for."""

    return rhythm_caps(budget_seconds).candidate_limit


__all__ = [
    "DEFAULT_RHYTHM",
    "DEFAULT_RHYTHM_MINUTES",
    "RHYTHMS",
    "RHYTHM_BUDGET_SECONDS",
    "RHYTHM_MINUTES",
    "Rhythm",
    "budget_seconds_for",
    "candidate_limit_for",
    "rhythm_for_budget",
    "rhythm_for_minutes",
    "rhythm_of",
]
