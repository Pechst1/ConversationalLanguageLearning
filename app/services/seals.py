"""The day's seal (WP-D4/D5): its edition number and its composition.

The edition is the day's issue number — the number Home prints as «Édition
Nº N». It is decided **once**, when the day is planned (:func:`assign_edition_no`),
and stored in the plan (``plan_selection["edition_no"]``); Home, the reader, the
recap, the Feuilleton archive and the seal collection all read that one number.

Why one decision: the number used to be recomputed on every read from two
unrelated sequences — ``episode_index + 1`` for a day that played a serial
episode, the count of the learner's days for a day without one (the authored
first day, a re-read). The two drift apart as soon as one day binds no episode,
so a re-read day printed the same Nº as the day before it, and Home (which
announced the next episode before the day existed) printed another. Issues are
now a strictly increasing sequence: a day's number is its own base (episode
index + 1, else its place among the learner's days), raised above the last
earlier day's number when that base would not move on. A plan stored before the
number was kept still reads through the old rule. The composition cycles over
:data:`SEAL_CYCLE` by edition, in the same order as ``sealForEdition`` in
``web-frontend/components/ui/Seal.tsx`` (a test holds the two together), so a
given edition always presses the same seal on the recap, Home and the
collection.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialEpisode

SEAL_CYCLE: tuple[str, ...] = ("row", "stack", "nested", "quad", "orbit", "frieze")


def seal_variant_for(edition_no: int | None) -> str | None:
    if edition_no is None:
        return None
    return SEAL_CYCLE[int(edition_no) % len(SEAL_CYCLE)]


#: ``plan_selection[EDITION_KEY]``: the day's issue number, written when it is planned.
EDITION_KEY = "edition_no"


def stored_edition_no(journey: DailyJourney) -> int | None:
    """The issue number the day's plan carries, or ``None`` for a plan that predates it."""

    selection = journey.plan_selection if isinstance(journey.plan_selection, dict) else {}
    value = selection.get(EDITION_KEY)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _episode_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def edition_numbers(db: Session, journeys: Iterable[DailyJourney]) -> dict[Any, int]:
    """``{journey.id: edition_no}`` for the given journeys, in two reads."""

    journeys = list(journeys)
    if not journeys:
        return {}
    episode_ids = {
        parsed
        for journey in journeys
        if stored_edition_no(journey) is None
        and (parsed := _episode_uuid(journey.serial_episode_id)) is not None
    }
    indexes: dict[uuid.UUID, int] = {}
    if episode_ids:
        rows = db.execute(
            select(SerialEpisode.id, SerialEpisode.episode_index).where(
                SerialEpisode.id.in_(episode_ids)
            )
        ).all()
        indexes = {row[0]: int(row[1]) for row in rows}

    out: dict[Any, int] = {}
    for journey in journeys:
        stored = stored_edition_no(journey)
        if stored is not None:
            out[journey.id] = stored
            continue
        episode = _episode_uuid(journey.serial_episode_id)
        if episode is not None and episode in indexes:
            out[journey.id] = indexes[episode] + 1
            continue
        ordinal = db.execute(
            select(func.count(DailyJourney.id)).where(
                DailyJourney.user_id == journey.user_id,
                DailyJourney.local_date <= journey.local_date,
            )
        ).scalar_one()
        out[journey.id] = max(1, int(ordinal or 0))
    return out


def next_edition_no(db: Session, user_id: Any, local_date: Any, *, base: int | None = None) -> int:
    """The issue number a day of this learner would carry on ``local_date``.

    ``base`` is the day's own number (the serial episode's ``episode_index + 1``);
    without one it is the day's place among the learner's days. It is raised above
    the number of the last earlier day, so issues only ever move forward and two
    days never share one. Home calls this before the day is planned and
    :func:`assign_edition_no` after: the same rule, so they cannot disagree.
    """

    if base is None:
        earlier_days = db.execute(
            select(func.count(DailyJourney.id)).where(
                DailyJourney.user_id == user_id, DailyJourney.local_date < local_date
            )
        ).scalar_one()
        base = int(earlier_days or 0) + 1
    last = db.scalars(
        select(DailyJourney)
        .where(DailyJourney.user_id == user_id, DailyJourney.local_date < local_date)
        .order_by(DailyJourney.local_date.desc())
        .limit(1)
    ).first()
    if last is None:
        return max(1, int(base))
    previous = edition_numbers(db, [last]).get(last.id) or 0
    return max(1, int(base), int(previous) + 1)


def assign_edition_no(db: Session, journey: DailyJourney, serial_episode_id: Any = None) -> int:
    """Decide the day's issue number (once, at planning) and return it."""

    base: int | None = None
    episode_id = _episode_uuid(serial_episode_id)
    if episode_id is not None:
        index = db.execute(
            select(SerialEpisode.episode_index).where(SerialEpisode.id == episode_id)
        ).scalar_one_or_none()
        if index is not None:
            base = int(index) + 1
    return next_edition_no(db, journey.user_id, journey.local_date, base=base)


def edition_no_for(db: Session, journey: DailyJourney) -> int | None:
    try:
        return edition_numbers(db, [journey]).get(journey.id)
    except Exception:  # pragma: no cover - defensive: never costs the day
        return None


def mastery_today_for(db: Session, journey: DailyJourney) -> dict[str, list[int]] | None:
    """WP-S7: the rules that became held on the journey's local day.

    The Seal gains a ring for each (``held_concept_ids``); the ones a passed
    test-out held are listed apart (``tested_out_concept_ids``). ``None`` when
    the owner switched the mastery rewards off.
    """

    from datetime import UTC, datetime, time, timedelta
    from zoneinfo import ZoneInfo

    from app.config import settings
    from app.db.models.grammar import UserGrammarProgress

    if not getattr(settings, "ATELIER_MASTERY_REWARDS_ENABLED", True):
        return None
    try:
        day = journey.local_date
        if isinstance(day, str):
            from datetime import date as _date

            day = _date.fromisoformat(day)
        try:
            zone = ZoneInfo(str(journey.timezone or "UTC"))
        except Exception:
            zone = ZoneInfo("UTC")
        start = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
        end = start + timedelta(days=1)
        rows = (
            db.query(UserGrammarProgress.concept_id, UserGrammarProgress.held_at, UserGrammarProgress.tested_out_at)
            .filter(UserGrammarProgress.user_id == journey.user_id, UserGrammarProgress.held_at.isnot(None))
            .all()
        )
    except Exception:  # pragma: no cover - defensive: never costs the day
        return None

    def _aware(value: Any) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    held: list[int] = []
    tested: list[int] = []
    for concept_id, held_at, tested_out_at in rows:
        stamp = _aware(held_at)
        if stamp is None or not (start <= stamp < end):
            continue
        held.append(int(concept_id))
        tested_at = _aware(tested_out_at)
        if tested_at is not None and start <= tested_at < end:
            tested.append(int(concept_id))
    return {"held_concept_ids": sorted(held), "tested_out_concept_ids": sorted(tested)}


__all__ = [
    "EDITION_KEY",
    "SEAL_CYCLE",
    "assign_edition_no",
    "edition_no_for",
    "edition_numbers",
    "mastery_today_for",
    "next_edition_no",
    "seal_variant_for",
    "stored_edition_no",
]
