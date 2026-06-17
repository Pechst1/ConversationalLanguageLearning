"""Integration tests for authentication endpoints."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def test_user_registration_success(client: TestClient) -> None:
    payload = {
        "email": "learner@example.com",
        "password": "securepassword",
        "full_name": "Learner One",
        "target_language": "es",
        "native_language": "en",
    }

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert uuid.UUID(data["id"])  # Valid UUID string
    assert data["email"] == payload["email"]
    assert data["target_language"] == "es"
    assert data["native_language"] == "en"
    assert data["is_active"] is True


def test_user_registration_duplicate_email(client: TestClient) -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "anothersecurepassword",
        "target_language": "fr",
        "native_language": "en",
    }

    first_response = client.post("/api/v1/auth/register", json=payload)
    assert first_response.status_code == 201

    duplicate_response = client.post("/api/v1/auth/register", json=payload)
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "A user with this email already exists."


def test_user_login_success(client: TestClient) -> None:
    registration_payload = {
        "email": "login@example.com",
        "password": "supersecure",
        "target_language": "de",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=registration_payload)

    login_payload = {
        "email": "login@example.com",
        "password": "supersecure",
    }
    response = client.post("/api/v1/auth/login", json=login_payload)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_refresh_rotates_refresh_token(client: TestClient) -> None:
    registration_payload = {
        "email": "refresh@example.com",
        "password": "supersecure",
        "target_language": "fr",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=registration_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "supersecure"},
    )
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert data["access_token"]
    assert data["refresh_token"] != refresh_token

    replay_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert replay_response.status_code == 401


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    registration_payload = {
        "email": "logout@example.com",
        "password": "supersecure",
        "target_language": "fr",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=registration_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "supersecure"},
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

    assert logout_response.status_code == 204
    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 401


def test_password_reset_request_is_generic_for_unknown_email(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)

    response = client.post("/api/v1/auth/password-reset/request", json={"email": "missing@example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["message"].startswith("If an account exists")
    assert data["reset_token"] is None
    assert data["reset_url"] is None


def test_password_reset_updates_password_and_revokes_sessions(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    monkeypatch.setattr(settings, "PASSWORD_RESET_BASE_URL", "https://app.example.test/auth/forgot-password")
    registration_payload = {
        "email": "reset@example.com",
        "password": "oldsecurepassword",
        "target_language": "fr",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=registration_payload)
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "oldsecurepassword"},
    )
    refresh_token = login_response.json()["refresh_token"]

    request_response = client.post("/api/v1/auth/password-reset/request", json={"email": "RESET@example.com"})

    assert request_response.status_code == 200
    reset_payload = request_response.json()
    reset_token = reset_payload["reset_token"]
    assert reset_token
    assert reset_payload["reset_url"].startswith("https://app.example.test/auth/forgot-password?token=")

    confirm_response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "newsecurepassword"},
    )

    assert confirm_response.status_code == 204
    old_login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "oldsecurepassword"},
    )
    assert old_login_response.status_code == 401
    new_login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "newsecurepassword"},
    )
    assert new_login_response.status_code == 200
    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 401

    replay_response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": reset_token, "new_password": "anothersecurepassword"},
    )
    assert replay_response.status_code == 400


def test_production_rejects_password_reset_without_smtp(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", False)
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", False)
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", None)

    with pytest.raises(RuntimeError, match="SMTP_HOST and SMTP_FROM_EMAIL"):
        with TestClient(create_app()):
            pass


def test_production_rejects_dev_auth_conveniences(monkeypatch) -> None:
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", True)
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", False)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "support@example.test")

    with pytest.raises(RuntimeError, match="AUTO_CREATE_USERS_ON_LOGIN"):
        with TestClient(create_app()):
            pass


def test_user_login_invalid_credentials(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", False)
    payload = {
        "email": "unknown@example.com",
        "password": "wrongpassword",
    }
    response = client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
