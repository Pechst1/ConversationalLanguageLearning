"""WP-95 «Le Carnet» — what the learner can do in French, band by band."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_or_demo, get_db
from app.db.models.user import User
from app.schemas.progress import CarnetResponse
from app.services.can_do import carnet_payload
from app.services.cefr_progress import CEFRProgressService

router = APIRouter(prefix="/can-dos", tags=["progress"])


@router.get("", response_model=CarnetResponse)
def get_carnet(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo),
) -> CarnetResponse:
    """Every sub-band's can-dos, each with its Seal once story evidence pressed it."""

    level = CEFRProgressService(db).current(current_user)
    return CarnetResponse(
        **carnet_payload(
            db,
            current_user.id,
            current_band=str(level.get("estimate") or "A1.1"),
            native_language=getattr(current_user, "native_language", None),
        )
    )
