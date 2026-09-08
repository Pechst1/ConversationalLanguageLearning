"""HTTP behaviour of the Atelier V2 daily journey (WP-02).

These are behavioural tests, not snapshots: they drive the real router with the
real state machine and assert what the learner and the client can observe.
Domain work is pinned to the deterministic ``_Missing*`` adapters so the state
machine is what is under test, never WP-03/05 content quality.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.daily_journey import get_journey_adapters
from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyMutation, DailyJourneyStep
from app.main import create_app
from app.services import journey_conversation, journey_planner
from app.services.daily_journey_adapters import (
    JourneyAdapters,
    _MissingCapabilitiesAdapter,
    _MissingContentAdapter,
    _MissingEventsAdapter,
    _MissingLearningAdapter,
)

TEST_PASSWORD = "securepass123"
TZ = "Europe/Paris"

PRIVATE_MARKERS = (
    "rubric",
    "rubric_native",
    "accepted_answers",
    "correct_option_id",
    "correct_tile_order",
    "solution_fr",
    "target_answer",
    "allowed_outcomes",
    "private_task",
    "scenario_brief",
    "suggested_response_fr",
)


def stub_adapters() -> JourneyAdapters:
    """The state machine under test, with the domain pinned for determinism.

    The planner is the **real** WP-04 module: there is no planner stub any more,
    and a plan built by a fake planner would not be worth asserting on. Content
    and learning stay deterministic so these tests fail for state-machine
    reasons, never because a scene was reworded.
    """

    return JourneyAdapters(
        content=_MissingContentAdapter(),
        planner=journey_planner,
        learning=_MissingLearningAdapter(),
        conversation=journey_conversation,
        capabilities=_MissingCapabilitiesAdapter(),
        events=_MissingEventsAdapter(),
    )


@pytest.fixture()
def journey_enabled() -> Generator[None, None, None]:
    previous = settings.ATELIER_DAILY_JOURNEY_ENABLED
    previous_cohort = settings.ATELIER_DAILY_JOURNEY_COHORT
    settings.ATELIER_DAILY_JOURNEY_ENABLED = True
    settings.ATELIER_DAILY_JOURNEY_COHORT = ""
    try:
        yield
    finally:
        settings.ATELIER_DAILY_JOURNEY_ENABLED = previous
        settings.ATELIER_DAILY_JOURNEY_COHORT = previous_cohort


@pytest.fixture()
def journey_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_journey_adapters] = stub_adapters
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
        },
    )
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def key() -> str:
    return uuid.uuid4().hex


def walk_keys(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for name, value in node.items():
            yield name
            yield from walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_keys(item)


def assert_no_private_material(payload: Any) -> None:
    leaked = sorted({name for name in walk_keys(payload) if name in PRIVATE_MARKERS})
    assert leaked == [], f"public payload leaked evaluator keys: {leaked}"
    blob = str(payload)
    # The evaluator rubric text itself must never travel.
    assert "STUB rubric" not in blob


def create_journey(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={
            "mutation_id": key(),
            "timezone": TZ,
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def step_of(journey: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(step for step in journey["steps"] if step["kind"] == kind)


def correct_recall_input(db: Session, step_id: str) -> dict[str, Any]:
    """The right answer, read from the private task the client never sees.

    Reading it here is also a second proof that the answer key lives in the
    database and not in any response the tests just asserted on.
    """

    step = db.get(DailyJourneyStep, uuid.UUID(step_id))
    assert step is not None
    task = dict(step.private_task or {}).get("recall_task", {})
    if task.get("correct_option_id"):
        return {"mode": "choice", "option_id": task["correct_option_id"]}
    if task.get("correct_tile_order"):
        return {"mode": "tiles", "tile_ids": list(task["correct_tile_order"])}
    accepted = task.get("accepted_answers") or [""]
    return {"mode": "text", "text": accepted[0]}


# ---------------------------------------------------------------------------
# Golden path
# ---------------------------------------------------------------------------


def test_create_read_help_attempt_advance_pause_resume_finish(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-golden@example.com")

    today = journey_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["enabled"] is True
    assert today["journey"] is None
    assert today["available"]["scenario_key"] == "order_at_cafe"
    assert today["control_language"] == "en"

    journey = create_journey(journey_client, headers)
    journey_id = journey["id"]
    assert journey["status"] == "active"
    assert journey["revision"] == 2
    kinds = [step["kind"] for step in journey["steps"]]
    # The CONTRACTS §3 envelope, not one hardcoded plan: WP-04 decides the shape.
    assert kinds[0] == "scene" and kinds[-1] == "resolution"
    assert kinds.count("respond") == 1
    assert kinds.count("recall") <= 2
    assert 3 <= len(kinds) <= 5
    scene = step_of(journey, "scene")
    assert journey["current_step_id"] == scene["id"]
    assert sum(step["estimated_seconds"] for step in journey["steps"]) <= 300
    assert_no_private_material(journey)

    # Reading is a read: same ids, same revision.
    reread = journey_client.get(
        f"/api/v1/daily-journeys/{journey_id}", headers=headers
    ).json()
    assert reread["revision"] == journey["revision"]
    assert [step["id"] for step in reread["steps"]] == [
        step["id"] for step in journey["steps"]
    ]
    assert_no_private_material(reread)

    # scene -> recall
    advanced = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": reread["revision"],
            "current_step_id": scene["id"],
        },
    )
    assert advanced.status_code == 200, advanced.text
    state = advanced.json()
    recall = step_of(state, "recall")
    assert state["current_step_id"] == recall["id"]
    assert step_of(state, "scene")["status"] == "completed"

    # help is recorded before the content is returned
    helped = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/steps/{recall['id']}/help",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "help_kind": "hint",
        },
    )
    assert helped.status_code == 200, helped.text
    help_body = helped.json()
    assert help_body["assistance_level"] == "hint"
    assert "hint" in recall["prompt"]["help_available"]
    assert help_body["content_fr"] or help_body["content_native"]
    assert step_of(help_body["journey"], "recall")["assistance_used"] == ["hint"]

    # recall attempt
    attempt = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/steps/{recall['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": help_body["journey"]["revision"],
            "input": correct_recall_input(db_session, recall["id"]),
        },
    )
    assert attempt.status_code == 200, attempt.text
    attempt_body = attempt.json()
    assert attempt_body["task_outcome"] == "met"
    assert attempt_body["assistance_level"] == "hint"
    assert attempt_body["pending"] is False
    assert attempt_body["evidence_ref"].startswith("stub:")
    assert_no_private_material(attempt_body)
    state = attempt_body["journey"]
    assert step_of(state, "recall")["status"] == "completed"

    # recall -> respond
    state = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "current_step_id": recall["id"],
        },
    ).json()
    respond = step_of(state, "respond")
    assert state["current_step_id"] == respond["id"]
    assert respond["prompt"]["input_modes"] == ["text"]

    # open production, unassisted
    spoken = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/steps/{respond['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "input": {
                "mode": "text",
                "text": "Je voudrais un café en terrasse, s'il vous plaît.",
            },
        },
    )
    assert spoken.status_code == 200, spoken.text
    spoken_body = spoken.json()
    assert spoken_body["task_outcome"] == "met"
    assert spoken_body["assistance_level"] == "none"
    assert spoken_body["next_turn"] is None
    # Provenance travels with the reply: never an authored line dressed up as live.
    assert spoken_body["reply_source"] in {"authored", "model", "none"}
    if spoken_body["character_reply_fr"]:
        assert spoken_body["reply_source"] != "none"
    state = spoken_body["journey"]
    # the declared consequence reached the resolution step
    assert step_of(state, "resolution")["prompt"]["outcome_key"] == "served_at_terrace"

    # respond -> resolution
    state = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "current_step_id": respond["id"],
        },
    ).json()
    resolution = step_of(state, "resolution")
    assert state["current_step_id"] == resolution["id"]

    paused = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/pause",
        headers=headers,
        json={"mutation_id": key(), "expected_revision": state["revision"]},
    ).json()
    assert paused["status"] == "paused"
    assert paused["current_step_id"] == resolution["id"]

    resumed = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/resume",
        headers=headers,
        json={"mutation_id": key(), "expected_revision": paused["revision"]},
    ).json()
    assert resumed["status"] == "active"
    # resume returns the same plan, not a new one
    assert [step["id"] for step in resumed["steps"]] == [
        step["id"] for step in journey["steps"]
    ]

    state = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": resumed["revision"],
            "current_step_id": resolution["id"],
        },
    ).json()
    assert state["current_step_id"] is None

    finished = journey_client.post(
        f"/api/v1/daily-journeys/{journey_id}/finish",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "finish_kind": "complete",
        },
    )
    assert finished.status_code == 200, finished.text
    final = finished.json()
    assert final["status"] == "completed"
    recap = final["recap"]
    assert recap["completion_kind"] == "complete"
    assert recap["objective_outcome"] == "met"
    # The recap has no rubric of its own: it reports what WP-09 found in the
    # canonical records. This journey ran on the stub learning adapter, which
    # writes no evidence at all, so there is nothing to claim. The real-module
    # agreement case lives in
    # tests/test_daily_journey_state.py::test_the_recap_and_the_progress_endpoint_agree_about_one_journey
    assert recap["capability_evidence"] == []
    assert recap["active_seconds"] is None
    assert {target["evidence_kind"] for target in recap["practiced_targets"]} == {
        "recognized",
        "produced_independent",
    }
    assert_no_private_material(final)


def test_reload_and_second_create_return_the_same_plan(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-reload@example.com")
    first = create_journey(journey_client, headers)

    again = journey_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={
            "mutation_id": key(),
            "timezone": TZ,
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        },
    )
    assert again.status_code == 200
    assert again.json()["id"] == first["id"]
    assert [step["id"] for step in again.json()["steps"]] == [
        step["id"] for step in first["steps"]
    ]

    today = journey_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["journey"]["id"] == first["id"]
    assert today["available"] is None


def test_a_timezone_change_does_not_duplicate_the_open_journey(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-tz@example.com")
    first = create_journey(journey_client, headers)

    moved = journey_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={
            "mutation_id": key(),
            "timezone": "Pacific/Auckland",
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        },
    )
    assert moved.status_code == 200
    assert moved.json()["id"] == first["id"]
    assert moved.json()["timezone"] == TZ


# ---------------------------------------------------------------------------
# Idempotency, revisions and ordering
# ---------------------------------------------------------------------------


def _to_respond_step(
    client: TestClient,
    headers: dict[str, str],
    journey: dict[str, Any],
    db: Session,
) -> dict[str, Any]:
    """Drive the plan forward to the respond step and return the snapshot."""

    journey_id = journey["id"]
    state = journey
    while True:
        step = next(
            item for item in state["steps"] if item["id"] == state["current_step_id"]
        )
        if step["kind"] == "respond":
            return state
        if step["kind"] == "recall" and step["status"] == "active":
            state = client.post(
                f"/api/v1/daily-journeys/{journey_id}/steps/{step['id']}/attempts",
                headers=headers,
                json={
                    "mutation_id": key(),
                    "expected_revision": state["revision"],
                    "input": correct_recall_input(db, step["id"]),
                },
            ).json()["journey"]
        state = client.post(
            f"/api/v1/daily-journeys/{journey_id}/advance",
            headers=headers,
            json={
                "mutation_id": key(),
                "expected_revision": state["revision"],
                "current_step_id": step["id"],
            },
        ).json()


def test_duplicate_committed_attempt_replays_without_double_applying(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-dup@example.com")
    journey = create_journey(journey_client, headers)
    state = _to_respond_step(journey_client, headers, journey, db_session)
    respond = step_of(state, "respond")

    body = {
        "mutation_id": key(),
        "expected_revision": state["revision"],
        "input": {"mode": "text", "text": "Je voudrais un café, s'il vous plaît."},
    }
    url = f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts"

    first = journey_client.post(url, headers=headers, json=body)
    assert first.status_code == 200
    second = journey_client.post(url, headers=headers, json=body)
    assert second.status_code == 200
    assert second.json() == first.json()
    # the replay did not consume another turn or bump the revision again
    after = journey_client.get(
        f"/api/v1/daily-journeys/{journey['id']}", headers=headers
    ).json()
    assert after["revision"] == first.json()["journey"]["revision"]


def test_in_flight_duplicate_returns_202_processing(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-inflight@example.com")
    journey = create_journey(journey_client, headers)
    state = _to_respond_step(journey_client, headers, journey, db_session)
    respond = step_of(state, "respond")

    mutation_id = key()
    body = {
        "mutation_id": mutation_id,
        "expected_revision": state["revision"],
        "input": {"mode": "text", "text": "Je voudrais un café, s'il vous plaît."},
    }
    url = f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts"
    first = journey_client.post(url, headers=headers, json=body)
    assert first.status_code == 200

    # Simulate the first request still running when the retry arrives.
    receipt = (
        db_session.query(DailyJourneyMutation)
        .filter(DailyJourneyMutation.mutation_id == mutation_id)
        .one()
    )
    receipt.status = "processing"
    db_session.commit()

    retry = journey_client.post(url, headers=headers, json=body)
    assert retry.status_code == 202
    assert retry.json()["detail"]["code"] == "processing"
    assert retry.json()["detail"]["retry_after_seconds"] >= 1


def test_same_key_with_a_different_body_is_an_idempotency_conflict(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-conflict@example.com")
    journey = create_journey(journey_client, headers)
    state = _to_respond_step(journey_client, headers, journey, db_session)
    respond = step_of(state, "respond")
    url = f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts"
    mutation_id = key()

    first = journey_client.post(
        url,
        headers=headers,
        json={
            "mutation_id": mutation_id,
            "expected_revision": state["revision"],
            "input": {"mode": "text", "text": "Je voudrais un café."},
        },
    )
    assert first.status_code == 200

    clashing = journey_client.post(
        url,
        headers=headers,
        json={
            "mutation_id": mutation_id,
            "expected_revision": state["revision"],
            "input": {"mode": "text", "text": "Une bière, s'il vous plaît."},
        },
    )
    assert clashing.status_code == 409
    assert clashing.json()["detail"]["code"] == "idempotency_conflict"


def test_a_stale_revision_is_refused_with_a_refresh_reference(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-stale@example.com")
    journey = create_journey(journey_client, headers)
    scene = step_of(journey, "scene")

    stale = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"] - 1,
            "current_step_id": scene["id"],
        },
    )
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["code"] == "journey_version_conflict"
    assert detail["current_revision"] == journey["revision"]
    assert detail["refresh_href"].endswith(journey["id"])


def test_a_committed_receipt_replays_before_the_revision_is_checked(
    journey_client: TestClient, journey_enabled: None
) -> None:
    """CONTRACTS §5: matching receipt first, stale-revision rejection second."""

    headers = login(journey_client, "journey-order@example.com")
    journey = create_journey(journey_client, headers)
    scene = step_of(journey, "scene")
    mutation_id = key()
    body = {
        "mutation_id": mutation_id,
        "expected_revision": journey["revision"],
        "current_step_id": scene["id"],
    }
    url = f"/api/v1/daily-journeys/{journey['id']}/advance"

    first = journey_client.post(url, headers=headers, json=body)
    assert first.status_code == 200
    # The very same request is now stale, but the receipt wins.
    replay = journey_client.post(url, headers=headers, json=body)
    assert replay.status_code == 200
    assert replay.json() == first.json()


def test_out_of_order_step_is_refused(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-order-step@example.com")
    journey = create_journey(journey_client, headers)
    respond = step_of(journey, "respond")

    early = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"],
            "input": {"mode": "text", "text": "Je voudrais un café."},
        },
    )
    assert early.status_code == 409
    assert early.json()["detail"]["code"] == "step_not_active"


def test_advance_cannot_skip_unanswered_required_work(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-skip@example.com")
    journey = create_journey(journey_client, headers)
    scene = step_of(journey, "scene")
    state = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"],
            "current_step_id": scene["id"],
        },
    ).json()
    recall = step_of(state, "recall")

    blocked = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "current_step_id": recall["id"],
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "step_not_active"


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------


def test_another_users_journey_and_step_ids_are_not_disclosed(
    journey_client: TestClient, journey_enabled: None
) -> None:
    owner = login(journey_client, "journey-owner@example.com")
    journey = create_journey(journey_client, owner)
    intruder = login(journey_client, "journey-intruder@example.com")

    read = journey_client.get(
        f"/api/v1/daily-journeys/{journey['id']}", headers=intruder
    )
    assert read.status_code == 404

    scene = step_of(journey, "scene")
    attempt = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{scene['id']}/attempts",
        headers=intruder,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"],
            "input": {"mode": "text", "text": "bonjour"},
        },
    )
    assert attempt.status_code == 404

    # A step id from someone else's journey is not reachable through your own.
    mine = create_journey(journey_client, intruder)
    crossed = journey_client.post(
        f"/api/v1/daily-journeys/{mine['id']}/steps/{scene['id']}/attempts",
        headers=intruder,
        json={
            "mutation_id": key(),
            "expected_revision": mine["revision"],
            "input": {"mode": "text", "text": "bonjour"},
        },
    )
    assert crossed.status_code == 404


def test_a_voice_transcript_reference_that_cannot_be_attributed_is_refused(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    """Contract revision 1: the ownership check is vacuous, not skipped."""

    headers = login(journey_client, "journey-voice@example.com")
    journey = create_journey(journey_client, headers)
    state = _to_respond_step(journey_client, headers, journey, db_session)
    respond = step_of(state, "respond")

    refused = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "input": {
                "mode": "voice",
                "text": "Je voudrais un café, s'il vous plaît.",
                "transcript_ref": str(uuid.uuid4()),
            },
        },
    )
    assert refused.status_code == 404

    # …while a voice attempt without a reference is a first-class path.
    accepted = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "input": {
                "mode": "voice",
                "text": "Je voudrais un café, s'il vous plaît.",
            },
        },
    )
    assert accepted.status_code == 200


# ---------------------------------------------------------------------------
# Blank answers, privacy, capability, flag
# ---------------------------------------------------------------------------


def test_blank_answer_is_422_and_mutates_nothing(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-blank@example.com")
    journey = create_journey(journey_client, headers)
    state = _to_respond_step(journey_client, headers, journey, db_session)
    respond = step_of(state, "respond")
    receipts_before = db_session.query(DailyJourneyMutation).count()

    blank = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            # non-breaking + narrow spaces: normalization folds these to nothing
            "input": {"mode": "text", "text": "  \u00a0\u202f  "},
        },
    )
    assert blank.status_code == 422
    assert blank.json()["detail"]["code"] == "empty_answer"

    after = journey_client.get(
        f"/api/v1/daily-journeys/{journey['id']}", headers=headers
    ).json()
    assert after["revision"] == state["revision"]
    assert step_of(after, "respond")["status"] == "active"
    assert db_session.query(DailyJourneyMutation).count() == receipts_before


def test_no_response_ever_carries_evaluator_material(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-private@example.com")
    journey = create_journey(journey_client, headers)
    assert_no_private_material(journey)

    state = _to_respond_step(journey_client, headers, journey, db_session)
    assert_no_private_material(state)
    respond = step_of(state, "respond")

    # A wrong first answer must not reveal the target.
    wrong = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/attempts",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state["revision"],
            "input": {"mode": "text", "text": "euh"},
        },
    ).json()
    assert wrong["task_outcome"] == "not_yet"
    assert_no_private_material(wrong)
    assert "Je voudrais un café" not in str(wrong)

    # Only an explicit reveal hands the suggestion over.
    revealed = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{respond['id']}/help",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": wrong["journey"]["revision"],
            "help_kind": "suggested_response",
        },
    ).json()
    assert revealed["content_fr"] == "Je voudrais un café, s'il vous plaît."
    assert revealed["assistance_level"] == "suggested_response"


def test_capability_progress_is_typed_and_never_infers_success(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-capability@example.com")
    response = journey_client.get(
        "/api/v1/daily-journeys/capabilities/progress", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rubric_version"] == "capability-rubric-v1"
    assert {item["capability_key"] for item in body["capabilities"]} == {
        "order_at_cafe",
        "arrange_meeting",
        "explain_delay",
    }
    assert all(item["state"] == "not_tried" for item in body["capabilities"])


def test_flag_off_refuses_creation_but_keeps_draining_existing_journeys(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-drain@example.com")
    journey = create_journey(journey_client, headers)
    scene = step_of(journey, "scene")

    settings.ATELIER_DAILY_JOURNEY_ENABLED = False

    today = journey_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["enabled"] is False
    assert today["available"] is None
    # …but the open journey stays readable and resumable.
    assert today["journey"]["id"] == journey["id"]

    refused = journey_client.post(
        "/api/v1/daily-journeys",
        headers=headers,
        json={
            "mutation_id": key(),
            "timezone": TZ,
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        },
    )
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "journey_disabled"

    read = journey_client.get(
        f"/api/v1/daily-journeys/{journey['id']}", headers=headers
    )
    assert read.status_code == 200

    state = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/advance",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"],
            "current_step_id": scene["id"],
        },
    )
    assert state.status_code == 200

    finished = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/finish",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": state.json()["revision"],
            "finish_kind": "early",
        },
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "ended_early"
    assert finished.json()["recap"]["objective_outcome"] == "not_yet"
    assert finished.json()["recap"]["collectible_ids"] == []


def test_cohort_allowlist_gates_the_pilot(
    journey_client: TestClient, journey_enabled: None
) -> None:
    settings.ATELIER_DAILY_JOURNEY_COHORT = "someone-else@example.com"
    headers = login(journey_client, "journey-cohort@example.com")

    today = journey_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["enabled"] is False

    settings.ATELIER_DAILY_JOURNEY_COHORT = "journey-cohort@example.com"
    today = journey_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["enabled"] is True


def test_every_route_requires_authentication(journey_client: TestClient) -> None:
    assert journey_client.get("/api/v1/daily-journeys/today").status_code == 401
    assert (
        journey_client.get("/api/v1/daily-journeys/capabilities/progress").status_code
        == 401
    )
    assert (
        journey_client.post(
            "/api/v1/daily-journeys",
            json={
                "mutation_id": key(),
                "timezone": TZ,
                "budget_seconds": 300,
                "preferred_input_mode": "text",
            },
        ).status_code
        == 401
    )
    assert (
        journey_client.get(f"/api/v1/daily-journeys/{uuid.uuid4()}").status_code == 401
    )


def test_legacy_atelier_session_gets_an_explicit_resume_entry(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    from app.db.models.atelier import AtelierSession
    from app.db.models.user import User

    headers = login(journey_client, "journey-legacy@example.com")
    user = (
        db_session.query(User).filter(User.email == "journey-legacy@example.com").one()
    )
    session = AtelierSession(user_id=user.id, status="in_progress")
    db_session.add(session)
    db_session.commit()

    today = journey_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["legacy_resume"]["session_id"] == str(session.id)
    assert today["legacy_resume"]["href"] == f"/atelier?session={session.id}"


def test_terminal_journeys_are_read_only(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    headers = login(journey_client, "journey-terminal@example.com")
    journey = create_journey(journey_client, headers)
    finished = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/finish",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"],
            "finish_kind": "early",
        },
    ).json()
    assert finished["status"] == "ended_early"

    for path, body in (
        (
            "advance",
            {
                "mutation_id": key(),
                "expected_revision": finished["revision"],
                "current_step_id": step_of(journey, "scene")["id"],
            },
        ),
        ("pause", {"mutation_id": key(), "expected_revision": finished["revision"]}),
        ("resume", {"mutation_id": key(), "expected_revision": finished["revision"]}),
        (
            "finish",
            {
                "mutation_id": key(),
                "expected_revision": finished["revision"],
                "finish_kind": "complete",
            },
        ),
    ):
        response = journey_client.post(
            f"/api/v1/daily-journeys/{journey['id']}/{path}", headers=headers, json=body
        )
        assert response.status_code == 409, path
        assert response.json()["detail"]["code"] in {
            "journey_not_active",
            "step_not_active",
        }

    # Reading it is still fine.
    assert (
        journey_client.get(
            f"/api/v1/daily-journeys/{journey['id']}", headers=headers
        ).status_code
        == 200
    )
    stored = db_session.get(DailyJourney, uuid.UUID(journey["id"]))
    assert stored is not None and stored.status == "ended_early"


def test_completing_with_unanswered_mandatory_work_is_refused(
    journey_client: TestClient, journey_enabled: None
) -> None:
    headers = login(journey_client, "journey-incomplete@example.com")
    journey = create_journey(journey_client, headers)

    refused = journey_client.post(
        f"/api/v1/daily-journeys/{journey['id']}/finish",
        headers=headers,
        json={
            "mutation_id": key(),
            "expected_revision": journey["revision"],
            "finish_kind": "complete",
        },
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "step_not_active"


def test_empty_cohort_enables_nobody_in_production(monkeypatch):
    """WP-18 finding: a blanked allowlist must not enable every learner in production."""
    from types import SimpleNamespace

    from app.services.daily_journey import journey_enabled_for

    user = SimpleNamespace(id="u-1", email="someone@example.com")
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")
    monkeypatch.setattr(settings, "APP_ENV", "development")
    assert journey_enabled_for(user) is True
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert journey_enabled_for(user) is False
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "*")
    assert journey_enabled_for(user) is True
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "someone@example.com")
    assert journey_enabled_for(user) is True
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "other@example.com")
    assert journey_enabled_for(user) is False
