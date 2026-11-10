"""S5 · the next season is written by a job, during the named interlude.

The season writer had one attempt, inside the learner's last answer, with their
rows locked (walk #649). Now the rollover only stores ``pending``
(``season_rollover``); the beat dispatches this job, which retries until a draft
is accepted or the rollover's budget is spent. Both caps are settings
(``ATELIER_SEASON_WRITER_MAX_ATTEMPTS``, ``ATELIER_SEASON_WRITER_MAX_USD``) and
count across the whole rollover, the retry on the promised date included.

Every attempt runs with no transaction open; only the bookkeeping takes the
life's lock, briefly. Each attempt is one cost row carrying its refusal reason
(``story_season_writer_cost``) and one entry in ``rollover.attempts``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.services import season_rollover

logger = logging.getLogger(__name__)

COST_EVENT = "story_season_writer_cost"


def _dispatch_celery(thread_id: str, final: bool = False) -> None:
    from app.tasks.season_writer import write_next_season

    write_next_season.delay(str(thread_id), final)


#: How a writer job is queued (tests swap it). ``final`` is the promised date's retry.
dispatcher: Callable[..., None] = _dispatch_celery


def spent(row: dict) -> tuple[int, float]:
    attempts = [a for a in row.get("attempts") or [] if isinstance(a, dict)]
    return len(attempts), round(sum(float(a.get("cost_usd") or 0) for a in attempts), 6)


def budget_left(row: dict) -> bool:
    count, usd = spent(row)
    return (
        count < int(settings.ATELIER_SEASON_WRITER_MAX_ATTEMPTS)
        and usd < float(settings.ATELIER_SEASON_WRITER_MAX_USD)
    )


def _locked(db: Session, thread_id: UUID):
    from app.db.models.serial import SerialThread

    return db.scalars(
        select(SerialThread).where(SerialThread.id == thread_id).with_for_update()
        .execution_options(populate_existing=True)
    ).first()


def _live(thread) -> dict:
    from app.services.living_story import STATE_KEY

    return dict((thread.state or {}).get(STATE_KEY) or {})


def _save(thread, live: dict) -> None:
    from app.services.living_story import STATE_KEY

    state = dict(thread.state or {})
    state[STATE_KEY] = live
    thread.state = state
    flag_modified(thread, "state")


def _writing(row: dict, season: int) -> bool:
    return season_rollover.is_open(row) and row.get("state") == season_rollover.PENDING and int(
        row.get("season") or 0
    ) == season


def run(
    thread_id: Any,
    *,
    session_factory: Callable[[], Session] | None = None,
    today: date | None = None,
    final: bool = False,
) -> str:
    """Write the next season for one life. Returns ``written``, ``spent`` (the budget
    ran out; the state is ``interlude``) or ``skipped`` (nothing to write).

    ``final`` is the retry the promised date fired: when it ends, the life is moved
    on that date (``season_rollover.advance``) — the written season, or the reprise."""

    from app.db.models.user import User
    from app.db.session import SessionLocal
    from app.services import living_story as engine
    from app.services import season_writer

    thread_id = UUID(str(thread_id))
    db = (session_factory or SessionLocal)()
    outcome = "skipped"
    try:
        thread = _locked(db, thread_id)
        row = season_rollover.state_of(_live(thread)) if thread is not None else {}
        season = int(row.get("season") or 0)
        while thread is not None and _writing(row, season):
            if not budget_left(row):
                live = _live(thread)
                season_rollover.store(
                    live, season_rollover.INTERLUDE,
                    **{k: v for k, v in row.items() if k != "state"},
                )
                _save(thread, live)
                db.commit()
                outcome = "spent"
                break
            live, world, user_id = _live(thread), dict(thread.world_bible or {}), thread.user_id
            db.commit()  # no transaction (and no lock) stays open across the model calls
            attempt = season_writer.write_attempt(live=live, world=world, next_season=season)
            thread = _locked(db, thread_id)
            live = _live(thread) if thread is not None else {}
            row = season_rollover.state_of(live)
            record = {
                "n": spent(row)[0] + 1,
                "reason": attempt.reason,
                "cost_usd": attempt.cost_usd,
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            user = db.get(User, user_id)
            if user is not None:
                engine._record_cost(
                    db, user, COST_EVENT, attempt.usage or [{"stage": "SeasonDraft", "cost_usd": 0.0}],
                    entity_type="living_story_season",
                    payload={"season": season, "attempt": record["n"], "reason": attempt.reason},
                )
            if thread is None or not _writing(row, season):
                db.commit()  # the life moved on meanwhile (the date, a reset): keep the log only
                break
            attempts = [*(row.get("attempts") or []), record]
            fields = {k: v for k, v in row.items() if k not in ("state", "attempts")}
            if attempt.season_file is not None:
                season_rollover.store(
                    live, season_rollover.WRITTEN, **fields, attempts=attempts, season_file=attempt.season_file
                )
                outcome = "written"
            else:
                row = season_rollover.store(live, season_rollover.PENDING, **fields, attempts=attempts)
            _save(thread, live)
            db.commit()
            logger.info("season_writer_job: thread %s attempt %s: %s", thread_id, record["n"], attempt.reason)
            if outcome == "written":
                break
        else:
            db.rollback()
        if final and today is not None:
            season_rollover.advance(db, thread_id, today=today)
        return outcome
    finally:
        if session_factory is None:
            db.close()


__all__ = ["COST_EVENT", "budget_left", "dispatcher", "run", "spent"]
