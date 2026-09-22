"""WP-72 — the privacy policy and the terms, served where App Store Connect can link them.

Two routers:

* ``public_router`` — ``GET /privacy`` and ``GET /terms`` at the API host's root,
  no sign-in. A small self-contained HTML page, so the App Store "Privacy Policy
  URL" can be ``https://<api-host>/privacy`` without a separate web host.
* ``api_router`` — ``POST/GET {API_V1_STR}/legal/consent``. Sign-up records that
  the learner accepted the terms, the privacy policy and AI processing, with the
  policy version and a timestamp.

Consent lives in the existing ``pilot_events`` ledger (``event_type="legal_consent"``,
JSON payload) because the ``users`` table has no free-form settings column and
this package adds no migration. The ledger row keeps ``occurred_at`` from the
server clock, never the client's.

The text is one JSON file (``app/data/legal/legal_content.json``); the web app
ships a byte-identical copy (``web-frontend/lib/legal-content.json``) so the
pages also work offline inside the native shell. A test keeps the two equal.
"""
from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services.pilot_events import PilotEventService

LEGAL_CONTENT_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "legal_content.json"
CONSENT_EVENT = "legal_consent"
SUPPORTED_LANGUAGES = ("en", "de", "fr")
DocumentKind = Literal["privacy", "terms"]


@lru_cache(maxsize=1)
def legal_content() -> dict[str, Any]:
    """The canonical legal text. Cached: it only changes with a deploy."""

    return json.loads(LEGAL_CONTENT_PATH.read_text(encoding="utf-8"))


def policy_version() -> str:
    return str(legal_content()["version"])


def resolve_language(explicit: str | None, accept_language: str | None) -> str:
    """``?lang=`` first, then the browser's ``Accept-Language`` order, then English."""

    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if accept_language:
        for part in accept_language.split(","):
            tag = part.split(";")[0].strip()
            if tag:
                candidates.append(tag)
    for candidate in candidates:
        base = candidate.lower().replace("_", "-").split("-")[0]
        if base in SUPPORTED_LANGUAGES:
            return base
    return "en"


def _fill(text: str, content: dict[str, Any]) -> str:
    """Escape, then substitute the two owner-filled placeholders."""

    escaped = html.escape(text, quote=False)
    contact = html.escape(str(content.get("contact_email") or ""))
    contact_html = (
        f'<a href="mailto:{contact}">{contact}</a>' if "@" in contact else contact
    )
    return escaped.replace("{contact}", contact_html).replace(
        "{operator}", html.escape(str(content.get("operator") or ""))
    )


def render_document(kind: DocumentKind, language: str) -> str:
    content = legal_content()
    doc = content["documents"][kind][language]
    labels = content["labels"][language]
    other: DocumentKind = "terms" if kind == "privacy" else "privacy"
    switcher = " · ".join(
        (
            f"<strong>{code.upper()}</strong>"
            if code == language
            else f'<a href="/{kind}?lang={code}" hreflang="{code}">{code.upper()}</a>'
        )
        for code in SUPPORTED_LANGUAGES
    )
    sections = "\n".join(
        "<section><h2>{}</h2>{}</section>".format(
            html.escape(section["h"]),
            "".join(f"<p>{_fill(p, content)}</p>" for p in section["p"]),
        )
        for section in doc["sections"]
    )
    return f"""<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(doc["title"])} · L’Atelier</title>
<style>
:root {{ --paper:#f1ece1; --ink:#14110d; --muted:#5c554b; --line:#d9d1c1; --blue:#1d3a8a; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --paper:#17140f; --ink:#f5efe1; --muted:#b5ad9f; --line:#3a342b; --blue:#7fa0ff; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--paper); color:var(--ink);
  font:17px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
main {{ max-width:40rem; margin:0 auto; padding:2rem 1rem 4rem; }}
nav {{ display:flex; justify-content:space-between; gap:1rem; font-size:.9rem; color:var(--muted); }}
h1 {{ font-family:Georgia, "Times New Roman", serif; font-style:italic; font-weight:400;
  font-size:2rem; line-height:1.15; margin:1.5rem 0 .25rem; }}
h2 {{ font-size:1rem; margin:1.75rem 0 .35rem; }}
p {{ margin:.35rem 0; }}
.meta {{ color:var(--muted); font-size:.9rem; }}
.lead {{ font-size:1.05rem; border-bottom:1px solid var(--line); padding-bottom:1rem; }}
a {{ color:var(--blue); }}
</style>
</head>
<body>
<main>
<nav><span>L’Atelier</span><span>{switcher}</span></nav>
<h1>{html.escape(doc["title"])}</h1>
<p class="meta">{html.escape(labels["updated"])} {html.escape(content["version"])}</p>
<p class="lead">{_fill(doc["lead"], content)}</p>
{sections}
<p class="meta"><a href="/{other}?lang={language}">{html.escape(labels[other])}</a></p>
</main>
</body>
</html>
"""


