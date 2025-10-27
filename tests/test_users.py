"""Tests for user profile endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient


def register_and_login(client: TestClient, email: str, password: str) -> str:
    payload = {
        "email": email,
        "password": password,
        "target_language": "es",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=payload)
    login_response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    token = login_response.json()["access_token"]
    return token


def test_get_current_user_profile(client: TestClient) -> None:
    token = register_and_login(client, "profile@example.com", "verysecure")

    response = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@example.com"
    assert data["target_language"] == "es"


def test_update_current_user_profile(client: TestClient) -> None:
    token = register_and_login(client, "update@example.com", "verysecure")

    update_payload = {"full_name": "Updated Learner", "daily_goal_minutes": 20}
    response = client.patch(
        "/api/v1/users/me",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Learner"
    assert data["daily_goal_minutes"] == 20


def test_list_users_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/users/")
    assert response.status_code == 401

    token = register_and_login(client, "list@example.com", "verysecure")
    auth_headers = {"Authorization": f"Bearer {token}"}

    list_response = client.get("/api/v1/users/", headers=auth_headers, params={"limit": 5})
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1
