"""Recovery remains usable after SMTP faults without retaining plaintext secrets."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_password
from app.db.models.password_reset_delivery import PasswordResetDelivery
from app.db.models.user import RefreshToken
from app.schemas.user import UserCreate
from app.services.auth import AuthService, InvalidPasswordResetTokenError
from app.services.password_reset_delivery import deliver_reset_email


@pytest.fixture()
def recovery(db_session, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    monkeypatch.setattr(AuthService, "_deliver_password_reset", lambda *args, **kwargs: False)
    service = AuthService(db_session)
    user = service.register_user(UserCreate(email=f"recovery-{uuid4()}@example.com", password="before-reset-password"))
    issued = service.request_password_reset(user.email)
    delivery = db_session.scalar(select(PasswordResetDelivery).where(PasswordResetDelivery.user_id == user.id))
    return service, user, issued, delivery


def test_smtp_failure_survives_a_new_session_and_retries_the_same_code(recovery, db_session, monkeypatch):
    _, user, issued, delivery = recovery
    assert delivery.status == "pending" and delivery.attempts == 1
    assert issued.reset_code not in delivery.encrypted_payload
    assert issued.reset_token not in delivery.encrypted_payload
    delivery_id, next_attempt = delivery.id, delivery.next_attempt_at
    db_session.expunge(delivery)
    sent = []
    monkeypatch.setattr(AuthService, "_deliver_password_reset", lambda self, user, **payload: sent.append(payload) or True)
    with Session(db_session.get_bind()) as restarted:
        assert deliver_reset_email(restarted, delivery_id, now=next_attempt.replace(tzinfo=UTC)) == "sent"
    assert sent[0]["code"] == issued.reset_code
    row = db_session.get(PasswordResetDelivery, delivery_id)
    assert row.encrypted_payload is None and row.attempts == 2
    assert deliver_reset_email(db_session, delivery_id) == "sent"
    assert len(sent) == 1


@pytest.mark.parametrize("reason", ["expired", "consumed", "superseded", "changed-key", "exhausted-code"])
def test_stale_recovery_messages_are_never_sent(recovery, db_session, monkeypatch, reason):
    service, user, issued, delivery = recovery
    future = datetime.now(UTC) + timedelta(minutes=2)
    if reason == "expired":
        future += timedelta(minutes=20)
    elif reason == "consumed":
        service.confirm_password_reset_code(user.email, issued.reset_code, "after-reset-password")
    elif reason == "superseded":
        user.password_reset_token_hash = "newer-reset"
        db_session.commit()
    elif reason == "exhausted-code":
        user.password_reset_code_hash = None
        db_session.commit()
    else:
        monkeypatch.setattr(settings, "SECRET_KEY", "a-different-test-secret")
    sent = []
    monkeypatch.setattr(AuthService, "_deliver_password_reset", lambda *args, **kwargs: sent.append(True) or True)
    assert deliver_reset_email(db_session, delivery.id, now=future) == "cancelled"
    assert sent == [] and delivery.encrypted_payload is None


def test_repeated_smtp_failures_are_bounded_and_erase_the_message(recovery, db_session):
    _, _, _, delivery = recovery
    for _ in range(4):
        deliver_reset_email(db_session, delivery.id, now=delivery.next_attempt_at.replace(tzinfo=UTC))
    assert delivery.status == "failed" and delivery.attempts == 5
    assert delivery.encrypted_payload is None


def test_exhausted_guesses_cannot_bypass_the_request_cooldown(recovery):
    service, user, issued, _ = recovery
    wrong = f"{(int(issued.reset_code) + 1) % 1_000_000:06d}"
    for _ in range(5):
        with pytest.raises(InvalidPasswordResetTokenError):
            service.confirm_password_reset_code(user.email, wrong, "after-reset-password")
    assert service.request_password_reset(user.email).reset_code is None


def test_password_change_and_session_revocation_roll_back_together(recovery, db_session, monkeypatch):
    service, user, issued, _ = recovery
    service.create_tokens(user)
    row = db_session.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))

    def fail_commit():
        raise RuntimeError("simulated failed transaction")

    with monkeypatch.context() as patch:
        patch.setattr(db_session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="failed transaction"):
            service.confirm_password_reset_code(user.email, issued.reset_code, "after-reset-password")
    db_session.rollback()
    db_session.refresh(user)
    db_session.refresh(row)
    assert verify_password("before-reset-password", user.hashed_password)
    assert row.revoked_at is None
    assert user.password_reset_code_hash is not None
