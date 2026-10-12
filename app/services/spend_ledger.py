"""E1 — hold money for a paid request before it runs.

:func:`app.services.spend_guard.enforce_daily_budget` reads what the ledgers
have already *recorded*. Requests that start together all read the same total,
all pass, and the day ends above its cap: the learner's own lanes (the story
thread pool, Celery, a double tap) are enough. Here the check and the hold are
one step under a lock:

1. take the reservation lock (a PostgreSQL transaction advisory lock; SQLite
   has a single writer already);
2. count recorded spend **plus every open hold** for the learner's day and the
   service's UTC day;
3. refuse with ``429 daily_budget_reached`` if this request's bound would cross
   either cap, otherwise write the hold and commit.

The request closes its hold when it ends (:func:`release`); its real cost is on
the usual ledgers by then. A hold nobody closed within
``SPEND_RESERVATION_STALE_SECONDS`` becomes ``uncertain`` and keeps counting
until its day is over, so a crash or a timeout is never billed at zero.

Holds are written on their own session bound to the caller's engine and
committed at once: a hold inside the caller's transaction would be invisible to
the very concurrent requests it has to stop.
"""
from __future__ import annotations

import uuid
import zlib
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.spend_reservation import OPEN_STATUSES, SpendReservation
from app.services import spend_guard

#: One lock for every hold: holds are short, and the service cap spans learners.
_LOCK_KEY = zlib.crc32(b"atelier:spend_reservations")


def enabled() -> bool:
    return bool(getattr(settings, "SPEND_RESERVATIONS_ENABLED", False))


def request_bound_usd() -> float:
    value = getattr(settings, "SPEND_RESERVATION_REQUEST_BOUND_USD", None)
    return 0.02 if value is None else max(0.0, float(value))


def _stale_after() -> timedelta:
    return timedelta(seconds=int(getattr(settings, "SPEND_RESERVATION_STALE_SECONDS", 300) or 300))


def _own_session(db: Session) -> Session:
    return Session(bind=db.get_bind(), autoflush=False, expire_on_commit=False)


def _lock(session: Session) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})


def _mark_stale(session: Session, now: datetime) -> None:
    session.execute(
        update(SpendReservation)
        .where(SpendReservation.status == "reserved", SpendReservation.created_at < now - _stale_after())
        .values(status="uncertain")
    )


def outstanding_usd(
    db: Session, user_id: Any = None, *, now: datetime | None = None, zone: Any = None
) -> float:
    """Open holds in the day around ``now``: one learner's, or the service's when ``user_id`` is None."""

    start, end = spend_guard.day_bounds(now, zone)
    filters = [
        SpendReservation.status.in_(OPEN_STATUSES),
        SpendReservation.created_at >= start,
        SpendReservation.created_at < end,
    ]
    if user_id is not None:
        filters.append(SpendReservation.user_id == user_id)
    total = db.scalar(select(func.coalesce(func.sum(SpendReservation.upper_bound_usd), 0.0)).where(*filters))
    return round(float(total or 0.0), 6)


def _refuse(now: datetime, zone: Any) -> None:
    from app.core.rate_limit import too_many_requests

    raise too_many_requests(
        spend_guard.DAILY_BUDGET_REACHED_CODE,
        "That is everything for today. Your practice continues tomorrow.",
        spend_guard.seconds_until_reset(now, zone),
    )


def reserve(
    db: Session,
    user: Any,
    *,
    kind: str,
    upper_bound_usd: float | None = None,
    request_key: str | None = None,
    open_day: bool = False,
    now: datetime | None = None,
) -> uuid.UUID:
    """Hold ``upper_bound_usd`` for one paid request, or raise ``429 daily_budget_reached``.

    ``open_day`` is WP-88's started day: the learner is held to the open-day
    ceiling instead of the cap. The same ``request_key`` twice returns the
    first hold instead of holding twice.
    """

    moment = (now or datetime.now(UTC)).astimezone(UTC)
    bound = request_bound_usd() if upper_bound_usd is None else max(0.0, float(upper_bound_usd))
    key = request_key or f"{kind}:{uuid.uuid4().hex}"
    user_id = getattr(user, "id", None)
    zone = spend_guard.learner_zone(user)
    session = _own_session(db)
    try:
        _lock(session)
        existing = session.scalar(select(SpendReservation).where(SpendReservation.request_key == key))
        if existing is not None:
            session.commit()
            return existing.id
        _mark_stale(session, moment)

        service_cap = spend_guard.service_daily_cap_usd()
        if service_cap > 0:
            service_total = spend_guard.service_spend_today_usd(session, now=moment) + outstanding_usd(
                session, now=moment
            )
            if service_total + bound > service_cap + 1e-9:
                session.commit()  # keep the stale marks; nothing else is pending
                logger.error(
                    "Service-wide daily spend cap reached: ${:.4f} held or spent + ${:.4f} > ${:.2f}",
                    service_total, bound, service_cap,
                )
                _refuse(moment, None)

        cap = spend_guard.daily_cap_usd()
        if cap > 0 and user_id is not None:
            limit = spend_guard.open_day_ceiling_usd() if open_day else cap
            learner_total = spend_guard.spend_today_usd(session, user_id, now=moment, zone=zone) + outstanding_usd(
                session, user_id, now=moment, zone=zone
            )
            if learner_total + bound > limit + 1e-9:
                session.commit()  # keep the stale marks; nothing else is pending
                logger.warning(
                    "Daily spend {} reached for learner {}: ${:.4f} held or spent + ${:.4f} > ${:.2f}",
                    "ceiling" if open_day else "cap", user_id, learner_total, bound, limit,
                )
                _refuse(moment, zone)

        hold = SpendReservation(
            request_key=key,
            user_id=user_id,
            kind=kind[:64],
            upper_bound_usd=bound,
            status="reserved",
            service_day=moment.date(),
            created_at=moment,
        )
        session.add(hold)
        session.commit()
        return hold.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _close(db: Session, reservation_id: uuid.UUID, *, status: str, actual_usd: float | None) -> None:
    session = _own_session(db)
    try:
        values: dict[str, Any] = {"status": status, "closed_at": datetime.now(UTC)}
        if actual_usd is not None:
            values["actual_usd"] = max(0.0, float(actual_usd))
        session.execute(
            update(SpendReservation)
            .where(SpendReservation.id == reservation_id, SpendReservation.status.in_(OPEN_STATUSES))
            .values(**values)
        )
        session.commit()
    except Exception as exc:  # pragma: no cover - defensive
        session.rollback()
        # Left open, the hold goes uncertain and keeps counting: safe, not free.
        logger.warning("Spend hold {} could not be closed: {}", reservation_id, exc)
    finally:
        session.close()


def release(db: Session, reservation_id: uuid.UUID) -> None:
    """The request ended and its real cost is on the ledgers: stop holding."""

    _close(db, reservation_id, status="released", actual_usd=None)


def settle(db: Session, reservation_id: uuid.UUID, actual_usd: float) -> None:
    """The request ended with a known cost that is on the ledgers: record it and stop holding."""

    _close(db, reservation_id, status="settled", actual_usd=actual_usd)


__all__ = [
    "enabled",
    "outstanding_usd",
    "release",
    "request_bound_usd",
    "reserve",
    "settle",
]
