"""WP-80 (+ WP-79's streak bullet): an honest streak, in the learner's local day.

* consecutive local days count, a miss resets on *read* (not only on the next
  practice), the same day never counts twice;
* one «jour de relâche» per full seven-day week, at most one banked, spent
  automatically on exactly one missed day and recorded;
* the local day is the learner's zone: the same two UTC instants are two days
  in Auckland and one day in Los Angeles;
* the streak is exposed, additively, on /atelier/today and the journey wire;
* the migration adds and removes exactly its three columns.
"""
from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import select

from app.db.models.user import User
from app.services import streak as streak_service
from app.services.journey_learning import record_daily_practice_streak
from app.services.streak import (
    missed_days_before,
    read_streak,
    record_practice_day,
    remember_timezone,
    settle_streak,
    snapshot_fields,
    valid_timezone,
)

D0 = date(2026, 9, 1)


def _user(db_session, *, tz: str = "Europe/Paris") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp80-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone=tz,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _practise(db_session, user: User, first: date, count: int) -> None:
    for offset in range(count):
        record_practice_day(db_session, user, on_date=first + timedelta(days=offset))


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


def test_consecutive_local_days_count_and_a_day_counts_once(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 3)
    assert record_practice_day(db_session, user, on_date=D0 + timedelta(days=2)).days == 3

    state = read_streak(user, today=D0 + timedelta(days=2))
    assert (state.days, state.today_done) == (3, True)
    # The next morning the chain is alive but today is not yet done.
    tomorrow = read_streak(user, today=D0 + timedelta(days=3))
    assert (tomorrow.days, tomorrow.today_done) == (3, False)
    # Mirrored for the streak-at-risk push and the achievements.
    assert user.current_streak == 3
    assert user.longest_streak == 3


def test_a_miss_reads_zero_on_the_next_read_not_the_stale_count(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 4)

    # Two days later (one full day missed, no freeze): 0, not «4 jours».
    assert read_streak(user, today=D0 + timedelta(days=5)).days == 0
    settled = settle_streak(db_session, user, today=D0 + timedelta(days=5))
    assert settled.days == 0
    assert user.current_streak == 0
    assert user.grammar_longest_streak == 4

    # Practising again restarts at 1.
    assert record_practice_day(db_session, user, on_date=D0 + timedelta(days=5)).days == 1


def test_a_full_week_earns_one_freeze_and_it_saves_exactly_one_miss(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 6)
    assert read_streak(user, today=D0 + timedelta(days=5)).freeze_available is False
    record_practice_day(db_session, user, on_date=D0 + timedelta(days=6))  # day 7
    assert read_streak(user, today=D0 + timedelta(days=6)).freeze_available is True
    assert user.streak_freezes == 1

    missed = D0 + timedelta(days=7)
    back = D0 + timedelta(days=8)
    # The read the day after the miss reports the freeze as spent…
    pure = read_streak(user, today=back)
    assert (pure.days, pure.freeze_available, pure.freeze_used_on) == (7, False, missed)
    # …and settling writes it down, so the number is explainable.
    settle_streak(db_session, user, today=back)
    assert user.streak_freezes == 0
    assert user.streak_freeze_used_on == missed

    # The relâche day keeps the chain; it does not add to it.
    after = record_practice_day(db_session, user, on_date=back)
    assert after.days == 8
    assert after.freeze_used_on == missed
    assert after.freeze_available is False


def test_a_freeze_never_covers_two_missed_days(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 7)
    assert user.streak_freezes == 1

    # Days 8 and 9 missed.
    assert read_streak(user, today=D0 + timedelta(days=9)).days == 0
    assert record_practice_day(db_session, user, on_date=D0 + timedelta(days=9)).days == 1
    # The unspent freeze stays banked; it was never used.
    assert user.streak_freezes == 1
    assert user.streak_freeze_used_on is None


def test_only_one_freeze_is_banked(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 14)
    assert user.streak_freezes == 1
    assert read_streak(user, today=D0 + timedelta(days=13)).days == 14


def test_a_freeze_spent_then_a_second_miss_breaks(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 7)
    # Miss day 8 (freeze), practise day 9, miss day 10 → broken on day 11.
    record_practice_day(db_session, user, on_date=D0 + timedelta(days=8))
    assert user.streak_freeze_used_on == D0 + timedelta(days=7)
    assert read_streak(user, today=D0 + timedelta(days=10)).days == 0


def test_the_legacy_helper_is_the_same_rule(db_session) -> None:
    user = _user(db_session)
    assert record_daily_practice_streak(db_session, user, on_date=D0) == 1
    assert record_daily_practice_streak(db_session, user, on_date=D0) == 1
    assert record_daily_practice_streak(db_session, user, on_date=D0 + timedelta(days=1)) == 2


def test_missed_days_counts_whole_local_days() -> None:
    assert missed_days_before(None, D0) == 0
    assert missed_days_before(D0, D0) == 0
    assert missed_days_before(D0, D0 + timedelta(days=1)) == 0
    assert missed_days_before(D0, D0 + timedelta(days=3)) == 2


# ---------------------------------------------------------------------------
# Timezones
# ---------------------------------------------------------------------------


