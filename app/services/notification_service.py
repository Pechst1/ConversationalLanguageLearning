"""Push delivery for browser subscriptions and native Apple devices."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

import httpx
from jose import jwt
from jose.exceptions import JOSEError
from loguru import logger
from pywebpush import WebPushException, webpush
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.push_subscription import PushSubscription


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def subscribe(
        self,
        user_id: UUID,
        subscription_info: dict,
        user_agent: str | None = None,
    ) -> None:
        """Register or refresh a Web Push subscription."""
        endpoint = subscription_info.get("endpoint")
        if not endpoint:
            raise ValueError("Endpoint required")

        keys = subscription_info.get("keys")
        if not isinstance(keys, dict) or not keys.get("p256dh") or not keys.get("auth"):
            raise ValueError("Subscription keys p256dh and auth are required")

        stmt = select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
        existing = self.db.scalars(stmt).first()
        if existing:
            existing.keys = keys
            existing.user_agent = user_agent
        else:
            self.db.add(
                PushSubscription(
                    user_id=user_id,
                    endpoint=endpoint,
                    keys=keys,
                    user_agent=user_agent,
                )
            )

        self.db.commit()

    def subscribe_native(
        self,
        user_id: UUID,
        *,
        token: str,
        platform: str,
        environment: str,
        user_agent: str | None = None,
    ) -> None:
        """Register a native token while reusing the existing subscription store."""
        normalized_platform = str(platform or "").strip().lower()
        normalized_environment = str(environment or "").strip().lower()
        normalized_token = str(token or "").strip()
        if normalized_platform != "ios":
            raise ValueError("Only iOS native push is supported in this pilot.")
        if normalized_environment not in {"sandbox", "production"}:
            raise ValueError("Environment must be sandbox or production.")
        if not normalized_token or len(normalized_token) > 512:
            raise ValueError("A valid native device token is required.")

        endpoint = f"apns://{normalized_environment}/{normalized_token}"
        stmt = select(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
        existing = self.db.scalars(stmt).first()
        keys = {
            "provider": "apns",
            "platform": normalized_platform,
            "environment": normalized_environment,
            "token": normalized_token,
        }
        if existing:
            existing.keys = keys
            existing.user_agent = user_agent
        else:
            self.db.add(
                PushSubscription(
                    user_id=user_id,
                    endpoint=endpoint,
                    keys=keys,
                    user_agent=user_agent,
                )
            )
        self.db.commit()

    def send_notification(
        self,
        user_id: UUID,
        message: str,
        title: str = "Feuilleton",
        *,
        data: dict[str, Any] | None = None,
    ) -> int:
        """Send to every configured device and return successful deliveries."""
        stmt = select(PushSubscription).where(PushSubscription.user_id == user_id)
        subscriptions = self.db.scalars(stmt).all()
        payload = json.dumps({"title": title, "body": message, "data": data or {}})
        delivered = 0

        for subscription in subscriptions:
            provider = str((subscription.keys or {}).get("provider") or "web")
            if provider == "apns" or str(subscription.endpoint).startswith("apns://"):
                delivered += int(
                    self._send_apns(
                        subscription,
                        title=title,
                        message=message,
                        data=data or {},
                    )
                )
                continue

            if not settings.VAPID_PRIVATE_KEY:
                logger.debug(
                    "VAPID keys not configured; skipping browser push",
                    subscription_id=str(subscription.id),
                )
                continue
            try:
                webpush(
                    subscription_info={
                        "endpoint": subscription.endpoint,
                        "keys": subscription.keys,
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                )
                delivered += 1
            except WebPushException as exc:
                if exc.response and exc.response.status_code in {404, 410}:
                    self.db.delete(subscription)
                else:
                    logger.warning(
                        "Web push failed",
                        subscription_id=str(subscription.id),
                        error=str(exc),
                    )

        self.db.commit()
        return delivered

    def _send_apns(
        self,
        subscription: PushSubscription,
        *,
        title: str,
        message: str,
        data: dict[str, Any],
    ) -> bool:
        keys = subscription.keys or {}
        token = str(keys.get("token") or "").strip()
        if not token:
            logger.warning(
                "APNs subscription is missing its device token",
                subscription_id=str(subscription.id),
            )
            return False
        if not all(
            (
                settings.APNS_TEAM_ID,
                settings.APNS_KEY_ID,
                settings.APNS_PRIVATE_KEY,
                settings.APNS_BUNDLE_ID,
            )
        ):
            logger.debug("APNs credentials not configured; skipping native push")
            return False

        use_sandbox = str(keys.get("environment") or "") == "sandbox"
        host = "api.sandbox.push.apple.com" if use_sandbox else "api.push.apple.com"
        notification_data = {str(key): value for key, value in data.items()}
        body = {
            "aps": {
                "alert": {"title": title, "body": message},
                "sound": "default",
            },
            **notification_data,
        }
        try:
            private_key = str(settings.APNS_PRIVATE_KEY).replace("\\n", "\n")
            provider_token = jwt.encode(
                {"iss": settings.APNS_TEAM_ID, "iat": int(time.time())},
                private_key,
                algorithm="ES256",
                headers={"kid": settings.APNS_KEY_ID},
            )
            with httpx.Client(http2=True, timeout=10.0) as client:
                response = client.post(
                    f"https://{host}/3/device/{token}",
                    headers={
                        "authorization": f"bearer {provider_token}",
                        "apns-topic": settings.APNS_BUNDLE_ID,
                        "apns-push-type": "alert",
                        "apns-priority": "10",
                    },
                    json=body,
                )
            if response.status_code == 200:
                return True
            if response.status_code in {404, 410}:
                self.db.delete(subscription)
            logger.warning(
                "APNs delivery failed",
                subscription_id=str(subscription.id),
                status=response.status_code,
                response=response.text[:300],
            )
        except (httpx.HTTPError, ImportError, JOSEError, ValueError) as exc:
            logger.warning(
                "APNs request failed",
                subscription_id=str(subscription.id),
                error=str(exc),
            )
        return False
