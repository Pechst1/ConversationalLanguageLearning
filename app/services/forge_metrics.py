"""WP-S8 — measure La Forge: per-rule speed, per-séance health, latency.

WORK-PACKAGES-2026-09-24-seance §3 WP-S8. Everything here is read from rows the
app already writes; nothing is estimated. The definitions (also in the doc's
Status):

**Per rule** (one learner × one grammar concept, ``UserGrammarProgress``):

* *items-to-proficient* — Atelier answers on the rule up to and including the
  first séance answer that put its forge rung at ≥ 4 (``produce``;
  ``correction_payload.forge.new_rung``). Test-out answers are not séance
  answers and never count here. Cohort: rules that first reached rung 4 in the
  window.
* *items-to-held* — Atelier answers on the rule up to its ``held_at``. Cohort:
  rules held in the window **by practice** (``tested_out_at`` empty); a
  test-out is a placement, reported as its own rate.
* *days-to-held* — ``held_at − introduced_at`` in days, same cohort.
* *lapse rate after held* — of the held rules that came back on a later day
  (a checked answer on a day after the hold day, in the window), the share
  whose first checked answer of some later day was wrong.
* *test-out pass rate* — finished «Épreuves de la règle» in the window that
  passed.

**Per séance** (forge séances, ``quote_payload.forge.mode == "seance"``,
started in the window):

* *active minutes* — the séance's own clock: start → each answer → completion,
  every gap capped at :data:`IDLE_GAP_CEILING_SECONDS` (the journey's idle
  ceiling), so a séance left open over lunch is not an hour of work;
* *completion* — status ``completed``;
* *abandon* — not completed and a ``forge_abandoned`` event, or still open with
  no activity for :data:`ABANDON_AFTER` (the learner never came back);
* *latency* — ``forge_verdict`` events: ``local_ms`` p50/p95 per rung, and
  ``async_llm_ms`` p50/p95 where a relecture ran.

**Band** is the learner's current ``cefr_estimate`` (A1, A2, B1…), read at
report time.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from statistics import median
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import forge as core
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.grammar import UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User

FORGE_ABANDONED_EVENT = "forge_abandoned"
FORGE_VERDICT_EVENT = "forge_verdict"

#: The forge rung that counts as *proficient* (``produce``).
PROFICIENT_RUNG = int(core.Rung.PRODUCE)
#: A gap between two actions longer than this is away time, not séance time.
IDLE_GAP_CEILING_SECONDS = 180
#: An open séance untouched this long was left (the parked-resume window).
ABANDON_AFTER = timedelta(hours=24)
#: The dashboard's windows, in days.
WINDOWS = (7, 30)
#: The Dossier line appears once this many rules are held.
DOSSIER_MIN_HELD = 3

_TEST_OUT_STATUSES = frozenset({"test_out", "test_out_done"})


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _percentile(values: Iterable[float], fraction: float) -> float | None:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1)))))
    return round(ordered[index], 1)


def _median(values: Iterable[float]) -> float | None:
    items = [float(v) for v in values]
    return round(float(median(items)), 1) if items else None


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def band_of_estimate(estimate: str | None) -> str:
    from app.services.lexical_coverage import band_of

    return band_of(estimate)


# ---------------------------------------------------------------------------
# The abandon event
# ---------------------------------------------------------------------------


def _forge_seance(session: AtelierSession) -> dict[str, Any] | None:
    """The séance's forge payload, or ``None`` for a legacy séance / a test-out."""

    if str(session.status or "") in _TEST_OUT_STATUSES:
        return None
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    forge = quote.get("forge") if isinstance(quote, dict) else None
    if not isinstance(forge, dict) or forge.get("tracks") is None:
        return None
    if str(forge.get("mode") or core.MODE_SEANCE) != core.MODE_SEANCE:
        return None
    return forge


def _already_abandoned(db: Session, session_id: UUID | str) -> bool:
    return (
        db.query(PilotEvent.id)
        .filter(PilotEvent.event_type == FORGE_ABANDONED_EVENT, PilotEvent.entity_id == str(session_id))
        .first()
        is not None
    )


