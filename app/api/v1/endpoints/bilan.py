"""«Le bilan» — ``/bilan``: the learner's week, computed on read.

Every route answers a plain 404 while ``settings.BILAN_ENABLED`` is off; the flag check
is the router's first dependency, before authentication, so the page stays invisible.
A read with no model call: no paid-route guard.

* ``GET /bilan?week=YYYY-MM-DD`` — the week holding that day (default: this week).
* ``GET /bilan/card`` — the last closed week, for Home's card (``week_start`` null when
  that week had no played day).
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.bilan import Bilan, BilanCard
from app.services import bilan


def require_bilan_enabled() -> None:
    if not bilan.bilan_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(prefix="/bilan", tags=["bilan"], dependencies=[Depends(require_bilan_enabled)])


@router.get("", response_model=Bilan)
def read_bilan(
    week: date | None = Query(None, description="Any day of the week asked for (learner-local)."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Bilan:
    return Bilan.model_validate(bilan.build_bilan(db, current_user, week_start=week))


@router.get("/card", response_model=BilanCard)
def read_card(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BilanCard:
    return BilanCard.model_validate(bilan.home_card(db, current_user))
