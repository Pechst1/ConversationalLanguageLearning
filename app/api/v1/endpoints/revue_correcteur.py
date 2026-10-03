"""WP-122 part B: Le Correcteur — ``/revue/correcteur/*``.

Every route answers a plain 404 while ``settings.REVUE_CORRECTEUR_ENABLED`` is off; the
flag check is the router's first dependency, before authentication, so the desk stays
invisible. Then the usual ``get_current_user`` and the paid-route guard (a draft may make
one model call when the rules cannot place the quota).

* ``GET  /revue/correcteur/week`` — the week's dossiers the learner has not corrected yet.
* ``POST /revue/correcteur/{dossier_id}`` — a new draft (the public view: no spans).
* ``POST /revue/correcteur/{correction_id}/marks`` — «Bon à tirer»: the graded result.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.rate_limit import paid_route_guard
from app.db.models.user import User
from app.schemas.revue_correcteur import CrDraftView, CrMarksRequest, CrResult, CrWeek
from app.services.revue import correcteur
from app.services.revue.encounter import current_week


def require_correcteur_enabled() -> None:
    if not getattr(settings, "REVUE_CORRECTEUR_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/revue/correcteur",
    tags=["revue"],
    dependencies=[Depends(require_correcteur_enabled), Depends(paid_route_guard(get_current_user))],
)


def get_correcteur_provider() -> correcteur.CorrecteurProvider | None:
    """Injection seam: tests override it with ``FakeCorrecteurProvider``."""

    return correcteur.default_provider()


@router.get("/week", response_model=CrWeek)
def read_week(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CrWeek:
    return CrWeek.model_validate(correcteur.week_for(db, current_user, current_week()))


@router.post("/{dossier_id}", response_model=CrDraftView)
def new_draft(
    dossier_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    provider: correcteur.CorrecteurProvider | None = Depends(get_correcteur_provider),
) -> CrDraftView:
    week = current_week()
    dossier = correcteur.find_any_dossier(dossier_id, week)
    if dossier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="correcteur_dossier_not_found")
    row = correcteur.create_correction(
        db, current_user, dossier, provider=provider, week_number=int(week.split("-W")[1])
    )
    return CrDraftView.model_validate(correcteur.public_view(row))


@router.post("/{correction_id}/marks", response_model=CrResult)
def submit_marks(
    correction_id: str,
    body: CrMarksRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CrResult:
    row = correcteur.owned_correction(db, current_user, correction_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="correcteur_draft_not_found")
    marks = [mark.model_dump() for mark in body.marks]
    row = correcteur.grade_marks(db, current_user, row, marks)
    return CrResult.model_validate(correcteur.result_view(row))
