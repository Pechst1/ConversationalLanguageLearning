"""Package V stage 3: an answer nobody could read is checked again later, by a job.

Before, «not checked» waited for the learner: the only way out was «Check again». A
provider outage became lost work, and a letter finished in that state never paid. Now:

1. **Queue.** When the ledger (:mod:`app.services.verdict_ledger`) records an answer that
   does not count and says a later check could help (``retryable``), :func:`note_unread`
   adds a ``queued`` row to ``verdict_settlements`` in the same flush.
2. **Sweep.** :func:`sweep` (Celery beat, ``app.tasks.verdict_settle.sweep``) sends every
   due subject to ``settle_verdict``. A broker that refuses leaves a ``refused`` row with a
   backoff; the record stays retryable and the next sweep sends it again.
3. **Settle.** :func:`settle` (the task's body) checks the answer again with the surface's
   own corrector (:data:`SETTLERS`). The row's flush writes the new ledger record, which
   supersedes the unread one. Attempts are capped (``VERDICT_SETTLE_MAX_ATTEMPTS``) with
   backoff (``VERDICT_SETTLE_BACKOFF_MINUTES``), and background attempts per learner and
   UTC day are capped too (``VERDICT_SETTLE_DAILY_BUDGET``).
4. **Pay.** When the answer now counts, :func:`_after_settled` pays what its surface held
   back: a finished letter's gold (through the record's chain, ``pay_verdict``) and token.
   Settling again finds nothing to do, so it pays once.

The learner's «Ask again» runs the same :func:`settle`, inline and with ``source="ask"``:
it answers on the spot, spends the learner's own limit (``enforce_recheck_limit``), not the
background budget, and is idempotent the same way.

Surfaces settled here: the Courrier (a letter's attempt, a reply), the Journal and, behind
``VERDICT_SETTLE_FORGE`` (stage R1), La Forge's free sentences (``FREE_PRODUCTION_ROUNDS``):
the settler puts the attempt's ``ai_review`` back to ``pending`` and runs the same relecture
(``AtelierCorrectionService.run_ai_review_for_attempt``) an on-time check runs, so a late
reading writes the same evidence, gold and error memory, once. The Feuilleton has no
re-check path yet; its unread answers are recorded but not queued.

The daily budget is spent at the sweep: it sends a learner no more due subjects than the
budget has left today, so a backlog after an outage (forty unread sentences) never spends
more than ``VERDICT_SETTLE_DAILY_BUDGET`` background checks in a UTC day, however many
workers run the jobs at once.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.verdict_record import VerdictRecord
from app.db.models.verdict_settlement import VerdictSettlement

__all__ = [
    "SETTLERS",
    "ask",
    "checked_since",
    "dispatcher",
    "note_unread",
    "settle",
    "sweep",
]

#: States from which the sweep sends the subject again once ``next_at`` has passed.
_WAITING = ("queued", "refused", "unread", "over_budget", "error")
#: States that spend an attempt (the corrector was asked).
_ATTEMPTED = ("unread", "settled", "error")


# ---------------------------------------------------------------------------
# The surfaces
# ---------------------------------------------------------------------------


def _courrier(db: Session, user: Any, row: Any) -> Any:
    from app.services.missions import recheck_message

    return recheck_message(db, user=user, row=row)


def _journal(db: Session, user: Any, row: Any) -> Any:
    from app.services.journal import JournalService

    JournalService(db).retry_correction(user, row)
    return []


def _forge_corrector(db: Session) -> Any:
    """The corrector a Forge recheck runs (tests swap it for one with a fake model)."""

    from app.services.atelier import AtelierCorrectionService

    return AtelierCorrectionService(db)


def _forge(db: Session, user: Any, row: Any) -> Any:
    """La Forge (R1): the second check again, through the relecture's own merge rules.

    The row is locked while its review goes back to ``pending``, so a learner's «Check
    again» and this job never both start it; a review already in flight or landed is
    left alone. ``run_ai_review_for_attempt`` then lands it (evidence, gold, error memory,
    once) or records the failure again.
    """

    service = _forge_corrector(db)
    db.refresh(row, with_for_update=True)
    status = service.ai_review_from_correction(row.correction_payload).get("status")
    if status in {"pending", "complete"}:
        db.commit()  # «Check again» is reading it, or it was read: nothing to start
        return []
    row, started = service.mark_ai_review_pending(row, auto_started=False)
    if started:
        service.run_ai_review_for_attempt(row.id)
    return []


def _model(subject_type: str) -> type:
    from app.db.models.atelier import AtelierAttempt
    from app.db.models.journal import JournalEntry
    from app.db.models.mission import RealWorldMissionAttempt, RealWorldMissionTurn

    return {
        "courrier_attempt": RealWorldMissionAttempt,
        "courrier_turn": RealWorldMissionTurn,
        "journal_entry": JournalEntry,
        "forge_attempt": AtelierAttempt,
    }[subject_type]


#: How each subject is checked again: ``settler(db, user, row)``, committing its own work.
SETTLERS: dict[str, Callable[[Session, Any, Any], Any]] = {
    "courrier_attempt": _courrier,
    "courrier_turn": _courrier,
    "journal_entry": _journal,
    "forge_attempt": _forge,
}


def _surface_on(subject_type: str) -> bool:
    """Whether this surface's unread answers are queued and settled at all."""

    if subject_type == "forge_attempt":
        return bool(settings.VERDICT_SETTLE_FORGE)
    return True


