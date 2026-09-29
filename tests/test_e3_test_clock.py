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
