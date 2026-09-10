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

from datetime import UTC, datetime, timedelta

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
