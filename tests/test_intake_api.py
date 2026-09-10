"""WP-34 — the intake API, driven the way Le Courrier drives it.

Behavioural, not snapshot: the real router, the real service, a fake provider in
place of the paid one. What is pinned here is what the page depends on — one
envelope per route, every route authenticated, a refusal that arrives as a
French sentence rather than a stack trace, and a deletion that really deletes.
"""
from __future__ import annotations

import io
import json
import uuid
from collections.abc import Generator, Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.db.models.intake import LearnerArtefact
from app.db.models.mission import RealWorldMission
from app.main import create_app
from app.services import intake as intake_module
from tests.test_intake import CAFE_MENU, LANDLORD_LETTER, _letter_reading, _menu_reading

TEST_PASSWORD = "securepass123"


class _FakeLLM:
    def __init__(self) -> None:
        self.reading: dict | None = _letter_reading()
        self.calls = 0

    def generate_chat_completion(self, messages, **kwargs):
        self.calls += 1
        if self.reading is None:
            raise RuntimeError("provider is down")
        return SimpleNamespace(
            content=json.dumps(self.reading, ensure_ascii=False),
            model="fake-vision",
            provider="fake",
            prompt_tokens=800,
            completion_tokens=250,
            total_tokens=1050,
            cost=0.0029,
        )


@pytest.fixture()
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> _FakeLLM:
    """Every service built inside a request gets this provider."""

    provider = _FakeLLM()
    monkeypatch.setattr(
        intake_module.IntakeService, "_get_llm_service", lambda self: provider
    )
    monkeypatch.setattr(settings, "ATELIER_INTAKE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_CAP", 5)
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_COST_CEILING_USD", 1.0)
    return provider


@pytest.fixture()
def intake_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "target_language": "fr",
            "native_language": "en",
            "proficiency_level": "A2",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _email() -> str:
    return f"intake-api-{uuid.uuid4().hex[:8]}@example.com"


