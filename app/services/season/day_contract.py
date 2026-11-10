"""The day contract at run time (red-thread design, 2026-11-10), behind
``STORY_DAY_CONTRACT`` (off by default).

Production printed a random loose end as «À suivre…» on every generated day (0 of
9 walked days showed the planned hook) and no surface said where the week was going.
With the flag on, a planned day that carries a contract (``gaps.json`` →
``days[].contract``) ends on its own hook, and the gap's destination and the days
left to it are read from the season, by code. Nothing here calls a model, and every
failure leaves the day as it was without the flag.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.season.format import TEXT_SPEAKERS, DayBeat, Gap, Season

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(getattr(settings, "STORY_DAY_CONTRACT", False))


def beat_for(season: Season, gap_id: str | None, premise: str | None) -> tuple[Gap, DayBeat] | None:
    """The planned day of ``gap_id`` that stages ``premise``, when it has a contract."""

    gap = season.gaps.get(str(gap_id or ""))
    if gap is None or not premise:
        return None
    beat = next((row for row in gap.days if row.premise == premise and row.contract), None)
    return (gap, beat) if beat else None


def staged_beat(season: Season, season_ctx: dict[str, Any]) -> tuple[Gap, DayBeat] | None:
    """The contract of the day a served page staged: the premise its checklist names,
    which is the one the plan asked for (a page about something else has none)."""

    if season_ctx.get("kind") == "tentpole" or season_ctx.get("bridge"):
        return None
    position = season_ctx.get("position") or {}
    premise = (season_ctx.get("checklist") or {}).get("premise_id")
    owed = season_ctx.get("required_premise")
    if owed and premise != owed:
        return None
    return beat_for(season, position.get("segment"), premise)


def hook_teaser(
    season: Season, season_ctx: dict[str, Any], *, band: str | None, date: str | None
) -> dict[str, Any] | None:
    """Tomorrow's line on a contract day: the plan's own hook, in its speaker's mouth.

    None on the gap's last planned day (the tentpole's own teaser stands), on a day
    without a contract, and with the flag off: the caller then keeps its old line.
    """

    if not enabled():
        return None
    try:
        found = staged_beat(season, season_ctx)
        if found is None:
            return None
        gap, beat = found
        hook = beat.contract.hook
        if hook.about in season.tentpoles:
            return None
        text = hook.fr.text(str(band or "A2")).strip()
        if not text:
            return None
        return {
            "text_fr": text,
            "character_id": None if hook.speaker in TEXT_SPEAKERS else hook.speaker,
            "date": date,
            "ref": f"contract:{gap.id}.{beat.premise}",
            "kind": "season",
        }
    except Exception:  # noqa: BLE001 - a teaser never costs the day's ending
        logger.exception("day_contract: the planned hook is unavailable; the old teaser stands")
        return None


def arc(season: Season, pos: Any) -> dict[str, Any] | None:
    """Where the gap is going and how far it is: ``{gap_title_fr, title_fr, when_fr,
    days_left}``. ``days_left`` counts the days until the tentpole's first day (on day
    5 of 7, Saturday's party is 3 days away)."""

    if not enabled() or not getattr(pos, "is_gap", False) or pos.segment is None:
        return None
    gap = season.gaps.get(pos.segment.id)
    if gap is None or gap.destination is None:
        return None
    left = pos.segment.days - int(pos.day_in_segment or 0) + 1
    if left < 1:
        return None
    return {
        "gap_title_fr": gap.title_fr,
        "title_fr": gap.destination.title_fr,
        "when_fr": gap.destination.when_fr,
        "days_left": left,
    }
