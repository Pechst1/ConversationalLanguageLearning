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

    # The pattern used to be \d{2}:\d{2}, which stored "25:99" as a reminder.
    impossible_time_response = client.patch(
        "/api/v1/users/me/settings",
        json={"reminder_time": "25:99"},
        headers=headers,
    )
    assert impossible_time_response.status_code == 422

    valid_time_response = client.patch(
        "/api/v1/users/me/settings",
        json={"reminder_time": "23:59"},
        headers=headers,
    )
    assert valid_time_response.status_code == 200
    assert valid_time_response.json()["reminder_time"] == "23:59"


def test_english_native_can_save_the_direction_registration_gave_them(client: TestClient) -> None:
    """The settings page always posts the stored direction back.

    Registration derives ``fr_to_en`` for English natives, but the settings
    schema only listed the German pair, so that round trip was a guaranteed 422
    and no preference on the page could be saved at all.
    """

    token = register_and_login(client, "direction-en@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    stored = client.get("/api/v1/users/me/settings", headers=headers).json()
    assert stored["default_vocab_direction"] == "fr_to_en"

    echo_response = client.patch(
        "/api/v1/users/me/settings",
        json={"default_vocab_direction": stored["default_vocab_direction"], "theme": "dark"},
        headers=headers,
    )
    assert echo_response.status_code == 200
    assert echo_response.json()["default_vocab_direction"] == "fr_to_en"

    for direction in ("en_to_fr", "fr_to_de", "de_to_fr", "mixed"):
        response = client.patch(
            "/api/v1/users/me/settings",
            json={"default_vocab_direction": direction},
            headers=headers,
        )
        assert response.status_code == 200, direction
        assert response.json()["default_vocab_direction"] == direction

    rejected = client.patch(
        "/api/v1/users/me/settings",
        json={"default_vocab_direction": "fr_to_martian"},
        headers=headers,
    )
    assert rejected.status_code == 422


def test_data_export_returns_every_section(client: TestClient) -> None:
    """The données panel's only download used to 500 on a bad model import."""

    token = register_and_login(client, "export@example.com", "verysecure")

    response = client.get("/api/v1/users/me/export", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "export@example.com"
    for section in (
        "exported_at",
        "vocabulary_progress",
        "grammar_progress",
        "errors",
        "sessions",
        "achievements",
    ):
        assert section in payload


# Account deletion is not covered here: DELETE /users/me walks SQLAlchemy's ORM
# cascade across every learner-owned relationship, and the sqlite schema this
# suite builds does not create all of them (npc_relationships and friends).
# Verified against the dev Postgres instead — the row and every cascading table
# go, and pilot_events/atelier_generation_events keep their rows with a NULL
# user_id (ON DELETE SET NULL), which is the intended anonymisation.


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


def test_address_preference_defaults_to_neutral_and_survives_a_profile_patch(
    client: TestClient,
) -> None:
    """The story engine addresses nobody by guesswork: the learner sets this."""

    token = register_and_login(client, "address-profile@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/users/me", headers=headers).json()["address_preference"] == (
        "neutral"
    )

    patched = client.patch(
        "/api/v1/users/me", json={"address_preference": "feminine"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["address_preference"] == "feminine"

    # A cached profile read must not serve the stale preference back.
    assert client.get("/api/v1/users/me", headers=headers).json()["address_preference"] == (
        "feminine"
    )


def test_address_preference_round_trips_through_the_settings_bundle(client: TestClient) -> None:
    token = register_and_login(client, "address-settings@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/users/me/settings", headers=headers).json()[
        "address_preference"
    ] == "neutral"

    for value in ("masculine", "feminine", "neutral"):
        saved = client.patch(
            "/api/v1/users/me/settings", json={"address_preference": value}, headers=headers
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["address_preference"] == value
        assert client.get("/api/v1/users/me/settings", headers=headers).json()[
            "address_preference"
        ] == value
        assert client.get("/api/v1/users/me", headers=headers).json()["address_preference"] == value


def test_invalid_address_preference_is_rejected(client: TestClient) -> None:
    token = register_and_login(client, "address-invalid@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}"}

    for payload in ({"address_preference": "ma puce"}, {"address_preference": None}):
        for endpoint in ("/api/v1/users/me", "/api/v1/users/me/settings"):
            response = client.patch(endpoint, json=payload, headers=headers)
            assert response.status_code == 422, (endpoint, payload, response.text)

    assert client.get("/api/v1/users/me", headers=headers).json()["address_preference"] == (
        "neutral"
    )
