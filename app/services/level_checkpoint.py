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

* ``locked`` has no row. The row is written ``ready`` the first time coverage
  is met (``open`` is accepted as a stored synonym of locked).
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
#: Stored only, read as locked: a band row written before its coverage was met.
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
        # WP-94 honesty: the épreuve is a «Numéro spécial» the story engine
        # stages and the journey grades. With the engine off nothing stages it,
        # so no surface may promise «l'épreuve dans l'histoire».
        "staged_in_story": _epreuve_staged(),
    }


def _epreuve_staged() -> bool:
    from app.config import settings

    return bool(getattr(settings, "ATELIER_STORY_ENGINE_ENABLED", False))


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.isoformat() if value is not None else None


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


# ----------------------------------------------------------------------
# WP-94 «Numéro spécial» — grading the épreuve a journey staged
# ----------------------------------------------------------------------


def epreuve_unit_ids(can_do_ids: list[str] | None, band: str) -> list[str]:
    """The grammar units (fr-core-v2 external ids) the épreuve's can-dos exercise.

    ``can_do_ids`` is the engine's list; when it is empty or names nothing of
    the band's, the band's whole can-do list stands in.
    """

    by_id = {item["id"]: item for item in band_can_dos(band)}
    chosen = [by_id[cid] for cid in (can_do_ids or []) if cid in by_id] or list(by_id.values())
    units: list[str] = []
    for item in chosen:
        for unit in item.get("units") or []:
            if unit not in units:
                units.append(unit)
    return units


def _unit_patterns(unit_id: str) -> list[str]:
    from app.services.grammar_units import _v2_rows_by_external_id, regex_patterns

    row = _v2_rows_by_external_id().get(unit_id) or {}
    detector = (row.get("syllabus") or {}).get("detector")
    return regex_patterns([detector] if isinstance(detector, dict) else [])


def _concept_external_ids(db: Session, concept_ids: list[int]) -> dict[int, set[str]]:
    """concept id → the v2 external ids it stands for (itself, or its v1→v2 replacements)."""

    from app.db.models.grammar import GrammarConcept
    from app.services.grammar_catalog import load_v1_to_v2_mapping

    if not concept_ids:
        return {}
    mapping = load_v1_to_v2_mapping()
    out: dict[int, set[str]] = {}
    for concept in db.query(GrammarConcept).filter(GrammarConcept.id.in_(concept_ids)).all():
        external = str(concept.external_id or "")
        out[concept.id] = {external, *mapping.get(external, [])} - {""}
    return out


def grade_epreuve(
    db: Session,
    *,
    band: str,
    can_do_ids: list[str] | None,
    objective_met: bool,
    turns: list[dict[str, Any]] | None,
    concept_evidence: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """The épreuve's verdict. Pure reading; nothing is written.

    **The rule (WP-94):** the épreuve is passed when

    1. the scene's objective was **met** across the conversation (the respond
       step's final outcome is ``met`` — ``partially_met`` is not a pass), and
    2. the reply evidence shows **at least one** of the épreuve's grammar units
       (the units of its can-dos, :func:`epreuve_unit_ids`) used **correctly**:
       either WP-L4's ``concept_evidence`` on the step says ``correct`` for a
       concept standing for one of them, or the unit's own regex detector finds
       it in one of the learner's turns and that turn's correction does not
       touch it (``concept_evidence.classify_reply``, the same classifier).

    Units whose only detector is an ``llm:`` description cannot be read
    deterministically; when **none** of the épreuve's units has a regex
    detector (or the list is empty), condition 2 is waived and the objective
    alone decides. The verdict carries its evidence for the checkpoint row.
    """

    from types import SimpleNamespace

    from app.services.concept_evidence import OUTCOME_CORRECT, classify_reply
    from app.services.journey_contracts import normalize_answer_text

    units = epreuve_unit_ids(can_do_ids, band)
    patterns = {unit: _unit_patterns(unit) for unit in units}
    measurable = [unit for unit, pats in patterns.items() if pats]
    used: set[str] = set()
    evidence = [item for item in (concept_evidence or []) if isinstance(item, dict)]
    correct_ids = [
        int(item["concept_id"])
        for item in evidence
        if item.get("outcome") == OUTCOME_CORRECT and str(item.get("concept_id") or "").isdigit()
    ]
    for externals in _concept_external_ids(db, correct_ids).values():
        used |= externals & set(units)
    for turn in turns or []:
        if not isinstance(turn, dict):
            continue
        text = normalize_answer_text(str(turn.get("learner") or ""))
        if not text:
            continue
        raw = turn.get("correction") if isinstance(turn.get("correction"), dict) else None
        correction = SimpleNamespace(**raw) if raw else None
        for unit in measurable:
            outcome, _span = classify_reply(patterns[unit], text, correction)
            if outcome == OUTCOME_CORRECT:
                used.add(unit)
    units_ok = (not measurable) or bool(used)
    return {
        "passed": bool(objective_met and units_ok),
        "objective_met": bool(objective_met),
        "units": units,
        "measurable_units": measurable,
        "units_used": sorted(used),
        "units_waived": not measurable,
    }


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
    "epreuve_unit_ids",
    "grade_epreuve",
    "credit_band",
    "current_checkpoint",
    "highest_closed_band",
    "mark_ready",
    "record_checkpoint_result",
    "rows_by_band",
    "state_of",
]
