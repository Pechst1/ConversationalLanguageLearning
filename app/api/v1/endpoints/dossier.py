"""WP-35 — «Votre dossier»: the API for the inspectable learner model.

Three routes, one envelope, the existing ``get_current_user`` dependency. No new
token path, no demo bypass: a learner model is the most personal payload in the
product and it is served to its owner or to nobody.

Two rules the transport keeps rather than the client:

* **The accepted answers never cross the wire.** ``ClaimItem.as_public`` is the
  only serializer the routes can reach, and it has no ``accepted`` field —
  shipping the answer with the question is the defect ``_review_task_payload``
  already had to fix once.
* **The claim is recorded on the way in and on the way out.** Opening a check
  writes a ``claimed`` row; submitting it writes a ``checked`` row with the
  verdict. Only the verified branch ever advances a schedule, and it does so
  through the SRS services, never here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services.learner_model import (
    CLAIM_ITEMS_REQUIRED,
    CLAIM_KINDS,
    DOSSIER_VERSION,
    ClaimRefused,
    build_claim_check,
    build_dossier,
    record_claim_opened,
    verify_claim,
)

router = APIRouter(prefix="/dossier", tags=["dossier"])

#: One French sentence per refusal. The page prints them as they arrive.
_REFUSAL_FR: dict[str, str] = {
    "unknown_claim_kind": "On ne peut déclarer connaître qu’un mot ou une faute notée.",
}
_REFUSAL_FALLBACK = "Cette action n’est pas possible pour l’instant."


class ClaimRequest(BaseModel):
    """«Je connais déjà », on one erratum or one word."""

    kind: str = Field(min_length=1, max_length=32)
    target_id: str = Field(min_length=1, max_length=64)


class ClaimAnswers(ClaimRequest):
    answers: list[str] = Field(default_factory=list)


class DossierEnvelope(BaseModel):
    """One shape for every route, so the page renders one state machine."""

    version: str = DOSSIER_VERSION
    #: The whole model. Present on the read and after a verification, absent
    #: while a check is being opened — opening a check changes no belief.
    dossier: dict | None = None
    #: The two questions, without their answers.
    check: dict | None = None
    #: What the check found, and whether anything moved.
    verdict: dict | None = None
    items_required: int = CLAIM_ITEMS_REQUIRED
    claim_kinds: list[str] = Field(default_factory=lambda: list(CLAIM_KINDS))


def _refuse(code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message_fr": _REFUSAL_FR.get(code, _REFUSAL_FALLBACK)},
    )


@router.get("/state", response_model=DossierEnvelope)
def read_dossier(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DossierEnvelope:
    """What the app believes about this learner, and why. A read, start to end."""

    return DossierEnvelope(dossier=build_dossier(db, user=current_user).as_dict())


@router.post("/claims", response_model=DossierEnvelope)
def open_claim(
    payload: ClaimRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DossierEnvelope:
    """Open the check behind «je connais déjà», and record that it was claimed."""

    try:
        check = build_claim_check(
            db, user=current_user, kind=payload.kind, target_id=payload.target_id
        )
    except ClaimRefused as refused:
        raise _refuse(refused.code) from refused
    record_claim_opened(db, user=current_user, check=check)
    db.commit()
    return DossierEnvelope(check=check.as_public())


@router.post("/claims/verify", response_model=DossierEnvelope)
def verify(
    payload: ClaimAnswers,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DossierEnvelope:
    """Grade the two items. Both right advances the schedule; anything else does not."""

    try:
        verdict = verify_claim(
            db,
            user=current_user,
            kind=payload.kind,
            target_id=payload.target_id,
            answers=list(payload.answers),
        )
    except ClaimRefused as refused:
        raise _refuse(refused.code) from refused
    db.commit()
    return DossierEnvelope(
        dossier=build_dossier(db, user=current_user).as_dict(),
        verdict=verdict.as_public(),
    )
