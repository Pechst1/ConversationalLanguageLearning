"""WP-25 — the placement API, driven the way the client drives it.

Behavioural, not snapshot: the real router, the real service, a fake grader in
place of the paid provider. What is pinned here is what the onboarding screen
depends on — the offer is made once, the conversation resumes, a replayed turn
costs nothing, and every route is authenticated.
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
from app.main import create_app
from app.services import placement as placement_module

TEST_PASSWORD = "securepass123"


class _FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps(
                {
                    "score_0_4": 3.0,
                    "demonstrated_band": None,
                    "dimensions": {"range": 3, "accuracy": 3, "coherence": 3, "task": 3},
                    "evidence_fr": "réponse complète",
                    "off_task": False,
                }
            ),
            model="test-model",
            provider="test",
            prompt_tokens=90,
            completion_tokens=30,
            total_tokens=120,
            cost=0.0003,
        )


@pytest.fixture()
def fake_grader(monkeypatch: pytest.MonkeyPatch) -> _FakeLLM:
    """Every placement service built inside the request gets this grader."""
    grader = _FakeLLM()
    monkeypatch.setattr(
        placement_module.PlacementService, "_get_llm_service", lambda self: grader
    )
    return grader


@pytest.fixture()
def placement_client(db_session: Session) -> Generator[TestClient, None, None]:
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
            "proficiency_level": "A1",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _email() -> str:
    return f"placement-api-{uuid.uuid4().hex[:8]}@example.com"


def test_every_placement_route_needs_a_signed_in_learner(placement_client):
    assert placement_client.get("/api/v1/placement/state").status_code == 401
    assert placement_client.post("/api/v1/placement/start").status_code == 401
    assert placement_client.post("/api/v1/placement/skip").status_code == 401


def test_a_new_learner_is_offered_the_placement_once(placement_client, fake_grader):
    headers = login(placement_client, _email())

    state = placement_client.get("/api/v1/placement/state", headers=headers).json()
    assert state["offer"] is True
    assert state["status"] == "none"
    assert state["prior"] is None

    placement_client.post("/api/v1/placement/skip", headers=headers)

    after = placement_client.get("/api/v1/placement/state", headers=headers).json()
    assert after["offer"] is False
    assert after["status"] == "skipped"


def test_the_conversation_asks_one_prompt_at_a_time_and_ends_with_a_level(
    placement_client, fake_grader
):
    headers = login(placement_client, _email())
    started = placement_client.post("/api/v1/placement/start", headers=headers).json()
    assert started["status"] == "in_progress"
    assert started["prompt"]["index"] == 0
    assert started["prompt"]["prompt_fr"]
    assert started["prompt"]["max_turns"] == placement_module.MAX_TURNS

    session_id = started["session_id"]
    envelope = started
    asked = 0
    while envelope["status"] == "in_progress":
        index = envelope["prompt"]["index"]
        envelope = placement_client.post(
            f"/api/v1/placement/{session_id}/respond",
            headers=headers,
            json={"answer": "Je voudrais un café, s’il vous plaît.", "turn_index": index},
        ).json()
        asked += 1
        assert asked <= placement_module.MAX_TURNS

    assert envelope["status"] == "complete"
    assert envelope["level"]
    assert envelope["estimate"]["graded_turns"] == asked
    assert envelope["estimate"]["dimension_labels"]["accuracy"] == "Correction grammaticale"
    assert envelope["prior"]["level"] == envelope["level"]


def test_the_level_reaches_the_cefr_payload_as_a_placement(placement_client, fake_grader):
    headers = login(placement_client, _email())
    started = placement_client.post("/api/v1/placement/start", headers=headers).json()
    envelope = started
    while envelope["status"] == "in_progress":
        envelope = placement_client.post(
            f"/api/v1/placement/{started['session_id']}/respond",
            headers=headers,
            json={"answer": "Je voudrais un café.", "turn_index": envelope["prompt"]["index"]},
        ).json()

    cefr = placement_client.get("/api/v1/progress/cefr", headers=headers).json()
    # The schema carried neither field before WP-25, so Le Relevé's unverified
    # branch could never fire: the service computed them and the response
    # dropped them on the floor.
    assert cefr["estimate_source"] == "placement"
    assert cefr["placement"]["level"] == envelope["level"]
    assert cefr["estimate"] == envelope["level"]


def test_a_replayed_response_neither_re_grades_nor_re_bills(placement_client, fake_grader):
    headers = login(placement_client, _email())
    started = placement_client.post("/api/v1/placement/start", headers=headers).json()
    body = {"answer": "Bonjour, je m’appelle Léa.", "turn_index": 0}
    first = placement_client.post(
        f"/api/v1/placement/{started['session_id']}/respond", headers=headers, json=body
    ).json()
    calls = fake_grader.calls
    second = placement_client.post(
        f"/api/v1/placement/{started['session_id']}/respond", headers=headers, json=body
    ).json()
    assert fake_grader.calls == calls
    assert second["prompt"]["index"] == first["prompt"]["index"]


def test_starting_again_resumes_rather_than_restarting(placement_client, fake_grader):
    headers = login(placement_client, _email())
    first = placement_client.post("/api/v1/placement/start", headers=headers).json()
    placement_client.post(
        f"/api/v1/placement/{first['session_id']}/respond",
        headers=headers,
        json={"answer": "Bonjour.", "turn_index": 0},
    )
    resumed = placement_client.post("/api/v1/placement/start", headers=headers).json()
    assert resumed["session_id"] == first["session_id"]
    assert resumed["prompt"]["index"] == 1


def test_reglages_can_re_run_a_finished_placement(placement_client, fake_grader):
    headers = login(placement_client, _email())
    first = placement_client.post("/api/v1/placement/start", headers=headers).json()
    rerun = placement_client.post(
        "/api/v1/placement/start", headers=headers, json={"restart": True}
    ).json()
    assert rerun["session_id"] != first["session_id"]
    assert rerun["status"] == "in_progress"


def test_finishing_with_no_graded_turn_reports_no_level(placement_client):
    """No fake grader here: this is the provider-outage screen."""
    headers = login(placement_client, _email())
    started = placement_client.post("/api/v1/placement/start", headers=headers).json()
    ended = placement_client.post(
        f"/api/v1/placement/{started['session_id']}/finish", headers=headers
    ).json()
    assert ended["status"] == "unassessed"
    assert ended["level"] is None
    assert ended["prior"] is None


def test_one_learner_cannot_open_anothers_placement(placement_client, fake_grader):
    owner = login(placement_client, _email())
    started = placement_client.post("/api/v1/placement/start", headers=owner).json()
    stranger = login(placement_client, _email())
    response = placement_client.post(
        f"/api/v1/placement/{started['session_id']}/respond",
        headers=stranger,
        json={"answer": "Bonjour.", "turn_index": 0},
    )
    assert response.status_code == 404