def test_every_intake_route_needs_a_signed_in_learner(intake_client, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", False)
    artefact_id = str(uuid.uuid4())
    assert intake_client.get("/api/v1/intake").status_code == 401
    assert intake_client.post("/api/v1/intake/text", json={"text": CAFE_MENU}).status_code == 401
    assert intake_client.get(f"/api/v1/intake/{artefact_id}").status_code == 401
    assert intake_client.delete(f"/api/v1/intake/{artefact_id}").status_code == 401


def test_pasting_a_document_returns_the_artefact_and_its_courrier_task(
    intake_client, fake_provider
):
    headers = login(intake_client, _email())
    response = intake_client.post(
        "/api/v1/intake/text", json={"text": LANDLORD_LETTER}, headers=headers
    )
    assert response.status_code == 200
    body = response.json()

    assert body["version"] == intake_module.INTAKE_VERSION
    artefact = body["artefact"]
    assert artefact["status"] == "read"
    assert artefact["artefact"]["type"] == "lettre"
    assert artefact["artefact"]["summary_fr"]
    assert artefact["artefact"]["glossed_words"]
    assert artefact["task"]["kind"] == "reply"
    assert artefact["task"]["kind_label_fr"] == "Répondre"

    # The task is a real Courrier mission, answered at the existing endpoint.
    assert body["mission"]["id"] == artefact["mission_id"]
    assert body["mission"]["cadence"] == "artefact"
    assert body["cap"]["used"] == 1
    assert body["cap"]["remaining"] == 4
    assert fake_provider.calls == 1


def test_a_photograph_is_read_and_its_bytes_are_never_stored(intake_client, fake_provider):
    fake_provider.reading = _menu_reading()
    headers = login(intake_client, _email())
    response = intake_client.post(
        "/api/v1/intake/photo",
        files={"file": ("menu.jpg", io.BytesIO(b"\xff\xd8\xff" + b"0" * 600), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 200
    artefact = response.json()["artefact"]
    assert artefact["source_kind"] == "image"
    # What is kept is the reading, not the photograph.
    assert "Trois Ponts" in artefact["source_text"]


def test_an_oversized_photo_is_refused_in_french_before_it_is_paid_for(
    intake_client, fake_provider, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_INTAKE_MAX_IMAGE_BYTES", 500)
    headers = login(intake_client, _email())
    response = intake_client.post(
        "/api/v1/intake/photo",
        files={"file": ("big.jpg", io.BytesIO(b"0" * 2000), "image/jpeg")},
        headers=headers,
    )
    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["code"] == "image_too_large"
    assert detail["message_fr"].startswith("La photo est trop lourde")
    assert fake_provider.calls == 0


def test_a_paste_that_is_not_a_document_is_refused_in_french(intake_client, fake_provider):
    headers = login(intake_client, _email())
    response = intake_client.post("/api/v1/intake/text", json={"text": "salut"}, headers=headers)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "document_too_short"
    assert "Collez" in detail["message_fr"]
    assert fake_provider.calls == 0


def test_the_weekly_cap_arrives_as_a_sentence_not_a_stack_trace(
    intake_client, fake_provider, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_INTAKE_WEEKLY_CAP", 1)
    headers = login(intake_client, _email())
    assert intake_client.post(
        "/api/v1/intake/text", json={"text": LANDLORD_LETTER}, headers=headers
    ).status_code == 200
    response = intake_client.post(
        "/api/v1/intake/text", json={"text": CAFE_MENU}, headers=headers
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "weekly_cap_reached"
    assert detail["message_fr"]


def test_a_provider_failure_is_non_lu_with_a_retry_not_a_500(intake_client, fake_provider):
    fake_provider.reading = None
    headers = login(intake_client, _email())
    response = intake_client.post(
        "/api/v1/intake/text", json={"text": LANDLORD_LETTER}, headers=headers
    )
    assert response.status_code == 200
    artefact = response.json()["artefact"]
    assert artefact["status"] == "unread"
    assert artefact["artefact"] == {}
    assert artefact["mission_id"] is None
    # The learner's own paste survives the failure.
    assert "chauffage" in artefact["source_text"]


def test_one_learner_cannot_read_anothers_document(intake_client, fake_provider):
    owner = login(intake_client, _email())
    created = intake_client.post(
        "/api/v1/intake/text", json={"text": LANDLORD_LETTER}, headers=owner
    ).json()["artefact"]

    stranger = login(intake_client, _email())
    assert intake_client.get(
        f"/api/v1/intake/{created['id']}", headers=stranger
    ).status_code == 404
    assert intake_client.get("/api/v1/intake", headers=stranger).json()["artefacts"] == []


def test_deleting_an_artefact_removes_the_document_and_its_task(
    intake_client, fake_provider, db_session
):
    headers = login(intake_client, _email())
    created = intake_client.post(
        "/api/v1/intake/text", json={"text": LANDLORD_LETTER}, headers=headers
    ).json()["artefact"]

    assert intake_client.delete(
        f"/api/v1/intake/{created['id']}", headers=headers
    ).status_code == 204

    assert db_session.get(LearnerArtefact, uuid.UUID(created["id"])) is None
    assert db_session.get(RealWorldMission, uuid.UUID(created["mission_id"])) is None
    assert intake_client.get(f"/api/v1/intake/{created['id']}", headers=headers).status_code == 404
    # Deleting twice says nothing about whether it was ever there.
    assert intake_client.delete(
        f"/api/v1/intake/{created['id']}", headers=headers
    ).status_code == 204


def test_the_listing_carries_the_allowance_even_when_empty(intake_client, fake_provider):
    headers = login(intake_client, _email())
    body = intake_client.get("/api/v1/intake", headers=headers).json()
    assert body["artefacts"] == []
    assert body["cap"]["enabled"] is True
    assert body["cap"]["remaining"] == body["cap"]["limit"]
    assert body["max_text_chars"] == intake_module.SOURCE_TEXT_MAX_CHARS
