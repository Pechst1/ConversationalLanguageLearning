"""WP-119 phase 3 «Le kiosque»: the weekly intake beat (§4.1), and its painter (§8.4).

The beat runs every morning at 05:00 Europe/Paris (``celery_app.beat_schedule
["revue-weekly-intake"]``); under ``REVUE_CADENCE=weekly`` the Monday run builds the week's
editorial dossiers from the feeds (``app.services.revue.intake.run_intake``) and the other
mornings find the week built and keep it. Under ``daily`` each morning builds its day. A
period already built is kept; ``refresh=True`` (the admin route) rebuilds it. Off while
``REVUE_ENABLED`` is off.

Each run gives the kiosk's dossiers without leads (built before them, or an evergreen top-up)
a try at the lead desk (``leads.ensure_leads``, once per dossier, one small call each), then
queues :func:`paint_pictures`: one picture per story the kiosk is missing (and
a plate for each new place), painted once and final (``plates.paint_period``), within the
service's daily cap. A morning that finds everything painted spends nothing; one whose
painting failed is caught up the next morning.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from app.celery_app import celery_app
from app.config import settings
from app.db.session import SessionLocal


def intake_now(*, refresh: bool = False, period: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Run the intake for ``period`` (default: the current one) and return its report."""

    from app.services.revue.intake import run_intake
    from app.services.revue.weekly import period_for

    if not getattr(settings, "REVUE_ENABLED", False):
        return {"status": "disabled"}
    target = period or period_for(now or datetime.now(UTC))
    db = SessionLocal()
    try:
        report = run_intake(db, target, refresh=refresh)
        return report.as_dict()
    except Exception as exc:  # noqa: BLE001 - the beat logs and returns; the kiosk keeps last week's files
        logger.exception("revue intake failed for {}", target)
        db.rollback()
        return {"status": "failed", "period": target, "error": type(exc).__name__}
    finally:
        db.close()


def paint_now(*, period: str | None = None, now: datetime | None = None, limit: int | None = None) -> dict[str, Any]:
    """Paint what ``period``'s kiosk (default: the current one) is missing; return the report."""

    from app.services.revue.plates import paint_period
    from app.services.revue.weekly import period_for

    if not getattr(settings, "REVUE_ENABLED", False):
        return {"status": "disabled"}
    target = period or period_for(now or datetime.now(UTC))
    db = SessionLocal()
    try:
        return paint_period(db, target, limit=limit).as_dict()
    except Exception as exc:  # noqa: BLE001 - the stage keeps its place plates; tomorrow retries
        logger.exception("revue painting failed for {}", target)
        db.rollback()
        return {"status": "failed", "period": target, "error": type(exc).__name__}
    finally:
        db.close()


def leads_now(*, period: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Write the leads ``period``'s kiosk (default: the current one) is missing; return what was written."""

    from app.services.revue.leads import ensure_leads
    from app.services.revue.weekly import period_for

    if not getattr(settings, "REVUE_ENABLED", False):
        return {"status": "disabled"}
    target = period or period_for(now or datetime.now(UTC))
    db = SessionLocal()
    try:
        return {"status": "ok", "period": target, "written": ensure_leads(db, target)}
    except Exception as exc:  # noqa: BLE001 - the kiosk keeps its summaries; tomorrow retries
        logger.exception("revue leads failed for {}", target)
        db.rollback()
        return {"status": "failed", "period": target, "error": type(exc).__name__}
    finally:
        db.close()


@celery_app.task(name="app.tasks.revue.paint_pictures")
def paint_pictures(period: str | None = None, limit: int | None = None) -> dict[str, Any]:
    """§8.4: the period's missing pictures, one image call each, final."""

    return paint_now(period=period, limit=limit)


def _queue_painting(period: str | None) -> dict[str, Any]:
    """Hand the painting to its own task (its own time limit); paint inline when the queue is
    unreachable, so a morning never ends without its pictures."""

    try:
        result = paint_pictures.delay(period)
        return {"status": "enqueued", "task_id": str(getattr(result, "id", ""))}
    except Exception as exc:  # noqa: BLE001 - no broker: the beat's own worker paints
        logger.warning("revue: painting could not be queued ({}); painting inline", exc)
        return paint_now(period=period)


@celery_app.task(name="app.tasks.revue.weekly_intake")
def weekly_intake(refresh: bool = False) -> dict[str, Any]:
    """The beat's entry. Weekly cadence: the first run of the week (Monday 05:00) builds the
    week and every later morning finds it built (``kept``) — a Monday that failed is caught
    up the next morning. Daily cadence: every morning builds that day. Either way the
    kiosk's missing leads are written (:func:`leads_now`) and its missing pictures are
    painted next (:func:`paint_pictures`)."""

    report = intake_now(refresh=refresh)
    if report.get("status") == "disabled":
        return report
    report["leads"] = leads_now(period=report.get("period"))
    report["pictures"] = _queue_painting(report.get("period"))
    return report
