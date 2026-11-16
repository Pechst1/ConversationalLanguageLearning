"""The password-reset entry points, kept for their callers: the outbox behind them
is the general mail outbox (``app/services/mail_outbox.py``, S4 stage 3)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.mail_delivery import MailDelivery
from app.db.models.user import User
from app.services.mail_outbox import (
    MAX_DELIVERY_ATTEMPTS,
    deliver_due_mail,
    deliver_mail,
    enqueue_mail,
)

__all__ = ["MAX_DELIVERY_ATTEMPTS", "deliver_due_reset_emails", "deliver_reset_email", "enqueue_reset_email"]


def enqueue_reset_email(db: Session, user: User, *, code: str, reset_url: str | None, now: datetime) -> MailDelivery:
    """Stage the message in the same transaction as the reset credentials."""
    from app.services.auth import PASSWORD_RESET_CODE_TTL_MINUTES

    return enqueue_mail(
        db, user, kind="password_reset", payload={"code": code, "reset_url": reset_url},
        token_hash=user.password_reset_token_hash, now=now,
        expires_at=now + timedelta(minutes=PASSWORD_RESET_CODE_TTL_MINUTES),
    )


deliver_reset_email = deliver_mail
deliver_due_reset_emails = deliver_due_mail
