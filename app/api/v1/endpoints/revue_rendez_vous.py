"""«Papier · les rendez-vous» (owner 2026-11-21): the routes of the regulars' memory, «Trois mots»,
«La une de la semaine» and «La carte de presse».

Each route answers a plain 404 unless ``REVUE_ENABLED`` and its own switch are on
(``REVUE_MEMORY_ENABLED``, ``REVUE_TROIS_MOTS_ENABLED``, ``REVUE_UNE_ENABLED``), so with the
switches off no existing payload changes and nothing new answers. No route calls a model.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints.revue import get_encounter, require_revue_enabled
from app.config import settings
from app.db.models.user import User
from app.schemas.revue_rendez_vous import (
    RvCarteDePresse,
    RvSouvenirResult,
    RvTroisMotsRequest,
    RvTroisMotsResult,
    RvUneSemaine,
)
from app.services.revue.encounter import RevueEncounter, RevueError, load, owned_session

router = APIRouter(prefix="/revue", tags=["revue"], dependencies=[Depends(require_revue_enabled)])

ISO_WEEK = r"^\d{4}-W\d{2}$"


def _switch(name: str):  # noqa: ANN202 - a FastAPI dependency
    """A dependency answering a bare 404 while ``name`` is off, before authentication."""

    def check() -> None:
        if not getattr(settings, name, False):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    return Depends(check)


MEMORY = [_switch("REVUE_MEMORY_ENABLED")]
TROIS_MOTS = [_switch("REVUE_TROIS_MOTS_ENABLED")]
UNE = [_switch("REVUE_UNE_ENABLED")]


def _http(error: RevueError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.detail)


@router.get("/sessions/{session_id}/souvenir", response_model=RvSouvenirResult, dependencies=MEMORY)
def read_souvenir(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RvSouvenirResult:
    """The regulars remember: ONE line for this session from the learner's earlier Papiers, or none."""

    from app.services.revue.souvenirs import line_for

    try:
        return RvSouvenirResult(line=line_for(db, owned_session(db, current_user, session_id)))
    except RevueError as error:
        raise _http(error) from error


@router.get("/sessions/{session_id}/trois-mots", response_model=RvTroisMotsResult, dependencies=TROIS_MOTS)
def read_trois_mots(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RvTroisMotsResult:
    """«Trois mots»: the closed session's round as it stands (``round`` ``None`` before the close)."""

    from app.services.revue import trois_mots

    try:
        loaded = load(owned_session(db, current_user, session_id))
    except RevueError as error:
        raise _http(error) from error
    round_ = trois_mots.build(loaded)
    return RvTroisMotsResult(round=trois_mots.view(loaded, round_) if round_ is not None else None)


@router.post("/sessions/{session_id}/trois-mots", response_model=RvTroisMotsResult, dependencies=TROIS_MOTS)
def post_trois_mots(
    session_id: str,
    body: RvTroisMotsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvTroisMotsResult:
    """One act of the round (``match`` all three pairs, then ``gap``); deterministic, no model call."""

    from app.services.revue import trois_mots

    try:
        loaded = load(owned_session(db, current_user, session_id, lock=True))
    except RevueError as error:
        raise _http(error) from error
    return trois_mots.act(encounter, loaded, body)


@router.get("/une", response_model=RvUneSemaine, dependencies=UNE)
def read_une(
    week: str | None = Query(None, pattern=ISO_WEEK),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RvUneSemaine:
    """«La une de la semaine»: the learner's own printed pieces of an ISO week (default: this one)."""

    from app.services.revue.une import une_semaine

    return une_semaine(db, current_user.id, week)


@router.get("/carte-de-presse", response_model=RvCarteDePresse, dependencies=UNE)
def read_carte_de_presse(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RvCarteDePresse:
    """«La carte de presse»: the rubriques the learner has filed, how many pieces, since when."""

    from app.services.revue.une import carte_de_presse

    return carte_de_presse(db, current_user.id)
