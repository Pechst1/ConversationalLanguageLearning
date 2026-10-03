"""WP-120 phase C: ``GET /revue/carte`` — La Carte, the learner's Papiers on a map.

Same gate as every Revue route (``revue.py``): a plain 404 while
``settings.REVUE_ENABLED`` is off, checked before authentication (copied here, not
imported, so the map does not couple to the encounter's router). A pure read, cached
per learner for a minute: no provider call, so no paid-route guard.

WP-121 A.3: ``GET /revue/carte/review/{place_id}`` (the due words of one place, posed
with the journey's recall formats) and ``POST …/grade`` (graded on the server, scheduled
through the existing SRS). No model call either.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.db.models.user import User
from app.schemas.revue_carte import (
    CarteReview,
    CarteReviewGrade,
    CarteReviewGradeRequest,
    CarteView,
)
from app.services.revue.carte import ReviewError, grade_review, pins_for, review_for


def require_revue_enabled() -> None:
    if not getattr(settings, "REVUE_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(prefix="/revue", tags=["revue"], dependencies=[Depends(require_revue_enabled)])


@router.get("/carte", response_model=CarteView)
def read_carte(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CarteView:
    """The learner's pins (closed Papiers with a place), «Mon quartier», counts per level."""

    return pins_for(db, current_user)


@router.get("/carte/review/{place_id}", response_model=CarteReview)
def read_carte_review(
    place_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CarteReview:
    """WP-121 A.3: the due words met at this place, what carried them, and the items to pose."""

    return review_for(db, current_user, place_id)


@router.post("/carte/review/{place_id}/grade", response_model=CarteReviewGrade)
def grade_carte_review(
    place_id: str,
    payload: CarteReviewGradeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CarteReviewGrade:
    """WP-121 A.3: grade one item on the server and move its cards through the SRS."""

    try:
        result = grade_review(
            db, current_user, place_id,
            item_id=payload.item_id, tile_ids=payload.tile_ids, text=payload.text, assisted=payload.assisted,
        )
    except ReviewError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status, detail=exc.code) from exc
    db.commit()
    return result