def record_forge_abandoned(
    db: Session, session: AtelierSession, *, reason: str, now: datetime | None = None
) -> PilotEvent | None:
    """A forge séance left unfinished: one ``forge_abandoned`` row per séance.

    ``reason`` — ``parked`` (the learner asked for another rule),
    ``exit`` (the close button), ``expired`` (found untouched on a later start).
    A finished or completed séance, a test-out and a legacy séance write
    nothing; a second call for the same séance writes nothing. Never commits.
    """

    from app.services.pilot_events import PilotEventService

    forge = _forge_seance(session)
    if forge is None or session.status == "completed" or forge.get("finished"):
        return None
    if _already_abandoned(db, session.id):
        return None
    history = forge.get("history") if isinstance(forge.get("history"), list) else []
    now = now or datetime.now(UTC)
    started = _aware(session.started_at)
    return PilotEventService(db).record(
        FORGE_ABANDONED_EVENT,
        user_id=session.user_id,
        entity_type="atelier_session",
        entity_id=session.id,
        payload={
            "reason": reason,
            "answered": len(history),
            "length": int(forge.get("length") or 0),
            "concept_ids": [int(t.get("concept_id")) for t in forge.get("tracks") or [] if isinstance(t, dict)],
            "origin": forge.get("origin"),
            "budget_seconds": forge.get("budget_seconds"),
            "open_seconds": int((now - started).total_seconds()) if started else None,
        },
        occurred_at=now,
    )


def _last_activity(db: Session, session: AtelierSession) -> datetime | None:
    from sqlalchemy import func

    last = (
        db.query(func.max(AtelierAttempt.created_at))
        .filter(AtelierAttempt.atelier_session_id == session.id)
        .scalar()
    )
    candidates = [value for value in (_aware(last), _aware(session.started_at)) if value is not None]
    return max(candidates) if candidates else None


def sweep_stale_forge_seances(
    db: Session, *, user_id: UUID, now: datetime | None = None, keep: UUID | None = None
) -> int:
    """On a start: open forge séances untouched for a day were left. Never commits."""

    now = now or datetime.now(UTC)
    rows = (
        db.query(AtelierSession)
        .filter(AtelierSession.user_id == user_id, AtelierSession.status.in_(("in_progress", "parked")))
        .all()
    )
    written = 0
    for session in rows:
        if keep is not None and session.id == keep:
            continue
        if _forge_seance(session) is None:
            continue
        last = _last_activity(db, session)
        if last is None or now - last < ABANDON_AFTER:
            continue
        if record_forge_abandoned(db, session, reason="expired", now=now) is not None:
            written += 1
    return written


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _checked_wrong(attempt: AtelierAttempt) -> tuple[bool, bool]:
    """``(checked, wrong)`` for one answer, the forge's own reading."""

    from app.services.forge import verdict_from_attempt

    verdict = verdict_from_attempt(attempt)
    return verdict.checked, verdict.outcome == core.OUTCOME_INCORRECT


def _new_rung(attempt: AtelierAttempt) -> int | None:
    correction = attempt.correction_payload if isinstance(attempt.correction_payload, dict) else {}
    forge = correction.get("forge") if isinstance(correction.get("forge"), dict) else None
    if not forge or forge.get("new_rung") is None:
        return None
    try:
        return int(forge["new_rung"])
    except (TypeError, ValueError):
        return None


def _in(value: datetime | None, since: datetime, until: datetime) -> bool:
    value = _aware(value)
    return value is not None and since <= value < until


