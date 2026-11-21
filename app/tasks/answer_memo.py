"""Package V stage 4 · the memo's second check (``app.services.answer_memo``) as Celery tasks.

``confirm_memo`` runs the second, independent check on one candidate; ``sweep`` (beat)
re-sends the candidates whose check was lost or could not read. The service decides, the
task only opens a session and commits.
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


@celery_app.task(name="app.tasks.answer_memo.confirm_memo")
def confirm_memo(memo_id: str) -> str:
    from app.services import answer_memo

    with _session() as db:
        state = answer_memo.confirm(db, memo_id)
        db.commit()
        return state


@celery_app.task(name="app.tasks.answer_memo.sweep")
def sweep() -> int:
    from app.services import answer_memo

    with _session() as db:
        return answer_memo.sweep(db)
