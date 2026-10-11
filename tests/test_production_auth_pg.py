"""Opt-in PostgreSQL races; every test uses an isolated, generated schema."""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.base import Base
from app.db.models.password_reset_delivery import PasswordResetDelivery
from app.db.models.user import RefreshToken, User
from app.schemas.user import UserCreate
from app.services.auth import AuthService, InvalidPasswordResetTokenError
from app.services.password_reset_delivery import deliver_reset_email

PG_URL = os.environ.get("PRODUCTION_READINESS_PG_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="set PRODUCTION_READINESS_PG_URL to a disposable CI database")


@pytest.fixture()
def pg_recovery(monkeypatch):
    url = make_url(PG_URL)
    if not (url.database or "").startswith(("atelier_ci_", "atelier_readiness_")):
        pytest.fail("production readiness races require a disposable CI database name")
    schema = f"auth_readiness_{uuid4().hex}"
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))  # noqa: S608 - generated hex identifier
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(settings, "PASSWORD_RESET_RETURN_TOKEN_IN_RESPONSE", True)
    monkeypatch.setattr(AuthService, "_deliver_password_reset", lambda *args, **kwargs: False)
    try:
        Base.metadata.create_all(engine, tables=[User.__table__, RefreshToken.__table__, PasswordResetDelivery.__table__])
        with sessions() as db:
            service = AuthService(db)
            user = service.register_user(UserCreate(email=f"race-{uuid4()}@example.com", password="before-reset-password"))
            issued = service.request_password_reset(user.email)
            user_id, email = user.id, user.email
        yield sessions, user_id, email, issued
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))  # noqa: S608 - generated hex identifier
        admin.dispose()


def _race(sessions, calls):
    barrier = Barrier(len(calls))

    def run(call):
        with sessions() as db:
            barrier.wait(timeout=10)
            try:
                call(AuthService(db))
                return "ok"
            except InvalidPasswordResetTokenError:
                db.rollback()
                return "invalid"

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(run, calls))


def test_link_and_code_racing_can_change_the_password_only_once(pg_recovery, monkeypatch):
    sessions, user_id, email, issued = pg_recovery
    complete = AuthService._complete_password_reset

    def slow_complete(self, user, password):
        time.sleep(0.15)
        return complete(self, user, password)

    monkeypatch.setattr(AuthService, "_complete_password_reset", slow_complete)
    results = _race(sessions, [
        lambda service: service.confirm_password_reset(issued.reset_token, "link-reset-password"),
        lambda service: service.confirm_password_reset_code(email, issued.reset_code, "code-reset-password"),
    ])
    assert sorted(results) == ["invalid", "ok"]
    with sessions() as db:
        assert db.get(User, user_id).auth_version == 1


def test_parallel_bad_guesses_do_not_lose_attempts(pg_recovery):
    sessions, user_id, email, issued = pg_recovery
    wrong = f"{(int(issued.reset_code) + 1) % 1_000_000:06d}"
    results = _race(sessions, [lambda service: service.confirm_password_reset_code(email, wrong, "new-reset-password")] * 5)
    assert results == ["invalid"] * 5
    with sessions() as db:
        assert db.get(User, user_id).password_reset_code_hash is None
        with pytest.raises(InvalidPasswordResetTokenError):
            AuthService(db).confirm_password_reset_code(email, issued.reset_code, "new-reset-password")


def test_parallel_requests_issue_only_one_new_message(pg_recovery):
    sessions, user_id, email, _ = pg_recovery
    with sessions() as db:
        user = db.get(User, user_id)
        user.password_reset_requested_at = None
        db.commit()
    barrier = Barrier(4)

    def request(_):
        with sessions() as db:
            barrier.wait(timeout=10)
            return AuthService(db).request_password_reset(email).reset_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(request, range(4)))
    assert sum(code is not None for code in codes) == 1
    with sessions() as db:
        assert len(list(db.scalars(select(PasswordResetDelivery)))) == 2


def test_racing_delivery_workers_send_the_same_message_only_once(pg_recovery, monkeypatch):
    sessions, _, _, issued = pg_recovery
    with sessions() as db:
        delivery = db.scalar(select(PasswordResetDelivery))
        delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        delivery_id = delivery.id
    sent = []

    def send(self, user, **payload):
        time.sleep(0.15)
        sent.append(payload["code"])
        return True

    monkeypatch.setattr(AuthService, "_deliver_password_reset", send)
    _race(sessions, [lambda service: deliver_reset_email(service.db, delivery_id)] * 2)
    assert sent == [issued.reset_code]
