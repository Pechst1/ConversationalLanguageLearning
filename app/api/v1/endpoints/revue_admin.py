"""WP-119 phase 3 «Le kiosque»: the operator's routes for the intake, and the Relevé read.

* ``POST /revue/admin/refresh`` (admin only): run the intake now for the current period
  (or ``?period=2026-W40`` / ``2026-10-03``) with ``refresh=True`` — the week's dossiers
  are rebuilt from the feeds and replace the stored ones. Synchronous: one builder call
  per story, about a minute for six. ``?enqueue=true`` hands it to the Celery task instead.
* ``GET /revue/releve``: the learner's filed Papiers for Le Relevé (newest first), with
  what was made, the claims with their source lines and the words. A pure read.

Same gate as every Revue route: a plain 404 while ``settings.REVUE_ENABLED`` is off,
checked before authentication (copied, not imported, like ``revue_carte.py``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.db.models.user import User
from app.services.revue.releve import ReleveView, releve_for

PERIOD_PATTERN = r"^(\d{4}-W\d{2}|\d{4}-\d{2}-\d{2})$"


def require_revue_enabled() -> None:
    if not getattr(settings, "REVUE_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if str(getattr(current_user, "role", "user") or "user") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges are required.")
    return current_user


router = APIRouter(prefix="/revue", tags=["revue"], dependencies=[Depends(require_revue_enabled)])


@router.post("/admin/refresh")
def refresh_intake(
    period: str | None = Query(None, pattern=PERIOD_PATTERN),
    enqueue: bool = Query(False),
    _admin: User = Depends(require_admin),
) -> dict[str, Any]:
    """Rebuild the period's dossiers from the feeds (``refresh=True``)."""

    if enqueue:
        from app.tasks.revue import weekly_intake

        result = weekly_intake.delay(refresh=True)
        return {"status": "enqueued", "task_id": str(getattr(result, "id", ""))}
    from app.tasks.revue import intake_now

    return intake_now(refresh=True, period=period)


@router.get("/releve", response_model=ReleveView)
def read_releve(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReleveView:
    """The learner's filed Papiers for Le Relevé."""

    return releve_for(db, current_user)
