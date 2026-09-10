"""WP-26 — latency as a product feature.

On a five-minute daily session a twenty-second spinner *is* the experience, and
the measured draft p50 (20–22 s, STATUS 2026-09-09) sits just under the 25 s
request timeout. This module makes the wait disappear where it can and makes it
visible where it cannot:

1. **Prefetch.** A bounded Celery beat generates the next scene ahead of time
   for active pilot learners, keyed by the WP-14C rule — story revision, scene
   identity, learner context and prompt version. A key that no longer matches at
   serve time is *discarded*, never served.
2. **Hot path.** :func:`take_prefetched_scene` hands the cached brief to the
   journey's generation phase. Taking one writes a consume row inside the
   caller's transaction, so a rolled-back create gives the scene back instead of
   burning it, and nothing is ever generated twice.
3. **Telemetry.** :func:`measure_phase` persists one wall-time row per draft,
   respond and recap request. The digest prints p50/p95 and the prefetch hit
   rate; :func:`evaluate_gate` turns those numbers into the release decision.

This module owns *no* story, planning or scene-selection logic. It schedules,
caches, measures and reports; every content decision stays in
``living_story`` / ``journey_content``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services.journey_contracts import InputMode, ScenarioBrief

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ledger vocabulary
# ---------------------------------------------------------------------------

#: One row per scene generated ahead of time. ``entity_id`` is the cache key.
PREFETCH_EVENT = "journey_scene_prefetched"
#: One row per scene handed to a live request. ``entity_id`` is the prefetch row id.
PREFETCH_CONSUMED_EVENT = "journey_scene_prefetch_consumed"
#: A prefetched scene nobody could use. Carries the wasted spend, because
#: ``bind_journey`` — which normally bills an accepted scene — never ran for it.
PREFETCH_DISCARDED_EVENT = "journey_scene_prefetch_discarded"
#: One row per measured learner-facing request.
LATENCY_EVENT = "journey_latency"

PREFETCH_ENTITY_TYPE = "journey_scene_prefetch"
LATENCY_ENTITY_TYPE = "journey_latency"

#: Phases the learner actually waits on.
PHASE_DRAFT = "draft"
PHASE_RESPOND = "respond"
PHASE_RECAP = "recap"
MEASURED_PHASES = (PHASE_DRAFT, PHASE_RESPOND, PHASE_RECAP)

# ---------------------------------------------------------------------------
# Release gate (WP-26 §3)
# ---------------------------------------------------------------------------

#: The gate. A draft that is prefetched costs a database read, so with prefetch
#: working the 95th percentile must fit comfortably inside a five-minute
#: session's opening beat. Set deliberately below the 25 s REQUEST_TIMEOUT so a
#: regression is caught by the gate, not by a learner's timeout.
DRAFT_P95_GATE_SECONDS = 8.0
#: The reply turn still pays a provider call; it is bounded, not eliminated.
RESPOND_P95_GATE_SECONDS = 20.0
#: The recap is assembled from persisted state and must never call out.
RECAP_P95_GATE_SECONDS = 3.0
#: Below this many samples the percentiles are noise: the gate reports
#: ``insufficient_data`` rather than a precise-looking pass.
GATE_MIN_SAMPLES = 10
#: With the beat running, this share of drafts should be served warm.
PREFETCH_HIT_RATE_GATE = 0.7

GATE_SECONDS: dict[str, float] = {
    PHASE_DRAFT: DRAFT_P95_GATE_SECONDS,
    PHASE_RESPOND: RESPOND_P95_GATE_SECONDS,
    PHASE_RECAP: RECAP_P95_GATE_SECONDS,
}


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


def prefetch_enabled_for(user: User) -> bool:
    """Flag **and** cohort **and** engine, checked server-side.

    The prefetch is an ahead-of-time paid call, so it is refused for anyone the
    journey itself would refuse: a learner outside the pilot cohort must never
    have money spent on them by a background beat.
    """

    if not settings.ATELIER_JOURNEY_PREFETCH_ENABLED:
        return False
    if not settings.ATELIER_STORY_ENGINE_ENABLED:
        # The authored path is a catalogue read, not a provider call. There is
        # no latency to remove and nothing to cache.
        return False
    from app.services.daily_journey import journey_enabled_for

    return journey_enabled_for(user)


# ---------------------------------------------------------------------------
# The WP-14C cache key
# ---------------------------------------------------------------------------


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scene_cache_key(db: Session, user: User, *, input_mode: InputMode) -> str | None:
    """The identity a prefetched scene must still have to be servable.

    WP-14C: *"key generation caches by the relevant story revision, scene
    identity, learner context and prompt version. A cache keyed only by user and
    exercise family is insufficient."* All four are here, and every one of them
    is cheap to recompute — the key costs a thread read, never a provider call.

    Returns ``None`` when there is nothing cacheable (engine off), which callers
    read as "no prefetch, generate as before".
    """

    if not settings.ATELIER_STORY_ENGINE_ENABLED:
        return None
    from app.services import living_story
    from app.services.journey_contracts import normalize_control_language
    from app.services.journey_errata import errata_targets_for_user

    try:
        revision = living_story.story_revision(db, user)
        # WP-24 + WP-28: the learner's due errata ARE learner context. A scene
        # is drafted to need the repaired form (``living_story.story_context``
        # puts the erratum in the director's prompt), so a scene generated for
        # one set of mistakes must not be served after that set has changed —
        # a repaired erratum would otherwise come back tomorrow morning in a
        # scene the learner already earned their way out of. Ids only, sorted:
        # the ranking's own ordering moves with the clock, the membership does
        # not.
        errata = sorted(target.error_id for target in errata_targets_for_user(db, user))
    except Exception:  # pragma: no cover - defensive: never break a live request
        logger.exception("journey_latency: cache key context unavailable")
        return None
    return _digest(
        {
            # 1. story revision
            "story_revision": revision,
            # 2. scene identity — the family the offer would resolve to today
            "scene_identity": "story_next",
            # 3. learner context
            "level_band": living_story.learner_level_band(user),
            "control_language": str(normalize_control_language(user.native_language)),
            "address": living_story.learner_address(user)["address"],
            "input_mode": str(input_mode),
            "errata_targets": errata,
            # 4. prompt version, plus the attempt policy that shapes the output
            "prompt_version": living_story.VERSION,
            "max_attempts": int(settings.ATELIER_STORY_MAX_ATTEMPTS),
        }
    )


# ---------------------------------------------------------------------------
# The store: append-only rows on the existing pilot ledger
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _ttl_floor() -> datetime:
    return _utcnow() - timedelta(seconds=settings.ATELIER_JOURNEY_PREFETCH_TTL_SECONDS)


def _consumed_ids(db: Session, candidate_ids: list[str]) -> set[str]:
    if not candidate_ids:
        return set()
    rows = db.scalars(
        select(PilotEvent.entity_id).where(
            PilotEvent.event_type.in_(
                [PREFETCH_CONSUMED_EVENT, PREFETCH_DISCARDED_EVENT]
            ),
            PilotEvent.entity_id.in_(candidate_ids),
        )
    ).all()
    return {str(value) for value in rows if value}


def _live_prefetch_rows(db: Session, user: User, *, cache_key: str | None) -> list[PilotEvent]:
    """Unconsumed, unexpired prefetch rows for this learner, newest first."""

    stmt = (
        select(PilotEvent)
        .where(
            PilotEvent.event_type == PREFETCH_EVENT,
            PilotEvent.user_id == user.id,
            PilotEvent.occurred_at >= _ttl_floor(),
        )
        .order_by(PilotEvent.occurred_at.desc())
        .limit(20)
    )
    if cache_key is not None:
        stmt = stmt.where(PilotEvent.entity_id == cache_key)
    rows = list(db.scalars(stmt).all())
    spent = _consumed_ids(db, [str(row.id) for row in rows])
    return [row for row in rows if str(row.id) not in spent]


def has_live_prefetch(db: Session, user: User, *, input_mode: InputMode = InputMode.TEXT) -> bool:
    """Is a scene waiting that would be served right now? Costs one query."""

    key = scene_cache_key(db, user, input_mode=input_mode)
    if key is None:
        return False
    return bool(_live_prefetch_rows(db, user, cache_key=key))


# ---------------------------------------------------------------------------
# Producing a prefetch
# ---------------------------------------------------------------------------


def _weekly_spend_usd(db: Session, user: User) -> float:
    since = _utcnow() - timedelta(days=7)
    rows = db.scalars(
        select(PilotEvent.cost_usd).where(
            PilotEvent.user_id == user.id,
            PilotEvent.occurred_at >= since,
            PilotEvent.event_type.in_(
                [
                    "journey_story_scene_cost",
                    "journey_story_turn_cost",
                    "journey_story_generation_failed",
                    PREFETCH_DISCARDED_EVENT,
                ]
            ),
        )
    ).all()
    return round(sum(float(value or 0.0) for value in rows), 6)


def prefetch_scene_for(
    db: Session, user: User, *, input_mode: InputMode = InputMode.TEXT
) -> str:
    """Generate the next scene ahead of time. Returns a status word.

    ``skipped_disabled`` / ``skipped_cohort`` — the flag is off or the learner is
    not in the pilot; ``skipped_open_journey`` — today's scene already exists;
    ``skipped_budget`` — the weekly cost guardrail is already met;
    ``cached`` — a valid prefetch is already waiting (idempotent, no second
    call); ``prefetched`` — a scene was generated and stored;
    ``unavailable`` — the provider refused, and the live path will try again.
    """

    if not prefetch_enabled_for(user):
        return "skipped_disabled"

    # An open or already-prepared day needs nothing prefetched: the scene it
    # will serve is the one it already holds.
    from app.db.models.daily_journey import OCCUPYING_STATUS_VALUES, DailyJourney
    from app.services.daily_journey import (
        local_date_for,
        resolve_timezone,
    )

    timezone_name = resolve_timezone(getattr(user, "timezone", None))
    today = local_date_for(timezone_name)
    open_journey = db.scalars(
        select(DailyJourney).where(
            DailyJourney.user_id == user.id,
            DailyJourney.status.in_(sorted(OCCUPYING_STATUS_VALUES)),
        )
    ).first()
    if open_journey is not None:
        return "skipped_open_journey"
    if db.scalars(
        select(DailyJourney).where(
            DailyJourney.user_id == user.id, DailyJourney.local_date == today
        )
    ).first():
        return "skipped_open_journey"

    key = scene_cache_key(db, user, input_mode=input_mode)
    if key is None:
        return "skipped_disabled"
    if _live_prefetch_rows(db, user, cache_key=key):
        # Idempotent: the same key twice never pays twice.
        return "cached"

    guardrail = float(settings.PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD or 0.0)
    if guardrail > 0 and _weekly_spend_usd(db, user) >= guardrail:
        return "skipped_budget"

    from app.services.journey_contracts import ContentUnavailable
    from app.services.living_story import generate_scene

    started = time.monotonic()
    result = generate_scene(db, user=user, input_mode=input_mode)
    elapsed = time.monotonic() - started
    if isinstance(result, ContentUnavailable) or not isinstance(result, ScenarioBrief):
        db.commit()
        return "unavailable"

    # The key is recomputed from the brief the provider actually produced: if the
    # thread moved under a long generation, this row is born stale and the serve
    # path will never match it.
    produced_key = scene_cache_key(db, user, input_mode=input_mode)
    db.add(
        PilotEvent(
            user_id=user.id,
            event_type=PREFETCH_EVENT,
            entity_type=PREFETCH_ENTITY_TYPE,
            entity_id=produced_key or key,
            payload={
                "cache_key": produced_key or key,
                "requested_key": key,
                "prompt_version": str(result.content_version),
                "input_mode": str(input_mode),
                "generated_seconds": round(elapsed, 3),
                "brief": _brief_codec()[0](result),
            },
            # Spend is billed once, by ``bind_journey``, when the scene is
            # actually served. A prefetch nobody uses is billed on its discard
            # row instead, so no engine money ever escapes the guardrail.
            cost_usd=0.0,
        )
    )
    db.commit()
    return "prefetched"


# ---------------------------------------------------------------------------
# Serving a prefetch
# ---------------------------------------------------------------------------


def _brief_codec():
    """The journey's own brief (de)serializer.

    ``ScenarioBrief`` is a frozen dataclass, not a pydantic model, so the cache
    must round-trip it with exactly the functions that already persist a brief
    into ``daily_journey_steps`` — a second, divergent serializer here would be a
    silent way to serve a subtly different scene. Imported lazily because
    ``daily_journey`` imports this module.
    """

    from app.services.daily_journey import _brief_from_json, _brief_to_json

    return _brief_to_json, _brief_from_json


def _usage_cost(brief_payload: dict[str, Any]) -> float:
    from app.services.living_story import usage_cost_usd

    brief = brief_payload.get("brief") or {}
    context = brief.get("story_context") or {}
    return usage_cost_usd(context.get("generation_usage"))


def _mark(
    db: Session,
    row: PilotEvent,
    event_type: str,
    *,
    reason: str,
    cost_usd: float = 0.0,
) -> None:
    db.add(
        PilotEvent(
            user_id=row.user_id,
            event_type=event_type,
            entity_type=PREFETCH_ENTITY_TYPE,
            entity_id=str(row.id),
            payload={
                "cache_key": (row.payload or {}).get("cache_key"),
                "reason": reason,
            },
            cost_usd=cost_usd,
        )
    )


def take_prefetched_scene(
    db: Session, user: User, *, input_mode: InputMode = InputMode.TEXT
) -> ScenarioBrief | None:
    """The hot path. Return a valid warm scene, or ``None`` to generate as now.

    Everything that does not match the *current* key is discarded here rather
    than served: a scene whose preconditions changed is exactly the "stale
    prefetch" WP-14C forbids. The consume row is added to the caller's session,
    so a create that later rolls back returns the scene to the cache untouched.
    """

    if not prefetch_enabled_for(user):
        return None
    key = scene_cache_key(db, user, input_mode=input_mode)
    if key is None:
        return None

    served: ScenarioBrief | None = None
    for row in _live_prefetch_rows(db, user, cache_key=None):
        payload = row.payload or {}
        matches = str(payload.get("cache_key") or row.entity_id or "") == key
        if served is not None or not matches:
            # Every entry this learner holds under a key that is no longer
            # current — and every duplicate behind the one being served — is
            # closed out here. A stale scene is discarded, never served, and its
            # spend is billed on the discard row.
            _mark(
                db,
                row,
                PREFETCH_DISCARDED_EVENT,
                reason="stale_cache_key" if not matches else "superseded",
                cost_usd=_usage_cost(payload),
            )
            continue
        try:
            served = _brief_codec()[1](dict(payload.get("brief") or {}))
        except Exception:
            logger.exception("journey_latency: unreadable prefetched brief")
            _mark(
                db,
                row,
                PREFETCH_DISCARDED_EVENT,
                reason="unreadable_brief",
                cost_usd=_usage_cost(payload),
            )
            continue
        _mark(db, row, PREFETCH_CONSUMED_EVENT, reason="served")
    return served


def sweep_expired_prefetches(db: Session, *, limit: int = 200) -> int:
    """Bill and close out prefetches nobody consumed before they expired."""

    rows = list(
        db.scalars(
            select(PilotEvent)
            .where(
                PilotEvent.event_type == PREFETCH_EVENT,
                PilotEvent.occurred_at < _ttl_floor(),
            )
            .order_by(PilotEvent.occurred_at.asc())
            .limit(limit)
        ).all()
    )
    spent = _consumed_ids(db, [str(row.id) for row in rows])
    closed = 0
    for row in rows:
        if str(row.id) in spent:
            continue
        _mark(
            db,
            row,
            PREFETCH_DISCARDED_EVENT,
            reason="expired",
            cost_usd=_usage_cost(row.payload or {}),
        )
        closed += 1
    if closed:
        db.commit()
    return closed


# ---------------------------------------------------------------------------
# Wall-time telemetry
# ---------------------------------------------------------------------------


def record_latency(
    db: Session,
    *,
    user: User | None,
    phase: str,
    seconds: float,
    prefetch_hit: bool | None = None,
    journey_id: uuid.UUID | str | None = None,
    outcome: str = "ok",
) -> PilotEvent:
    """One durable row per learner-facing wait. Never raises into the request."""

    event = PilotEvent(
        user_id=getattr(user, "id", None),
        event_type=LATENCY_EVENT,
        entity_type=LATENCY_ENTITY_TYPE,
        entity_id=str(journey_id) if journey_id is not None else None,
        payload={
            "phase": str(phase),
            "seconds": round(max(0.0, float(seconds)), 3),
            "ms": int(max(0.0, float(seconds)) * 1000),
            "outcome": str(outcome),
            **({} if prefetch_hit is None else {"prefetch_hit": bool(prefetch_hit)}),
        },
        cost_usd=0.0,
    )
    event.occurred_at = _utcnow()
    db.add(event)
    return event


class PhaseTiming:
    """Mutable handle a measured block uses to declare what actually happened."""

    def __init__(self) -> None:
        self.prefetch_hit: bool | None = None
        self.outcome: str = "ok"
        self.journey_id: uuid.UUID | str | None = None


@contextmanager
def measure_phase(
    db: Session,
    *,
    user: User | None,
    phase: str,
    journey_id: uuid.UUID | str | None = None,
    commit: bool = True,
) -> Iterator[PhaseTiming]:
    """Measure one request's wall time and persist it, success or failure.

    The row is added to the caller's session. A create that rolls back drops its
    own measurement with it, which is correct: an aborted transaction produced no
    served draft to measure.
    """

    timing = PhaseTiming()
    timing.journey_id = journey_id
    started = time.monotonic()
    try:
        yield timing
    except BaseException:
        timing.outcome = "failed"
        raise
    finally:
        try:
            record_latency(
                db,
                user=user,
                phase=phase,
                seconds=time.monotonic() - started,
                prefetch_hit=timing.prefetch_hit,
                journey_id=timing.journey_id or journey_id,
                outcome=timing.outcome,
            )
            if commit:
                # The measured mutation has already committed its own effects by
                # the time this runs, so this commit can only flush the row.
                db.commit()
        except Exception:  # pragma: no cover - telemetry must never break a request
            logger.exception("journey_latency: could not record %s latency", phase)
            try:
                db.rollback()
            except Exception:  # noqa: S110 - nothing useful is left to say
                logger.debug("journey_latency: rollback after a failed record")


# ---------------------------------------------------------------------------
# Reporting and the gate
# ---------------------------------------------------------------------------


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    index = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return round(ordered[index], 3)


def latency_rollup(
    db: Session, day: date, *, user_id: str | uuid.UUID | None = None
) -> dict[str, Any]:
    """Per-phase p50/p95 and the prefetch hit rate for one day."""

    from app.services.pilot_events import _day_bounds

    start, end = _day_bounds(day)
    stmt = select(PilotEvent).where(
        PilotEvent.event_type.in_(
            [LATENCY_EVENT, PREFETCH_EVENT, PREFETCH_CONSUMED_EVENT, PREFETCH_DISCARDED_EVENT]
        ),
        PilotEvent.occurred_at >= start,
        PilotEvent.occurred_at < end,
    )
    if user_id:
        stmt = stmt.where(PilotEvent.user_id == uuid.UUID(str(user_id)))

    seconds: dict[str, list[float]] = {phase: [] for phase in MEASURED_PHASES}
    failures: dict[str, int] = dict.fromkeys(MEASURED_PHASES, 0)
    draft_hits = 0
    draft_measured = 0
    prefetched = 0
    consumed = 0
    discarded = 0
    wasted_usd = 0.0

    for row in db.scalars(stmt).all():
        payload = row.payload or {}
        if row.event_type == PREFETCH_EVENT:
            prefetched += 1
            continue
        if row.event_type == PREFETCH_CONSUMED_EVENT:
            consumed += 1
            continue
        if row.event_type == PREFETCH_DISCARDED_EVENT:
            discarded += 1
            wasted_usd += float(row.cost_usd or 0.0)
            continue
        phase = str(payload.get("phase") or "")
        if phase not in seconds:
            continue
        if str(payload.get("outcome") or "ok") != "ok":
            failures[phase] += 1
            continue
        seconds[phase].append(float(payload.get("seconds") or 0.0))
        if phase == PHASE_DRAFT and "prefetch_hit" in payload:
            draft_measured += 1
            if payload.get("prefetch_hit"):
                draft_hits += 1

    phases = {
        phase: {
            "samples": len(values),
            "failures": failures[phase],
            "p50_seconds": _percentile(values, 0.5),
            "p95_seconds": _percentile(values, 0.95),
            "gate_seconds": GATE_SECONDS[phase],
        }
        for phase, values in seconds.items()
    }
    return {
        "day": day.isoformat(),
        "phases": phases,
        "prefetch": {
            "generated": prefetched,
            "consumed": consumed,
            "discarded": discarded,
            "wasted_usd": round(wasted_usd, 6),
            "draft_requests": draft_measured,
            "draft_hits": draft_hits,
            "hit_rate": (
                round(draft_hits / draft_measured, 3) if draft_measured else None
            ),
            "hit_rate_gate": PREFETCH_HIT_RATE_GATE,
        },
    }


def evaluate_gate(rollup: dict[str, Any]) -> dict[str, Any]:
    """The release decision, computed from telemetry rather than asserted.

    ``status`` is ``pass``, ``fail`` or ``insufficient_data``. A day with fewer
    than :data:`GATE_MIN_SAMPLES` measured drafts is never reported as a pass:
    a gate that green-lights on three samples is not a gate.
    """

    phases = rollup.get("phases") or {}
    reasons: list[str] = []
    thin: list[str] = []
    for phase in MEASURED_PHASES:
        stats = phases.get(phase) or {}
        samples = int(stats.get("samples") or 0)
        p95 = stats.get("p95_seconds")
        limit = float(stats.get("gate_seconds") or GATE_SECONDS[phase])
        if samples < GATE_MIN_SAMPLES or p95 is None:
            thin.append(f"{phase}: {samples} samples (< {GATE_MIN_SAMPLES})")
            continue
        if float(p95) > limit:
            reasons.append(f"{phase} p95 {float(p95):.2f}s > {limit:.2f}s")

    prefetch = rollup.get("prefetch") or {}
    hit_rate = prefetch.get("hit_rate")
    draft_requests = int(prefetch.get("draft_requests") or 0)
    if draft_requests >= GATE_MIN_SAMPLES and hit_rate is not None:
        if float(hit_rate) < PREFETCH_HIT_RATE_GATE:
            reasons.append(
                f"prefetch hit rate {float(hit_rate):.0%} < {PREFETCH_HIT_RATE_GATE:.0%}"
            )

    if reasons:
        status = "fail"
    elif thin:
        status = "insufficient_data"
    else:
        status = "pass"
    return {"status": status, "reasons": reasons, "insufficient": thin}


def format_latency_lines(rollup: dict[str, Any]) -> list[str]:
    """The digest section. Every rate carries its denominator (WP-11 house style)."""

    lines = ["Journey latency (WP-26):"]
    phases = rollup.get("phases") or {}
    for phase in MEASURED_PHASES:
        stats = phases.get(phase) or {}
        samples = int(stats.get("samples") or 0)
        if not samples:
            lines.append(f"  {phase}: no measured requests")
            continue
        p50 = stats.get("p50_seconds")
        p95 = stats.get("p95_seconds")
        line = (
            f"  {phase}: n={samples} · p50 {float(p50):.1f}s · p95 {float(p95):.1f}s "
            f"(gate p95 ≤ {float(stats.get('gate_seconds') or 0.0):.0f}s)"
        )
        if stats.get("failures"):
            line += f" · {stats['failures']} failed request(s)"
        lines.append(line)
    prefetch = rollup.get("prefetch") or {}
    hit_rate = prefetch.get("hit_rate")
    if prefetch.get("draft_requests"):
        lines.append(
            f"  prefetch: {prefetch.get('draft_hits', 0)}/{prefetch['draft_requests']} drafts "
            f"served warm ({float(hit_rate):.0%})"
            if hit_rate is not None
            else "  prefetch: no draft carried a hit flag"
        )
    else:
        lines.append("  prefetch: no measured drafts")
    lines.append(
        f"  prefetch rows: {prefetch.get('generated', 0)} generated · "
        f"{prefetch.get('consumed', 0)} consumed · {prefetch.get('discarded', 0)} discarded "
        f"(${float(prefetch.get('wasted_usd') or 0.0):.4f} wasted)"
    )
    gate = evaluate_gate(rollup)
    if gate["status"] == "pass":
        lines.append("  release gate: PASS")
    elif gate["status"] == "fail":
        lines.append("  release gate: FAIL — " + "; ".join(gate["reasons"]))
    else:
        lines.append(
            "  release gate: insufficient data — " + "; ".join(gate["insufficient"])
        )
    return lines


__all__ = [
    "DRAFT_P95_GATE_SECONDS",
    "GATE_MIN_SAMPLES",
    "GATE_SECONDS",
    "LATENCY_EVENT",
    "MEASURED_PHASES",
    "PHASE_DRAFT",
    "PHASE_RECAP",
    "PHASE_RESPOND",
    "PREFETCH_CONSUMED_EVENT",
    "PREFETCH_DISCARDED_EVENT",
    "PREFETCH_EVENT",
    "PREFETCH_HIT_RATE_GATE",
    "RECAP_P95_GATE_SECONDS",
    "RESPOND_P95_GATE_SECONDS",
    "evaluate_gate",
    "format_latency_lines",
    "has_live_prefetch",
    "latency_rollup",
    "measure_phase",
    "prefetch_enabled_for",
    "prefetch_scene_for",
    "record_latency",
    "scene_cache_key",
    "sweep_expired_prefetches",
    "take_prefetched_scene",
]