public_router = APIRouter(tags=["legal"])


def _document_response(kind: DocumentKind, lang: str | None, accept_language: str | None) -> HTMLResponse:
    language = resolve_language(lang, accept_language)
    return HTMLResponse(
        render_document(kind, language),
        headers={"Cache-Control": "public, max-age=3600", "Content-Language": language},
    )


@public_router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
def privacy_page(
    lang: Annotated[str | None, Query(max_length=16)] = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    return _document_response("privacy", lang, accept_language)


@public_router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
def terms_page(
    lang: Annotated[str | None, Query(max_length=16)] = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> HTMLResponse:
    return _document_response("terms", lang, accept_language)


api_router = APIRouter(prefix="/legal", tags=["legal"])


class ConsentRequest(BaseModel):
    version: str = Field(..., min_length=1, max_length=32)
    surface: Literal["signup", "settings", "reconsent"] = "signup"
    language: str | None = Field(None, max_length=16)


class ConsentStatus(BaseModel):
    current_version: str
    accepted_version: str | None = None
    accepted_at: datetime | None = None
    up_to_date: bool = False


def _latest_consent(db: Session, user: User) -> PilotEvent | None:
    return (
        db.query(PilotEvent)
        .filter(PilotEvent.user_id == user.id, PilotEvent.event_type == CONSENT_EVENT)
        .order_by(PilotEvent.occurred_at.desc())
        .first()
    )


def _status(event: PilotEvent | None) -> ConsentStatus:
    current = policy_version()
    if event is None:
        return ConsentStatus(current_version=current)
    accepted = str((event.payload or {}).get("version") or "") or None
    return ConsentStatus(
        current_version=current,
        accepted_version=accepted,
        accepted_at=event.occurred_at,
        up_to_date=accepted == current,
    )


@api_router.post("/consent", response_model=ConsentStatus, status_code=status.HTTP_201_CREATED)
def record_consent(
    payload: ConsentRequest,
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> ConsentStatus:
    """Record acceptance of the terms, the privacy policy and AI processing.

    Only the version the server is currently serving can be accepted: a client
    holding stale text must not record consent to words it never showed.
    """

    current = policy_version()
    if payload.version != current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy version {payload.version!r} is not current ({current}).",
        )
    event = PilotEventService(db).record(
        CONSENT_EVENT,
        user_id=current_user.id,
        entity_type="legal",
        entity_id=current,
        payload={
            "version": current,
            "documents": ["terms", "privacy"],
            "ai_processing": True,
            "ai_provider": "openai",
            "surface": payload.surface,
            "language": resolve_language(payload.language, None),
        },
        occurred_at=datetime.now(UTC),
    )
    db.commit()
    db.refresh(event)
    return _status(event)


@api_router.get("/consent", response_model=ConsentStatus)
def read_consent(
    db: Annotated[Session, Depends(deps.get_db)],
    current_user: Annotated[User, Depends(deps.get_current_user)],
) -> ConsentStatus:
    return _status(_latest_consent(db, current_user))
