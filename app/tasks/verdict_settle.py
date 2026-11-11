"""Package V stage 3 · the settlement job (``app.services.verdict_settle``) as Celery tasks.

``settle_verdict`` checks one unread answer again; ``sweep`` (beat) sends every due one.
Same pattern as :mod:`app.tasks.season_writer`: the service holds the caps and the
backoff, the task only opens a session.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal


@contextmanager
def _session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(name="app.tasks.verdict_settle.settle_verdict")
def settle_verdict(subject_type: str, subject_id: str, source: str = "auto") -> str:
    from app.services import verdict_settle

    with _session() as db:
        return verdict_settle.settle(db, subject_type, subject_id, source=source)


@celery_app.task(name="app.tasks.verdict_settle.sweep")
def sweep() -> int:
    from app.services import verdict_settle

    with _session() as db:
        return verdict_settle.sweep(db)