def _settleable(subject_type: str, row: Any) -> bool:
    """Whether a re-check can change this row: a Forge attempt only on a free sentence."""

    if subject_type == "forge_attempt":
        from app.services.atelier import FREE_PRODUCTION_ROUNDS

        return str(getattr(row, "round", "") or "") in FREE_PRODUCTION_ROUNDS
    return True


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------


def _clock() -> datetime:
    return datetime.now(UTC)


def _now(now: datetime | None) -> datetime:
    return (now or _clock()).astimezone(UTC)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _backoff(attempt: int) -> timedelta:
    steps = [int(part) for part in str(settings.VERDICT_SETTLE_BACKOFF_MINUTES).split(",") if part.strip()] or [5]
    return timedelta(minutes=steps[min(max(attempt, 0), len(steps) - 1)])


def _latest(db: Session, subject_type: str, subject_id: Any) -> VerdictSettlement | None:
    with db.no_autoflush:
        pending = [
            row
            for row in db.new
            if isinstance(row, VerdictSettlement)
            and row.subject_type == subject_type
            and row.subject_id == str(subject_id)
        ]
        if pending:
            return pending[-1]
        return db.scalars(
            select(VerdictSettlement)
            .where(VerdictSettlement.subject_type == subject_type, VerdictSettlement.subject_id == str(subject_id))
            .order_by(VerdictSettlement.created_at.desc(), VerdictSettlement.attempt.desc())
            .limit(1)
        ).first()


def _attempts(db: Session, subject_type: str, subject_id: Any) -> int:
    return int(
        db.scalar(
            select(func.count(VerdictSettlement.id)).where(
                VerdictSettlement.subject_type == subject_type,
                VerdictSettlement.subject_id == str(subject_id),
                VerdictSettlement.source == "auto",
                VerdictSettlement.state.in_(_ATTEMPTED),
            )
        )
        or 0
    )


def _spent_today(db: Session, user_id: Any, now: datetime) -> int:
    start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    return int(
        db.scalar(
            select(func.count(VerdictSettlement.id)).where(
                VerdictSettlement.user_id == user_id,
                VerdictSettlement.source == "auto",
                VerdictSettlement.state.in_(_ATTEMPTED),
                VerdictSettlement.created_at >= start,
            )
        )
        or 0
    )


def _log(
    db: Session,
    *,
    subject_type: str,
    subject_id: Any,
    user_id: Any,
    record: VerdictRecord | None,
    state: str,
    source: str = "auto",
    attempt: int = 0,
    next_at: datetime | None = None,
    error: str | None = None,
    settled: VerdictRecord | None = None,
    now: datetime | None = None,
) -> VerdictSettlement:
    row = VerdictSettlement(
        id=uuid.uuid4(),
        user_id=user_id,
        subject_type=subject_type,
        subject_id=str(subject_id),
        record_id=getattr(record, "id", None),
        source=source,
        state=state,
        attempt=attempt,
        next_at=next_at,
        error=(error or None) and str(error)[:500],
        settled_record_id=getattr(settled, "id", None),
        created_at=_now(now),
    )
    db.add(row)
    return row


def _wants_settling(record: VerdictRecord) -> bool:
    shown = (record.verdict or {}).get("shown") or {}
    return (
        not record.counts
        and bool(shown.get("retryable"))
        and record.subject_type in SETTLERS
        and _surface_on(record.subject_type)
    )


def _live(db: Session, subject_type: str, subject_id: Any) -> VerdictRecord | None:
    from app.services import verdict_ledger

    return verdict_ledger.live_record(db, subject_type, subject_id)


