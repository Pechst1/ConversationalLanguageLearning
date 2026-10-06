"""WP-119 phase 3 «Le kiosque»: the weekly intake beat (§4.1).

The beat runs every morning at 05:00 Europe/Paris (``celery_app.beat_schedule
["revue-weekly-intake"]``); under ``REVUE_CADENCE=weekly`` the Monday run builds the week's
editorial dossiers from the feeds (``app.services.revue.intake.run_intake``) and the other
mornings find the week built and keep it. Under ``daily`` each morning builds its day. A
period already built is kept; ``refresh=True`` (the admin route) rebuilds it. Off while
``REVUE_ENABLED`` is off.
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


@celery_app.task(name="app.tasks.revue.weekly_intake")
def weekly_intake(refresh: bool = False) -> dict[str, Any]:
    """The beat's entry. Weekly cadence: the first run of the week (Monday 05:00) builds the
    week and every later morning finds it built (``kept``) — a Monday that failed is caught
    up the next morning. Daily cadence: every morning builds that day."""

    return intake_now(refresh=refresh)
