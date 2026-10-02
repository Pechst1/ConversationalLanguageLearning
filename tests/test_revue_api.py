"""WP-119 phase 1: the Revue routes (``app/api/v1/endpoints/revue.py``) against the wire.

The flag keeps the feature invisible (a plain 404 on every route, before auth); with the
flag on, the acceptance test runs end to end over HTTP with the fake provider, and the
resume contract holds: ``GET /revue/sessions/{id}`` replays the same thread.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.revue import get_revue_provider
from app.config import settings
from app.db.models.npc import NPC, NPCMemory
from app.db.models.revue_session import RevueSession
from app.db.models.story import Story
from app.main import create_app
from app.services.revue import encounter as enc
from app.services.revue.encounter import FakeRevueProvider
from app.services.revue.evergreen import evergreens_for_week

PASSWORD = "securepass123"
WEEK = "2026-W40"
MARCHE = "evergreen-marche-du-dimanche"
PRICE_QUESTION = "Est-ce que les prix au marché sont plus bas qu'au supermarché ?"
REVUE_TABLES = (Story.__table__, NPC.__table__, NPCMemory.__table__, RevueSession.__table__)
PRIVATE_KEYS = {"answer", "contradicted_by", "supported_by", "snapshot", "events", "retry_feedback"}


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in REVUE_TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def fake() -> FakeRevueProvider:
    return FakeRevueProvider()


@pytest.fixture()
def api(db_session: Session, revue_tables, fake, monkeypatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_revue_provider] = lambda: fake
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def revue_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)


@pytest.fixture()
def revue_off(monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)


def login(client: TestClient) -> dict[str, str]:
    email = f"revue-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def keys(node) -> Iterator[str]:
    if isinstance(node, dict):
        for name, value in node.items():
            yield name
            yield from keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from keys(item)


def start(client: TestClient, headers: dict[str, str], **body) -> dict:
    response = client.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, **body})
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# The flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/revue/week"),
        ("post", "/api/v1/revue/match"),
        ("post", "/api/v1/revue/sessions"),
        ("get", f"/api/v1/revue/sessions/{uuid.uuid4()}"),
        ("post", f"/api/v1/revue/sessions/{uuid.uuid4()}/turns"),
        ("get", f"/api/v1/revue/sessions/{uuid.uuid4()}/make"),
        ("post", f"/api/v1/revue/sessions/{uuid.uuid4()}/make"),
        ("post", f"/api/v1/revue/sessions/{uuid.uuid4()}/close"),
    ],
)
def test_every_route_is_404_while_the_flag_is_off(api: TestClient, revue_off, method: str, path: str) -> None:
    headers = login(api)
    for with_auth in (headers, {}):
        response = getattr(api, method)(path, headers=with_auth, **({"json": {}} if method == "post" else {}))
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}


def test_auth_is_required_when_on(api: TestClient, revue_on) -> None:
    assert api.get("/api/v1/revue/week").status_code == 401


# ---------------------------------------------------------------------------
# The acceptance test over HTTP, and the resume contract
# ---------------------------------------------------------------------------


def test_acceptance_over_http(api: TestClient, revue_on, fake) -> None:
    headers = login(api)
    offer = api.get("/api/v1/revue/week", headers=headers, params={"week": WEEK})
    assert offer.status_code == 200, offer.text
    body = offer.json()
    assert body["week"] == {"iso": WEEK, "label": "Semaine 40", "range": "du 28 sept. au 4 oct."}
    assert body["recommended"]["evergreen"] is True and body["evergreen_only"] is True
    assert body["resume"] is None and body["filed"] is None

    session = start(api, headers, dossier_id=MARCHE)
    session_id = session["id"]
    assert session["beat"] == "arrive"
    assert session["plan"]["chosen_by"] == "learner"
    assert session["plan"]["make_options"] == ["headline_choice", "reader_question"]
    assert session["quick_replies"] == [{"label": "D'accord, je t'aide.", "send_fr": "D'accord, je t'aide."}]
    assert not PRIVATE_KEYS & set(keys(session))

    turns = f"/api/v1/revue/sessions/{session_id}/turns"
    first = api.post(turns, headers=headers, json={"text": "D'accord, je t'aide.", "mode": "text", "client_turn_id": "a"})
    assert first.status_code == 200, first.text
    assert [item["kind"] for item in first.json()["items"]] == ["mine", "line", "claims"]
    assert first.json()["beat"] == "facts"

    turn = api.post(turns, headers=headers, json={"text": PRICE_QUESTION, "mode": "voice"})
    assert turn.status_code == 200, turn.text
    data = turn.json()
    reply = next(item for item in data["items"] if item["kind"] == "line")
    assert "ne le disent pas" in reply["text_fr"]
    assert any(item["kind"] == "uncertainty" for item in data["items"])
    assert data["evidence"] == {"outcome": "unscored", "capability_known": False, "grader": "revue-unscored-adapter-v1"}
    assert data["items"][0] == {**data["items"][0], "kind": "mine", "mode": "voice"}

    make = f"/api/v1/revue/sessions/{session_id}/make"
    options = api.get(make, headers=headers)
    assert options.status_code == 200, options.text
    assert options.json()["recommended"] == "reader_question"
    assert not PRIVATE_KEYS & set(keys(options.json()))

    draft = api.post(make, headers=headers, json={"kind": "reader_question", "action": "propose"})
    assert draft.status_code == 200, draft.text
    proposal = draft.json()["draft"]["proposal_fr"]
    sent = api.post(make, headers=headers, json={"kind": "reader_question", "action": "send", "text_fr": proposal})
    assert sent.status_code == 200, sent.text
    assert sent.json()["made"]["kind"] == "reader_question"

    before = api.get(f"/api/v1/revue/sessions/{session_id}", headers=headers).json()
    closed = api.post(f"/api/v1/revue/sessions/{session_id}/close", headers=headers, json={})
    assert closed.status_code == 200, closed.text
    closing = closed.json()["closing"]
    headline = closing["dispatch"]["headline_fr"]
    assert "prix" in headline and "supermarché" in headline
    assert closing["dispatch"]["contribution"]
    assert closing["question_kept_fr"] == proposal
    assert closed.json()["session"]["status"] == "closed"

    calls = len(fake.calls)
    resumed = api.get(f"/api/v1/revue/sessions/{session_id}", headers=headers).json()
    assert resumed["thread"][: len(before["thread"])] == before["thread"]
    assert resumed["closing"] == closing and resumed["beat"] == "close"
    assert len(fake.calls) == calls, "a resume calls no model"

    filed = api.get("/api/v1/revue/week", headers=headers, params={"week": WEEK}).json()["filed"]
    assert filed["session_id"] == session_id and filed["made"]["kind"] == "reader_question"
    late = api.post(turns, headers=headers, json={"text": "Encore ?"})
    assert late.status_code == 409 and late.json()["detail"]["code"] == "revue_session_closed"


def test_resume_mid_session_is_a_pure_replay(api: TestClient, revue_on, fake) -> None:
    headers = login(api)
    session = start(api, headers)
    turns = f"/api/v1/revue/sessions/{session['id']}/turns"
    api.post(turns, headers=headers, json={"text": "D'accord, je t'aide."})
    api.post(turns, headers=headers, json={"text": PRICE_QUESTION})
    calls = len(fake.calls)
    one = api.get(f"/api/v1/revue/sessions/{session['id']}", headers=headers).json()
    two = api.get(f"/api/v1/revue/sessions/{session['id']}", headers=headers).json()
    assert one == two and len(fake.calls) == calls
    offer = api.get("/api/v1/revue/week", headers=headers, params={"week": WEEK}).json()
    assert offer["resume"]["session_id"] == session["id"]
    assert offer["resume"]["open_question_fr"] == PRICE_QUESTION


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


def test_one_active_session_per_week_over_http(api: TestClient, revue_on) -> None:
    headers = login(api)
    session = start(api, headers)
    again = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK})
    assert again.status_code == 409
    assert again.json()["detail"] == {"code": "revue_session_active", "session_id": session["id"]}


def test_errors_follow_the_wire(api: TestClient, revue_on) -> None:
    headers = login(api)
    assert api.get("/api/v1/revue/week", headers=headers, params={"week": "2026-40"}).status_code == 422
    unknown = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": "nope"})
    assert unknown.status_code == 404 and unknown.json()["detail"]["code"] == "revue_dossier_not_found"

    session = start(api, headers)
    other = login(api)
    stolen = api.get(f"/api/v1/revue/sessions/{session['id']}", headers=other)
    assert stolen.status_code == 404 and stolen.json()["detail"] == {"code": "revue_session_not_found"}
    assert api.get("/api/v1/revue/sessions/not-a-uuid", headers=headers).status_code == 404

    make = f"/api/v1/revue/sessions/{session['id']}/make"
    api.post(f"/api/v1/revue/sessions/{session['id']}/turns", headers=headers, json={"text": "D'accord, je t'aide."})
    bad = api.post(make, headers=headers, json={"kind": "headline_choice", "action": "pick", "option_id": "h9"})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "revue_unknown_option"
    mixed = api.post(make, headers=headers, json={"kind": "headline_choice", "action": "send", "text_fr": "x"})
    assert mixed.status_code == 422
    empty = api.post(f"/api/v1/revue/sessions/{session['id']}/turns", headers=headers, json={"text": ""})
    assert empty.status_code == 422


def test_match_endpoint(api: TestClient, revue_on) -> None:
    headers = login(api)
    hit = api.post("/api/v1/revue/match", headers=headers, json={"text": "la grève", "week": WEEK})
    assert hit.json() == {"match": "evergreen-greve-transports", "romy_line_fr": None}
    miss = api.post("/api/v1/revue/match", headers=headers, json={"text": "le rugby", "week": WEEK}).json()
    assert miss["match"] is None and miss["romy_line_fr"].startswith("Je n'ai que ça cette semaine")