def note_unread(session: Session, record: VerdictRecord) -> None:
    """From the ledger's flush: queue a just-recorded answer nobody could read."""

    if not settings.VERDICT_SETTLE_ENABLED or not _wants_settling(record):
        return
    latest = _latest(session, record.subject_type, record.subject_id)
    if latest is not None and latest.state in (*_WAITING, "gave_up"):
        return  # already waiting (or spent): one job per answer
    _log(
        session,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        user_id=record.user_id,
        record=record,
        state="queued",
        next_at=_now(None) + _backoff(0),
    )


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def _dispatch_celery(subject_type: str, subject_id: str, source: str = "auto") -> None:
    from app.tasks.verdict_settle import settle_verdict

    settle_verdict.delay(subject_type, subject_id, source)


#: How a settlement is queued (tests swap it). Raising means the broker refused.
dispatcher: Callable[..., None] = _dispatch_celery


def sweep(db: Session, *, now: datetime | None = None, limit: int = 200) -> int:
    """Send every due subject to the job. Returns how many were sent. Commits."""

    if not settings.VERDICT_SETTLE_ENABLED:
        return 0
    now = _now(now)
    newest = (
        select(
            VerdictSettlement.subject_type,
            VerdictSettlement.subject_id,
            func.max(VerdictSettlement.created_at).label("at"),
        )
        .group_by(VerdictSettlement.subject_type, VerdictSettlement.subject_id)
        .subquery()
    )
    rows = db.scalars(
        select(VerdictSettlement)
        .join(
            newest,
            (VerdictSettlement.subject_type == newest.c.subject_type)
            & (VerdictSettlement.subject_id == newest.c.subject_id)
            & (VerdictSettlement.created_at == newest.c.at),
        )
        .where(VerdictSettlement.state.in_(_WAITING))
        .order_by(VerdictSettlement.next_at)
        .limit(limit)
    ).all()
    due = []
    seen: set[tuple[str, str]] = set()
    left: dict[Any, int] = {}
    budget = int(settings.VERDICT_SETTLE_DAILY_BUDGET)
    tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
    for row in rows:
        key = (row.subject_type, row.subject_id)
        if key in seen or not _surface_on(row.subject_type):
            continue
        seen.add(key)
        if _utc(row.next_at) is not None and _utc(row.next_at) > now:
            continue
        if row.user_id not in left:
            left[row.user_id] = budget - _spent_today(db, row.user_id, now)
        if left[row.user_id] <= 0:
            # The budget is spent at the sweep, not by jobs racing each other: whatever
            # a learner's backlog, no more than the day's budget is sent.
            _log(
                db,
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                user_id=row.user_id,
                record=_live(db, row.subject_type, row.subject_id),
                state="over_budget",
                attempt=_attempts(db, row.subject_type, row.subject_id),
                next_at=tomorrow,
                now=now,
            )
            continue
        left[row.user_id] -= 1
        due.append((key, row.user_id))
    db.commit()
    sent = 0
    for (subject_type, subject_id), user_id in due:
        try:
            dispatcher(subject_type, subject_id, "auto")
        except Exception as exc:  # noqa: BLE001 - a refused task leaves the record retryable
            logger.warning("verdict_settle: broker refused {} {} ({})", subject_type, subject_id, exc)
            db.rollback()
            from app.services import verdict_ledger

            _log(
                db,
                subject_type=subject_type,
                subject_id=subject_id,
                user_id=user_id,
                record=verdict_ledger.live_record(db, subject_type, subject_id),
                state="refused",
                attempt=_attempts(db, subject_type, subject_id),
                next_at=now + _backoff(_attempts(db, subject_type, subject_id)),
                error=f"{type(exc).__name__}: {exc}",
                now=now,
            )
            db.commit()
            continue
        sent += 1
    return sent


# ---------------------------------------------------------------------------
# Settling
# ---------------------------------------------------------------------------


