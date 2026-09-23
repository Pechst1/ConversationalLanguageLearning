"""WP-L7 — the band's checkpoint («épreuve»): a small state machine.

Owner decision 2026-09-23 §5.3: the level check is a special, finale-like
episode, staged by the story engine **as soon as the band's coverage is met**,
decoupled from the season calendar. This module owns the state; the engine
(Codex, WP-L5/L7) owns the episode. The engine reads :func:`checkpoint_view`
(also in ``GET /progress/cefr`` → ``checkpoint``) and reports the outcome
through :func:`record_checkpoint_result` (``POST /progress/cefr/checkpoint``).

States per (learner, band)::

    locked ──coverage met──▶ ready ──passed──▶ passed        (band closed, level +1)
                              │  ▲
                        failed│  │retry_after reached (a week later)
                              ▼  │
                            failed (retry_after = failed_at + 7 days)

    credited — closed without an épreuve: the level the learner was shown
    before this rule shipped (release day), or a placement / declaration that
    in-app work confirmed.

* ``locked`` has no row, or an ``open`` row: the band is being worked through
  and the row only remembers which of its units have been held
  (``payload.held_unit_ids``), because a unit once held stays counted in the
  band's coverage. The row turns ``ready`` the first time coverage is met.
* Coverage that later slips does **not** take ``ready`` away: fragile items
  simply come back in the reviews, and the épreuve itself is the test.
* A pass closes the band for good — demotion is never visible.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.cefr import UserLevelCheckpoint
from app.services.level_coverage import SUB_BANDS, band_index

STATE_LOCKED = "locked"
#: Stored only: a band in progress whose row tracks the units held so far.
STATE_OPEN = "open"
STATE_READY = "ready"
STATE_PASSED = "passed"
STATE_FAILED = "failed"
STATE_CREDITED = "credited"
CLOSED_STATES = frozenset({STATE_PASSED, STATE_CREDITED})

#: A failed épreuve comes back after a week of consolidation (§WP-L7).
RETRY_AFTER_DAYS = 7

SOURCE_COVERAGE = "coverage"
SOURCE_RELEASE = "release_grandfather"
SOURCE_PRIOR_CONFIRMED = "prior_confirmed"

CAN_DOS_PATH = Path(__file__).resolve().parents[1] / "data" / "syllabus" / "fr_core_can_dos_v2.json"


class CheckpointError(ValueError):
    """A result the state machine refuses (wrong band, not ready, retry too early)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def rows_by_band(db: Session, user_id: Any) -> dict[str, UserLevelCheckpoint]:
    rows = db.query(UserLevelCheckpoint).filter(UserLevelCheckpoint.user_id == user_id).all()
    return {row.band: row for row in rows}


def highest_closed_band(rows: dict[str, UserLevelCheckpoint]) -> str | None:
    closed = [band for band, row in rows.items() if row.status in CLOSED_STATES and band in SUB_BANDS]
    return max(closed, key=band_index) if closed else None


def state_of(row: UserLevelCheckpoint | None, *, coverage_met: bool, now: datetime) -> str:
    """The state the learner is in for one band, derived — never stale."""

    if row is None or row.status == STATE_OPEN:
        return STATE_READY if coverage_met else STATE_LOCKED
    if row.status in CLOSED_STATES:
        return row.status
    if row.status == STATE_FAILED:
        retry = _aware(row.retry_after)
        if retry is not None and now >= retry:
            return STATE_READY
        return STATE_FAILED
    return STATE_READY


