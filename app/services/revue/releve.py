"""Le Papier in Le Relevé (WP-119 phase 3; design §3.6 #releve).

One entry per filed Papier, newest first: the period, the title, what the learner made,
the claims they read with their source lines, and the words with their glosses — all read
from the session's own close (``closed`` event, ``RvClosing.kept``), so the Relevé shows
exactly what the close showed. A pure read: no provider, no cache.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueSession
from app.services.revue.carte import _artifact, _closing, _events, _snapshot

#: The Relevé shows the last year of Papiers at most.
MAX_ENTRIES = 60


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ReleveSource(_Model):
    id: str
    name: str
    url: str
    published_at: str


class ReleveClaim(_Model):
    id: str
    kind: str
    fr: str
    quote: str
    attributed_to: str | None = None
    source: ReleveSource


class ReleveWord(_Model):
    fr: str
    gloss: str
    claim_id: str
    used: bool = False


class ReleveMade(_Model):
    kind: str
    text_fr: str


class ReleveEntry(_Model):
    session_id: str
    period: str
    period_label: str
    closed_at: str | None
    title_fr: str
    headline_fr: str | None = None
    made: ReleveMade | None = None
    claims: list[ReleveClaim]
    words: list[ReleveWord]
    sources: list[ReleveSource]
    #: A second Papier in the same period (§12.2: counts for evidence, never "filed").
    second: bool = False


class ReleveView(_Model):
    entries: list[ReleveEntry]


def _period_label(period: str) -> str:
    from app.services.revue.dossier import parse_week
    from app.services.revue.weekly import week_of_period

    try:
        _, number = parse_week(week_of_period(period))
    except ValueError:
        return period
    return f"Semaine {number}"


def _source(raw: Any) -> ReleveSource | None:
    if not isinstance(raw, dict) or not raw.get("name"):
        return None
    return ReleveSource(
        id=str(raw.get("id") or raw["name"]),
        name=str(raw["name"]),
        url=str(raw.get("url") or ""),
        published_at=str(raw.get("published_at") or "")[:10],
    )


def entry_of(row: RevueSession, *, second: bool = False) -> ReleveEntry:
    events = _events(row.state)
    snapshot = _snapshot(events)
    closing = _closing(events)
    kept = closing.get("kept") if isinstance(closing.get("kept"), dict) else {}
    dispatch = closing.get("dispatch") if isinstance(closing.get("dispatch"), dict) else {}
    claims: list[ReleveClaim] = []
    for raw in kept.get("claims") or []:
        source = _source((raw or {}).get("source"))
        if not isinstance(raw, dict) or source is None or not raw.get("fr"):
            continue
        claims.append(
            ReleveClaim(
                id=str(raw.get("id") or ""),
                kind=str(raw.get("kind") or "fact"),
                fr=str(raw["fr"]),
                quote=str(raw.get("quote") or ""),
                attributed_to=raw.get("attributed_to"),
                source=source,
            )
        )
    words = [
        ReleveWord(fr=str(w["fr"]), gloss=str(w.get("gloss") or ""), claim_id=str(w.get("claim_id") or ""), used=bool(w.get("used")))
        for w in kept.get("words") or []
        if isinstance(w, dict) and w.get("fr")
    ]
    sources = [s for s in (_source(raw) for raw in dispatch.get("sources") or []) if s is not None]
    if not sources:
        sources = list({c.source.id: c.source for c in claims}.values())
    artifact = _artifact(events)
    made = (
        ReleveMade(kind=str(artifact.get("kind")), text_fr=str(artifact.get("text_fr")))
        if artifact and artifact.get("kind") and artifact.get("text_fr")
        else None
    )
    return ReleveEntry(
        session_id=str(row.id),
        period=row.week,
        period_label=_period_label(row.week),
        closed_at=row.closed_at.isoformat() if row.closed_at else None,
        title_fr=str(snapshot.get("title_fr") or row.dossier_id),
        headline_fr=str(dispatch["headline_fr"]) if dispatch.get("headline_fr") else None,
        made=made,
        claims=claims,
        words=words,
        sources=sources,
        second=second,
    )


def releve_for(db: Session, user: Any) -> ReleveView:
    rows = list(
        db.scalars(
            select(RevueSession)
            .where(RevueSession.user_id == user.id, RevueSession.status == "closed")
            .order_by(RevueSession.closed_at.desc(), RevueSession.started_at.desc())
            .limit(MAX_ENTRIES)
        )
    )
    first_of: dict[str, Any] = {}
    for row in rows:  # newest first: the last one seen per period is its first Papier
        first_of[row.week] = row.id
    return ReleveView(entries=[entry_of(row, second=first_of.get(row.week) != row.id) for row in rows])


__all__ = ["ReleveEntry", "ReleveView", "entry_of", "releve_for"]
