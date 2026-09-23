"""WP-D5 (+ WP-D4's edition): the streak is a collection of seals.

* the calendar and ``User.grammar_streak_days`` are read from the same writes,
  so they agree across a missed day, a «jour de relâche» and a day boundary in
  the learner's timezone;
* a day is ``completed | relache | missed | today | future``; only a
  *completed* journey presses a seal (an early stop moves the streak but shows
  no seal), with its edition and a composition fixed by the edition;
* the backend seal cycle is the frontend's ``sealForEdition`` cycle;
* the migration creates the table and backfills a grid that agrees with the
  stored number.
"""
from __future__ import annotations

import importlib.util
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.services.seals import SEAL_CYCLE, edition_no_for, seal_variant_for
from app.services.streak import record_practice_day, settle_streak
from app.services.streak_calendar import streak_calendar

ROOT = Path(__file__).resolve().parents[1]
D0 = date(2026, 9, 7)  # a Monday


def _user(db_session, *, tz: str = "Europe/Paris") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wpd5-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone=tz,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _noon(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)


def _practise(db_session, user: User, day: date) -> None:
    record_practice_day(db_session, user, on_date=day)
    db_session.commit()


def _by_date(payload: dict) -> dict[date, dict]:
    return {entry["date"]: entry for entry in payload["calendar"]}


def _chain_from_grid(payload: dict) -> int:
    """Count the streak the way a learner reads the grid: back from today,
    completed days count, relâche days hold, a missed day ends it."""

    days = [entry for entry in payload["calendar"] if entry["state"] != "future"]
    count = 0
    for entry in reversed(days):
        if entry["state"] == "today":
            continue
        if entry["state"] == "completed":
            count += 1
        elif entry["state"] == "relache":
            continue
        else:
            break
    return count


def _assert_agree(db_session, user: User, payload: dict) -> None:
    db_session.refresh(user)
    assert payload["current_streak"] == _chain_from_grid(payload)
    # Home prints `grammar_streak_days` checked on read; after the calendar's
    # own settle the stored number is that same number.
    assert payload["current_streak"] == int(user.grammar_streak_days or 0)


def test_a_missed_day_breaks_the_number_and_the_grid_together(db_session) -> None:
    user = _user(db_session)
    for offset in (0, 1):
        _practise(db_session, user, D0 + timedelta(days=offset))
    _practise(db_session, user, D0 + timedelta(days=3))  # D0+2 missed, no freeze

    payload = streak_calendar(db_session, user, now=_noon(D0 + timedelta(days=3)))
    db_session.commit()
    grid = _by_date(payload)
    assert [grid[D0 + timedelta(days=i)]["state"] for i in range(4)] == [
        "completed",
        "completed",
        "missed",
        "completed",
    ]
    assert grid[D0 + timedelta(days=3)]["is_today"] is True
    assert payload["current_streak"] == 1
    _assert_agree(db_session, user, payload)
    # The rest of the week is future; the grid ends on Sunday.
    assert payload["calendar"][-1]["date"] == D0 + timedelta(days=6)
    assert grid[D0 + timedelta(days=4)]["state"] == "future"


def test_today_not_yet_practised_reads_today_and_keeps_the_chain(db_session) -> None:
    user = _user(db_session)
    for offset in range(3):
        _practise(db_session, user, D0 + timedelta(days=offset))
    payload = streak_calendar(db_session, user, now=_noon(D0 + timedelta(days=3)))
    db_session.commit()
    assert _by_date(payload)[D0 + timedelta(days=3)]["state"] == "today"
    assert payload["current_streak"] == 3
    assert payload["today_done"] is False
    _assert_agree(db_session, user, payload)


