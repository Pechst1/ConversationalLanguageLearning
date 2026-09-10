"""WP-34 — «Apportez votre français» : the API for a document the learner brought.

Authenticated with the Courrier's own dependency (``get_atelier_user``), and
deliberately so: the task an artefact produces is an ordinary
:class:`RealWorldMission` answered through ``POST /missions/{id}/submit``, which
resolves its learner the same way. Two different identity resolvers on the two
halves of one loop would mean an artefact whose task belonged to somebody else.

Three rules the transport keeps rather than the client:

* **Every refusal is a French sentence**, not a stack trace. A learner at the
  weekly cap, a photo too large, a paste too short — each one is a 409 or 413
  carrying copy the page prints as it stands.
* **The document leaves by one door only.** :func:`app.services.intake.public_view`
  is the only serializer, and these routes have no other way to emit an artefact.
* **Deletion is real.** ``DELETE`` removes the artefact and the Courrier task
  derived from it, and answers 204 either way it is called twice.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import get_atelier_user
from app.config import settings
from app.db.models.user import User
from app.services.intake import (
    INTAKE_VERSION,
    MAX_UNKNOWN_WORDS,
    SOURCE_TEXT_MAX_CHARS,
    IntakeRefused,
    IntakeService,
    cap_state,
    public_view,
)
from app.services.missions import serialize_mission

router = APIRouter(prefix="/intake", tags=["intake"])

#: One French sentence per refusal code. The page prints them verbatim, so a new
#: code without a sentence here shows up as the fallback line — visible, not silent.
_REFUSAL_FR: dict[str, str] = {
    "intake_disabled": "La lecture de vos documents est désactivée pour l’instant.",
    "weekly_cap_reached": (
        "Vous avez déjà fait lire vos documents de la semaine. Le prochain se libère bientôt."
    ),
    "cost_ceiling_reached": (
        "Le budget de lecture de la semaine est atteint. Réessayez dans quelques jours."
    ),
    "document_too_short": "Collez un peu plus de texte : quelques mots ne font pas un document.",
    "image_type_unsupported": "Ce format d’image n’est pas lisible. Essayez une photo JPEG ou PNG.",
    "image_empty": "La photo est vide. Reprenez-la, puis réessayez.",
    "image_too_large": "La photo est trop lourde. Reprenez-la de plus près, puis réessayez.",
    "image_undecodable": "La photo n’a pas pu être lue. Reprenez-la, puis réessayez.",
}
_REFUSAL_FALLBACK = "Cette action n’est pas possible pour l’instant."

#: Codes that are about the payload the learner sent, not about their allowance.
_BAD_REQUEST_CODES = frozenset(
    {"document_too_short", "image_type_unsupported", "image_empty", "image_undecodable"}
)


class IntakeCapView(BaseModel):
    """The weekly bound, as the learner sees it."""

    limit: int
    used: int
    remaining: int
    spent_usd: float
    ceiling_usd: float
    enabled: bool


class IntakeEnvelope(BaseModel):
    """One shape for every intake route, so the page renders one state machine."""

    version: str = INTAKE_VERSION
    #: The artefact this request is about, when there is one.
    artefact: dict | None = None
    #: The Courrier task derived from it, already serialized as a mission.
    mission: dict | None = None
    #: Everything the learner has brought in, newest first.
    artefacts: list[dict] = Field(default_factory=list)
    cap: IntakeCapView
    max_text_chars: int = SOURCE_TEXT_MAX_CHARS
    max_image_bytes: int = Field(default_factory=lambda: int(settings.ATELIER_INTAKE_MAX_IMAGE_BYTES))
    max_unknown_words: int = MAX_UNKNOWN_WORDS


class IntakeTextRequest(BaseModel):
    text: str = Field(default="", max_length=SOURCE_TEXT_MAX_CHARS * 2)


def _refused(exc: IntakeRefused) -> HTTPException:
    code = exc.code
    if code == "image_too_large":
        http_status = status.HTTP_413_CONTENT_TOO_LARGE
    elif code in _BAD_REQUEST_CODES:
        http_status = status.HTTP_400_BAD_REQUEST
    else:
        http_status = status.HTTP_409_CONFLICT
    return HTTPException(
        status_code=http_status,
        detail={"code": code, "message_fr": _REFUSAL_FR.get(code, _REFUSAL_FALLBACK)},
    )


def _cap_view(db: Session, user: User) -> IntakeCapView:
    return IntakeCapView(**cap_state(db, user).as_dict())


def _envelope(
    db: Session,
    user: User,
    *,
    artefact=None,
    include_list: bool = True,
) -> IntakeEnvelope:
    service = IntakeService(db)
    mission = None
    if artefact is not None and artefact.mission_id:
        from app.db.models.mission import RealWorldMission

        row = db.get(RealWorldMission, artefact.mission_id)
        if row is not None and row.user_id == user.id:
            mission = serialize_mission(row)
    return IntakeEnvelope(
        artefact=public_view(artefact),
        mission=mission,
        artefacts=[
            view
            for view in (public_view(row) for row in (service.list_for(user) if include_list else []))
            if view
        ],
        cap=_cap_view(db, user),
    )


@router.get("", response_model=IntakeEnvelope)
@router.get("/", response_model=IntakeEnvelope)
def list_artefacts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> IntakeEnvelope:
    """Everything this learner has brought in, and how much allowance is left."""

    return _envelope(db, current_user)


@router.post("/text", response_model=IntakeEnvelope)
def submit_text(
    request: IntakeTextRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> IntakeEnvelope:
    """Read one pasted document. Costs exactly one model call."""

    try:
        artefact = IntakeService(db).submit_text(current_user, text=request.text)
    except IntakeRefused as exc:
        raise _refused(exc) from exc
    return _envelope(db, current_user, artefact=artefact)


@router.post("/photo", response_model=IntakeEnvelope)
async def submit_photo(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> IntakeEnvelope:
    """Read one photographed document.

    The bytes are read to one byte past the ceiling and no further, so an
    oversized upload is refused without ever being held whole in memory, and they
    are never written anywhere: what survives the request is the reading.
    """

    ceiling = int(settings.ATELIER_INTAKE_MAX_IMAGE_BYTES)
    data = await file.read(ceiling + 1)
    try:
        artefact = IntakeService(db).submit_image(
            current_user, data=data, content_type=file.content_type or ""
        )
    except IntakeRefused as exc:
        raise _refused(exc) from exc
    return _envelope(db, current_user, artefact=artefact)


@router.get("/{artefact_id}", response_model=IntakeEnvelope)
def get_artefact(
    artefact_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> IntakeEnvelope:
    artefact = IntakeService(db).get(current_user, artefact_id)
    if artefact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artefact not found")
    return _envelope(db, current_user, artefact=artefact, include_list=False)


@router.delete("/{artefact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artefact(
    artefact_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> Response:
    """Delete the artefact and the Courrier task derived from it.

    Answers 204 whether or not the row was there. A learner deleting a document
    twice must not be told which of their documents exist.
    """

    IntakeService(db).delete(current_user, artefact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
