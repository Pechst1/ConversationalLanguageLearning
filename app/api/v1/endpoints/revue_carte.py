"""WP-120 phase C: ``GET /revue/carte`` — La Carte, the learner's Papiers on a map.

Same gate as every Revue route (``revue.py``): a plain 404 while
``settings.REVUE_ENABLED`` is off, checked before authentication (copied here, not
imported, so the map does not couple to the encounter's router). A pure read, cached
per learner for a minute: no provider call, so no paid-route guard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.db.models.user import User
from app.schemas.revue_carte import CarteView
from app.services.revue.carte import pins_for


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