def test_a_relache_day_is_stored_per_day_and_holds_the_chain(db_session) -> None:
    user = _user(db_session)
    for offset in range(7):  # a full week earns one «jour de relâche»
        _practise(db_session, user, D0 + timedelta(days=offset))
    assert int(user.streak_freezes or 0) == 1
    # D0+7 is missed; the next day's practice spends the freeze on it.
    _practise(db_session, user, D0 + timedelta(days=8))
    assert user.grammar_streak_days == 8

    payload = streak_calendar(db_session, user, now=_noon(D0 + timedelta(days=8)))
    db_session.commit()
    grid = _by_date(payload)
    assert grid[D0 + timedelta(days=7)]["state"] == "relache"
    assert grid[D0 + timedelta(days=8)]["state"] == "completed"
    assert payload["current_streak"] == 8
    _assert_agree(db_session, user, payload)

    # A second week later the relâche is still the same day in the grid.
    again = streak_calendar(db_session, user, now=_noon(D0 + timedelta(days=9)))
    db_session.commit()
    assert _by_date(again)[D0 + timedelta(days=7)]["state"] == "relache"
    assert _by_date(again)[D0 + timedelta(days=9)]["state"] == "today"


def test_the_calendar_settles_a_due_relache_on_read(db_session) -> None:
    user = _user(db_session)
    for offset in range(7):
        _practise(db_session, user, D0 + timedelta(days=offset))
    # Nothing on D0+7; the learner opens «Vos sceaux» on D0+8.
    payload = streak_calendar(db_session, user, now=_noon(D0 + timedelta(days=8)))
    db_session.commit()
    grid = _by_date(payload)
    assert grid[D0 + timedelta(days=7)]["state"] == "relache"
    assert grid[D0 + timedelta(days=8)]["state"] == "today"
    assert payload["current_streak"] == 7
    _assert_agree(db_session, user, payload)


@pytest.mark.parametrize(
    ("tz", "expected_days", "expected_today"),
    [
        # 23:30 then 00:30 local: two days in Auckland …
        ("Pacific/Auckland", 2, date(2026, 9, 9)),
        # … and the same afternoon in Los Angeles.
        ("America/Los_Angeles", 1, date(2026, 9, 8)),
    ],
)
def test_the_learners_timezone_decides_the_day(db_session, tz, expected_days, expected_today) -> None:
    user = _user(db_session, tz=tz)
    first = datetime(2026, 9, 8, 11, 30, tzinfo=UTC)  # 23:30 NZST, 04:30 PDT
    second = first + timedelta(hours=1)  # 00:30 NZST next day, 05:30 PDT
    record_practice_day(db_session, user, now=first)
    record_practice_day(db_session, user, now=second)
    db_session.commit()

    payload = streak_calendar(db_session, user, now=second)
    db_session.commit()
    assert payload["today"] == expected_today
    assert payload["timezone"] == tz
    completed = [entry["date"] for entry in payload["calendar"] if entry["state"] == "completed"]
    assert len(completed) == expected_days
    assert payload["current_streak"] == expected_days
    _assert_agree(db_session, user, payload)


def _journey(db_session, user: User, day: date, status: str, episode: SerialEpisode | None = None):
    journey = DailyJourney(
        user_id=user.id,
        local_date=day,
        timezone="Europe/Paris",
        status=status,
        serial_episode_id=str(episode.id) if episode else None,
        scenario_snapshot={},
        plan_selection={},
    )
    db_session.add(journey)
    db_session.flush()
    return journey


def test_only_a_completed_journey_presses_a_seal(db_session) -> None:
    user = _user(db_session)
    thread = SerialThread(user_id=user.id)
    db_session.add(thread)
    db_session.flush()
    episode = SerialEpisode(thread_id=thread.id, episode_index=46, kind="scene")
    db_session.add(episode)
    db_session.flush()

    sealed = _journey(db_session, user, D0, "completed", episode)
    _practise(db_session, user, D0)
    early = _journey(db_session, user, D0 + timedelta(days=1), "ended_early")
    _practise(db_session, user, D0 + timedelta(days=1))

    payload = streak_calendar(db_session, user, now=_noon(D0 + timedelta(days=1)))
    db_session.commit()
    grid = _by_date(payload)
    assert grid[D0]["state"] == "completed"
    assert grid[D0]["sealed"] is True
    assert grid[D0]["edition_no"] == 47
    assert grid[D0]["seal_variant"] == seal_variant_for(47)
    # An early stop keeps the streak honest but presses no seal.
    assert grid[D0 + timedelta(days=1)]["state"] == "completed"
    assert grid[D0 + timedelta(days=1)]["sealed"] is False
    assert grid[D0 + timedelta(days=1)]["seal_variant"] is None
    _assert_agree(db_session, user, payload)

    # The journey wire carries the same edition, so the recap agrees.
    assert edition_no_for(db_session, sealed) == 47
    # With no serial episode, the day is numbered by the learner's own days.
    assert edition_no_for(db_session, early) == 2


