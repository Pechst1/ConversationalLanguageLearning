"""WP-72 — public legal pages on the API host and the sign-up consent record."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.legal import (
    CONSENT_EVENT,
    LEGAL_CONTENT_PATH,
    legal_content,
    render_document,
    resolve_language,
)
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User

ROOT = Path(__file__).resolve().parents[1]
WEB_COPY = ROOT / "web-frontend" / "lib" / "legal-content.json"


def test_web_copy_is_byte_identical_to_the_canonical_text() -> None:
    assert WEB_COPY.read_bytes() == LEGAL_CONTENT_PATH.read_bytes(), (
        "Run `node web-frontend/scripts/sync-legal-content.mjs` after editing "
        "app/data/legal/legal_content.json."
    )


def test_every_document_exists_in_every_language_with_the_same_shape() -> None:
    content = legal_content()
    assert set(content["languages"]) == {"en", "de", "fr"}
    for kind in ("privacy", "terms"):
        shapes = {
            lang: len(content["documents"][kind][lang]["sections"]) for lang in content["languages"]
        }
        assert len(set(shapes.values())) == 1, (kind, shapes)


def test_privacy_policy_names_what_the_code_actually_collects_and_sends() -> None:
    text = json.dumps(legal_content()["documents"]["privacy"]["en"], ensure_ascii=False)
    for fact in (
        "OpenAI",  # text, transcription, vision, images, audio
        "voice",  # /audio/transcribe — audio discarded, transcript kept
        "photo",  # Courrier intake — image never stored (app/services/intake.py)
        "ElevenLabs",  # optional TTS (TTS_PROVIDER / ELEVENLABS_API_KEY)
        "Anthropic",  # optional fallback text provider in llm_service
        "Réglages → Données",  # export + delete live there
        "delete",
        "export",
    ):
        assert fact in text, fact


@pytest.mark.parametrize(
    ("explicit", "header", "expected"),
    [
        ("de", None, "de"),
        (None, "fr-FR,fr;q=0.9,en;q=0.8", "fr"),
        (None, "es-ES,de;q=0.7", "de"),
        ("pt", "it-IT", "en"),
        (None, None, "en"),
    ],
)
def test_language_resolution(explicit: str | None, header: str | None, expected: str) -> None:
    assert resolve_language(explicit, header) == expected


@pytest.mark.parametrize("path", ["/privacy", "/terms"])
def test_public_pages_are_served_without_sign_in(client: TestClient, path: str) -> None:
    response = client.get(path, headers={"Accept-Language": "de-DE,de;q=0.9"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-language"] == "de"
    body = response.text
    assert '<html lang="de">' in body
    assert legal_content()["version"] in body

    french = client.get(f"{path}?lang=fr")
    assert '<html lang="fr">' in french.text


def test_rendered_page_escapes_and_fills_placeholders() -> None:
    page = render_document("privacy", "en")
    assert "{contact}" not in page and "{operator}" not in page
    assert "<script" not in page


@pytest.fixture()
def legal_user(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp72-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        full_name="Consent Tester",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def signed_in(client: TestClient, legal_user: User):
    client.app.dependency_overrides[deps.get_current_user] = lambda: legal_user
    try:
        yield client
    finally:
        client.app.dependency_overrides.pop(deps.get_current_user, None)


def test_consent_is_recorded_with_version_and_timestamp(signed_in: TestClient, db_session, legal_user: User) -> None:
    before = signed_in.get("/api/v1/legal/consent").json()
    assert before["accepted_version"] is None and before["up_to_date"] is False

    version = legal_content()["version"]
    response = signed_in.post(
        "/api/v1/legal/consent", json={"version": version, "surface": "signup", "language": "de-DE"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accepted_version"] == version and body["up_to_date"] is True
    assert body["accepted_at"]

    event = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.user_id == legal_user.id, PilotEvent.event_type == CONSENT_EVENT)
        .one()
    )
    assert event.payload["version"] == version
    assert event.payload["ai_processing"] is True
    assert event.payload["ai_provider"] == "openai"
    assert event.payload["language"] == "de"

    after = signed_in.get("/api/v1/legal/consent").json()
    assert after["up_to_date"] is True


def test_consent_to_a_stale_version_is_refused(signed_in: TestClient) -> None:
    response = signed_in.post("/api/v1/legal/consent", json={"version": "1999-01-01"})
    assert response.status_code == 409


def test_consent_requires_a_session(client: TestClient) -> None:
    response = client.post("/api/v1/legal/consent", json={"version": legal_content()["version"]})
    assert response.status_code == 401
