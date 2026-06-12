"""Tests for user profile endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models.user import User


def register_and_login_pair(client: TestClient, email: str, password: str) -> dict[str, str]:
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
    return login_response.json()


def register_and_login(client: TestClient, email: str, password: str) -> str:
    return register_and_login_pair(client, email, password)["access_token"]


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


def test_user_settings_bundle_can_be_updated(client: TestClient) -> None:
    token = register_and_login(client, "settings@example.com", "verysecure")

    response = client.patch(
        "/api/v1/users/me/settings",
        json={
            "theme": "dark",
            "font_size": "large",
            "default_vocab_direction": "mixed",
            "practice_reminders": False,
            "grammar_correction_level": "strict",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == "dark"
    assert data["font_size"] == "large"
    assert data["default_vocab_direction"] == "mixed"
    assert data["practice_reminders"] is False
    assert data["grammar_correction_level"] == "strict"


def test_user_settings_validation_rejects_invalid_payloads(client: TestClient) -> None:
    token = register_and_login(client, "settings-validation@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    invalid_theme_response = client.patch(
        "/api/v1/users/me/settings",
        json={"theme": "sepia"},
        headers=headers,
    )
    assert invalid_theme_response.status_code == 422

    invalid_time_response = client.patch(
        "/api/v1/users/me/settings",
        json={"reminder_time": "morning"},
        headers=headers,
    )
    assert invalid_time_response.status_code == 422

    empty_payload_response = client.patch(
        "/api/v1/users/me/settings",
        json={},
        headers=headers,
    )
    assert empty_payload_response.status_code == 422


def test_password_change_invalidates_existing_access_token(client: TestClient) -> None:
    token = register_and_login(client, "password@example.com", "verysecure")

    response = client.patch(
        "/api/v1/users/me/password",
        json={"current_password": "verysecure", "new_password": "newsecurepassword"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    old_token_response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert old_token_response.status_code == 401

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "password@example.com", "password": "newsecurepassword"},
    )
    assert login_response.status_code == 200


def test_password_change_revokes_existing_refresh_token(client: TestClient) -> None:
    tokens = register_and_login_pair(client, "password-refresh@example.com", "verysecure")

    response = client.patch(
        "/api/v1/users/me/password",
        json={"current_password": "verysecure", "new_password": "newsecurepassword"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 204
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401


def test_failed_password_change_keeps_refresh_token_valid(client: TestClient) -> None:
    tokens = register_and_login_pair(client, "password-failed@example.com", "verysecure")

    response = client.patch(
        "/api/v1/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "newsecurepassword"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 400
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200


def test_email_change_updates_login_and_invalidates_old_token(client: TestClient) -> None:
    token = register_and_login(client, "old-email@example.com", "verysecure")

    response = client.patch(
        "/api/v1/users/me/email",
        json={"current_password": "verysecure", "new_email": "new-email@example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "new-email@example.com"
    old_token_response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert old_token_response.status_code == 401
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "new-email@example.com", "password": "verysecure"},
    )
    assert login_response.status_code == 200


def test_email_change_revokes_existing_refresh_token(client: TestClient, monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", False)
    tokens = register_and_login_pair(client, "email-refresh-old@example.com", "verysecure")

    response = client.patch(
        "/api/v1/users/me/email",
        json={"current_password": "verysecure", "new_email": "email-refresh-new@example.com"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 200
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401

    old_email_login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "email-refresh-old@example.com", "password": "verysecure"},
    )
    assert old_email_login_response.status_code == 401


def test_sign_out_all_invalidates_existing_access_token(client: TestClient) -> None:
    token = register_and_login(client, "signout@example.com", "verysecure")

    response = client.post("/api/v1/users/me/sign-out-all", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204
    old_token_response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert old_token_response.status_code == 401


def test_sign_out_all_revokes_existing_refresh_token(client: TestClient) -> None:
    tokens = register_and_login_pair(client, "signout-refresh@example.com", "verysecure")

    response = client.post(
        "/api/v1/users/me/sign-out-all",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 204
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401


def test_list_users_requires_admin(client: TestClient, db_session) -> None:
    response = client.get("/api/v1/users/")
    assert response.status_code == 401

    token = register_and_login(client, "list@example.com", "verysecure")
    auth_headers = {"Authorization": f"Bearer {token}"}

    list_response = client.get("/api/v1/users/", headers=auth_headers, params={"limit": 5})
    assert list_response.status_code == 403

    admin_token = register_and_login(client, "admin@example.com", "verysecure")
    admin_user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    admin_user.role = "admin"
    db_session.add(admin_user)
    db_session.commit()

    list_response = client.get(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"limit": 5},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1
