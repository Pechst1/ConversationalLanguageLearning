"""S4 stage 3 — one mail outbox with kinds, and a verified address.

Before this stage the only mail was the password-reset code, built inline in
``AuthService`` and sent through an outbox that knew only that message. The
address was never verified (``User.is_verified`` existed and nothing set it),
and ``PATCH /users/me/email`` took effect at once, on an unconfirmed address.

These tests pin the new contract:
* three kinds (``password_reset``, ``verify_email``, ``email_changed``), each
  with a template in en, de and fr under ``app/mail/``, addressing the learner
  with tu / du;
* sign-up queues ``verify_email``; an unverified account still plays;
* a reset by mail needs a verified address (an unverified one gets the
  verification mail again instead, so nobody is stranded);
* an email change waits for the code sent to the new address, then is announced
  at the old one;
* the migration keeps pending reset rows deliverable and marks existing
  accounts verified, so nobody is locked out.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db.models.mail_delivery import MailDelivery
from app.db.models.user import User
from app.mail import MAIL_KINDS, render_mail
from app.services import mail_outbox

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "verysecurepassword"


@pytest.fixture()
def outbox(monkeypatch):
    """Every message the outbox hands to SMTP, as (kind, to, subject, body)."""
    sent: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "atelier@example.com")

    def fake_send(message, *, kind):
        sent.append((kind, message["To"], message["Subject"], message.get_content()))
        return True

    monkeypatch.setattr(mail_outbox, "send_message", fake_send)
    return sent


def _register(client: TestClient, email: str, native: str = "de") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": native},
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return response.json()["access_token"]


def _code(body: str) -> str:
    match = re.search(r"\b(\d{6})\b", body)
    assert match, body
    return match.group(1)


def test_every_kind_has_a_template_in_three_languages_with_tu_and_du():
    assert set(MAIL_KINDS) == {"password_reset", "verify_email", "email_changed"}
    values = {"code": "123456", "reset_url": "https://app.example/reset?token=x", "purpose": "signup",
              "new_email": "n***@example.com", "ttl_minutes": 15, "link_ttl_minutes": 60,
              "ttl_hours": 48, "contact": "contact@example.com"}
    for kind in MAIL_KINDS:
        for language in ("en", "de", "fr"):
            subject, body = render_mail(kind, language, **values)
            assert subject.strip() and body.strip(), (kind, language)
            text = f"{subject}\n{body}"
            if language == "fr":
                assert not re.search(r"\b(vous|votre|vos)\b|\b\w{3,}ez\b", text, re.I), (kind, text)
            if language == "de":
                assert not re.search(r"\b(Sie|Ihr|Ihre|Ihnen)\b", text), (kind, text)
    # An unknown language falls back to English rather than failing.
    assert render_mail("verify_email", "pt", **values)[0] == render_mail("verify_email", "en", **values)[0]


def test_sign_up_queues_verify_email_in_the_learners_language_and_the_account_plays(client, db_session, outbox):
    email = f"verify-{uuid4().hex[:8]}@example.com"
    token = _register(client, email, native="de")
    kinds = [row[0] for row in outbox if row[1] == email]
    assert kinds == ["verify_email"], outbox
    assert "Code" in outbox[-1][3] and "deine Adresse" in outbox[-1][3]
    user = db_session.scalar(select(User).where(User.email == email))
    assert user.is_verified is False
    # Unverified, the learner still plays: the account's own reads answer.
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/users/me/settings", headers=headers).status_code == 200

    wrong = client.post("/api/v1/auth/verify-email", json={"code": "000000"}, headers=headers)
    assert wrong.status_code == 400
    ok = client.post("/api/v1/auth/verify-email", json={"code": _code(outbox[-1][3])}, headers=headers)
    assert ok.status_code == 200, ok.text
    db_session.refresh(user)
    assert user.is_verified is True


def test_reset_by_mail_needs_a_verified_address(client, db_session, outbox):
    email = f"reset-{uuid4().hex[:8]}@example.com"
    token = _register(client, email, native="fr")
    outbox.clear()
    # Unverified: the reset is not sent, the verification mail is sent again.
    user = db_session.scalar(select(User).where(User.email == email))
    user.email_verification_sent_at = None  # past the resend cooldown
    db_session.commit()
    assert client.post("/api/v1/auth/password-reset/request", json={"email": email}).status_code in (200, 202)
    assert [row[0] for row in outbox] == ["verify_email"]
    verify = client.post(
        "/api/v1/auth/verify-email", json={"code": _code(outbox[-1][3])},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify.status_code == 200
    outbox.clear()
    assert client.post("/api/v1/auth/password-reset/request", json={"email": email}).status_code in (200, 202)
    assert [row[0] for row in outbox] == ["password_reset"]
    assert "ton" in outbox[-1][3].lower() and "votre" not in outbox[-1][3].lower()


def test_an_unverified_learner_who_forgot_the_password_is_not_stranded(client, db_session, outbox):
    """The verification code sent instead of a reset code works on the reset screen."""
    email = f"forgot-{uuid4().hex[:8]}@example.com"
    _register(client, email, native="en")
    user = db_session.scalar(select(User).where(User.email == email))
    user.email_verification_sent_at = None
    db_session.commit()
    outbox.clear()
    client.post("/api/v1/auth/password-reset/request", json={"email": email})
    kind, _, _, body = outbox[-1]
    assert kind == "verify_email" and "reset screen" in body
    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": email, "code": _code(body), "new_password": "a-brand-new-password"},
    )
    assert confirmed.status_code == 204, confirmed.text
    db_session.refresh(user)
    assert user.is_verified is True
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "a-brand-new-password"})
    assert login.status_code == 200


def test_an_email_change_waits_for_the_new_address_and_is_announced_at_the_old(client, db_session, outbox):
    old = f"old-{uuid4().hex[:8]}@example.com"
    new = f"new-{uuid4().hex[:8]}@example.com"
    token = _register(client, old, native="en")
    headers = {"Authorization": f"Bearer {token}"}
    change = {"current_password": PASSWORD, "new_email": new}

    refused = client.patch("/api/v1/users/me/email", json=change, headers=headers)
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "email_unverified"

    client.post("/api/v1/auth/verify-email", json={"code": _code(outbox[-1][3])}, headers=headers)
    outbox.clear()
    pending = client.patch("/api/v1/users/me/email", json=change, headers=headers)
    assert pending.status_code == 200, pending.text
    assert pending.json()["email"] == old and pending.json()["pending_email"] == new
    user = db_session.scalar(select(User).where(User.email == old))
    assert user is not None and user.pending_email == new
    assert [(row[0], row[1]) for row in outbox] == [("verify_email", new)]

    confirmed = client.post("/api/v1/auth/verify-email", json={"code": _code(outbox[-1][3])}, headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    db_session.refresh(user)
    assert user.email == new and user.pending_email is None and user.is_verified is True
    assert ("email_changed", old) in [(row[0], row[1]) for row in outbox]
    assert new not in next(row for row in outbox if row[0] == "email_changed")[3], "the old inbox gets a masked address"


def test_a_failed_send_stays_in_the_outbox_and_retries(client, db_session, monkeypatch, outbox):
    monkeypatch.setattr(mail_outbox, "send_message", lambda message, *, kind: False)
    email = f"retry-{uuid4().hex[:8]}@example.com"
    _register(client, email)
    row = db_session.scalar(select(MailDelivery).where(MailDelivery.kind == "verify_email").order_by(MailDelivery.created_at.desc()))
    assert row.status == "pending" and row.attempts == 1 and row.recipient == email
    assert row.encrypted_payload and "code" not in row.encrypted_payload


def test_the_migration_keeps_pending_resets_and_marks_existing_accounts_verified():
    migration = next((ROOT / "alembic" / "versions").glob("*_mail_outbox_kinds.py")).read_text()
    assert 'op.rename_table("password_reset_deliveries", "mail_deliveries")' in migration
    assert "server_default=\"password_reset\"" in migration
    assert "UPDATE users SET is_verified = true" in migration
    # The reset cipher key is unchanged, so a row encrypted before the migration still opens.
    assert "atelier-password-reset-delivery-v1:" in (ROOT / "app" / "services" / "mail_outbox.py").read_text()


def test_mail_is_built_only_from_the_templates():
    auth = (ROOT / "app" / "services" / "auth.py").read_text()
    assert "Votre code" not in auth and "EmailMessage()" not in auth, "the reset mail is a template in app/mail/"
