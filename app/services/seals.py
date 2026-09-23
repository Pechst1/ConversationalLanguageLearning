"""The day's seal (WP-D4/D5): its edition number and its composition.

The edition is the serial episode the day played, ``episode_index + 1`` — the
number Home prints as «Édition Nº N». A day with no serial episode (the
authored first day) is numbered by its place among the learner's own days, so
every finished day has one. The composition cycles over
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
        if (parsed := _episode_uuid(journey.serial_episode_id)) is not None
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


def edition_no_for(db: Session, journey: DailyJourney) -> int | None:
    try:
        return edition_numbers(db, [journey]).get(journey.id)
    except Exception:  # pragma: no cover - defensive: never costs the day
        return None


__all__ = ["SEAL_CYCLE", "edition_no_for", "edition_numbers", "seal_variant_for"]
