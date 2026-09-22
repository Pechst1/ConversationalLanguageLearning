"""WP-71 — accounts that stay signed in and can be recovered.

Four defects, each a learner either thrown out of the app or locked out of it:

* Ten requests waking together after the access token expired each refreshed
  with the same token. The server rotated on the first and answered the other
  nine 401, and the client wiped the keychain. A just-rotated token now gets the
  same successor for a short grace window; after it, a replay revokes the family.
* bcrypt 5 raises past 72 bytes, which was a 500 on sign-up and sign-in.
* Email case was significant: «Anna@» and «anna@» were two accounts.
* Password reset sent a localhost link. It now sends a six-digit code that is
  typed in the app: hashed, 15 minutes, five attempts, one use.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import get_password_hash, verify_password
from app.db.models.user import RefreshToken, User
from app.services import auth as auth_service
from app.services.auth import AuthService

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "supersecure"


def _register(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "native_language": "en"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _me(client: TestClient, access_token: str) -> int:
    return client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"}
    ).status_code


def _refresh(client: TestClient, refresh_token: str):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


# ---------------------------------------------------------------------------
# Refresh grace window
# ---------------------------------------------------------------------------


def test_ten_refreshes_racing_one_rotation_all_stay_signed_in(client: TestClient) -> None:
    _register(client, "racer@example.com")
    stale = _login(client, "racer@example.com")["refresh_token"]

    responses = [_refresh(client, stale) for _ in range(10)]

    assert [r.status_code for r in responses] == [200] * 10
    successors = {r.json()["refresh_token"] for r in responses}
    # One rotation, one successor: every racer holds the token the winner holds.
    assert len(successors) == 1
    (successor,) = successors
    assert successor != stale
    for response in responses:
        assert _me(client, response.json()["access_token"]) == 200

    # The shared successor is a normal live token: it rotates onward.
    onward = _refresh(client, successor)
    assert onward.status_code == 200
    assert onward.json()["refresh_token"] not in {stale, successor}


def test_grace_does_not_mint_extra_sessions(client: TestClient, db_session: Session) -> None:
    user = _register(client, "single@example.com")
    stale = _login(client, "single@example.com")["refresh_token"]

    for _ in range(5):
        assert _refresh(client, stale).status_code == 200

    rows = db_session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == uuid.UUID(user["id"]))
    ).all()
    live = [row for row in rows if row.revoked_at is None]
    assert len(rows) == 2 and len(live) == 1
    assert rows[0].family_id == rows[1].family_id


def test_replay_after_the_window_revokes_the_family(client: TestClient, monkeypatch) -> None:
    _register(client, "replay@example.com")
    stale = _login(client, "replay@example.com")["refresh_token"]
    successor = _refresh(client, stale).json()["refresh_token"]

    monkeypatch.setattr(auth_service, "REFRESH_TOKEN_GRACE_SECONDS", -1)
    assert _refresh(client, stale).status_code == 401
    # The replay was treated as theft: the successor dies with its family…
    assert _refresh(client, successor).status_code == 401
    # …but another device's sign-in is a different family and survives.


def test_replay_revokes_only_its_own_family(client: TestClient, monkeypatch) -> None:
    _register(client, "twodevices@example.com")
    phone = _login(client, "twodevices@example.com")["refresh_token"]
    laptop = _login(client, "twodevices@example.com")["refresh_token"]
    _refresh(client, phone)

    monkeypatch.setattr(auth_service, "REFRESH_TOKEN_GRACE_SECONDS", -1)
    assert _refresh(client, phone).status_code == 401
    assert _refresh(client, laptop).status_code == 200


def test_grace_window_is_bounded_in_time(client: TestClient, db_session: Session) -> None:
    _register(client, "late@example.com")
    stale = _login(client, "late@example.com")["refresh_token"]
    assert _refresh(client, stale).status_code == 200

    record = db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == AuthService.hash_token(stale))
    )
    record.rotated_at = datetime.now(UTC) - timedelta(
        seconds=auth_service.REFRESH_TOKEN_GRACE_SECONDS + 5
    )
    db_session.commit()

    assert _refresh(client, stale).status_code == 401


def test_grace_never_outlives_a_logout(client: TestClient) -> None:
    _register(client, "logout-race@example.com")
    stale = _login(client, "logout-race@example.com")["refresh_token"]
    successor = _refresh(client, stale).json()["refresh_token"]

    assert client.post("/api/v1/auth/logout", json={"refresh_token": successor}).status_code == 204
    assert _refresh(client, stale).status_code == 401
    assert _refresh(client, successor).status_code == 401


def test_grace_never_outlives_a_password_change(client: TestClient) -> None:
    _register(client, "pwchange@example.com")
    tokens = _login(client, "pwchange@example.com")
    stale = tokens["refresh_token"]
    _refresh(client, stale)

    changed = client.patch(
        "/api/v1/users/me/password",
        json={"current_password": PASSWORD, "new_password": "anothersecure"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert changed.status_code == 204
    assert _refresh(client, stale).status_code == 401


def test_a_racer_one_rotation_behind_follows_the_chain(client: TestClient) -> None:
    _register(client, "chain@example.com")
    first = _login(client, "chain@example.com")["refresh_token"]
    second = _refresh(client, first).json()["refresh_token"]
    third = _refresh(client, second).json()["refresh_token"]

    late = _refresh(client, first)
    assert late.status_code == 200
    assert late.json()["refresh_token"] == third


# ---------------------------------------------------------------------------
# bcrypt's 72 bytes
# ---------------------------------------------------------------------------


def test_signup_with_a_password_over_72_bytes_is_a_422_not_a_500(client: TestClient) -> None:
    # 40 characters, 80 bytes: under the old 128-character cap, over bcrypt's.
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "long@example.com", "password": "é" * 40},
    )
    assert response.status_code == 422
    assert "72 bytes" in str(response.json())


def test_signup_with_exactly_72_bytes_works(client: TestClient) -> None:
    _register(client, "edge@example.com", password="é" * 36)
    assert _login(client, "edge@example.com", password="é" * 36)["access_token"]


def test_signin_with_a_long_password_is_a_401_not_a_500(client: TestClient) -> None:
    _register(client, "short@example.com")
    response = client.post(
        "/api/v1/auth/login", json={"email": "short@example.com", "password": "x" * 300}
    )
    assert response.status_code == 401


def test_a_bcrypt4_account_with_a_long_password_still_signs_in(db_session: Session, client: TestClient) -> None:
    long_password = "a-very-long-passphrase-" * 5  # 115 bytes
    legacy_hash = bcrypt.hashpw(long_password.encode()[:72], bcrypt.gensalt()).decode()
    db_session.add(User(email="legacy-long@example.com", hashed_password=legacy_hash))
    db_session.commit()

    assert _login(client, "legacy-long@example.com", password=long_password)["access_token"]


def test_verify_password_never_raises() -> None:
    assert verify_password("x" * 200, get_password_hash("short-enough")) is False
    assert verify_password("anything", "not-a-bcrypt-hash") is False
    assert verify_password("anything", "") is False
    with pytest.raises(ValueError):
        get_password_hash("x" * 73)


def test_password_change_and_reset_refuse_over_72_bytes(client: TestClient) -> None:
    _register(client, "change-long@example.com")
    access = _login(client, "change-long@example.com")["access_token"]
    response = client.patch(
        "/api/v1/users/me/password",
        json={"current_password": PASSWORD, "new_password": "🙂" * 19},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "change-long@example.com", "code": "123456", "new_password": "🙂" * 19},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Email case
# ---------------------------------------------------------------------------


def test_email_is_stored_normalised_and_matched_without_case(client: TestClient) -> None:
    created = _register(client, "  Anna.Martin@Example.COM ")
    assert created["email"] == "anna.martin@example.com"

    assert _login(client, "ANNA.MARTIN@example.com")["access_token"]
    assert _login(client, " anna.martin@EXAMPLE.com")["access_token"]


def test_two_accounts_differing_by_case_cannot_be_created(client: TestClient) -> None:
    _register(client, "Case@Example.com")
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "case@example.com", "password": PASSWORD},
    )
    assert duplicate.status_code == 400


def test_legacy_mixed_case_account_signs_in_and_blocks_its_twin(
    client: TestClient, db_session: Session
) -> None:
    db_session.add(User(email="Legacy@Example.com", hashed_password=get_password_hash(PASSWORD)))
    db_session.commit()

    assert _login(client, "legacy@example.com")["access_token"]
    duplicate = client.post(
        "/api/v1/auth/register", json={"email": "legacy@example.com", "password": PASSWORD}
    )
    assert duplicate.status_code == 400


def test_legacy_duplicates_by_case_do_not_500(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    db_session.add_all(
        [
            User(email="Twin@Example.com", hashed_password=get_password_hash("first-password")),
            User(email="twin@example.com", hashed_password=get_password_hash("second-password")),
        ]
    )
    db_session.commit()

    assert _login(client, "TWIN@example.com", password="first-password")["access_token"]
    assert _login(client, "twin@example.com", password="second-password")["access_token"]

    requested = client.post("/api/v1/auth/password-reset/request", json={"email": "TWIN@example.com"})
    assert requested.status_code == 200
    code = requested.json()["reset_code"]
    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "twin@example.com", "code": code, "new_password": "brand-new-password"},
    )
    assert confirmed.status_code == 204
    # The exact-case account is the one that was reset.
    assert _login(client, "twin@example.com", password="brand-new-password")["access_token"]


# ---------------------------------------------------------------------------
# Six-digit reset code
# ---------------------------------------------------------------------------


def _request_code(client: TestClient, email: str) -> str:
    response = client.post("/api/v1/auth/password-reset/request", json={"email": email})
    assert response.status_code == 200
    code = response.json()["reset_code"]
    assert code and len(code) == 6 and code.isdigit()
    return code


def _confirm_code(client: TestClient, email: str, code: str, new_password: str = "newsecurepassword"):
    return client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": email, "code": code, "new_password": new_password},
    )


def _age_reset_request(db_session: Session, email: str, **delta: float) -> None:
    user = db_session.scalar(select(User).where(User.email == email))
    user.password_reset_requested_at = datetime.now(UTC) - timedelta(**delta)
    db_session.commit()


def test_reset_completes_with_the_emailed_code(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "coder@example.com", password="oldsecurepassword")
    session = _login(client, "coder@example.com", password="oldsecurepassword")

    code = _request_code(client, "Coder@Example.com")
    user = db_session.scalar(select(User).where(User.email == "coder@example.com"))
    assert code not in (user.password_reset_code_hash or "")  # stored hashed

    assert _confirm_code(client, " CODER@example.com", f" {code} ").status_code == 204

    # Every session ended through the token version.
    assert _refresh(client, session["refresh_token"]).status_code == 401
    assert _me(client, session["access_token"]) == 401
    assert client.post(
        "/api/v1/auth/login", json={"email": "coder@example.com", "password": "oldsecurepassword"}
    ).status_code == 401
    assert _login(client, "coder@example.com", password="newsecurepassword")["access_token"]

    # Single use.
    assert _confirm_code(client, "coder@example.com", code, "yetanotherpassword").status_code == 400


def test_code_allows_five_attempts_then_dies(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "guesser@example.com")
    code = _request_code(client, "guesser@example.com")
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"

    for _ in range(auth_service.PASSWORD_RESET_CODE_MAX_ATTEMPTS):
        response = _confirm_code(client, "guesser@example.com", wrong)
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid or expired password reset code."

    # The right code, too late.
    assert _confirm_code(client, "guesser@example.com", code).status_code == 400
    assert _login(client, "guesser@example.com")["access_token"]


def test_a_wrong_guess_or_two_does_not_burn_the_code(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "typo@example.com")
    code = _request_code(client, "typo@example.com")
    wrong = f"{(int(code) + 7) % 1_000_000:06d}"

    assert _confirm_code(client, "typo@example.com", wrong).status_code == 400
    assert _confirm_code(client, "typo@example.com", wrong).status_code == 400
    assert _confirm_code(client, "typo@example.com", code).status_code == 204


def test_code_expires_after_fifteen_minutes(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "slow@example.com")
    code = _request_code(client, "slow@example.com")
    _age_reset_request(db_session, "slow@example.com", minutes=16)

    assert _confirm_code(client, "slow@example.com", code).status_code == 400


def test_code_for_one_account_does_not_open_another(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "owner@example.com")
    _register(client, "victim@example.com")
    code = _request_code(client, "owner@example.com")

    assert _confirm_code(client, "victim@example.com", code).status_code == 400
    assert _confirm_code(client, "nobody@example.com", code).status_code == 400


def test_a_new_code_is_not_issued_within_the_cooldown(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "again@example.com")
    _request_code(client, "again@example.com")

    second = client.post("/api/v1/auth/password-reset/request", json={"email": "again@example.com"})
    assert second.status_code == 200 and second.json()["reset_code"] is None

    # After the cooldown a request issues a fresh code again.
    _age_reset_request(db_session, "again@example.com", seconds=90)
    fresh = _request_code(client, "again@example.com")
    assert _confirm_code(client, "again@example.com", fresh).status_code == 204


def test_within_the_cooldown_the_first_code_stays_valid(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "patient@example.com")
    first = _request_code(client, "patient@example.com")
    client.post("/api/v1/auth/password-reset/request", json={"email": "patient@example.com"})

    assert _confirm_code(client, "patient@example.com", first).status_code == 204


def test_the_old_link_token_still_works_and_spends_the_code(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    _register(client, "linker@example.com")
    payload = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "linker@example.com"}
    ).json()

    confirmed = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": payload["reset_token"], "new_password": "linkedpassword"},
    )
    assert confirmed.status_code == 204
    assert _confirm_code(client, "linker@example.com", payload["reset_code"]).status_code == 400


def test_confirm_requires_a_token_or_email_and_code(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/password-reset/confirm", json={"new_password": "newsecurepassword"}
    )
    assert response.status_code == 422
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"email": "a@example.com", "code": "12ab56", "new_password": "newsecurepassword"},
    )
    assert response.status_code == 422


class _FakeSMTP:
    sent: list = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def starttls(self) -> None:
        pass

    def login(self, *args) -> None:
        pass

    def send_message(self, message) -> None:
        _FakeSMTP.sent.append(message)


@pytest.mark.parametrize(
    ("base_url", "expects_link"),
    [
        ("http://localhost:3000/auth/forgot-password", False),
        ("https://atelier.example.org/auth/forgot-password", True),
    ],
)
def test_the_email_carries_the_code_and_a_link_only_when_public(
    client: TestClient, monkeypatch, base_url: str, expects_link: bool
) -> None:
    _FakeSMTP.sent = []
    monkeypatch.setattr(auth_service.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "atelier@example.test")
    monkeypatch.setattr(settings, "PASSWORD_RESET_BASE_URL", base_url)
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    email = f"mailed-{'public' if expects_link else 'local'}@example.com"
    _register(client, email)

    code = _request_code(client, email)

    assert len(_FakeSMTP.sent) == 1
    body = _FakeSMTP.sent[0].get_content()
    assert code in _FakeSMTP.sent[0]["Subject"] and code in body
    assert ("http" in body) is expects_link
    assert "localhost" not in body


# ---------------------------------------------------------------------------
# Deploy manifest
# ---------------------------------------------------------------------------


def test_render_manifest_satisfies_the_production_startup_check() -> None:
    yaml = pytest.importorskip("yaml")
    manifest = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    for service in manifest["services"]:
        if service.get("type") not in {"web", "worker"}:
            continue
        env = {item["key"]: item for item in service.get("envVars", [])}
        assert env["APP_ENV"].get("value") == "production", service["name"]
        assert "ATELIER_DAILY_JOURNEY_COHORT" in env
        if service["type"] == "web":
            # app.main.lifespan refuses to start production without these.
            assert env["AUTO_CREATE_USERS_ON_LOGIN"]["value"] == "false"
            assert env["PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE"]["value"] == "false"
            for key in ("SMTP_HOST", "SMTP_FROM_EMAIL", "SMTP_USERNAME", "SMTP_PASSWORD"):
                assert env[key].get("sync") is False, key


def test_docker_image_installs_against_the_pinned_constraints() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    constraints = (ROOT / "constraints.txt").read_text(encoding="utf-8")
    assert "constraints.txt" in dockerfile
    pins = {
        line.split("==")[0].strip().lower()
        for line in constraints.splitlines()
        if "==" in line and not line.lstrip().startswith("#")
    }
    for package in ("bcrypt", "passlib", "scikit-learn", "fastapi", "sqlalchemy", "python-jose"):
        assert package in pins, package
