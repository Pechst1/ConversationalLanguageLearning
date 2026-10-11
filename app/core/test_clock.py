"""E-3 · a test-only server clock, so a browser walk can play days 2..7 in minutes.

The app reads "now" and "today" from ``datetime.now(...)`` / ``date.today()`` all over
``app.services``. When ``ATELIER_TEST_CLOCK_ENABLED`` is on (never in production: the
app refuses to start, and :func:`install` refuses too) this module swaps the ``datetime``
and ``date`` names *inside the app's own modules* for stand-ins whose ``now()`` /
``utcnow()`` / ``today()`` add a whole-day offset, settable through
``POST /api/v1/dev/test-clock``. Stdlib and third-party code (SQLAlchemy, pydantic,
psycopg2) keep the real classes, and every instance the stand-ins hand out is a plain
``datetime`` / ``date``, so nothing downstream can tell the difference.
"""
from __future__ import annotations

import datetime as _dt
import sys
import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

_REAL_DATETIME = _dt.datetime
_REAL_DATE = _dt.date
_lock = threading.Lock()
_offset = _dt.timedelta(0)
_installed = False

# Modules whose names are left alone: schemas build pydantic models from the real
# classes, and this module needs them to stay real.
_SKIP_PREFIXES = ("app.schemas", "app.core.test_clock")


def _production() -> bool:
    return settings.APP_ENV.strip().lower() == "production"


def offset_days() -> int:
    return _offset.days


def set_offset_days(days: int) -> int:
    global _offset
    if _production():
        raise RuntimeError("the test clock is refused in production")
    with _lock:
        _offset = _dt.timedelta(days=int(days))
    return offset_days()


def set_offset(delta: _dt.timedelta) -> _dt.timedelta:
    """Any offset, not only whole days: the suite's pinned clock (WP-153) moves "now" to
    the next noon UTC, so a test that reads «today» twice can never straddle a
    midnight (UTC, Paris or Berlin)."""

    global _offset
    if _production():
        raise RuntimeError("the test clock is refused in production")
    with _lock:
        _offset = delta
    return _offset


def uninstall() -> int:
    """Put the real ``datetime`` / ``date`` back into every ``app.*`` module and zero the offset."""

    global _installed
    set_offset(_dt.timedelta(0))
    moved = 0
    for module in list(sys.modules.values()):
        if module is None or not getattr(module, "__name__", "").startswith("app."):
            continue
        for attr, stand_in, real in (
            ("datetime", ShiftedDatetime, _REAL_DATETIME),
            ("date", ShiftedDate, _REAL_DATE),
            ("_date", ShiftedDate, _REAL_DATE),
        ):
            if getattr(module, attr, None) is stand_in:
                setattr(module, attr, real)
                moved += 1
    _installed = False
    return moved


class _DatetimeMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        return isinstance(instance, _REAL_DATETIME)

    def __subclasscheck__(cls, subclass: Any) -> bool:
        return issubclass(subclass, _REAL_DATETIME)


class _DateMeta(type):
    def __instancecheck__(cls, instance: Any) -> bool:
        return isinstance(instance, _REAL_DATE)

    def __subclasscheck__(cls, subclass: Any) -> bool:
        return issubclass(subclass, _REAL_DATE)


class ShiftedDatetime(metaclass=_DatetimeMeta):
    """Stand-in for ``datetime.datetime``: every constructor returns a real one."""

    min = _REAL_DATETIME.min
    max = _REAL_DATETIME.max
    resolution = _REAL_DATETIME.resolution

    def __new__(cls, *args: Any, **kwargs: Any) -> _dt.datetime:  # type: ignore[misc]
        return _REAL_DATETIME(*args, **kwargs)

    @staticmethod
    def now(tz: Any = None) -> _dt.datetime:
        return _REAL_DATETIME.now(tz) + _offset

    @staticmethod
    def utcnow() -> _dt.datetime:
        return _REAL_DATETIME.now(_dt.UTC).replace(tzinfo=None) + _offset

    @staticmethod
    def today() -> _dt.datetime:
        return _REAL_DATETIME.now() + _offset

    def __class_getitem__(cls, item: Any) -> Any:  # pragma: no cover
        return cls

    def __getattr__(cls, name: str) -> Any:  # pragma: no cover - instances are real
        return getattr(_REAL_DATETIME, name)


for _name in (
    "fromisoformat", "fromtimestamp", "utcfromtimestamp", "combine", "strptime", "fromordinal",
    "fromisocalendar",
):
    setattr(ShiftedDatetime, _name, staticmethod(getattr(_REAL_DATETIME, _name)))


class ShiftedDate(metaclass=_DateMeta):
    """Stand-in for ``datetime.date``."""

    min = _REAL_DATE.min
    max = _REAL_DATE.max
    resolution = _REAL_DATE.resolution

    def __new__(cls, *args: Any, **kwargs: Any) -> _dt.date:  # type: ignore[misc]
        return _REAL_DATE(*args, **kwargs)

    @staticmethod
    def today() -> _dt.date:
        return (_REAL_DATETIME.now() + _offset).date()


for _name in ("fromisoformat", "fromtimestamp", "fromordinal", "fromisocalendar"):
    setattr(ShiftedDate, _name, staticmethod(getattr(_REAL_DATE, _name)))


def install() -> int:
    """Swap the stand-ins into every loaded ``app.*`` module; returns how many names moved."""

    global _installed
    if _production():
        raise RuntimeError("the test clock is refused in production")
    moved = 0
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith("app.") or name.startswith(_SKIP_PREFIXES):
            continue
        for attr, stand_in, real in (
            ("datetime", ShiftedDatetime, _REAL_DATETIME),
            ("date", ShiftedDate, _REAL_DATE),
            ("_date", ShiftedDate, _REAL_DATE),
        ):
            if getattr(module, attr, None) is real:
                setattr(module, attr, stand_in)
                moved += 1
    _installed = True
    return moved


class ClockBody(BaseModel):
    offset_days: int = Field(0, ge=0, le=400)


class ClockState(BaseModel):
    offset_days: int
    installed: bool


router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/test-clock", response_model=ClockState)
def read_clock() -> ClockState:
    return ClockState(offset_days=offset_days(), installed=_installed)


@router.post("/test-clock", response_model=ClockState)
def move_clock(body: ClockBody) -> ClockState:
    if _production():
        raise HTTPException(status_code=404, detail="Not found")
    # Modules imported after startup (lazy imports inside functions) get patched here.
    install()
    set_offset_days(body.offset_days)
    return ClockState(offset_days=offset_days(), installed=_installed)
