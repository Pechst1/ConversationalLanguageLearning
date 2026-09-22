"""WP-26 — the ahead-of-time scene prefetch beat.

One bounded pass per run: pick the active pilot learners who have no open day
and no valid cached scene, generate one scene each, and stop at the configured
learner bound. Everything expensive is refused before it is paid for — the flag,
the cohort, an already-open journey, an already-valid cache entry, and the
weekly cost guardrail are all checked in :func:`prefetch_scene_for`, so this
module stays a scheduler and nothing more.

Idempotency is the cache key's job, not a lock's: a second run within the same
story revision and prompt version finds a live entry and returns ``cached``.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.journey_contracts import InputMode
from app.services.journey_latency import (
    prefetch_enabled_for,
    prefetch_scene_for,
    sweep_expired_prefetches,
)

#: Learners are "active" if the ledger saw a journey event from them recently.
#: Reading the existing event stream keeps this task free of its own state.
_ACTIVITY_EVENT_PREFIX = "journey_"


def _active_learner_ids(db, *, days: int, limit: int) -> list[str]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = db.execute(
        select(PilotEvent.user_id, PilotEvent.occurred_at)
        .where(
            PilotEvent.occurred_at >= since,
            PilotEvent.user_id.is_not(None),
            PilotEvent.event_type.like(f"{_ACTIVITY_EVENT_PREFIX}%"),
        )
        .order_by(PilotEvent.occurred_at.desc())
        .limit(2000)
    ).all()
    seen: list[str] = []
    known: set[str] = set()
    for user_id, _ in rows:
        key = str(user_id)
        if key in known:
            continue
        known.add(key)
        seen.append(key)
        if len(seen) >= limit:
            break
    return seen


@celery_app.task(name="app.tasks.journey_prefetch.prefetch_next_journey_scenes")
def prefetch_next_journey_scenes() -> dict[str, int | str]:
    """Generate tomorrow's opening scene for the active pilot cohort."""

    if not settings.ATELIER_JOURNEY_PREFETCH_ENABLED:
        return {"status": "disabled"}

    bound = int(settings.ATELIER_JOURNEY_PREFETCH_MAX_LEARNERS)
    if bound <= 0:
        return {"status": "bounded_to_zero"}

    counts: dict[str, int] = {}
    db = SessionLocal()
    try:
        expired = sweep_expired_prefetches(db)
        candidate_ids = _active_learner_ids(
            db,
            days=int(settings.ATELIER_JOURNEY_PREFETCH_ACTIVE_DAYS),
            # Read more candidates than the budget: most of them will be
            # refused cheaply (open journey, already cached), and the bound
            # below is on *paid* work, not on rows examined.
            limit=bound * 4,
        )
        paid = 0
        for user_id in candidate_ids:
            if paid >= bound:
                counts["stopped_at_bound"] = counts.get("stopped_at_bound", 0) + 1
                break
            user = db.get(User, user_id)
            if user is None or not prefetch_enabled_for(user):
                counts["skipped_cohort"] = counts.get("skipped_cohort", 0) + 1
                continue
            try:
                status = prefetch_scene_for(db, user, input_mode=InputMode.TEXT)
            except Exception as exc:  # pragma: no cover - one learner never fails the beat
                logger.warning(
                    "Journey scene prefetch failed", user_id=str(user_id), error=str(exc)
                )
                db.rollback()
                status = "error"
            counts[status] = counts.get(status, 0) + 1
            if status == "prefetched":
                paid += 1
        return {
            "status": "ok",
            "expired_closed": expired,
            "candidates": len(candidate_ids),
            **counts,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# WP-75 — warm day 2 for a learner who just finished day 1
# ---------------------------------------------------------------------------

#: How long after the learner's local midnight the warm-up runs: past the day
#: boundary, so the prefetch's own "today already has a journey" guard lets it
#: through, and long before anyone opens the app in the morning.
WARMUP_AFTER_MIDNIGHT = timedelta(minutes=10)


def _next_midnight(now: datetime, zone: ZoneInfo) -> datetime:
    local = now.astimezone(zone)
    tomorrow = local.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, tzinfo=zone).astimezone(UTC)


def next_day_warmup_eta(timezone_name: str | None, *, now: datetime | None = None) -> datetime:
    """When day 2 may be prefetched: after the learner's next local midnight.

    The later of the journey's own midnight and UTC's, because the prefetch
    decides "today" in the timezone it can read for the learner (UTC when the
    account stores none) and must not find day 1 still sitting on it.
    """

    moment = now or datetime.now(UTC)
    try:
        zone = ZoneInfo(str(timezone_name or "UTC"))
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    boundary = max(_next_midnight(moment, zone), _next_midnight(moment, ZoneInfo("UTC")))
    return boundary + WARMUP_AFTER_MIDNIGHT


@celery_app.task(name="app.tasks.journey_prefetch.warm_learner_next_day")
def warm_learner_next_day(user_id: str, input_mode: str = "text") -> dict[str, str]:
    """Prefetch one learner's next scene. Every guard is ``prefetch_scene_for``'s."""

    if not settings.ATELIER_JOURNEY_PREFETCH_ENABLED:
        return {"status": "disabled"}
    try:
        mode = InputMode(str(input_mode))
    except ValueError:
        mode = InputMode.TEXT
    db = SessionLocal()
    try:
        user = db.get(User, uuid.UUID(str(user_id)))
        if user is None or not prefetch_enabled_for(user):
            return {"status": "skipped_cohort"}
        return {"status": prefetch_scene_for(db, user, input_mode=mode)}
    except Exception as exc:  # pragma: no cover - a warm-up never raises
        logger.warning("Day-2 warm-up failed", user_id=str(user_id), error=str(exc))
        db.rollback()
        return {"status": "error"}
    finally:
        db.close()


def schedule_next_day_warmup(
    user: User,
    *,
    timezone_name: str | None,
    input_mode: InputMode = InputMode.TEXT,
    now: datetime | None = None,
) -> datetime | None:
    """Queue the day-2 warm-up. Returns its ETA, or ``None`` when nothing was queued.

    Refused up front for anyone the prefetch would refuse (flag, engine,
    cohort), so a learner outside the pilot never costs a broker round trip,
    let alone a scene. A broker that is down costs the warm start only.
    """

    if not prefetch_enabled_for(user):
        return None
    eta = next_day_warmup_eta(timezone_name, now=now)
    try:
        warm_learner_next_day.apply_async(
            args=[str(user.id), str(input_mode)], eta=eta
        )
    except Exception as exc:  # pragma: no cover - broker-less dev/test fallback
        logger.info("Day-2 warm-up not queued", user_id=str(user.id), error=str(exc))
        return None
    return eta
