"""S5 · the season rollover's beat: the promised date starts the next season.

Each open rollover (``app.services.season_rollover``) is advanced in its own short
transaction, at the learner's own date. No request waits on this, and nothing here
calls a model.
"""
from __future__ import annotations

from loguru import logger

from app.celery_app import celery_app
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import season_rollover


def _learner_today(db, thread_id):
    from app.services.daily_journey import local_date_for, resolve_timezone

    thread = db.get(SerialThread, thread_id)
    user = db.get(User, thread.user_id) if thread is not None else None
    return local_date_for(resolve_timezone(getattr(user, "timezone", None)))


def advance_all(db) -> dict[str, int]:
    """Advance every open rollover once. Returns a count per outcome."""

    counts: dict[str, int] = {}
    for thread_id in season_rollover.open_rollovers(db):
        try:
            outcome = season_rollover.advance(db, thread_id, today=_learner_today(db, thread_id))
        except Exception:  # pragma: no cover - one life never stops the sweep
            logger.exception("season_rollover: thread {} could not advance", thread_id)
            db.rollback()
            outcome = "error"
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


@celery_app.task(name="app.tasks.season_rollover.advance_due_rollovers")
def advance_due_rollovers() -> dict[str, int]:
    db = SessionLocal()
    try:
        return advance_all(db)
    finally:
        db.close()
