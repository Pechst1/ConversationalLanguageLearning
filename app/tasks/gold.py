"""Package O-1 — the nightly gold job (shadow).

Once a night: every learner active in the last two days gets their milestones
reconciled (a rule held through the journey, an épreuve passed elsewhere) and
their livret recomputed from the ledger; then the §18 report is built and kept
as a ``gold_shadow_report`` pilot event. Idempotent: a second run the same night
writes no milestone twice and stores a second, identical report.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger

from app.celery_app import celery_app
from app.db.session import SessionLocal

#: Learners with a ledger entry this recently get their milestones reconciled.
RECONCILE_ACTIVE_DAYS = 2
REPORT_EVENT = "gold_shadow_report"


def run_nightly(db: Any, *, days: int = 14, now: datetime | None = None) -> dict[str, Any]:
    """The job's body, on a given session (the task opens one; tests pass theirs)."""

    from app.db.models.gold import GoldLedgerEntry
    from app.db.models.user import User
    from app.services import gold_ledger
    from app.services.gold_report import build_gold_report
    from app.services.pilot_events import PilotEventService

    now = now or datetime.now(UTC)
    if not gold_ledger.ledger_on():
        return {"skipped": "ATELIER_GOLD_MODE=off"}
    active_since = now.date() - timedelta(days=RECONCILE_ACTIVE_DAYS)
    user_ids = [
        user_id
        for (user_id,) in db.query(GoldLedgerEntry.user_id)
        .filter(GoldLedgerEntry.local_date >= active_since)
        .distinct()
        .all()
    ]
    reconciled = failed = 0
    for user_id in user_ids:
        user = db.get(User, user_id)
        if user is None:
            continue
        try:
            gold_ledger.reconcile_milestones(db, user=user, now=now)
            gold_ledger.recompute_balance(db, user_id=user.id, now=now)
            db.commit()
            reconciled += 1
        except Exception as exc:  # pragma: no cover - one learner never stops the night
            db.rollback()
            failed += 1
            logger.warning("gold nightly: learner skipped", user_id=str(user_id), error=str(exc))
    report = build_gold_report(db, days=days, now=now)
    PilotEventService(db).record(REPORT_EVENT, user_id=None, entity_type="gold", payload=report)
    db.commit()
    summary = {
        "reconciled": reconciled,
        "failed": failed,
        "learners": report["learners"],
        "learner_days": report["learner_days"],
        "production_share": report["production_share"],
        "plafond_day_share": report["plafond"]["touched_day_share"],
    }
    logger.info("gold nightly report", **summary)
    return summary


@celery_app.task(name="app.tasks.gold.nightly_report")
def nightly_report(days: int = 14) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return run_nightly(db, days=days)
    finally:
        db.close()


__all__ = ["RECONCILE_ACTIVE_DAYS", "REPORT_EVENT", "nightly_report", "run_nightly"]
