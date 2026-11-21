"""«La une de la semaine» and «La carte de presse» (owner 2026-11-21, ``REVUE_UNE_ENABLED``).

Both are pure reads of ONE learner's closed ``revue_sessions`` (the ``artifact`` event, the
``closed`` event's closing, the dossier snapshot); no model call, nothing written.

**La une.** A front page composed only from what the learner filed in an ISO week (Europe/Paris):
each filed rubrique becomes an item — their headline over the story («Le titre»), their opinion
as the vox-pop line («Au comptoir»), their retelling as a brief («Le fil»), their score and right
corrections as the «rectificatif» («L'intox express»), and, once those branches file, their
caption under its picture («La photo») and their interview as a pull quote («Le micro»).

* **Text as printed.** An item prints the artifact's ``text_fr`` — what «La page» printed after
  Romy's check (``proof`` ``clean`` | ``fixed`` | ``corrected``) — never ``learner_fr`` (the raw
  draft). A piece printed ``as_written`` (no check ran) and a chat-mode make (its text is the
  learner's draft) give no item; they still count as pieces and their words still go to the
  Lexique.
* **The editorial rule.** A ``titre`` leads (the latest first); then the rest by the length of
  their printed text, longest first; ties by filing time.
* The story's first picture and its credit, the week's «Lexique» (the closes' kept words, each
  once, in filing order), the count of distinct rubriques of :data:`RUBRIQUES` filed.

**La carte de presse.** Which of the six rubriques the learner has filed, how many pieces, since
when. No points, no streak.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select

from app.db.models.revue_session import RevueSession
from app.schemas.revue import RvPicture
from app.schemas.revue_rendez_vous import (
    RUBRIQUES,
    RvCarteDePresse,
    RvCarteRubrique,
    RvUneItem,
    RvUneSemaine,
)
from app.services.revue.souvenirs import FR_DAYS, QUOTABLE_PROOFS, _aware, _events, _payload

PARIS = ZoneInfo("Europe/Paris")
ROLES = {"titre": "headline", "photo": "caption", "micro": "quote", "opinion": "vox", "fil": "brief",
         "intox": "rectificatif"}
#: Rubriques whose printed text is app-composed from graded answers (no draft to correct).
NO_PROOF_NEEDED = frozenset({"intox"})


def current_week(now: datetime | None = None) -> str:
    year, number, _ = (now or datetime.now(UTC)).astimezone(PARIS).isocalendar()
    return f"{year}-W{number:02d}"


def week_days(week: str) -> tuple[date, date]:
    year, number = week.split("-W")
    monday = date.fromisocalendar(int(year), int(number), 1)
    return monday, monday + timedelta(days=6)


def _closed_rows(db: Any, user_id: Any, *, since: datetime | None = None, until: datetime | None = None) -> list[RevueSession]:
    """The learner's closed sessions, oldest first; the window is applied here, on aware datetimes."""

    rows = db.scalars(select(RevueSession).where(RevueSession.user_id == user_id, RevueSession.status == "closed")).all()
    out = [r for r in rows if r.closed_at is not None]
    if since is not None:
        out = [r for r in out if _aware(r.closed_at) >= since]
    if until is not None:
        out = [r for r in out if _aware(r.closed_at) < until]
    return sorted(out, key=lambda r: (_aware(r.closed_at), str(r.id)))


def _artifact(row: Any) -> dict[str, Any] | None:
    artifacts = [_payload(e) for e in _events(row) if e.get("kind") == "artifact"]
    return artifacts[-1] if artifacts else None


def _closing(row: Any) -> dict[str, Any]:
    closed = [_payload(e).get("closing") for e in _events(row) if e.get("kind") == "closed"]
    return closed[-1] if closed and isinstance(closed[-1], dict) else {}


def _snapshot(row: Any) -> dict[str, Any]:
    for event in _events(row):
        payload = _payload(event)
        if event.get("kind") == "choice" and payload.get("kind") == "dossier" and isinstance(payload.get("snapshot"), dict):
            return payload["snapshot"]
    return {}


def _kept(closing: dict[str, Any]) -> list[str]:
    kept = closing.get("kept") if isinstance(closing.get("kept"), dict) else {}
    return [str(w["fr"]) for w in kept.get("words") or [] if isinstance(w, dict) and w.get("fr")]


def _picture(db: Any, row: Any) -> RvPicture | None:
    """The story's first picture (painted or photo) with its credit, else its dispatch's picture."""

    try:
        from app.services.revue.encounter import load
        from app.services.revue.photos import gallery_for

        pictures = gallery_for(db, load(row).dossier)
        if pictures:
            return pictures[0]
    except Exception as exc:  # noqa: BLE001 - an item prints without its picture
        logger.debug("une: no gallery for {} ({})", row.id, exc)
    dispatch = _closing(row).get("dispatch") if isinstance(_closing(row).get("dispatch"), dict) else {}
    if dispatch.get("picture_url"):
        return RvPicture(kind="illustration", url=str(dispatch["picture_url"]), credit_fr="Illustration · Le Papier")
    return None


