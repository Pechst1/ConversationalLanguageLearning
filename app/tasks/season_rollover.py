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


def advance_all(db, *, today=None) -> dict[str, int]:
    """Advance every open rollover once, and queue the writer job where the sweep
    says so. ``today(thread_id)`` is the learner's own date (tests pass a clock).
    Returns a count per outcome."""

    from app.services import season_writer_job

    today = today or (lambda thread_id: _learner_today(db, thread_id))
    counts: dict[str, int] = {}
    for thread_id in season_rollover.open_rollovers(db):
        try:
            day = today(thread_id)
            outcome = season_rollover.advance(db, thread_id, today=day)
            if outcome in ("dispatch", "retry"):
                try:
                    season_writer_job.dispatcher(str(thread_id), final=outcome == "retry")
                except Exception as exc:  # the broker refused it: nothing is writing
                    logger.warning("season_rollover: thread {} writer not queued: {}", thread_id, exc)
                    outcome = season_rollover.dispatch_failed(
                        db, thread_id, today=day, final=outcome == "retry", error=f"{type(exc).__name__}: {exc}"
                    )
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
