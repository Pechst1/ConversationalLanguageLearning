"""WP-120 phase B: ``GET /revue/vignettes`` — the learner's minted vignettes.

Same gate as every Revue route (``revue.py``): a plain 404 while
``settings.REVUE_ENABLED`` is off, checked before authentication. A read only: no
provider call, so no paid-route guard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints.revue import require_revue_enabled
from app.db.models.user import User
from app.schemas.revue_vignette import VignettesResponse
from app.services.revue.vignette import vignettes_for

router = APIRouter(prefix="/revue", tags=["revue"], dependencies=[Depends(require_revue_enabled)])


@router.get("/vignettes", response_model=VignettesResponse)
def read_vignettes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VignettesResponse:
    return VignettesResponse(vignettes=vignettes_for(db, current_user.id))