def test_the_same_edition_always_has_the_same_composition() -> None:
    assert seal_variant_for(47) == seal_variant_for(47 + len(SEAL_CYCLE))
    assert seal_variant_for(None) is None


def test_the_seal_cycle_is_the_frontends() -> None:
    source = (ROOT / "web-frontend" / "components" / "ui" / "Seal.tsx").read_text(encoding="utf-8")
    match = re.search(r"const SEAL_CYCLE: SealVariant\[\] = \[([^\]]+)\]", source)
    assert match, "sealForEdition's cycle moved"
    frontend = tuple(re.findall(r"'(\w+)'", match.group(1)))
    assert frontend == SEAL_CYCLE


def test_settle_writes_the_relache_row_once(db_session) -> None:
    user = _user(db_session)
    for offset in range(7):
        _practise(db_session, user, D0 + timedelta(days=offset))
    day = D0 + timedelta(days=8)
    settle_streak(db_session, user, today=day)
    settle_streak(db_session, user, today=day)
    db_session.commit()
    rows = db_session.execute(
        sa.text("SELECT kind FROM streak_days WHERE user_id = :u AND local_date = :d"),
        {"u": user.id.hex, "d": (D0 + timedelta(days=7)).isoformat()},
    ).all()
    assert [row[0] for row in rows] == ["relache"]


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

MIGRATION = ROOT / "alembic" / "versions" / "c4d6e8f0a2b3_wpd5_streak_days.py"


def test_migration_backfills_a_grid_that_agrees_with_the_number() -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "b8e0f2a4c6d8"' in source

    spec = importlib.util.spec_from_file_location("wpd5_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    uid = uuid.uuid4()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE users (id CHAR(32) PRIMARY KEY, grammar_streak_days INTEGER, "
                "grammar_last_review_date DATE, streak_freeze_used_on DATE)"
            )
        )
        connection.execute(
            sa.text("CREATE TABLE daily_journeys (user_id CHAR(32), local_date DATE, status VARCHAR(20))")
        )
        # A chain of 3 practised days ending D0+4, with D0+3 covered by a relâche.
        connection.execute(
            sa.text("INSERT INTO users VALUES (:id, 3, :last, :used)"),
            {"id": uid.hex, "last": (D0 + timedelta(days=4)).isoformat(), "used": (D0 + timedelta(days=3)).isoformat()},
        )
        connection.execute(
            sa.text("INSERT INTO daily_journeys VALUES (:id, :d, 'completed')"),
            {"id": uid.hex, "d": D0.isoformat()},
        )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        rows = connection.execute(
            sa.text("SELECT local_date, kind FROM streak_days ORDER BY local_date")
        ).all()
        assert [(str(row[0])[:10], row[1]) for row in rows] == [
            (D0.isoformat(), "practised"),
            ((D0 + timedelta(days=1)).isoformat(), "practised"),
            ((D0 + timedelta(days=2)).isoformat(), "practised"),
            ((D0 + timedelta(days=3)).isoformat(), "relache"),
            ((D0 + timedelta(days=4)).isoformat(), "practised"),
        ]
        module.upgrade()  # idempotent
        module.downgrade()
        assert "streak_days" not in sa.inspect(connection).get_table_names()