def settle(
    db: Session,
    subject_type: str,
    subject_id: Any,
    *,
    source: str = "auto",
    now: datetime | None = None,
    collect: list | None = None,
) -> str:
    """Check one unread answer again. Returns the state it ends in. Commits.

    Idempotent: an answer that already counts (or no longer exists) is left alone and
    pays nothing again. ``collect`` receives what the surface's settler returned.
    """

    from app.db.models.user import User
    from app.services import verdict_ledger

    now = _now(now)
    if subject_type not in SETTLERS:
        return "unsupported"
    if not _surface_on(subject_type):
        return "off"
    row = db.get(_model(subject_type), uuid.UUID(str(subject_id)))
    if row is None:
        return "gone"
    record = verdict_ledger.live_record(db, subject_type, subject_id)
    if record is not None and record.counts:
        return "settled"
    user = db.get(User, row.user_id)
    user_id = getattr(user, "id", None)
    attempt = _attempts(db, subject_type, subject_id) + 1 if source == "auto" else 0
    log = {"subject_type": subject_type, "subject_id": subject_id, "user_id": user_id, "source": source, "now": now}

    if source == "auto":
        if (record is not None and not _wants_settling(record)) or not _settleable(subject_type, row):
            # Recorded as unread for a reason a re-check cannot change (no model at all,
            # a keyed rung): the job ends here, so the sweep stops sending it.
            _log(db, record=record, state="gone", attempt=attempt - 1, **log)
            db.commit()
            return "gone"
        if attempt > int(settings.VERDICT_SETTLE_MAX_ATTEMPTS):
            _log(db, record=record, state="gave_up", attempt=attempt - 1, **log)
            db.commit()
            return "gave_up"
        if _spent_today(db, user_id, now) >= int(settings.VERDICT_SETTLE_DAILY_BUDGET):
            tomorrow = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
            _log(db, record=record, state="over_budget", attempt=attempt - 1, next_at=tomorrow, **log)
            db.commit()
            return "over_budget"

    try:
        result = SETTLERS[subject_type](db, user, row)
    except Exception as exc:  # noqa: BLE001 - one failed attempt is a retry, not a lost answer
        logger.warning("verdict_settle: {} {} raised ({})", subject_type, subject_id, exc)
        db.rollback()
        _log(db, record=record, state="error", attempt=attempt, next_at=now + _backoff(attempt), error=repr(exc), **log)
        db.commit()
        if source == "ask":
            raise
        return "error"
    if collect is not None:
        collect.extend(result or [])

    db.expire_all()
    live = verdict_ledger.live_record(db, subject_type, subject_id)
    if live is not None and live.counts:
        _log(db, record=record, state="settled", attempt=attempt, settled=live, **log)
        _after_settled(db, subject_type, db.get(_model(subject_type), uuid.UUID(str(subject_id))), user, now=now)
        db.commit()
        return "settled"
    if live is None and not verdict_ledger_enabled(db):
        return "unrecorded"
    _log(db, record=record, state="unread", attempt=attempt, next_at=now + _backoff(attempt), **log)
    db.commit()
    return "unread"


def verdict_ledger_enabled(db: Session) -> bool:
    from app.services import verdict_ledger

    return verdict_ledger._enabled(db)


def ask(db: Session, *, user: Any, row: Any, subject_type: str) -> Any:
    """The learner's «Ask again»: :func:`settle` inline, on their own limit. Returns what
    the surface's settler returned (the Courrier's newly filed errata)."""

    filed: list = []
    settle(db, subject_type, row.id, source="ask", collect=filed)
    return filed


def _after_settled(db: Session, subject_type: str, row: Any, user: Any, *, now: datetime) -> None:
    """Pay what the surface held back while the answer was unread.

    La Forge (R1) owes nothing more here: its settler ran the relecture an on-time check
    runs, which already wrote, once, what the answer owes: the séance's evidence
    (``ForgeService.amend_attempt``, or ``_apply_deferred_evidence`` outside a Forge
    séance), the Forge item's gold (``settle_forge_item`` revives the entry voided as
    unread, under its own key ``gold:forge:{attempt}``) and the error memory. No verdict
    gold (``pay_verdict``) is minted: the Forge pays through its item entry, never twice.
    Vocabulary credit stays the submit's, as on time (the relecture never re-credits).
    """

    if row is None or user is None or not subject_type.startswith("courrier_"):
        return
    from app.services.missions import settle_finished_letter

    settle_finished_letter(db, user=user, mission=row.mission, now=now)


def checked_since(db: Session | None, subject_type: str, subject_id: Any) -> datetime | None:
    """When an answer saved unread was checked since, or ``None``.

    True of a subject whose live record counts and supersedes one that did not: the
    learner saw «not checked» and the job (or their «Ask again») read it later.
    """

    if db is None:
        return None
    from app.services import verdict_ledger

    try:
        live = verdict_ledger.live_record(db, subject_type, subject_id)
        if live is None or not live.counts or live.supersedes_id is None:
            return None
        previous = db.get(VerdictRecord, live.supersedes_id)
    except Exception:  # noqa: BLE001 - a screen never fails on the ledger
        return None
    if previous is None or previous.counts:
        return None
    return _utc(live.settled_at or live.created_at)
