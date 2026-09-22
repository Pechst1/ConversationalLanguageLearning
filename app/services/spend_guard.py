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

**The day** is the UTC calendar day. Learners carry no stored time zone yet
(``daily_journey.resolve_timezone`` falls back to UTC for everyone), so a
learner-local day would be UTC anyway; ``Retry-After`` counts to the next UTC
midnight.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent

DAILY_BUDGET_REACHED_CODE = "daily_budget_reached"

#: Kept in step with ``pilot_events._SCENE_ATTRIBUTED_COST_EVENT_TYPES``.
SCENE_ATTRIBUTED_EVENT_TYPES = frozenset({"journey_story_scene_cost", "journey_story_turn_cost"})


def daily_cap_usd() -> float:
    value = getattr(settings, "USER_DAILY_SPEND_CAP_USD", None)
    return 0.50 if value is None else max(0.0, float(value))


def day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    start = datetime.combine(moment.date(), time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def seconds_until_reset(now: datetime | None = None) -> int:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    _start, end = day_bounds(moment)
    return max(1, int((end - moment).total_seconds()))


def spend_today_usd(db: Session, user_id: Any, *, now: datetime | None = None) -> float:
    """What this learner has cost since UTC midnight, across both ledgers."""

    start, end = day_bounds(now)
    rows = db.execute(
        select(PilotEvent.event_type, func.coalesce(func.sum(PilotEvent.cost_usd), 0.0))
        .where(
            PilotEvent.user_id == user_id,
            PilotEvent.occurred_at >= start,
            PilotEvent.occurred_at < end,
            PilotEvent.cost_usd > 0,
        )
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
    payloads = db.execute(
        select(GraphicNovelScene.script_payload).where(
            GraphicNovelScene.user_id == user_id,
            GraphicNovelScene.created_at >= start,
            GraphicNovelScene.created_at < end,
        )
    ).scalars()
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


def enforce_daily_budget(db: Session, user: Any, *, now: datetime | None = None) -> None:
    """Raise ``429 daily_budget_reached`` once today's spend meets the cap.

    A cap of 0 switches the check off. A ledger read that fails must not cost
    the learner their request, so it is logged and the call proceeds.
    """

    cap = daily_cap_usd()
    user_id = getattr(user, "id", None)
    if cap <= 0 or user_id is None:
        return
    try:
        spent = spend_today_usd(db, user_id, now=now)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Daily spend check skipped: {}", exc)
        return
    if spent < cap:
        return
    logger.warning("Daily spend cap reached for learner {}: ${:.4f} >= ${:.2f}", user_id, spent, cap)
    from app.core.rate_limit import too_many_requests

    raise too_many_requests(
        DAILY_BUDGET_REACHED_CODE,
        "That is everything for today. Your practice continues tomorrow.",
        seconds_until_reset(now),
    )


__all__ = [
    "DAILY_BUDGET_REACHED_CODE",
    "SCENE_ATTRIBUTED_EVENT_TYPES",
    "daily_cap_usd",
    "day_bounds",
    "enforce_daily_budget",
    "seconds_until_reset",
    "spend_today_usd",
]