def rule_metrics(
    progress_rows: list[UserGrammarProgress],
    attempts: list[AtelierAttempt],
    test_out_sessions: list[AtelierSession],
    *,
    since: datetime,
    until: datetime,
    test_out_session_ids: set[Any] | None = None,
) -> dict[str, Any]:
    """Per-rule speed over one window, from the rows alone (pure: no queries)."""

    test_out_ids = {str(sid) for sid in (test_out_session_ids or set())}
    test_out_ids |= {str(session.id) for session in test_out_sessions}
    by_rule: dict[tuple[str, int], list[AtelierAttempt]] = defaultdict(list)
    for attempt in attempts:
        if attempt.concept_id is None:
            continue
        by_rule[(str(attempt.user_id), int(attempt.concept_id))].append(attempt)
    for rows in by_rule.values():
        rows.sort(key=lambda row: (_aware(row.created_at) or since, str(row.id)))

    to_proficient: list[int] = []
    to_held: list[int] = []
    days_to_held: list[float] = []
    returned = 0
    lapsed = 0
    for progress in progress_rows:
        rows = by_rule.get((str(progress.user_id), int(progress.concept_id)), [])
        # Items to proficient: the first séance answer that seated rung ≥ 4.
        for index, attempt in enumerate(rows):
            if str(attempt.atelier_session_id) in test_out_ids:
                continue
            rung = _new_rung(attempt)
            if rung is not None and rung >= PROFICIENT_RUNG:
                if _in(attempt.created_at, since, until):
                    to_proficient.append(index + 1)
                break
        held_at = _aware(progress.held_at)
        if held_at is None:
            continue
        if progress.tested_out_at is None and since <= held_at < until:
            to_held.append(sum(1 for row in rows if (_aware(row.created_at) or held_at) <= held_at))
            introduced = _aware(progress.introduced_at)
            if introduced is not None and introduced <= held_at:
                days_to_held.append((held_at - introduced).total_seconds() / 86400)
        # Lapses: the first checked answer of each later day.
        first_of_day: dict[Any, bool] = {}
        for attempt in rows:
            created = _aware(attempt.created_at)
            if created is None or created.date() <= held_at.date() or not (since <= created < until):
                continue
            checked, wrong = _checked_wrong(attempt)
            if not checked or created.date() in first_of_day:
                continue
            first_of_day[created.date()] = wrong
        if first_of_day:
            returned += 1
            lapsed += 1 if any(first_of_day.values()) else 0

    finished = [s for s in test_out_sessions if s.status == "test_out_done" and _in(s.completed_at, since, until)]
    passed = sum(
        1 for s in finished if bool(((s.recap_payload or {}).get("test_out") or {}).get("passed"))
    )
    return {
        "items_to_proficient": {"n": len(to_proficient), "median": _median(to_proficient), "p90": _percentile(to_proficient, 0.9)},
        "items_to_held": {"n": len(to_held), "median": _median(to_held), "p90": _percentile(to_held, 0.9)},
        "days_to_held": {"n": len(days_to_held), "median": _median(days_to_held), "p90": _percentile(days_to_held, 0.9)},
        "lapse_after_held": {"returned": returned, "lapsed": lapsed, "rate": _rate(lapsed, returned)},
        "test_out": {"finished": len(finished), "passed": passed, "pass_rate": _rate(passed, len(finished))},
    }


def active_seconds(session: AtelierSession, attempts: list[AtelierAttempt]) -> int:
    """The séance's clock: start → answers → completion, idle gaps capped."""

    moments = [_aware(session.started_at)]
    moments += [_aware(attempt.created_at) for attempt in attempts]
    if session.status == "completed":
        moments.append(_aware(session.completed_at))
    points = sorted(m for m in moments if m is not None)
    return int(
        sum(min(IDLE_GAP_CEILING_SECONDS, max(0.0, (b - a).total_seconds())) for a, b in zip(points, points[1:]))
    )


