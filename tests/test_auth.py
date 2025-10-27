"""Integration tests for authentication endpoints."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


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


def test_user_login_invalid_credentials(client: TestClient) -> None:
    payload = {
        "email": "unknown@example.com",
        "password": "wrongpassword",
    }
    response = client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
