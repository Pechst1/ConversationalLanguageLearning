# ruff: noqa: F811 - the WP-70 fixtures are imported by name and requested as arguments
"""E1 — a paid request holds money before it runs.

The WP-70/WP-138 check reads recorded spend only, so requests that start
together all pass it. With ``SPEND_RESERVATIONS_ENABLED`` the check and a hold
are one locked step, every open hold counts as spent, and the hold ends with
the request. Each test sets the caps relative to what the shared database has
already "spent" today.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.spend_reservation import SpendReservation
from app.services import spend_guard, spend_ledger
from tests.test_wp70_rate_limits import (  # noqa: F401 - fixtures
    _assert_429,
    _learner,
    _memory_limiter,
    _spend,
    abuser_client,
    speech,
)


@pytest.fixture()
def holds_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SPEND_RESERVATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "SPEND_RESERVATION_REQUEST_BOUND_USD", 0.02)
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", 0.0)
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_CAP_USD", 0.50)


def _refused(call) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(HTTPException) as caught:
        call()
    assert caught.value.status_code == 429
    assert caught.value.detail["code"] == spend_guard.DAILY_BUDGET_REACHED_CODE


def test_open_holds_count_as_spent(db_session: Session, holds_on) -> None:
    user, _ = _learner(db_session)
    _spend(db_session, user, 0.45)

    spend_ledger.reserve(db_session, user, kind="test")  # 0.47
    spend_ledger.reserve(db_session, user, kind="test")  # 0.49
    _refused(lambda: spend_ledger.reserve(db_session, user, kind="test"))  # 0.51 > 0.50

    assert spend_ledger.outstanding_usd(db_session, user.id, zone=spend_guard.learner_zone(user)) == pytest.approx(0.04)


def test_a_released_hold_frees_its_money(db_session: Session, holds_on) -> None:
    user, _ = _learner(db_session)
    _spend(db_session, user, 0.47)
    first = spend_ledger.reserve(db_session, user, kind="test")
    _refused(lambda: spend_ledger.reserve(db_session, user, kind="test"))

    spend_ledger.release(db_session, first)
    spend_ledger.reserve(db_session, user, kind="test")


def test_settle_records_the_actual_cost(db_session: Session, holds_on) -> None:
    user, _ = _learner(db_session)
    hold = spend_ledger.reserve(db_session, user, kind="test")
    spend_ledger.settle(db_session, hold, 0.0042)
    row = db_session.get(SpendReservation, hold)
    db_session.refresh(row)
    assert row.status == "settled"
    assert row.actual_usd == pytest.approx(0.0042)
    assert spend_ledger.outstanding_usd(db_session, user.id) == 0.0


def test_the_same_request_key_holds_once(db_session: Session, holds_on) -> None:
    user, _ = _learner(db_session)
    first = spend_ledger.reserve(db_session, user, kind="test", request_key=f"turn-{user.id}")
    again = spend_ledger.reserve(db_session, user, kind="test", request_key=f"turn-{user.id}")
    assert first == again
    assert spend_ledger.outstanding_usd(db_session, user.id) == pytest.approx(0.02)


def test_an_abandoned_hold_turns_uncertain_and_keeps_counting(
    db_session: Session, holds_on, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "SPEND_RESERVATION_STALE_SECONDS", 60)
    user, _ = _learner(db_session)
    now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    # Spent on the same learner day as the holds: at 22:00 UTC a spend stamped with
    # the wall clock already falls on the next local day and the cap never trips.
    _spend(db_session, user, 0.47, when=now - timedelta(minutes=20))
    old = spend_ledger.reserve(db_session, user, kind="test", now=now - timedelta(minutes=10))

    _refused(lambda: spend_ledger.reserve(db_session, user, kind="test", now=now))
    row = db_session.get(SpendReservation, old)
    db_session.refresh(row)
    assert row.status == "uncertain"

    spend_ledger.release(db_session, old)  # a late close still frees it
    spend_ledger.reserve(db_session, user, kind="test", now=now)


def test_the_open_day_ceiling_applies_to_a_started_day(db_session: Session, holds_on, monkeypatch) -> None:
    monkeypatch.setattr(settings, "USER_DAILY_SPEND_OPEN_DAY_MULTIPLIER", 2.0)
    user, _ = _learner(db_session)
    _spend(db_session, user, 0.60)
    _refused(lambda: spend_ledger.reserve(db_session, user, kind="test"))
    spend_ledger.reserve(db_session, user, kind="test", open_day=True)


def test_the_service_cap_counts_every_learners_holds(db_session: Session, holds_on, monkeypatch) -> None:
    baseline = spend_guard.service_spend_today_usd(db_session) + spend_ledger.outstanding_usd(db_session)
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", baseline + 0.05)
    first, _ = _learner(db_session)
    second, _ = _learner(db_session)

    spend_ledger.reserve(db_session, first, kind="test")
    spend_ledger.reserve(db_session, first, kind="test")
    _refused(lambda: spend_ledger.reserve(db_session, second, kind="test"))
    assert spend_guard.service_budget_reached(db_session) is False
    monkeypatch.setattr(settings, "SERVICE_DAILY_SPEND_CAP_USD", baseline + 0.04)
    assert spend_guard.service_budget_reached(db_session) is True


def test_a_paid_route_holds_while_it_runs_and_releases_after(
    abuser_client: TestClient, db_session: Session, speech, holds_on
) -> None:
    user, headers = _learner(db_session)
    response = abuser_client.post("/api/v1/audio/speak", json={"text": "Bonjour"}, headers=headers)
    assert response.status_code == 200, response.text
    assert speech.calls == 1

    rows = db_session.scalars(select(SpendReservation).where(SpendReservation.user_id == user.id)).all()
    assert len(rows) == 1
    db_session.refresh(rows[0])
    assert rows[0].status == "released"
    assert rows[0].kind.startswith("route:POST ")


def test_a_paid_route_is_refused_before_the_provider_when_the_hold_would_cross_the_cap(
    abuser_client: TestClient, db_session: Session, speech, holds_on
) -> None:
    user, headers = _learner(db_session)
    _spend(db_session, user, 0.49)
    response = abuser_client.post("/api/v1/audio/speak", json={"text": "Encore"}, headers=headers)
    _assert_429(response, "daily_budget_reached")
    assert speech.calls == 0


def test_off_by_default() -> None:
    assert type(settings).model_fields["SPEND_RESERVATIONS_ENABLED"].default is False


def test_requests_racing_for_the_last_of_the_cap_on_real_postgres() -> None:
    """Twenty requests start at the same instant with room for five holds: exactly five pass."""

    import os
    import subprocess
    import sys
    import threading
    import uuid
    from pathlib import Path
    from unittest import mock

    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    base = os.environ.get("E1_PG_URL", "").strip()
    if not base:
        pytest.skip("set E1_PG_URL to a PostgreSQL server this test may create a database on")
    name = f"e1_race_{uuid.uuid4().hex[:8]}"
    admin = create_engine(make_url(base).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(base).set(database=name).render_as_string(hide_password=False)
    engine = create_engine(url, pool_size=25, max_overflow=0)
    try:
        root = Path(__file__).resolve().parent.parent
        subprocess.run(  # noqa: S603 - this interpreter running alembic on its own throwaway database
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=root, env={**os.environ, "DATABASE_URL": url}, check=True, capture_output=True,
        )
        from app.db.models.user import User

        Session = sessionmaker(bind=engine)
        with Session() as setup:
            user = User(
                email=f"e1-{uuid.uuid4().hex[:8]}@example.com",
                hashed_password="not-used",
                target_language="fr",
                proficiency_level="A2",
                is_active=True,
            )
            setup.add(user)
            setup.commit()
            setup.refresh(user)
            setup.expunge(user)

        passed: list[uuid.UUID] = []
        refused: list[int] = []
        errors: list[str] = []
        barrier = threading.Barrier(20)

        def paid_request() -> None:
            db = Session()
            try:
                barrier.wait()
                passed.append(spend_ledger.reserve(db, user, kind="race"))
            except HTTPException as exc:
                refused.append(exc.status_code)
            except Exception as exc:  # noqa: BLE001 - collected and asserted below
                errors.append(repr(exc)[:300])
            finally:
                db.close()

        with mock.patch.multiple(
            settings,
            SPEND_RESERVATIONS_ENABLED=True,
            SPEND_RESERVATION_REQUEST_BOUND_USD=0.10,
            USER_DAILY_SPEND_CAP_USD=0.50,
            SERVICE_DAILY_SPEND_CAP_USD=5.00,
        ):
            threads = [threading.Thread(target=paid_request) for _ in range(20)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)

        assert errors == []
        assert len(passed) == 5
        assert refused == [429] * 15
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
