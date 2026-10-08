"""WP-69 — a best-effort lookup may fail; it may not take the transaction with it.

The journey path is full of optional reads that end in ``except Exception: log;
return None`` — the Courrier letter waiting, the prefetch warmth, the errata
queue, the due concept behind «Plus de pratique». Each comment says the same
thing ("a letter is never worth the day"), and on PostgreSQL each one was wrong:
a failed statement puts the whole transaction into the *aborted* state, the
``except`` swallows the error, and the **next** statement the learner's request
makes — marking the journey ready, or even marking it unavailable — fails with
``InFailedSqlTransaction``. On 2026-09-22 that cost a learner their first scene:
40 seconds of «Envoi…», a 500, and a journey stuck in ``preparing``.

The fix is structural, not per call site: run the optional work inside a
SAVEPOINT (``Session.begin_nested``). A failure rolls back to the savepoint
only; everything the request did before it stays pending, and the transaction
stays usable. Success releases the savepoint and changes nothing.

Two shapes, same semantics::

    letter = None
    with best_effort(db, "Courrier: awaiting-letter lookup") as attempt:
        letter = lookup()
    # attempt.failed / attempt.error say what happened

    letter = run_best_effort(db, "Courrier lookup", lookup, default=None)

``reraise`` names exception types that are *not* best-effort (an
``AdapterUnavailable`` the state machine must see): the savepoint is still
rolled back, then the exception propagates.

Inner code that commits or rolls back the whole session is tolerated: the
savepoint is then already closed and there is nothing left to release.

SQLite note: pysqlite's legacy transaction handling does not emit ``BEGIN``
until the first write, so a SAVEPOINT taken before any write opens the
transaction itself. That is harmless for reads — which is what these blocks
are — and the WP-69 tests install SQLAlchemy's documented "SAVEPOINT
workaround" hooks on their own engine to prove a real rollback of a write.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class BestEffortAttempt:
    """What happened inside one :func:`best_effort` block."""

    label: str
    failed: bool = False
    error: BaseException | None = None


def _close_savepoint(db: Session, nested: Any, *, commit: bool) -> None:
    """Release or roll back ``nested`` if it is still open; never raise."""

    try:
        if nested is not None and nested.is_active:
            if commit:
                nested.commit()
            else:
                nested.rollback()
        # Otherwise the inner code committed or rolled back the whole session
        # itself (or no savepoint could be taken), and there is nothing to close.
    except Exception:  # pragma: no cover - the connection itself is gone
        logger.warning("savepoint could not be closed cleanly; rolling back the session", exc_info=True)
        _rollback_quietly(db)
        return
    if not commit and not session_is_usable(db):
        # A failure after the inner code's own commit is outside any savepoint;
        # on PostgreSQL it leaves the new transaction aborted. Nothing of the
        # caller's is pending at that point, so a full rollback loses nothing.
        _rollback_quietly(db)


def _rollback_quietly(db: Session) -> None:
    try:
        db.rollback()
    except Exception:  # noqa: S110 - nothing useful is left to say
        logger.debug("session rollback after a failed best-effort block failed")


@contextmanager
def best_effort(
    db: Session,
    label: str,
    *,
    reraise: tuple[type[BaseException], ...] = (),
    log: logging.Logger | None = None,
) -> Iterator[BestEffortAttempt]:
    """Run the block inside a SAVEPOINT; swallow and log its failure.

    The caller assigns its fallback *before* the block, so a swallowed failure
    leaves the fallback in place.
    """

    attempt = BestEffortAttempt(label=label)
    sink = log or logger
    nested = None
    try:
        nested = db.begin_nested()
    except Exception:
        # Taking the savepoint flushes pending work first, and on a transaction
        # that is already aborted the SAVEPOINT itself fails. Either way there
        # is nothing to protect any more: roll the session back so the block
        # (and everything after it) runs on a usable transaction.
        sink.warning("%s: no savepoint could be taken; rolling back first", label, exc_info=True)
        _rollback_quietly(db)
        nested = None
    try:
        yield attempt
    except reraise:
        _close_savepoint(db, nested, commit=False)
        raise
    except Exception as exc:
        attempt.failed = True
        attempt.error = exc
        _close_savepoint(db, nested, commit=False)
        sink.warning("%s failed (rolled back to its savepoint): %s", label, exc, exc_info=True)
    else:
        _close_savepoint(db, nested, commit=True)


def run_best_effort(
    db: Session,
    label: str,
    fn: Callable[[], T],
    *,
    default: T,
    reraise: tuple[type[BaseException], ...] = (),
    log: logging.Logger | None = None,
) -> T:
    """Call ``fn`` inside :func:`best_effort`; ``default`` when it fails."""

    result = default
    with best_effort(db, label, reraise=reraise, log=log):
        result = fn()
    return result


def session_is_usable(db: Session) -> bool:
    """Can this session run a statement right now?

    False when SQLAlchemy is waiting for a rollback after a failed flush, or
    when the database has aborted the transaction (PostgreSQL after any failed
    statement). A cheap ``SELECT 1`` answers both.
    """

    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


__all__ = [
    "BestEffortAttempt",
    "best_effort",
    "run_best_effort",
    "session_is_usable",
]
