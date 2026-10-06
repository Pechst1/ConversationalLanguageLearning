"""A database outbox survives worker, broker and SMTP outages.

Credentials are encrypted with a purpose-specific key derived from SECRET_KEY.
Only the account's current, unexpired reset can be delivered. All terminal states
erase the ciphertext; metadata is removed after seven days.
"""
from __future__ import annotations

import base64
import hmac
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.password_reset_delivery import PasswordResetDelivery
from app.db.models.user import User

MAX_DELIVERY_ATTEMPTS = 5


def _cipher() -> Fernet:
    material = b"atelier-password-reset-delivery-v1:" + settings.SECRET_KEY.encode()
    return Fernet(base64.urlsafe_b64encode(sha256(material).digest()))


def enqueue_reset_email(db: Session, user: User, *, code: str, reset_url: str | None, now: datetime) -> PasswordResetDelivery:
    """Stage the message in the same transaction as the reset credentials."""
    from app.services.auth import PASSWORD_RESET_CODE_TTL_MINUTES

    payload = json.dumps({"code": code, "reset_url": reset_url}).encode()
    delivery = PasswordResetDelivery(
        user_id=user.id,
        token_hash=user.password_reset_token_hash,
        encrypted_payload=_cipher().encrypt(payload).decode("ascii"),
        status="pending",
        attempts=0,
        next_attempt_at=now,
        expires_at=now + timedelta(minutes=PASSWORD_RESET_CODE_TTL_MINUTES),
    )
    db.add(delivery)
    return delivery


def _finish(delivery: PasswordResetDelivery, status: str, now: datetime) -> None:
    delivery.status = status
    delivery.completed_at = now
    delivery.encrypted_payload = None


def deliver_reset_email(db: Session, delivery_id, *, now: datetime | None = None) -> str:
    """Send one message. Account then message is the lock order used everywhere.

    An interrupted SMTP call may have delivered before the transaction committed.
    Its retry sends the same credentials, never mints a new reset. SMTP has no
    exactly-once delivery guarantee.
    """
    from app.services.auth import AuthService, _as_utc

    user_id = db.scalar(select(PasswordResetDelivery.user_id).where(PasswordResetDelivery.id == delivery_id))
    if user_id is None:
        return "missing"
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    delivery = db.scalar(
        select(PasswordResetDelivery).where(PasswordResetDelivery.id == delivery_id)
        .with_for_update(skip_locked=True).execution_options(populate_existing=True)
    )
    if delivery is None:
        db.commit()
        return "busy"
    now = now or datetime.now(UTC)
    if delivery.status != "pending":
        db.commit()
        return delivery.status
    if (
        user is None or not user.is_active
        or user.password_reset_token_hash != delivery.token_hash
        or _as_utc(delivery.expires_at) <= now
    ):
        _finish(delivery, "cancelled", now)
    elif _as_utc(delivery.next_attempt_at) > now:
        db.commit()
        return "waiting"
    else:
        try:
            payload = json.loads(_cipher().decrypt(delivery.encrypted_payload.encode("ascii")))
        except (InvalidToken, ValueError, AttributeError):
            _finish(delivery, "cancelled", now)
        else:
            if not hmac.compare_digest(
                user.password_reset_code_hash or "",
                AuthService.hash_reset_code(user, payload["code"]),
            ):
                _finish(delivery, "cancelled", now)
            else:
                delivery.attempts += 1
                sent = AuthService(db)._deliver_password_reset(user, **payload)
                if sent:
                    _finish(delivery, "sent", now)
                elif delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
                    _finish(delivery, "failed", now)
                else:
                    delivery.next_attempt_at = now + timedelta(seconds=30 * 2 ** (delivery.attempts - 1))
    db.commit()
    return delivery.status


def deliver_due_reset_emails(db: Session, *, limit: int = 25) -> dict[str, int]:
    now = datetime.now(UTC)
    ids = list(db.scalars(
        select(PasswordResetDelivery.id).where(
            PasswordResetDelivery.status == "pending",
            PasswordResetDelivery.next_attempt_at <= now,
        ).order_by(PasswordResetDelivery.next_attempt_at).limit(limit)
    ))
    counts: dict[str, int] = {}
    for delivery_id in ids:
        result = deliver_reset_email(db, delivery_id)
        counts[result] = counts.get(result, 0) + 1
    db.execute(delete(PasswordResetDelivery).where(
        PasswordResetDelivery.completed_at < now - timedelta(days=7),
    ))
    db.commit()
    return counts