def seance_metrics(
    sessions: list[AtelierSession],
    attempts_by_session: dict[str, list[AtelierAttempt]],
    abandoned_ids: set[str],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Per-séance health over forge séances (pure)."""

    started = completed = abandoned = still_open = 0
    minutes: list[float] = []
    items: list[int] = []
    reasons: dict[str, int] = defaultdict(int)
    for session in sessions:
        if _forge_seance(session) is None:
            continue
        started += 1
        rows = attempts_by_session.get(str(session.id), [])
        if session.status == "completed":
            completed += 1
            minutes.append(active_seconds(session, rows) / 60)
            items.append(len(rows))
            continue
        last = max([_aware(r.created_at) for r in rows] + [_aware(session.started_at)], default=None)
        if str(session.id) in abandoned_ids:
            abandoned += 1
        elif last is not None and now - last >= ABANDON_AFTER:
            abandoned += 1
            reasons["never_returned"] += 1
        else:
            still_open += 1
    return {
        "started": started,
        "completed": completed,
        "abandoned": abandoned,
        "still_open": still_open,
        "completion_rate": _rate(completed, started),
        "abandon_rate": _rate(abandoned, started),
        "active_minutes": {"n": len(minutes), "median": _median(minutes), "p90": _percentile(minutes, 0.9)},
        "items": {"median": _median(items)},
        "never_returned": reasons["never_returned"],
    }


def latency_metrics(events: list[PilotEvent]) -> dict[str, Any]:
    """``forge_verdict`` rows → p50/p95 per rung, local and asynchronous."""

    from app.services.forge import rung_for_attempt

    local: dict[str, list[float]] = defaultdict(list)
    remote: dict[str, list[float]] = defaultdict(list)
    changed: dict[str, int] = defaultdict(int)
    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        rung = rung_for_attempt(payload.get("rung"), payload.get("mode"))
        name = core.rung_name(rung) if rung is not None else str(payload.get("rung") or "other")
        if isinstance(payload.get("local_ms"), (int, float)):
            local[name].append(float(payload["local_ms"]))
        if isinstance(payload.get("async_llm_ms"), (int, float)):
            remote[name].append(float(payload["async_llm_ms"]))
            changed[name] += 1 if payload.get("verdict_changed") else 0
    order = [core.rung_name(r) for r in core.Rung]
    names = sorted(set(local) | set(remote), key=lambda n: (order.index(n) if n in order else 99, n))
    return {
        "by_rung": [
            {
                "rung": name,
                "n": len(local[name]),
                "local_p50_ms": _percentile(local[name], 0.5),
                "local_p95_ms": _percentile(local[name], 0.95),
                "async_n": len(remote[name]),
                "async_p50_ms": _percentile(remote[name], 0.5),
                "async_p95_ms": _percentile(remote[name], 0.95),
                "verdict_changed": changed[name],
            }
            for name in names
        ],
        "local_p95_ms": _percentile([v for values in local.values() for v in values], 0.95),
    }


# ---------------------------------------------------------------------------
# The dashboard
# ---------------------------------------------------------------------------


def _window_report(db: Session, *, since: datetime, until: datetime, user_ids: set[str] | None) -> dict[str, Any]:
    def scoped(query, column):
        if user_ids is None:
            return query
        return query.filter(column.in_([UUID(uid) for uid in user_ids] or [UUID(int=0)]))

    progress_rows = scoped(
        db.query(UserGrammarProgress).filter(
            (UserGrammarProgress.held_at.isnot(None)) | (UserGrammarProgress.forge_rung.isnot(None))
        ),
        UserGrammarProgress.user_id,
    ).all()
    pairs = {(str(row.user_id), int(row.concept_id)) for row in progress_rows}
    attempt_users = {UUID(uid) for uid, _cid in pairs}
    attempts = (
        db.query(AtelierAttempt)
        .filter(AtelierAttempt.user_id.in_(attempt_users or {UUID(int=0)}), AtelierAttempt.created_at < until)
        .all()
    )
    attempts = [a for a in attempts if a.concept_id is not None and (str(a.user_id), int(a.concept_id)) in pairs]
    test_out_sessions = scoped(
        db.query(AtelierSession).filter(AtelierSession.status.in_(tuple(_TEST_OUT_STATUSES))),
        AtelierSession.user_id,
    ).all()
    rules = rule_metrics(progress_rows, attempts, test_out_sessions, since=since, until=until)

    sessions = scoped(
        db.query(AtelierSession).filter(AtelierSession.started_at >= since, AtelierSession.started_at < until),
        AtelierSession.user_id,
    ).all()
    sessions = [s for s in sessions if _forge_seance(s) is not None]
    session_ids = [s.id for s in sessions]
    by_session: dict[str, list[AtelierAttempt]] = defaultdict(list)
    if session_ids:
        for attempt in db.query(AtelierAttempt).filter(AtelierAttempt.atelier_session_id.in_(session_ids)).all():
            by_session[str(attempt.atelier_session_id)].append(attempt)
    abandoned_ids = {
        str(entity_id)
        for (entity_id,) in db.query(PilotEvent.entity_id)
        .filter(PilotEvent.event_type == FORGE_ABANDONED_EVENT, PilotEvent.entity_id.in_([str(s) for s in session_ids] or ["-"]))
        .all()
    }
    seances = seance_metrics(sessions, by_session, abandoned_ids, now=until)
    reasons: dict[str, int] = defaultdict(int)
    for event in (
        db.query(PilotEvent)
        .filter(PilotEvent.event_type == FORGE_ABANDONED_EVENT, PilotEvent.entity_id.in_(list(abandoned_ids) or ["-"]))
        .all()
    ):
        reasons[str((event.payload or {}).get("reason") or "unknown")] += 1
    if seances["never_returned"]:
        reasons["never_returned"] += seances["never_returned"]
    seances["abandon_reasons"] = dict(reasons)

    events = scoped(
        db.query(PilotEvent).filter(
            PilotEvent.event_type == FORGE_VERDICT_EVENT,
            PilotEvent.occurred_at >= since,
            PilotEvent.occurred_at < until,
        ),
        PilotEvent.user_id,
    ).all()
    learners = {str(s.user_id) for s in sessions} | {str(e.user_id) for e in events if e.user_id}
    return {
        "learners": len(learners),
        "rules": rules,
        "seances": seances,
        "latency": latency_metrics(events),
    }


def forge_dashboard(
    db: Session,
    *,
    now: datetime | None = None,
    windows: Iterable[int] = WINDOWS,
    user_ids: Iterable[UUID | str] | None = None,
) -> dict[str, Any]:
    """«La Forge» on the pilot dashboard: every window, overall and per band.

    ``user_ids`` narrows the report to a cohort (default: every learner).
    """

    now = _aware(now) or datetime.now(UTC)
    cohort = {str(uid) for uid in user_ids} if user_ids is not None else None
    bands: dict[str, set[str]] = defaultdict(set)
    for user_id, estimate in db.query(User.id, User.cefr_estimate).all():
        if cohort is None or str(user_id) in cohort:
            bands[band_of_estimate(estimate)].add(str(user_id))
    report: dict[str, Any] = {"generated_at": now.isoformat(), "windows": []}
    for days in windows:
        since = now - timedelta(days=int(days))
        overall = _window_report(db, since=since, until=now, user_ids=cohort)
        by_band = []
        if overall["learners"]:
            for band in sorted(bands):
                section = _window_report(db, since=since, until=now, user_ids=bands[band])
                if section["learners"] or section["rules"]["items_to_held"]["n"]:
                    by_band.append({"band": band, **section})
        report["windows"].append({"days": int(days), "since": since.isoformat(), "overall": overall, "by_band": by_band})
    return report


# ---------------------------------------------------------------------------
# The learner's own claim (the Dossier)
# ---------------------------------------------------------------------------


def learner_rule_speed(db: Session, *, user_id: UUID) -> dict[str, Any]:
    """«Your rules: n held, median x days to hold» — measured, never promised.

    ``held`` counts every held rule (a test-out included); the median is over
    rules held by practice only (a test-out holds a rule in zero days, which
    says nothing about speed). ``show`` is true from :data:`DOSSIER_MIN_HELD`
    held rules.
    """

    rows = (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user_id, UserGrammarProgress.held_at.isnot(None))
        .all()
    )
    days = []
    for row in rows:
        held = _aware(row.held_at)
        introduced = _aware(row.introduced_at)
        if row.tested_out_at is None and held is not None and introduced is not None and introduced <= held:
            days.append((held - introduced).total_seconds() / 86400)
    median_days = int(round(median(days))) if days else None
    return {
        "held": len(rows),
        "held_by_practice": len(days),
        "median_days_to_held": median_days,
        "show": len(rows) >= DOSSIER_MIN_HELD,
        "minimum": DOSSIER_MIN_HELD,
    }


__all__ = [
    "ABANDON_AFTER",
    "DOSSIER_MIN_HELD",
    "FORGE_ABANDONED_EVENT",
    "PROFICIENT_RUNG",
    "active_seconds",
    "forge_dashboard",
    "latency_metrics",
    "learner_rule_speed",
    "record_forge_abandoned",
    "rule_metrics",
    "seance_metrics",
    "sweep_stale_forge_seances",
]
