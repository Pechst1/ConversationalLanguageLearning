"""S5 · the season writer job (``app.services.season_writer_job``) as a Celery task."""
from __future__ import annotations

from datetime import date

from app.celery_app import celery_app
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.db.session import SessionLocal


def _learner_today(thread_id: str) -> date:
    from app.services.daily_journey import local_date_for, resolve_timezone

    db = SessionLocal()
    try:
        thread = db.get(SerialThread, thread_id)
        user = db.get(User, thread.user_id) if thread is not None else None
        return local_date_for(resolve_timezone(getattr(user, "timezone", None)))
    finally:
        db.close()


@celery_app.task(name="app.tasks.season_writer.write_next_season")
def write_next_season(thread_id: str, final: bool = False) -> str:
    from uuid import UUID

    from app.services import season_writer_job

    today = _learner_today(UUID(thread_id)) if final else None
    return season_writer_job.run(thread_id, today=today, final=final)
