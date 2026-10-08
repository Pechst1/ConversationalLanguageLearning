"""Pilot registration gate (WP-138): a journey cohort is not an invite list."""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.models.user import User
from app.services.auth import registration_allowed


def _payload(email: str) -> dict[str, str]:
    return {"email": email, "password": "securepassword", "target_language": "fr", "native_language": "en"}


def test_registration_is_open_by_default_in_dev_and_tests() -> None:
    assert settings.REGISTRATION_OPEN is True
    assert registration_allowed("anyone@example.com")


@pytest.mark.parametrize(
    ("allowed", "email", "expected"),
    [
        ("owner@example.com", "owner@example.com", True),
        (" Owner@Example.com , friend@example.com ", "  OWNER@example.COM ", True),
        ("owner@example.com,friend@example.com", "friend@example.com", True),
        ("owner@example.com", "stranger@example.com", False),
        ("", "owner@example.com", False),
        (",,", "", False),
    ],
)
def test_closed_registration_admits_only_the_allowlist(monkeypatch, allowed, email, expected) -> None:
    monkeypatch.setattr(settings, "REGISTRATION_OPEN", False)
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWED_EMAILS", allowed)
    assert registration_allowed(email) is expected


def test_register_endpoint_refuses_an_uninvited_email(client: TestClient, db_session, monkeypatch) -> None:
    tag = uuid4().hex[:10]
    owner, stranger = f"owner-{tag}@example.com", f"stranger-{tag}@example.com"
    monkeypatch.setattr(settings, "REGISTRATION_OPEN", False)
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWED_EMAILS", owner)

    refused = client.post("/api/v1/auth/register", json=_payload(stranger))
    assert refused.status_code == 403
    assert "invitation" in refused.json()["detail"]
    assert db_session.query(User).filter(User.email == stranger).count() == 0

    admitted = client.post("/api/v1/auth/register", json=_payload(owner.upper()))
    assert admitted.status_code == 201
    assert admitted.json()["email"] == owner


def test_existing_accounts_still_sign_in_when_registration_closes(client: TestClient, monkeypatch) -> None:
    early = f"early-{uuid4().hex[:10]}@example.com"
    assert client.post("/api/v1/auth/register", json=_payload(early)).status_code == 201
    monkeypatch.setattr(settings, "REGISTRATION_OPEN", False)
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWED_EMAILS", "")

    login = client.post("/api/v1/auth/login", json={"email": early, "password": "securepassword"})
    assert login.status_code == 200


def test_dev_auto_create_on_login_respects_the_gate(client: TestClient, db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", True)
    monkeypatch.setattr(settings, "REGISTRATION_OPEN", False)
    monkeypatch.setattr(settings, "REGISTRATION_ALLOWED_EMAILS", "")

    ghost = f"ghost-{uuid4().hex[:10]}@example.com"
    response = client.post("/api/v1/auth/login", json={"email": ghost, "password": "securepassword"})
    assert response.status_code == 401
    assert db_session.query(User).filter(User.email == ghost).count() == 0
