"""Package O-2 — l'or on screen: the livret, the day and «D'où vient ton or».

Read-only. While ``ATELIER_GOLD_UI`` is ``owner`` only admin accounts get
anything but ``{"visible": false}``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.user import User
from app.schemas.gold import GoldLedgerWeek, GoldView
from app.services.gold_view import build_gold_ledger, build_gold_view

router = APIRouter(prefix="/gold", tags=["gold"])


@router.get("", response_model=GoldView)
def read_gold(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> GoldView:
    """The counter, the day's seal rim and the week (§16)."""

    return GoldView.model_validate(build_gold_view(db, user=current_user))


@router.get("/ledger", response_model=GoldLedgerWeek)
def read_gold_ledger(
    *,
    week: str | None = Query(default=None, max_length=10, description="ISO week, 2026-W45; this week by default."),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> GoldLedgerWeek:
    """One week of entries with their reasons («D'où vient ton or»)."""

    try:
        return GoldLedgerWeek.model_validate(build_gold_ledger(db, user=current_user, week=week))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