def test_the_same_two_instants_are_two_days_in_auckland_and_one_in_los_angeles(db_session) -> None:
    late = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)  # 23:00 NZST 22 Sept · 04:00 PDT 22 Sept
    later = datetime(2026, 9, 22, 13, 0, tzinfo=UTC)  # 01:00 NZST 23 Sept · 06:00 PDT 22 Sept

    auckland = _user(db_session, tz="Pacific/Auckland")
    record_practice_day(db_session, auckland, now=late)
    assert record_practice_day(db_session, auckland, now=later).days == 2
    assert auckland.grammar_last_review_date == date(2026, 9, 23)

    los_angeles = _user(db_session, tz="America/Los_Angeles")
    record_practice_day(db_session, los_angeles, now=late)
    assert record_practice_day(db_session, los_angeles, now=later).days == 1
    assert los_angeles.grammar_last_review_date == date(2026, 9, 22)

    # A day later in UTC, Los Angeles is still inside its next local day.
    next_la = datetime(2026, 9, 23, 20, 0, tzinfo=UTC)  # 13:00 PDT 23 Sept
    assert read_streak(los_angeles, now=next_la).days == 1
    # …while Auckland (09:00 NZST 24 Sept) has not missed anything either.
    assert read_streak(auckland, now=next_la).days == 2
    # Two local days later Auckland has missed 24 Sept.
    assert read_streak(auckland, now=datetime(2026, 9, 24, 13, 0, tzinfo=UTC)).days == 0


def test_timezone_is_validated_and_remembered() -> None:
    user = User(timezone="Europe/Paris")
    assert valid_timezone("Pacific/Auckland") == "Pacific/Auckland"
    assert valid_timezone("Mars/Olympus") is None
    assert valid_timezone("") is None
    assert remember_timezone(user, "Not/AZone") is False
    assert user.timezone == "Europe/Paris"
    assert remember_timezone(user, "America/Los_Angeles") is True
    assert remember_timezone(user, "America/Los_Angeles") is False
    assert streak_service.user_timezone(User(timezone=None)) == "Europe/Paris"


# ---------------------------------------------------------------------------
# On the wire
# ---------------------------------------------------------------------------


def _auth(client, email: str) -> dict[str, str]:
    from tests.test_users import register_and_login

    return {"Authorization": f"Bearer {register_and_login(client, email, 'verysecure')}"}


def test_settings_accept_an_iana_zone_and_refuse_anything_else(client, db_session) -> None:
    headers = _auth(client, "wp80-settings@example.com")
    ok = client.patch("/api/v1/users/me/settings", json={"timezone": "Pacific/Auckland"}, headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["timezone"] == "Pacific/Auckland"
    bad = client.patch("/api/v1/users/me/settings", json={"timezone": "Europe/Atlantis"}, headers=headers)
    assert bad.status_code == 422


def test_journey_today_persists_the_client_zone_and_reports_the_streak(client, db_session) -> None:
    headers = _auth(client, "wp80-today@example.com")
    response = client.get(
        "/api/v1/daily-journeys/today", params={"timezone": "America/Los_Angeles"}, headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["streak"] == {
        "days": 0,
        "today_done": False,
        "freeze_available": False,
        "freeze_used_on": None,
    }
    assert body["missed_days"] == 0
    user = db_session.scalar(select(User).where(User.email == "wp80-today@example.com"))
    db_session.refresh(user)
    assert user.timezone == "America/Los_Angeles"

    # A junk zone is ignored, never stored.
    client.get("/api/v1/daily-journeys/today", params={"timezone": "Nope/Nope"}, headers=headers)
    db_session.refresh(user)
    assert user.timezone == "America/Los_Angeles"


def test_journey_today_settles_a_stale_streak_to_zero(client, db_session) -> None:
    headers = _auth(client, "wp80-stale@example.com")
    user = db_session.scalar(select(User).where(User.email == "wp80-stale@example.com"))
    user.grammar_streak_days = 12
    user.current_streak = 12
    user.grammar_last_review_date = date.today() - timedelta(days=6)
    db_session.commit()

    body = client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert body["streak"]["days"] == 0
    assert body["missed_days"] >= 4
    db_session.refresh(user)
    assert user.current_streak == 0


def test_snapshot_fields_are_a_pure_read(db_session) -> None:
    user = _user(db_session)
    _practise(db_session, user, D0, 7)
    fields = snapshot_fields(db_session, user.id, D0 + timedelta(days=8))
    assert fields["streak"]["days"] == 7
    assert fields["streak"]["freeze_used_on"] == (D0 + timedelta(days=7)).isoformat()
    assert fields["missed_days"] == 1
    # Nothing was written by the read.
    assert user.streak_freezes == 1
    assert user.streak_freeze_used_on is None


def test_atelier_summary_reads_the_checked_streak(db_session) -> None:
    from app.services.atelier import AtelierScheduler

    user = _user(db_session)
    user.grammar_streak_days = 9
    user.grammar_last_review_date = date.today() - timedelta(days=5)
    db_session.commit()
    assert AtelierScheduler(db_session).summary(user)["streak"] == 0


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "b8e0f2a4c6d8_wp80_streak_freeze_and_timezone.py"
)


def test_migration_is_additive_and_reversible() -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "2face6b8f71e"' in source

    spec = importlib.util.spec_from_file_location("wp80_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(sa.text("INSERT INTO users (id) VALUES ('a')"))
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
        assert {"timezone", "streak_freezes", "streak_freeze_used_on"} <= columns
        row = connection.execute(sa.text("SELECT timezone, streak_freezes FROM users")).one()
        assert tuple(row) == ("Europe/Paris", 0)
        module.upgrade()  # idempotent
        module.downgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("users")}
        assert columns == {"id"}


@pytest.mark.parametrize("name", ["timezone", "streak_freezes", "streak_freeze_used_on"])
def test_the_model_has_the_migrated_columns(name: str) -> None:
    assert name in User.__table__.columns
