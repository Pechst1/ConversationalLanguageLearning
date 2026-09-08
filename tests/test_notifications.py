"""Tests for push notification subscription persistence."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db.models.push_subscription import PushSubscription
from app.db.models.user import User
from app.services.notification_service import NotificationService
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


def test_native_notification_subscribe_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/notifications/native/subscribe",
        json={
            "token": "device-token",
            "platform": "ios",
            "environment": "sandbox",
        },
    )

    assert response.status_code == 401


def test_native_notification_subscribe_persists_apns_token(client: TestClient, db_session) -> None:
    token = register_and_login(client, "native-push@example.com", "verysecure")

    response = client.post(
        "/api/v1/notifications/native/subscribe",
        json={
            "token": "apple-device-token",
            "platform": "ios",
            "environment": "sandbox",
        },
        headers={"Authorization": f"Bearer {token}", "User-Agent": "Feuilleton/iPhone"},
    )

    assert response.status_code == 200
    subscription = db_session.scalar(
        select(PushSubscription).where(PushSubscription.endpoint.like("apns://%"))
    )
    assert subscription is not None
    assert subscription.endpoint == "apns://sandbox/apple-device-token"
    assert subscription.keys == {
        "provider": "apns",
        "platform": "ios",
        "environment": "sandbox",
        "token": "apple-device-token",
    }
    assert subscription.user_agent == "Feuilleton/iPhone"


def test_native_notification_subscribe_rejects_unsupported_platform(
    client: TestClient,
) -> None:
    token = register_and_login(client, "android-push@example.com", "verysecure")

    response = client.post(
        "/api/v1/notifications/native/subscribe",
        json={
            "token": "device-token",
            "platform": "android",
            "environment": "production",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only iOS native push is supported in this pilot."


def test_apns_delivery_uses_http2_and_preserves_deep_link(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    access_token = register_and_login(client, "apns-delivery@example.com", "verysecure")
    client.post(
        "/api/v1/notifications/native/subscribe",
        json={
            "token": "apple-device-token",
            "platform": "ios",
            "environment": "sandbox",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )
    user = db_session.scalar(select(User).where(User.email == "apns-delivery@example.com"))
    request: dict = {}

    class FakeResponse:
        status_code = 200
        text = ""

    class FakeClient:
        def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            request["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            return None

        def post(self, url, **kwargs):  # type: ignore[no-untyped-def]
            request["post"] = (url, kwargs)
            return FakeResponse()

    monkeypatch.setattr(settings, "APNS_TEAM_ID", "TEAM")
    monkeypatch.setattr(settings, "APNS_KEY_ID", "KEY")
    monkeypatch.setattr(settings, "APNS_PRIVATE_KEY", "PRIVATE")
    monkeypatch.setattr(settings, "APNS_BUNDLE_ID", "com.pixellab.feuilleton")
    monkeypatch.setattr(
        "app.services.notification_service.jwt.encode",
        lambda *args, **kwargs: "provider-token",
    )
    monkeypatch.setattr("app.services.notification_service.httpx.Client", FakeClient)

    delivered = NotificationService(db_session).send_notification(
        user.id,
        "Votre édition est prête.",
        "Épisode 2 disponible",
        data={"route": "/serial"},
    )

    assert delivered == 1
    assert request["client"]["http2"] is True
    url, kwargs = request["post"]
    assert url == "https://api.sandbox.push.apple.com/3/device/apple-device-token"
    assert kwargs["headers"]["apns-topic"] == "com.pixellab.feuilleton"
    assert kwargs["json"]["route"] == "/serial"
