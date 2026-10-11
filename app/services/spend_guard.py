"""WP-70 — a ceiling on what one learner can cost in a day.

The only guardrail before this was weekly, read by the prefetch beat alone
(``journey_latency._weekly_spend_usd``): a script with a valid token could call
the paid endpoints all day. This module sums what the learner has already cost
*today* and refuses the next paid request, before the provider is called, once
that reaches ``USER_DAILY_SPEND_CAP_USD`` (default US$0.50).

A normal Séance costs about US$0.05 (WP-68 evidence), so the default sits an
order of magnitude above a real learner's day and only stops a loop.

**The ledgers.** Every priced call in the app lands on ``PilotEvent.cost_usd``
(transcription, speech, corrections, journal, intake, placement, rehearsal,
story engine…). Feuilleton generation is also carried on
``GraphicNovelScene.script_payload.estimated_cost``, and the story engine
writes *both* for the same money (``journey_story_scene_cost`` /
``journey_story_turn_cost`` rows mirror the scene's own estimate). So the day's
spend is::

    other event rows + max(scene-attributed event rows, today's scene estimates)

— the same de-duplication rule as ``PilotEventService.daily_rollup``, taken as
a max so neither ledger can hide the other.

**The day** is the learner's own calendar day (``User.timezone``, WP-80),
the same day their streak counts, so a cap reset can never land in the middle
of a local evening. ``Retry-After`` counts to the learner's next midnight.

**WP-88 — a started day is never cut off.** Creating a day checks the cap as
before; the routes that finish a day already started (attempts, help, retry,
the scene's audio) are refused only past ``cap × USER_DAILY_SPEND_OPEN_DAY_MULTIPLIER``,
a ceiling that still stops a loop. Panel art is not counted here at all: it has
its own per-day allowance (:func:`art_spend_today_usd`), and above it a panel
keeps its location plate instead of refusing anything.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent

DAILY_BUDGET_REACHED_CODE = "daily_budget_reached"

#: Kept in step with ``pilot_events._SCENE_ATTRIBUTED_COST_EVENT_TYPES``.
SCENE_ATTRIBUTED_EVENT_TYPES = frozenset({"journey_story_scene_cost", "journey_story_turn_cost"})

#: WP-88. Drawn panels: priced per panel, budgeted apart from the text cap.
PANEL_ART_EVENT_TYPE = "journey_panel_art_cost"
ART_EVENT_TYPES = frozenset({PANEL_ART_EVENT_TYPE})


def daily_cap_usd() -> float:
    value = getattr(settings, "USER_DAILY_SPEND_CAP_USD", None)
    return 0.50 if value is None else max(0.0, float(value))


def open_day_ceiling_usd() -> float:
    """Where a day already started is finally refused (WP-88)."""

    multiplier = getattr(settings, "USER_DAILY_SPEND_OPEN_DAY_MULTIPLIER", None)
    return daily_cap_usd() * max(1.0, float(2.0 if multiplier is None else multiplier))


def learner_zone(user: Any = None) -> ZoneInfo:
    """The learner's stored zone, or UTC when there is none or it is unknown."""

    name = str(getattr(user, "timezone", None) or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            pass
    return ZoneInfo("UTC")


def day_bounds(now: datetime | None = None, zone: ZoneInfo | None = None) -> tuple[datetime, datetime]:
    """The learner-local calendar day around ``now``, as UTC instants."""

    zone = zone or ZoneInfo("UTC")
    local = (now or datetime.now(UTC)).astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    end = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def seconds_until_reset(now: datetime | None = None, zone: ZoneInfo | None = None) -> int:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    _start, end = day_bounds(moment, zone)
    return max(1, int((end - moment).total_seconds()))


def art_spend_today_usd(
    db: Session, user_id: Any, *, now: datetime | None = None, zone: ZoneInfo | None = None
) -> float:
    """What today's drawn panels have cost this learner (WP-88's separate allowance)."""

    start, end = day_bounds(now, zone)
    total = db.scalar(
        select(func.coalesce(func.sum(PilotEvent.cost_usd), 0.0)).where(
            PilotEvent.user_id == user_id,
            PilotEvent.event_type.in_(ART_EVENT_TYPES),
            PilotEvent.occurred_at >= start,
            PilotEvent.occurred_at < end,
        )
    )
    return round(float(total or 0.0), 6)


_EVERYONE = object()


def spend_today_usd(
    db: Session, user_id: Any, *, now: datetime | None = None, zone: ZoneInfo | None = None
) -> float:
    """What this learner has cost since their local midnight, across both text ledgers.

    ``user_id=_EVERYONE`` (see :func:`service_spend_today_usd`) sums every learner.
    """

    start, end = day_bounds(now, zone)
    everyone = user_id is _EVERYONE
    event_filters = [
        PilotEvent.occurred_at >= start,
        PilotEvent.occurred_at < end,
        PilotEvent.cost_usd > 0,
        PilotEvent.event_type.not_in(ART_EVENT_TYPES),
    ]
    if not everyone:
        event_filters.append(PilotEvent.user_id == user_id)
    rows = db.execute(
        select(PilotEvent.event_type, func.coalesce(func.sum(PilotEvent.cost_usd), 0.0))
        .where(*event_filters)
        .group_by(PilotEvent.event_type)
    ).all()
    scene_attributed = 0.0
    other = 0.0
    for event_type, amount in rows:
        if event_type in SCENE_ATTRIBUTED_EVENT_TYPES:
            scene_attributed += float(amount or 0.0)
        else:
            other += float(amount or 0.0)

    scenes_total = 0.0
    scene_filters = [GraphicNovelScene.created_at >= start, GraphicNovelScene.created_at < end]
    if not everyone:
        scene_filters.append(GraphicNovelScene.user_id == user_id)
    payloads = db.execute(select(GraphicNovelScene.script_payload).where(*scene_filters)).scalars()
    for payload in payloads:
        cost = payload.get("estimated_cost") if isinstance(payload, dict) else None
        if isinstance(cost, dict):
            try:
                total = cost.get("total_estimated_usd")
                if total is None:
                    total = float(cost.get("story_generation_usd") or 0.0) + float(
                        cost.get("image_generation_usd") or 0.0
                    )
                scenes_total += float(total or 0.0)
            except (TypeError, ValueError):
                continue

    return round(other + max(scene_attributed, scenes_total), 6)


def service_daily_cap_usd() -> float:
    value = getattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", None)
    return 0.0 if value is None else max(0.0, float(value))


def service_spend_today_usd(db: Session, *, now: datetime | None = None) -> float:
    """WP-138: what every learner together has cost since UTC midnight, art included.

    Scene estimates are de-duplicated against the scene-attributed rows across
    the whole service, which can only under- or exactly count the per-learner
    sums; it is a ceiling on the bill, not an invoice.
    """

    text = spend_today_usd(db, _EVERYONE, now=now)
    start, end = day_bounds(now)
    art = db.scalar(
        select(func.coalesce(func.sum(PilotEvent.cost_usd), 0.0)).where(
            PilotEvent.event_type.in_(ART_EVENT_TYPES),
            PilotEvent.occurred_at >= start,
            PilotEvent.occurred_at < end,
        )
    )
    return round(text + float(art or 0.0), 6)


def service_budget_reached(db: Session, *, now: datetime | None = None) -> bool:
    """True once the service-wide cap is met. A failed read never stops anyone."""

    cap = service_daily_cap_usd()
    if cap <= 0:
        return False
    try:
        return service_spend_today_usd(db, now=now) >= cap
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Service spend check skipped: {}", exc)
        return False


def enforce_daily_budget(
    db: Session, user: Any, *, now: datetime | None = None, open_day: bool = False
) -> None:
    """Raise ``429 daily_budget_reached`` once today's spend meets the cap.

    ``open_day`` marks a route that finishes a day already started (WP-88): it
    is held to :func:`open_day_ceiling_usd` instead, so a learner who began
    their day under the cap always gets to finish it.

    A cap of 0 switches the check off. A ledger read that fails must not cost
    the learner their request, so it is logged and the call proceeds.
    """

    if service_budget_reached(db, now=now):
        logger.error("Service-wide daily spend cap reached: paid routes refused until UTC midnight")
        from app.core.rate_limit import too_many_requests

        raise too_many_requests(
            DAILY_BUDGET_REACHED_CODE,
            "That is everything for today. Your practice continues tomorrow.",
            seconds_until_reset(now),
        )
    cap = daily_cap_usd()
    user_id = getattr(user, "id", None)
    if cap <= 0 or user_id is None:
        return
    limit = open_day_ceiling_usd() if open_day else cap
    zone = learner_zone(user)
    try:
        spent = spend_today_usd(db, user_id, now=now, zone=zone)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Daily spend check skipped: {}", exc)
        return
    if spent < limit:
        return
    logger.warning(
        "Daily spend {} reached for learner {}: ${:.4f} >= ${:.2f}",
        "ceiling" if open_day else "cap", user_id, spent, limit,
    )
    from app.core.rate_limit import too_many_requests

    raise too_many_requests(
        DAILY_BUDGET_REACHED_CODE,
        "That is everything for today. Your practice continues tomorrow.",
        seconds_until_reset(now, zone),
    )


__all__ = [
    "ART_EVENT_TYPES",
    "DAILY_BUDGET_REACHED_CODE",
    "PANEL_ART_EVENT_TYPE",
    "SCENE_ATTRIBUTED_EVENT_TYPES",
    "art_spend_today_usd",
    "daily_cap_usd",
    "day_bounds",
    "enforce_daily_budget",
    "learner_zone",
    "open_day_ceiling_usd",
    "seconds_until_reset",
    "service_budget_reached",
    "service_daily_cap_usd",
    "service_spend_today_usd",
    "spend_today_usd",
]
