"""Tests for push notification subscription persistence."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db.models.push_subscription import PushSubscription
from app.db.models.user import User
from tests.test_users import register_and_login


def _subscription_payload(endpoint: str = "https://push.example.test/device-1") -> dict:
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": "test-p256dh-key",
            "auth": "test-auth-key",
        },
    }


def test_notification_subscribe_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/notifications/subscribe", json=_subscription_payload())

    assert response.status_code == 401


def test_vapid_public_key_requires_configuration(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", None)

    response = client.get("/api/v1/notifications/vapid-public-key")

    assert response.status_code == 503
    assert response.json()["detail"] == "Push notifications are not configured."


def test_vapid_public_key_returns_configured_key(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VAPID_PUBLIC_KEY", "test-public-key")

    response = client.get("/api/v1/notifications/vapid-public-key")

    assert response.status_code == 200
    assert response.json() == {"publicKey": "test-public-key"}


def test_notification_subscribe_persists_current_user_subscription(client: TestClient, db_session) -> None:
    token = register_and_login(client, "push@example.com", "verysecure")

    response = client.post(
        "/api/v1/notifications/subscribe",
        json=_subscription_payload(),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "pytest-device",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    subscription = db_session.scalar(select(PushSubscription))
    assert subscription is not None
    assert subscription.endpoint == "https://push.example.test/device-1"
    assert subscription.keys["p256dh"] == "test-p256dh-key"
    assert subscription.user_agent == "pytest-device"


def test_notification_subscribe_updates_existing_endpoint(client: TestClient, db_session) -> None:
    token = register_and_login(client, "push-update@example.com", "verysecure")
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "first-agent"}
    payload = _subscription_payload()

    create_response = client.post("/api/v1/notifications/subscribe", json=payload, headers=headers)
    assert create_response.status_code == 200

    payload["keys"] = {"p256dh": "new-p256dh-key", "auth": "new-auth-key"}
    update_response = client.post(
        "/api/v1/notifications/subscribe",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "second-agent"},
    )
    assert update_response.status_code == 200

    user = db_session.scalar(select(User).where(User.email == "push-update@example.com"))
    subscriptions = db_session.scalars(
        select(PushSubscription).where(PushSubscription.user_id == user.id)
    ).all()
    assert len(subscriptions) == 1
    assert subscriptions[0].keys["p256dh"] == "new-p256dh-key"
    assert subscriptions[0].user_agent == "second-agent"


def test_notification_subscribe_rejects_incomplete_payload(client: TestClient) -> None:
    token = register_and_login(client, "push-invalid@example.com", "verysecure")

    response = client.post(
        "/api/v1/notifications/subscribe",
        json={"endpoint": "https://push.example.test/device-1", "keys": {"p256dh": "missing-auth"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Subscription keys p256dh and auth are required"
