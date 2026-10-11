"""Minting the vignette at close, and reading the learner's vignettes back (WP-120 §4.3).

At ``close`` the encounter mints one ``revue_vignettes`` row per session (idempotent:
``session_id`` is unique): the ring follows what the learner made (:func:`ring_for`),
``kept_contribution`` says whether their part survived into the dispatch. The
pictogram is shared per dossier (:func:`app.services.revue.pictogram.pictogram_for`).

:func:`vignettes_for` composes each stamp's data for ``GET /revue/vignettes``. It reads
the session's state JSON directly (the dossier snapshot and the closing) rather than
importing the encounter, and never calls a provider: a dossier without a stored
pictogram shows its topic fallback.

The hook in ``RevueEncounter.close`` is :func:`mint_for_close`.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.schemas.revue_vignette import VignetteView
from app.services.revue.pictogram import PictogramProvider, fallback_svg, pictogram_for

Ring = Literal["headline", "question", "report"]

#: What the learner made → the ring's colour (ink · blue · red).
RING_BY_MAKE: dict[str, Ring] = {
    "headline_choice": "headline",
    "headline_write": "headline",
    "reader_question": "question",
    "short_report": "report",
    "tell_margaux": "report",
}


def ring_for(make_option: str | None) -> Ring:
    """``headline_choice``/``headline_write`` → headline, ``reader_question`` → question,
    ``short_report`` (and ``tell_margaux``) → report; nothing made → headline (the dispatch still has one)."""

    return RING_BY_MAKE.get(str(make_option or ""), "headline")


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def mint(
    db: Session,
    *,
    user_id: Any,
    session_id: Any,
    dossier_id: str,
    ring: Ring,
    kept_contribution: bool,
    week: str,
    place_label_fr: str,
) -> RevueVignette:
    """The session's vignette; minted once, returned as it is on every later call."""

    sid = _uuid(session_id)
    existing = db.scalar(select(RevueVignette).where(RevueVignette.session_id == sid))
    if existing is not None:
        return existing
    if ring not in RING_BY_MAKE.values():
        raise ValueError(f"ring must be headline, question or report, got {ring!r}")
    row = RevueVignette(
        user_id=_uuid(user_id),
        session_id=sid,
        dossier_id=str(dossier_id),
        ring=ring,
        kept_contribution=bool(kept_contribution),
        week=str(week),
        place_label_fr=str(place_label_fr or "")[:200],
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(RevueVignette).where(RevueVignette.session_id == sid))
        if existing is None:
            raise
        return existing
    return row


def mint_for_close(
    db: Session,
    *,
    row: RevueSession,
    dossier: Any,
    make_option: str | None,
    kept_contribution: bool,
    place_label_fr: str,
    provider: PictogramProvider | None = None,
) -> RevueVignette | None:
    """The close hook: draw (or reuse) the dossier's pictogram, then mint. Never raises.

    A failure here must not cost the learner their Papier: it is logged and the close
    goes on without a vignette.
    """

    try:
        if provider is not None:
            pictogram_for(db, dossier, provider)
        return mint(
            db,
            user_id=row.user_id,
            session_id=row.id,
            dossier_id=str(dossier.id),
            ring=ring_for(make_option),
            kept_contribution=kept_contribution,
            week=row.week,
            place_label_fr=place_label_fr,
        )
    except Exception as exc:  # noqa: BLE001
        logger.bind(session_id=str(row.id)).warning("revue vignette: mint failed ({})", exc)
        return None


def _snapshot(state: dict[str, Any] | None) -> dict[str, Any]:
    for event in (state or {}).get("events") or []:
        payload = event.get("payload") or {}
        if event.get("kind") == "choice" and payload.get("kind") == "dossier" and isinstance(payload.get("snapshot"), dict):
            return payload["snapshot"]
    return {}


def _filed_headline(state: dict[str, Any] | None) -> str | None:
    closed = [e for e in (state or {}).get("events") or [] if e.get("kind") == "closed"]
    if not closed:
        return None
    closing = (closed[-1].get("payload") or {}).get("closing") or {}
    headline = (closing.get("dispatch") or {}).get("headline_fr")
    return str(headline) if headline else None


def vignettes_for(db: Session, user_id: Any) -> list[VignetteView]:
    """The learner's minted vignettes, newest first, each with its composed data."""

    uid = _uuid(user_id)
    rows = db.execute(
        select(RevueVignette, RevueSession)
        .join(RevueSession, RevueSession.id == RevueVignette.session_id, isouter=True)
        .where(RevueVignette.user_id == uid)
        .order_by(RevueVignette.minted_at.desc(), RevueVignette.week.desc())
    ).all()
    dossier_ids = {vignette.dossier_id for vignette, _ in rows}
    pictograms = (
        {p.dossier_id: p.svg for p in db.scalars(select(RevuePictogram).where(RevuePictogram.dossier_id.in_(dossier_ids)))}
        if dossier_ids
        else {}
    )
    views: list[VignetteView] = []
    for vignette, session in rows:
        state = session.state if session is not None else None
        snapshot = _snapshot(state)
        svg = pictograms.get(vignette.dossier_id) or fallback_svg(snapshot.get("topic"))
        headline = _filed_headline(state) or str(snapshot.get("title_fr") or "")
        views.append(
            VignetteView(
                id=str(vignette.id),
                session_id=str(vignette.session_id),
                dossier_id=vignette.dossier_id,
                week=vignette.week,
                place_label_fr=vignette.place_label_fr,
                ring=vignette.ring,  # type: ignore[arg-type]
                kept_contribution=bool(vignette.kept_contribution),
                pictogram_svg=svg,
                headline_fr=headline,
                minted_at=vignette.minted_at,
            )
        )
    return views

def view_of(db: Session, vignette: RevueVignette) -> VignetteView:
    """One minted vignette composed for the wire (the close response carries it, WP-120 §4.3)."""

    from app.db.models.revue_session import RevueSession

    session = db.get(RevueSession, vignette.session_id)
    state = session.state if session is not None else None
    snapshot = _snapshot(state)
    pictogram = db.get(RevuePictogram, vignette.dossier_id)
    svg = (pictogram.svg if pictogram is not None else None) or fallback_svg(snapshot.get("topic"))
    headline = _filed_headline(state) or str(snapshot.get("title_fr") or "")
    return VignetteView(
        id=str(vignette.id),
        session_id=str(vignette.session_id),
        dossier_id=vignette.dossier_id,
        week=vignette.week,
        place_label_fr=vignette.place_label_fr,
        ring=vignette.ring,  # type: ignore[arg-type]
        kept_contribution=bool(vignette.kept_contribution),
        pictogram_svg=svg,
        headline_fr=headline,
        minted_at=vignette.minted_at,
    )
