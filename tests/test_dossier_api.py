"""WP-35 — the «Votre dossier» API, driven the way the page drives it.

The real router, the real service, no fake anything: the dossier makes no model
call, so there is nothing to stub and nothing to pay for.

What is pinned here is what the page depends on: every route authenticated, one
learner's model invisible to another, the accepted answers absent from every
response, and a claim that changes nothing until the check passes.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.error import UserError
from app.db.models.user import User
from app.main import create_app
from app.services.error_memory import ErrorMemoryService
from app.services.learner_model import (
    VERDICT_NOT_YET,
    VERDICT_VERIFIED,
)

TEST_PASSWORD = "securepass123"


@pytest.fixture()
def dossier_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _email() -> str:
    return f"dossier-api-{uuid.uuid4().hex[:8]}@example.com"


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


def _record_mistake(db_session: Session, email: str) -> UserError:
    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None
    ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "display_label": "Accord en genre",
            "learner_text": "une homme",
            "corrected_target": "un homme",
            "why_wrong": "homme est masculin",
            "repair_hint": "un homme",
            "task_error_type": "agreement",
            "severity": 2,
        },
        source_type="daily_journey",
    )
    db_session.commit()
    return (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id)
        .order_by(UserError.created_at.desc())
        .first()
    )


def test_every_dossier_route_needs_a_signed_in_learner(dossier_client) -> None:
    assert dossier_client.get("/api/v1/dossier/state").status_code in {401, 403}
    assert dossier_client.post(
        "/api/v1/dossier/claims", json={"kind": "erratum", "target_id": "x"}
    ).status_code in {401, 403}
    assert dossier_client.post(
        "/api/v1/dossier/claims/verify",
        json={"kind": "erratum", "target_id": "x", "answers": []},
    ).status_code in {401, 403}


def test_the_state_route_answers_the_whole_model(dossier_client, db_session) -> None:
    email = _email()
    headers = login(dossier_client, email)
    _record_mistake(db_session, email)

    body = dossier_client.get("/api/v1/dossier/state", headers=headers).json()

    assert body["version"] == "learner-model-v1"
    dossier = body["dossier"]
    assert set(dossier) >= {
        "level",
        "capabilities",
        "errata",
        "vocabulary",
        "today",
        "claims",
    }
    assert dossier["level"]["estimate_source"] in {"declared", "placement", "measured"}
    assert dossier["errata"]["counts"]["open"] == 1
    # No journey today: the page is told so rather than promised a line.
    assert dossier["today"]["has_journey"] is False
    assert dossier["today"]["because"] is None


def test_opening_a_claim_returns_two_questions_and_no_answers(dossier_client, db_session) -> None:
    email = _email()
    headers = login(dossier_client, email)
    error = _record_mistake(db_session, email)

    response = dossier_client.post(
        "/api/v1/dossier/claims",
        headers=headers,
        json={"kind": "erratum", "target_id": str(error.id)},
    )

    assert response.status_code == 200
    check = response.json()["check"]
    assert check["verifiable"] is True
    assert len(check["items"]) == 2
    # The repair card had to learn this once: never ship the answer with the
    # question. "un homme" is the answer to item 1.
    assert "un homme" not in response.text
    assert "accepted" not in response.text


def test_a_verified_claim_moves_the_erratum_and_a_failed_one_does_not(
    dossier_client, db_session
) -> None:
    email = _email()
    headers = login(dossier_client, email)
    error = _record_mistake(db_session, email)
    before = (error.next_review_date, error.reps, error.state)

    failed = dossier_client.post(
        "/api/v1/dossier/claims/verify",
        headers=headers,
        json={"kind": "erratum", "target_id": str(error.id), "answers": ["une homme", "une"]},
    ).json()
    db_session.refresh(error)

    assert failed["verdict"]["verdict"] == VERDICT_NOT_YET
    assert failed["verdict"]["advanced"] is False
    assert (error.next_review_date, error.reps, error.state) == before

    passed = dossier_client.post(
        "/api/v1/dossier/claims/verify",
        headers=headers,
        json={"kind": "erratum", "target_id": str(error.id), "answers": ["un homme", "un"]},
    ).json()
    db_session.refresh(error)

    assert passed["verdict"]["verdict"] == VERDICT_VERIFIED
    assert passed["verdict"]["advanced"] is True
    assert error.state == "repairing"
    # The response carries the refreshed model, so the page needs no second call.
    assert passed["dossier"]["errata"]["counts"]["repairing"] == 1


def test_a_claim_kind_the_dossier_does_not_know_is_a_french_refusal(dossier_client) -> None:
    headers = login(dossier_client, _email())

    response = dossier_client.post(
        "/api/v1/dossier/claims", headers=headers, json={"kind": "mood", "target_id": "1"}
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "unknown_claim_kind"
    assert detail["message_fr"].startswith("On ne peut")


def test_one_learners_dossier_is_invisible_to_another(dossier_client, db_session) -> None:
    owner_email = _email()
    login(dossier_client, owner_email)
    error = _record_mistake(db_session, owner_email)

    stranger = login(dossier_client, _email())
    response = dossier_client.post(
        "/api/v1/dossier/claims",
        headers=stranger,
        json={"kind": "erratum", "target_id": str(error.id)},
    )

    assert response.status_code == 200
    check = response.json()["check"]
    assert check["verifiable"] is False
    assert check["reason"] == "not_found"

    body = dossier_client.get("/api/v1/dossier/state", headers=stranger).json()
    assert body["dossier"]["errata"]["counts"]["open"] == 0


def test_the_dossier_makes_no_paid_call(dossier_client, db_session, monkeypatch) -> None:
    """A page that explains the model must not cost anything to open."""

    from app.services import llm_service as llm_module

    def _explode(*args, **kwargs):  # pragma: no cover - the point is that it is not called
        raise AssertionError("the dossier called a model")

    monkeypatch.setattr(llm_module.LLMService, "generate_chat_completion", _explode, raising=False)

    email = _email()
    headers = login(dossier_client, email)
    error = _record_mistake(db_session, email)

    assert dossier_client.get("/api/v1/dossier/state", headers=headers).status_code == 200
    assert (
        dossier_client.post(
            "/api/v1/dossier/claims/verify",
            headers=headers,
            json={"kind": "erratum", "target_id": str(error.id), "answers": ["un homme", "un"]},
        ).status_code
        == 200
    )
