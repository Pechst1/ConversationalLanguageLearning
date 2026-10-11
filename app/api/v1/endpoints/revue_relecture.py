"""WP-121 B: La Relecture — re-answer your own Papier's question six weeks later.

* ``GET  /revue/relecture/offer`` — the oldest eligible Papier (or ``{"offer": null}``);
* ``POST /revue/relecture/{session_id}`` — the learner's new answer (text, or the
  transcript of a spoken one) → stored once in ``revue_relectures``, graded with the
  phase-2 rubric, answered with the pair; 409 when not yet eligible or already re-read;
* ``GET  /revue/relecture/{session_id}`` — the stored pair again.

Same flag gate as every Revue route (404 while ``REVUE_ENABLED`` is off, before auth).
The POST may call the critic model, so it carries the paid-route guard like the encounter.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.rate_limit import paid_route_guard
from app.db.models.user import User
from app.schemas.revue_relecture import RelectureAnswerRequest, RelectureOfferView, RelecturePair
from app.services.revue import grading, relecture
from app.services.revue.relecture import RelectureError


def require_revue_enabled() -> None:
    if not getattr(settings, "REVUE_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(prefix="/revue/relecture", tags=["revue"], dependencies=[Depends(require_revue_enabled)])


def get_relecture_scorer() -> grading.RubricScorer:
    """Injection seam: the encounter's scorer (the critic when a provider is configured)."""

    from app.services.revue.encounter import default_provider, scorer_for

    return scorer_for(default_provider())


def _raise(exc: RelectureError) -> None:
    raise HTTPException(status_code=exc.status, detail=exc.code) from exc


@router.get("/offer", response_model=RelectureOfferView)
def read_offer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RelectureOfferView:
    return RelectureOfferView(offer=relecture.offer(db, current_user))


@router.get("/{session_id}", response_model=RelecturePair)
def read_pair(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RelecturePair:
    try:
        return relecture.read(db, current_user, session_id)
    except RelectureError as exc:
        _raise(exc)
        raise  # pragma: no cover


@router.post(
    "/{session_id}",
    response_model=RelecturePair,
    dependencies=[Depends(paid_route_guard(get_current_user))],
)
def post_answer(
    session_id: str,
    payload: RelectureAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    scorer: grading.RubricScorer = Depends(get_relecture_scorer),
) -> RelecturePair:
    try:
        pair = relecture.answer(db, current_user, session_id, answer_fr=payload.answer_fr, mode=payload.mode, scorer=scorer)
    except RelectureError as exc:
        db.rollback()
        _raise(exc)
        raise  # pragma: no cover
    db.commit()
    return pair
