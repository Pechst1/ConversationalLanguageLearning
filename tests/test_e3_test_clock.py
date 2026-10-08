"""E-3: the walk harness's test-only clock is real, contained and refused in production."""
from __future__ import annotations

import datetime as dt

import pytest

from app.config import settings
from app.core import test_clock


@pytest.fixture(autouse=True)
def _restore_clock():
    yield
    test_clock._offset = dt.timedelta(0)


def test_offset_shifts_now_and_today_but_instances_stay_real():
    test_clock.set_offset_days(3)
    shifted = test_clock.ShiftedDatetime.now(dt.UTC)
    assert type(shifted) is dt.datetime
    assert (shifted - dt.datetime.now(dt.UTC)).days in (2, 3)
    assert test_clock.ShiftedDate.today() - dt.date.today() >= dt.timedelta(days=2)
    assert isinstance(dt.datetime.now(), test_clock.ShiftedDatetime)
    assert type(test_clock.ShiftedDatetime(2026, 1, 2)) is dt.datetime


def test_refused_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with pytest.raises(RuntimeError):
        test_clock.install()
    with pytest.raises(RuntimeError):
        test_clock.set_offset_days(1)


def test_the_pinned_clock_holds_every_app_clock_at_noon_utc_and_lets_go(pinned_clock):
    """WP-153: the suite's pinned clock (tests/conftest.py)."""
    from app.db.models._clock import app_now
    from app.services import streak

    assert pinned_clock.hour == 12 and pinned_clock.tzinfo is not None
    assert abs((app_now() - pinned_clock).total_seconds()) < 60
    assert streak.datetime.now(dt.UTC).date() == pinned_clock.date()


def test_after_the_pinned_clock_the_app_reads_the_real_clock_again():
    from app.db.models._clock import app_now

    assert abs((app_now() - dt.datetime.now(dt.UTC)).total_seconds()) < 5
    assert test_clock._offset == dt.timedelta(0)
