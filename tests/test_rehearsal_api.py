"""WP-31 — the «Répétition» API, driven the way the page drives it.

Behavioural, not snapshot: the real router, the real service, a fake provider in
place of the paid one. What is pinned here is what the page depends on — one
envelope per route, every route authenticated, a refusal that arrives as a
French sentence rather than a stack trace, and a scene whose private rubric and
recognition cues never cross the wire while the rehearsal is live.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Generator, Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints import rehearsal as rehearsal_endpoint
from app.main import create_app
from app.services import rehearsal as rehearsal_module
from tests.test_rehearsal import GOOD_BRIEF, GOOD_SCENE

TEST_PASSWORD = "securepass123"


class _FakeLLM:
    def __init__(self) -> None:
        self.prepare_calls = 0

    def generate_chat_completion(self, messages, **kwargs):
        self.prepare_calls += 1
        return SimpleNamespace(
            content=json.dumps({"brief": GOOD_BRIEF, "scene": GOOD_SCENE}, ensure_ascii=False),
            model="test-model",
            provider="test",
            prompt_tokens=400,
            completion_tokens=300,
            total_tokens=700,
            cost=0.004,
        )

    def generate_error_detection(self, messages, **kwargs):  # pragma: no cover - unused here
        raise ValueError("no corrector")


@pytest.fixture()
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> _FakeLLM:
    """Every service built inside a request gets this provider."""

    provider = _FakeLLM()
    monkeypatch.setattr(
        rehearsal_module.RehearsalService, "_get_llm_service", lambda self: provider
    )
    return provider


@pytest.fixture()
def rehearsal_client(db_session: Session) -> Generator[TestClient, None, None]:
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
    return f"rehearsal-api-{uuid.uuid4().hex[:8]}@example.com"


def test_every_rehearsal_route_needs_a_signed_in_learner(rehearsal_client):
    assert rehearsal_client.get("/api/v1/rehearsals/state").status_code == 401
    assert rehearsal_client.post("/api/v1/rehearsals", json={"declaration": "x"}).status_code == 401
    fake_id = str(uuid.uuid4())
    assert rehearsal_client.post(f"/api/v1/rehearsals/{fake_id}/prepare").status_code == 401
    assert rehearsal_client.post(f"/api/v1/rehearsals/{fake_id}/phrases").status_code == 401
    assert (
        rehearsal_client.post(
            f"/api/v1/rehearsals/{fake_id}/turns", json={"text": "a", "turn_index": 0}
        ).status_code
        == 401
    )
    assert (
        rehearsal_client.post(
            f"/api/v1/rehearsals/{fake_id}/debrief", json={"outcome": "done"}
        ).status_code
        == 401
    )


def test_a_learner_with_no_rehearsal_is_offered_one_within_the_weekly_cap(
    rehearsal_client, fake_provider
):
    headers = login(rehearsal_client, _email())
    state = rehearsal_client.get("/api/v1/rehearsals/state", headers=headers).json()

    assert state["rehearsal"] is None
    assert state["debrief_due"] is None
    assert state["cap"]["remaining"] == state["cap"]["limit"]
    assert state["min_turns"] == rehearsal_module.MIN_TURNS
    assert state["max_turns"] == rehearsal_module.MAX_TURNS


def test_the_whole_flow_from_declaration_to_debrief(rehearsal_client, fake_provider, monkeypatch):
    # The clock is frozen on a Friday: «tuesday» then resolves to the next
    # Tuesday, 2026-09-15, and the early debrief below is genuinely early.
    # Read from the wall clock this test passed until the calendar reached the
    # date it had hard-coded (WP-43 found it on 2026-09-15 itself).
    from datetime import UTC, datetime

    class _Frozen(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: D401 - the stdlib signature
            return datetime(2026, 9, 11, 9, 0, tzinfo=UTC if tz is None else tz)

    monkeypatch.setattr(rehearsal_module, "datetime", _Frozen)
    monkeypatch.setattr(rehearsal_endpoint, "datetime", _Frozen)
    headers = login(rehearsal_client, _email())

    created = rehearsal_client.post(
        "/api/v1/rehearsals",
        headers=headers,
        json={"declaration": "call the landlord about the heating, tuesday"},
    )
    assert created.status_code == 201
    envelope = created.json()
    rehearsal = envelope["rehearsal"]
    assert rehearsal["status"] == "ready"
    assert rehearsal["brief"]["counterpart"] == "le propriétaire"
    assert rehearsal["brief"]["register"] == "vous"
    assert rehearsal["event_date"] == "2026-09-15"
    assert rehearsal["turns_total"] == 4

    # The private rubric and the cues are not on the wire while it is live.
    body = created.text
    assert rehearsal["scene"]["rubric_native"] is None
    assert rehearsal["scene"]["phrases"] == []
    assert "cues" not in body
    assert GOOD_SCENE["rubric_native"] not in body

    rehearsal_id = rehearsal["id"]
    after_one = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal_id}/turns",
        headers=headers,
        json={"text": "Bonjour, le chauffage est en panne.", "turn_index": 0},
    ).json()
    assert after_one["rehearsal"]["status"] == "rehearsing"
    assert len(after_one["rehearsal"]["turns"]) == 1

    # A replayed index is a no-op, not a second grading.
    replayed = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal_id}/turns",
        headers=headers,
        json={"text": "Bonjour, le chauffage est en panne.", "turn_index": 0},
    ).json()
    assert len(replayed["rehearsal"]["turns"]) == 1

    finished = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal_id}/turns",
        headers=headers,
        json={"text": "Vous pouvez passer quand ?", "turn_index": 1},
    ).json()
    assert finished["rehearsal"]["status"] == "rehearsed"
    # Finished: the rubric may now be read, because it can no longer be a spoiler.
    assert finished["rehearsal"]["scene"]["rubric_native"] == GOOD_SCENE["rubric_native"]
    assert finished["rehearsal"]["result"]["outcome"] == "met"

    # Before the day, the debrief is refused in French rather than 500-ing.
    early = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal_id}/debrief",
        headers=headers,
        json={"outcome": "done", "free_line": ""},
    )
    assert early.status_code == 409
    assert early.json()["detail"]["code"] == "debrief_not_due"
    assert "rendez-vous" in early.json()["detail"]["message_fr"]

    # On the day, it opens.
    monkeypatch.setattr(
        rehearsal_module,
        "debrief_available",
        lambda rehearsal, *, today: rehearsal.status == "rehearsed",
    )
    done = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal_id}/debrief",
        headers=headers,
        json={"outcome": "done", "free_line": "J'ai appele et il vient jeudi."},
    ).json()
    assert done["rehearsal"]["status"] == "debriefed"
    assert done["rehearsal"]["outcome"] == "done"
    # The corrector was not reachable in this run, and the payload says so
    # rather than passing the line off as correct.
    assert done["rehearsal"]["debrief"]["correction_available"] is False


def test_asking_for_the_phrases_returns_them_and_records_the_help(
    rehearsal_client, fake_provider
):
    headers = login(rehearsal_client, _email())
    rehearsal = rehearsal_client.post(
        "/api/v1/rehearsals", headers=headers, json={"declaration": "call the landlord"}
    ).json()["rehearsal"]

    revealed = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal['id']}/phrases", headers=headers
    ).json()["rehearsal"]
    assert revealed["scene"]["phrases_revealed"] is True
    assert len(revealed["scene"]["phrases"]) == 2

    graded = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal['id']}/turns",
        headers=headers,
        json={"text": "Le chauffage est en panne, quand pouvez-vous passer ?", "turn_index": 0},
    ).json()["rehearsal"]
    assert graded["turns"][0]["assistance"] == "suggested_response"
    assert graded["turns"][0]["evidence_kind"] == "produced_supported"


def test_an_empty_declaration_is_refused_in_french(rehearsal_client, fake_provider):
    headers = login(rehearsal_client, _email())
    refused = rehearsal_client.post(
        "/api/v1/rehearsals", headers=headers, json={"declaration": "   "}
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "declaration_empty"
    assert refused.json()["detail"]["message_fr"].startswith("Dites d’abord")


def test_a_rehearsal_belongs_to_its_learner_and_nobody_else(rehearsal_client, fake_provider):
    mine = login(rehearsal_client, _email())
    theirs = login(rehearsal_client, _email())
    rehearsal = rehearsal_client.post(
        "/api/v1/rehearsals", headers=mine, json={"declaration": "call the landlord"}
    ).json()["rehearsal"]

    stolen = rehearsal_client.post(
        f"/api/v1/rehearsals/{rehearsal['id']}/turns",
        headers=theirs,
        json={"text": "Bonjour", "turn_index": 0},
    )
    assert stolen.status_code == 404
