"""S4 stage 3 — one database outbox for every mail kind.

Grown from the password-reset outbox. A message is staged in the same
transaction as the credential it carries, encrypted with a key derived from
SECRET_KEY, and delivered with retries that survive worker, broker and SMTP
outages. Every terminal state erases the ciphertext; metadata is removed after
seven days.

A row is sent only while it is still true:
* ``password_reset``: the account's current reset (token and code) is the one staged;
* ``verify_email``: the account's current verification code is the one staged,
  and the address it goes to is still the one waiting to be verified;
* ``email_changed``: always, until it expires (it carries no credential).
"""
from __future__ import annotations

import base64
import hmac
import json
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from hashlib import sha256
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.mail_delivery import MailDelivery
from app.db.models.user import User
from app.mail import MAIL_KINDS, mail_language, render_mail

logger = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 5
EMAIL_CHANGED_TTL = timedelta(days=1)


def _cipher() -> Fernet:
    # The key material predates the other kinds: unchanged, so a reset row
    # staged before the migration still decrypts after it.
    material = b"atelier-password-reset-delivery-v1:" + settings.SECRET_KEY.encode()
    return Fernet(base64.urlsafe_b64encode(sha256(material).digest()))


def enqueue_mail(
    db: Session,
    user: User,
    *,
    kind: str,
    payload: dict[str, Any],
    token_hash: str,
    expires_at: datetime,
    now: datetime,
    recipient: str | None = None,
) -> MailDelivery:
    """Stage one message in the caller's transaction (the caller commits)."""
    if kind not in MAIL_KINDS:
        raise ValueError(f"unknown mail kind {kind!r}")
    delivery = MailDelivery(
        user_id=user.id,
        kind=kind,
        recipient=recipient,
        token_hash=token_hash,
        encrypted_payload=_cipher().encrypt(json.dumps(payload).encode()).decode("ascii"),
        status="pending",
        attempts=0,
        next_attempt_at=now,
        expires_at=expires_at,
    )
    db.add(delivery)
    return delivery


def build_message(kind: str, user: User, to: str, payload: dict[str, Any]) -> EmailMessage:
    from app.services.auth import EMAIL_VERIFICATION_CODE_TTL_HOURS, PASSWORD_RESET_CODE_TTL_MINUTES

    values = {
        **payload,
        "ttl_minutes": PASSWORD_RESET_CODE_TTL_MINUTES,
        "link_ttl_minutes": settings.PASSWORD_RESET_TOKEN_TTL_MINUTES,
        "ttl_hours": EMAIL_VERIFICATION_CODE_TTL_HOURS,
        "contact": settings.LEGAL_CONTACT_EMAIL or settings.SMTP_FROM_EMAIL or "",
    }
    subject, body = render_mail(kind, mail_language(user), **values)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL or ""
    message["To"] = to
    message.set_content(body)
    return message


def send_message(message: EmailMessage, *, kind: str) -> bool:
    """Hand one message to SMTP. ``False`` when SMTP is not configured or fails."""
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        logger.info("A %s mail is waiting, but SMTP is not configured.", kind)
        return False
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:  # pragma: no cover - network/email provider failure
        # SMTP exceptions and trace locals can contain the message and its code.
        logger.error("A %s mail could not be delivered (%s)", kind, type(exc).__name__)
        return False
    return True


def _finish(delivery: MailDelivery, status: str, now: datetime) -> None:
    delivery.status = status
    delivery.completed_at = now
    delivery.encrypted_payload = None


def _still_true(db: Session, delivery: MailDelivery, user: User, payload: dict[str, Any]) -> bool:
    from app.services.auth import AuthService

    if delivery.kind == "password_reset":
        return (
            user.password_reset_token_hash == delivery.token_hash
            and hmac.compare_digest(user.password_reset_code_hash or "", AuthService.hash_reset_code(user, payload["code"]))
        )
    if delivery.kind == "verify_email":
        waiting_for = user.pending_email if payload.get("purpose") == "change" else user.email
        return (
            (user.email_verification_code_hash or "") == delivery.token_hash
            and (delivery.recipient or user.email) == waiting_for
            and (payload.get("purpose") == "change" or not user.is_verified)
        )
    return delivery.kind == "email_changed"


def _send(db: Session, delivery: MailDelivery, user: User, payload: dict[str, Any]) -> bool:
    from app.services.auth import AuthService

    if delivery.kind == "password_reset":
        # Kept as the seam the reset tests stub.
        return AuthService(db)._deliver_password_reset(user, **payload)
    message = build_message(delivery.kind, user, delivery.recipient or user.email, payload)
    return send_message(message, kind=delivery.kind)


def deliver_mail(db: Session, delivery_id, *, now: datetime | None = None) -> str:
    """Send one message. Account then message is the lock order used everywhere.

    An interrupted SMTP call may have delivered before the transaction committed.
    Its retry sends the same message, never mints a new credential. SMTP has no
    exactly-once delivery guarantee.
    """
    from app.services.auth import _as_utc

    user_id = db.scalar(select(MailDelivery.user_id).where(MailDelivery.id == delivery_id))
    if user_id is None:
        return "missing"
    user = db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    delivery = db.scalar(
        select(MailDelivery).where(MailDelivery.id == delivery_id)
        .with_for_update(skip_locked=True).execution_options(populate_existing=True)
    )
    if delivery is None:
        db.commit()
        return "busy"
    now = now or datetime.now(UTC)
    if delivery.status != "pending":
        db.commit()
        return delivery.status
    if user is None or not user.is_active or _as_utc(delivery.expires_at) <= now:
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
            if not _still_true(db, delivery, user, payload):
                _finish(delivery, "cancelled", now)
            else:
                delivery.attempts += 1
                if _send(db, delivery, user, payload):
                    _finish(delivery, "sent", now)
                elif delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
                    _finish(delivery, "failed", now)
                else:
                    delivery.next_attempt_at = now + timedelta(seconds=30 * 2 ** (delivery.attempts - 1))
    db.commit()
    return delivery.status


def deliver_due_mail(db: Session, *, limit: int = 25) -> dict[str, int]:
    now = datetime.now(UTC)
    ids = list(db.scalars(
        select(MailDelivery.id).where(
            MailDelivery.status == "pending",
            MailDelivery.next_attempt_at <= now,
        ).order_by(MailDelivery.next_attempt_at).limit(limit)
    ))
    counts: dict[str, int] = {}
    for delivery_id in ids:
        result = deliver_mail(db, delivery_id)
        counts[result] = counts.get(result, 0) + 1
    db.execute(delete(MailDelivery).where(MailDelivery.completed_at < now - timedelta(days=7)))
    db.commit()
    return counts