def printed_text(kind: str, artifact: dict[str, Any]) -> str | None:
    """The artifact's text as «La page» printed it, or ``None`` when it may not be reprinted."""

    text = str(artifact.get("text_fr") or "").strip()
    if not text or kind not in ROLES:
        return None
    if kind not in NO_PROOF_NEEDED and artifact.get("proof") not in QUOTABLE_PROOFS:
        return None
    return text


def item_of(db: Any, row: Any) -> RvUneItem | None:
    artifact = _artifact(row)
    if artifact is None:
        return None
    kind = str(artifact.get("kind") or "")
    text = printed_text(kind, artifact)
    if text is None:
        return None
    closing = _closing(row)
    snapshot = _snapshot(row)
    when = _aware(row.closed_at).astimezone(PARIS)  # type: ignore[union-attr]
    corrections: list[str] = []
    total = None
    if kind == "intox":
        page = closing.get("intox_page") if isinstance(closing.get("intox_page"), dict) else {}
        corrections = [str(line["learner_fr"]) for line in page.get("lines") or []
                       if isinstance(line, dict) and line.get("learner_fr") and line.get("fixed_right")]
        total = page.get("total") if isinstance(page.get("total"), int) else None
    title = str(snapshot.get("title_fr") or (closing.get("dispatch") or {}).get("headline_fr") or "")
    return RvUneItem(
        session_id=str(row.id),
        rubrique=kind,  # type: ignore[arg-type]
        role=ROLES[kind],  # type: ignore[arg-type]
        story_title_fr=title,
        text_fr=text,
        score=artifact.get("score") if kind == "intox" and isinstance(artifact.get("score"), int) else None,
        total=total,
        corrections_fr=corrections,
        stance=artifact.get("stance") if kind == "opinion" and artifact.get("stance") in {"pour", "contre", "nuance"} else None,
        picture=_picture(db, row),
        filed_on=when.date().isoformat(),
        filed_weekday_fr=FR_DAYS[when.weekday()],
    )


def editorial_order(items: list[RvUneItem]) -> list[RvUneItem]:
    """A ``titre`` leads (the latest first); then the longest printed text; ties by filing time."""

    titres = sorted((i for i in items if i.rubrique == "titre"), key=lambda i: i.filed_on, reverse=True)
    rest = sorted((i for i in items if i.rubrique != "titre"), key=lambda i: (-len(i.text_fr), i.filed_on, i.session_id))
    return titres + rest


def une_semaine(db: Any, user_id: Any, week: str | None = None, *, now: datetime | None = None) -> RvUneSemaine:
    from app.services.revue.encounter import week_view

    now = now or datetime.now(UTC)
    week = week or current_week(now)
    monday, sunday = week_days(week)
    start = datetime.combine(monday, datetime.min.time(), tzinfo=PARIS)
    rows = _closed_rows(db, user_id, since=start, until=start + timedelta(days=7))
    items = [item for item in (item_of(db, row) for row in rows) if item is not None]
    lexique = list(dict.fromkeys(word for row in rows for word in _kept(_closing(row))))
    filed = {str((_artifact(row) or {}).get("kind")) for row in rows} & set(RUBRIQUES)
    pieces = sum(1 for row in rows if _artifact(row) is not None)
    view = week_view(week)
    today = now.astimezone(PARIS).date()
    return RvUneSemaine(
        week=view,
        dateline_fr=f"{view.label} · {view.range}",
        items=editorial_order(items),
        lexique=lexique,
        rubriques_filed=len(filed),
        pieces=pieces,
        due_today=week == current_week(now) and today == sunday and len(items) >= 2,
    )


def carte_de_presse(db: Any, user_id: Any) -> RvCarteDePresse:
    rows = _closed_rows(db, user_id)
    per: dict[str, list[datetime]] = {kind: [] for kind in RUBRIQUES}
    firsts: list[datetime] = []
    for row in rows:
        artifact = _artifact(row)
        if artifact is None:
            continue
        when = _aware(row.closed_at)
        firsts.append(when)  # type: ignore[arg-type]
        kind = str(artifact.get("kind") or "")
        if kind in per:
            per[kind].append(when)  # type: ignore[arg-type]
    return RvCarteDePresse(
        rubriques=[RvCarteRubrique(rubrique=kind, pieces=len(per[kind]),  # type: ignore[arg-type]
                                   first_on=min(per[kind]).astimezone(PARIS).date().isoformat() if per[kind] else None)
                   for kind in RUBRIQUES],
        pieces=len(firsts),
        since=min(firsts).astimezone(PARIS).date().isoformat() if firsts else None,
    )


__all__ = ["carte_de_presse", "current_week", "editorial_order", "item_of", "printed_text", "une_semaine", "week_days"]