@lru_cache(maxsize=1)
def _can_dos() -> dict[str, list[dict[str, Any]]]:
    try:
        payload = json.loads(CAN_DOS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # pragma: no cover - defensive
        return {}
    bands = payload.get("sub_bands") if isinstance(payload, dict) else None
    return bands if isinstance(bands, dict) else {}


def band_can_dos(band: str) -> list[dict[str, Any]]:
    """The band's can-do tasks (WP-L2) — what the épreuve asks for in free replies."""

    return [
        {
            "id": item.get("id"),
            "title_fr": item.get("title_fr"),
            "title_en": item.get("title_en"),
            "title_de": item.get("title_de"),
            "units": list(item.get("units") or []),
            "words": list(item.get("words") or []),
        }
        for item in _can_dos().get(band, [])
        if isinstance(item, dict)
    ]


def checkpoint_view(
    band: str,
    row: UserLevelCheckpoint | None,
    *,
    coverage_met: bool,
    now: datetime,
) -> dict[str, Any]:
    """The API shape the story engine reads (``payload["checkpoint"]``)."""

    state = state_of(row, coverage_met=coverage_met, now=now)
    retry = _aware(row.retry_after) if row is not None else None
    return {
        "band": band,
        "state": state,
        # The engine's one question: stage the épreuve now?
        "checkpoint_ready": state == STATE_READY,
        "attempts": int(row.attempts or 0) if row is not None else 0,
        "ready_since": _iso(row.ready_at) if row is not None else None,
        "last_attempt_at": _iso(row.last_attempt_at) if row is not None else None,
        "retry_after": _iso(retry) if state == STATE_FAILED else None,
        "passed_at": _iso(row.passed_at) if row is not None else None,
        "can_dos": band_can_dos(band),
        "retry_after_days": RETRY_AFTER_DAYS,
    }


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.isoformat() if value is not None else None


def held_ever(row: UserLevelCheckpoint | None) -> set[int]:
    """The band's units this learner has held at least once."""

    values = ((row.payload or {}) if row is not None else {}).get("held_unit_ids") or []
    out: set[int] = set()
    for value in values:
        try:
            out.add(int(value))
        except (TypeError, ValueError):
            continue
    return out


def track_band(
    db: Session,
    user_id: Any,
    band: str,
    *,
    held_unit_ids: set[int],
    coverage_met: bool,
    now: datetime,
) -> UserLevelCheckpoint:
    """Remember the band's held units; turn the row ``ready`` when coverage is met."""

    row = db.query(UserLevelCheckpoint).filter_by(user_id=user_id, band=band).one_or_none()
    if row is None:
        row = UserLevelCheckpoint(user_id=user_id, band=band, status=STATE_OPEN, attempts=0, payload={})
        db.add(row)
    row.payload = {**(row.payload or {}), "held_unit_ids": sorted(held_unit_ids)}
    if coverage_met and row.status == STATE_OPEN:
        row.status = STATE_READY
        row.source = SOURCE_COVERAGE
        row.ready_at = now
    db.flush()
    return row


def mark_ready(db: Session, user_id: Any, band: str, *, now: datetime) -> UserLevelCheckpoint:
    """Turn a band ``ready`` (its coverage is met). Idempotent."""

    row = db.query(UserLevelCheckpoint).filter_by(user_id=user_id, band=band).one_or_none()
    if row is None:
        row = UserLevelCheckpoint(user_id=user_id, band=band, attempts=0, payload={})
        db.add(row)
    elif row.status != STATE_OPEN:
        return row
    row.status = STATE_READY
    row.source = SOURCE_COVERAGE
    row.ready_at = now
    db.flush()
    return row


def credit_band(db: Session, user_id: Any, band: str, *, source: str, now: datetime) -> UserLevelCheckpoint:
    """Close a band without an épreuve (release-day grandfathering, a confirmed prior)."""

    row = db.query(UserLevelCheckpoint).filter_by(user_id=user_id, band=band).one_or_none()
    if row is not None and row.status in CLOSED_STATES:
        return row
    if row is None:
        row = UserLevelCheckpoint(user_id=user_id, band=band, attempts=0, payload={})
        db.add(row)
    row.status = STATE_CREDITED
    row.source = source
    row.passed_at = now
    row.retry_after = None
    db.flush()
    return row


def current_checkpoint(db: Session, user: Any) -> dict[str, Any]:
    """The épreuve's state for the band in force, computed now. Writes nothing.

    For the story engine in-process: ``current_checkpoint(db, user)["checkpoint_ready"]``.
    """

    from app.services.cefr_progress import CEFRProgressService

    payload = CEFRProgressService(db).recompute(user, source="checkpoint_read", persist=False, track=False)
    view = dict(payload.get("checkpoint") or {})
    view.setdefault("band", payload.get("estimate"))
    view["coverage"] = payload.get("coverage")
    view["level_label"] = payload.get("level_label")
    return view


def record_checkpoint_result(
    db: Session,
    user: Any,
    *,
    band: str,
    passed: bool,
    now: datetime | None = None,
    evidence: dict[str, Any] | None = None,
    source: str = "episode",
) -> UserLevelCheckpoint:
    """Record the épreuve's outcome. Never commits; the caller recomputes the level.

    Refuses (``CheckpointError``) a result for a band that is already closed, or
    one that is not ready (coverage not met, or a failed épreuve still inside its
    week of consolidation). A pass closes the band; a fail sets ``retry_after``.
    """

    from app.services.cefr_progress import CEFRProgressService

    now = now or datetime.now(UTC)
    if band not in SUB_BANDS:
        raise CheckpointError("unknown_band", f"Unknown band {band!r}.")
    row = db.query(UserLevelCheckpoint).filter_by(user_id=user.id, band=band).one_or_none()
    if row is not None and row.status in CLOSED_STATES:
        raise CheckpointError("already_closed", f"The {band} checkpoint is already {row.status}.")
    if row is None or row.status == STATE_OPEN:
        # The engine may only stage an épreuve the learner is ready for; the
        # coverage is re-read here rather than trusted from the caller.
        payload = CEFRProgressService(db).recompute(user, source="checkpoint_check", persist=False, track=False)
        view = payload.get("checkpoint") or {}
        if view.get("band") != band or not view.get("checkpoint_ready"):
            raise CheckpointError("not_ready", f"The {band} checkpoint is not ready.")
        row = mark_ready(db, user.id, band, now=now)
    elif state_of(row, coverage_met=True, now=now) != STATE_READY:
        raise CheckpointError("retry_later", f"The {band} checkpoint can be retried after {row.retry_after}.")

    row.attempts = int(row.attempts or 0) + 1
    row.last_attempt_at = now
    history = list((row.payload or {}).get("results") or [])
    history.append({"at": now.isoformat(), "passed": bool(passed), "source": source, "evidence": evidence or {}})
    row.payload = {**(row.payload or {}), "results": history[-10:]}
    if passed:
        row.status = STATE_PASSED
        row.passed_at = now
        row.retry_after = None
    else:
        row.status = STATE_FAILED
        row.retry_after = now + timedelta(days=RETRY_AFTER_DAYS)
    row.source = source
    db.add(row)
    db.flush()
    return row


__all__ = [
    "CLOSED_STATES",
    "RETRY_AFTER_DAYS",
    "STATE_CREDITED",
    "STATE_FAILED",
    "STATE_LOCKED",
    "STATE_OPEN",
    "STATE_PASSED",
    "STATE_READY",
    "CheckpointError",
    "band_can_dos",
    "checkpoint_view",
    "credit_band",
    "current_checkpoint",
    "held_ever",
    "highest_closed_band",
    "mark_ready",
    "record_checkpoint_result",
    "rows_by_band",
    "state_of",
    "track_band",
]
