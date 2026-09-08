"""Journey observability and honest duration reporting (WP-11).

This module is the **only** place the ten frozen
:class:`~app.services.journey_contracts.JourneyEventName` values are turned into
rows. It writes through the existing :class:`~app.services.pilot_events.PilotEventService`
ledger — there is deliberately no analytics SDK and no second event table.

Three properties matter more than the volume of telemetry:

1. **Authoritative transitions are deduplicated.** A duplicate HTTP request is
   observable as a *retry* on the existing row (``payload["repeats"]``); it can
   never become a second ``journey_completed``. One sample day is therefore
   reconstructable without double-counting.
2. **No learner content ever reaches telemetry.** Every metadata key is
   allow-listed and every value is validated against a closed set, a numeric
   range, or a strict slug pattern. A learner utterance ("Je voudrais un café,
   s'il vous plaît.") fails every validator under every key, so it cannot be
   stored even by a caller that tries.
3. **Duration is measured, never estimated.** ``active_seconds`` comes from the
   server's own event timestamps with pauses excluded, idle stretches capped and
   provider waiting reported separately, so a slow provider is distinguishable
   from a slow learner. When it genuinely cannot be measured the answer is
   ``None`` — never the plan's estimate and never a fabricated number
   (CONTRACTS §9).

Client-supplied timings are accepted under ``metadata["client"]`` and kept as
**diagnostics only**: :func:`measure_journey_duration` never reads them, so no
client can inflate (or deflate) the number that reaches
``JourneyRecap.active_seconds``, and nothing here is evidence for a reward or an
ability judgement.
"""
from __future__ import annotations

import logging
import re
import time
from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.services.journey_contracts import (
    AssistanceLevel,
    CapabilityKey,
    EvidenceKind,
    HelpKind,
    InputMode,
    JourneyEventName,
    JourneyStatus,
    StepKind,
    StepStatus,
    TaskOutcome,
    effect_source_key,
)

logger = logging.getLogger(__name__)

#: Payload shape version. Bumped when a field's meaning changes, so an old row
#: is never silently reinterpreted by a newer digest.
JOURNEY_EVENT_SCHEMA_VERSION = 1

#: ``PilotEvent.entity_type`` for every event written here.
JOURNEY_ENTITY_TYPE = "daily_journey"

#: WP-03 writes its own content events with this entity type. They carry no
#: journey id, so the digest counts them for reliability but not for the funnel.
CONTENT_ENTITY_TYPE = "daily_journey_content"

JOURNEY_EVENT_NAMES: frozenset[str] = frozenset(str(name) for name in JourneyEventName)

#: Only these two end a journey.
TERMINAL_EVENT_NAMES: frozenset[str] = frozenset(
    {str(JourneyEventName.COMPLETED), str(JourneyEventName.ENDED_EARLY)}
)

#: The zone the rest of the pilot ledger already uses. Only reached for an event
#: whose payload carries no journey timezone snapshot; the digest counts those
#: separately rather than pretending they were attributed properly.
FALLBACK_TIMEZONE = "Europe/Berlin"

#: Below this many started journeys a rate is noise, not a measurement.
MIN_DIGEST_SAMPLE = 5

# --------------------------------------------------------------------------
# Duration measurement constants (CONTRACTS §9)
# --------------------------------------------------------------------------

#: A single step is never legitimately longer than this, so anything beyond it
#: is the learner being away rather than working.
IDLE_CEILING_DEFAULT_SECONDS = 180
IDLE_CEILING_MIN_SECONDS = 60
IDLE_CEILING_MAX_SECONDS = 240
#: How much slower than the plan a genuinely engaged learner may be.
IDLE_CEILING_FACTOR = 3


# --------------------------------------------------------------------------
# Payload discipline
# --------------------------------------------------------------------------

class _Rejected(Exception):
    """A metadata value that is not allowed to be stored."""


_SLUG_RE = re.compile(r"^[A-Za-z0-9_.:@/+-]{1,64}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TZ_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_+-]*(?:/[A-Za-z0-9_+-]+){0,2}$")

#: Numeric client-side diagnostics. Never used for ``active_seconds``.
_CLIENT_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "foreground_ms",
        "background_ms",
        "idle_ms",
        "playback_ms",
        "network_ms",
        "render_ms",
        "input_ms",
    }
)


def _slug(value: Any) -> str:
    text = str(value)
    if not _SLUG_RE.match(text):
        raise _Rejected("not a slug")
    return text


def _enum_of(*allowed: str):
    permitted = frozenset(allowed)

    def check(value: Any) -> str:
        text = str(value)
        if text not in permitted:
            raise _Rejected("not an allowed value")
        return text

    return check


def _int_between(low: int, high: int):
    def check(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _Rejected("not a number")
        number = int(value)
        if number < low or number > high:
            raise _Rejected("out of range")
        return number

    return check


def _float_between(low: float, high: float):
    def check(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _Rejected("not a number")
        number = round(float(value), 6)
        if number < low or number > high:
            raise _Rejected("out of range")
        return number

    return check


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise _Rejected("not a boolean")
    return value


def _local_date(value: Any) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    text = str(value)
    if not _DATE_RE.match(text):
        raise _Rejected("not a YYYY-MM-DD date")
    return text


def _timezone_name(value: Any) -> str:
    text = str(value)
    if len(text) > 64 or not _TZ_RE.match(text):
        raise _Rejected("not an IANA zone")
    return text


def _client_metrics(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise _Rejected("client diagnostics must be an object")
    clean: dict[str, float] = {}
    for key, raw in value.items():
        if key not in _CLIENT_METRIC_KEYS:
            continue
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        number = float(raw)
        if 0 <= number <= 24 * 60 * 60 * 1000:
            clean[key] = round(number, 3)
    if not clean:
        raise _Rejected("no usable client metric")
    return clean


_ONE_DAY_MS = 24 * 60 * 60 * 1000

#: The complete allow-list. A key that is not here is dropped and only its
#: *name* is recorded, so telemetry cannot become a second answer transcript.
_FIELD_RULES: dict[str, Any] = {
    # identities
    "journey_id": _slug,
    "step_id": _slug,
    "learning_session_id": _slug,
    "serial_thread_id": _slug,
    "serial_episode_id": _slug,
    "evidence_ref": _slug,
    "collectible_id": _slug,
    "mutation_scope": _slug,
    # cost references — the amount itself rides on PilotEvent.cost_usd
    "cost_ref": _slug,
    "cost_usd": _float_between(0.0, 1000.0),
    "cost_known": _bool,
    # closed vocabularies
    "scenario_key": _enum_of(*[str(key) for key in CapabilityKey]),
    "step_kind": _enum_of(*[str(kind) for kind in StepKind]),
    "step_status": _enum_of(*[str(status) for status in StepStatus]),
    "journey_status": _enum_of(*[str(status) for status in JourneyStatus]),
    "input_mode": _enum_of(*[str(mode) for mode in InputMode]),
    "modality": _enum_of(*[str(mode) for mode in InputMode]),
    "assistance": _enum_of(*[str(level) for level in AssistanceLevel]),
    "outcome": _enum_of(*[str(outcome) for outcome in TaskOutcome]),
    "evidence_kind": _enum_of(*[str(kind) for kind in EvidenceKind]),
    "help_kind": _enum_of(*[str(kind) for kind in HelpKind]),
    "finish_kind": _enum_of("complete", "early"),
    "reply_source": _enum_of("model", "authored", "none"),
    "control_language": _enum_of("en", "de", "fr"),
    "level_band": _enum_of("A1", "A2", "B1", "B2", "C1", "C2"),
    "conflict_kind": _enum_of(
        "version_conflict",
        "idempotency_conflict",
        "step_not_active",
        "journey_not_active",
        "already_finished",
        "expired_claim",
    ),
    # short machine-readable slugs, never free text
    "content_version": _slug,
    "provider": _slug,
    "model": _slug,
    "prompt_version": _slug,
    "reason": _slug,
    "failure_reason": _slug,
    "unavailable_reason": _slug,
    # numbers
    "ordinal": _int_between(0, 64),
    "step_count": _int_between(0, 64),
    "turn_index": _int_between(0, 32),
    "revision": _int_between(0, 1_000_000),
    "expected_revision": _int_between(0, 1_000_000),
    "current_revision": _int_between(0, 1_000_000),
    "attempt": _int_between(0, 64),
    "generation_attempts": _int_between(0, 64),
    "budget_seconds": _int_between(0, 86_400),
    "estimated_seconds": _int_between(0, 86_400),
    "estimated_active_seconds": _int_between(0, 86_400),
    "provider_wait_ms": _float_between(0.0, float(_ONE_DAY_MS)),
    "retry_after_seconds": _int_between(0, 86_400),
    # booleans
    "optional": _bool,
    "pending": _bool,
    "retry_allowed": _bool,
    "authored_fallback": _bool,
    "voice_available": _bool,
    # day attribution
    "local_date": _local_date,
    "timezone": _timezone_name,
    # diagnostics only
    "client": _client_metrics,
}

#: Reserved payload keys this module owns; a caller cannot overwrite them.
_RESERVED_KEYS: frozenset[str] = frozenset(
    {
        "schema_version",
        "event",
        "source_key",
        "dedup_key",
        "repeats",
        "last_repeat_at",
        "dropped_metadata_keys",
    }
)


def sanitize_metadata(metadata: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Return ``(clean, dropped_key_names)``.

    Only key *names* are reported back; a rejected value is never echoed
    anywhere, which is what keeps a learner's answer out of the ledger even when
    a producer passes it by mistake.
    """

    clean: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in sorted((metadata or {}).items()):
        name = str(key)
        if name in _RESERVED_KEYS:
            dropped.append(name)
            continue
        rule = _FIELD_RULES.get(name)
        if rule is None or value is None:
            if value is not None:
                dropped.append(name)
            continue
        try:
            clean[name] = rule(value)
        except _Rejected:
            dropped.append(name)
    return clean, dropped[:16]


# --------------------------------------------------------------------------
# Deduplication
# --------------------------------------------------------------------------

#: Extra payload fields that make two events with the same source key genuinely
#: different observations. Everything not listed collapses onto the source key,
#: which is exactly what stops a retried completion becoming a second one.
_DEDUP_DISCRIMINATORS: dict[str, tuple[str, ...]] = {
    str(JourneyEventName.CREATED): (),
    str(JourneyEventName.STARTED): (),
    str(JourneyEventName.COMPLETED): (),
    str(JourneyEventName.ENDED_EARLY): (),
    str(JourneyEventName.STEP_COMPLETED): ("step_id",),
    str(JourneyEventName.HELP_USED): ("step_id", "help_kind"),
    str(JourneyEventName.PAUSED): ("revision",),
    str(JourneyEventName.GENERATION_FALLBACK): ("scenario_key", "attempt", "revision"),
    str(JourneyEventName.PROVIDER_FAILED): (
        "scenario_key",
        "provider",
        "attempt",
        "revision",
    ),
    str(JourneyEventName.RESUME_CONFLICT): (
        "conflict_kind",
        "expected_revision",
        "revision",
    ),
}


def dedup_key(event_name: str, source_key: str, payload: dict[str, Any]) -> str:
    """The canonical identity of one observation.

    Built from the frozen source key plus the fields that legitimately separate
    two occurrences (a different step, a different help kind, a later revision).
    """

    parts = [source_key or f"journey:unknown:{event_name}"]
    for name in _DEDUP_DISCRIMINATORS.get(event_name, ()):
        parts.append(f"{name}={payload.get(name, '')}")
    return "|".join(parts)


def _pending_journey_events(db: Session) -> list[PilotEvent]:
    """Events added to this session but not yet flushed.

    Read without forcing a flush: telemetry must never push half-built domain
    state to the database as a side effect.
    """

    return [obj for obj in db.new if isinstance(obj, PilotEvent)]


def _find_existing(
    db: Session, *, event_name: str, entity_id: str | None, key: str
) -> PilotEvent | None:
    for candidate in _pending_journey_events(db):
        if (
            candidate.event_type == event_name
            and (candidate.payload or {}).get("dedup_key") == key
        ):
            return candidate
    with db.no_autoflush:
        query = db.query(PilotEvent).filter(PilotEvent.event_type == event_name)
        if entity_id is not None:
            query = query.filter(PilotEvent.entity_id == entity_id)
        # The candidate set is a handful of rows per journey per event name, so
        # comparing the key in Python keeps this portable across PostgreSQL and
        # the SQLite test configuration.
        for row in query.order_by(PilotEvent.occurred_at).all():
            if (row.payload or {}).get("dedup_key") == key:
                return row
    return None


def _journey_id_from_source_key(source_key: str) -> str | None:
    parts = (source_key or "").split(":")
    if len(parts) >= 3 and parts[0] == "journey" and parts[1]:
        return parts[1]
    return None


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------
# The frozen callable (CONTRACTS §6, WP-11)
# --------------------------------------------------------------------------

def record_journey_event(
    db: Session,
    *,
    event_name: str,
    user_id: UUID | None,
    source_key: str,
    metadata: dict[str, Any] | None = None,
) -> PilotEvent | None:
    """Record one journey event through the existing pilot ledger.

    Writes with ``db.add`` / ``db.flush`` only — **the caller owns the
    transaction** and this function never commits.

    Returns the stored :class:`PilotEvent`. When the same canonical observation
    is recorded again the *existing* row is returned with its ``repeats``
    counter incremented; no second row is created. Returns ``None`` only when
    the event cannot honestly be recorded (an unfrozen event name).
    """

    name = str(event_name)
    if name not in JOURNEY_EVENT_NAMES:
        logger.warning(
            "journey_events: refusing unknown event name %r (not one of the ten frozen names)",
            name,
        )
        return None

    clean, dropped = sanitize_metadata(metadata)
    journey_id = clean.get("journey_id") or _journey_id_from_source_key(source_key)
    if journey_id and "journey_id" not in clean:
        clean["journey_id"] = journey_id
    entity_id = journey_id or clean.get("scenario_key")

    key = dedup_key(name, source_key, clean)
    existing = _find_existing(db, event_name=name, entity_id=entity_id, key=key)
    if existing is not None:
        payload = dict(existing.payload or {})
        payload["repeats"] = int(payload.get("repeats", 0)) + 1
        payload["last_repeat_at"] = _utcnow().isoformat()
        # Reassignment (not mutation) so the JSON column is marked dirty.
        existing.payload = payload
        return existing

    cost_usd = clean.get("cost_usd")
    payload = {
        "schema_version": JOURNEY_EVENT_SCHEMA_VERSION,
        "event": name,
        "source_key": source_key,
        "dedup_key": key,
        # A cost of 0.0 on the row is ambiguous, so the payload states whether a
        # cost was actually known. The digest never counts unknown as zero.
        "cost_known": bool(clean.get("cost_known", cost_usd is not None)),
        **clean,
    }
    if dropped:
        payload["dropped_metadata_keys"] = dropped

    from app.services.pilot_events import PilotEventService  # local: avoids a cycle

    return PilotEventService(db).record(
        name,
        user_id=user_id,
        entity_type=JOURNEY_ENTITY_TYPE,
        entity_id=entity_id,
        payload=payload,
        cost_usd=float(cost_usd or 0.0),
        # An explicit instant, not the transaction's ``now()``: in PostgreSQL
        # every row written inside one transaction shares ``func.now()``, which
        # would collapse the very intervals this package exists to measure.
        occurred_at=_utcnow(),
    )


# --------------------------------------------------------------------------
# Typed constructors for the producers
# --------------------------------------------------------------------------

def journey_event_metadata(journey: Any, **extra: Any) -> dict[str, Any]:
    """Build the standard payload fields from a journey row.

    Duck-typed on purpose: WP-11 does not import WP-02's ORM model.
    """

    metadata: dict[str, Any] = {}
    for attribute, key in (
        ("id", "journey_id"),
        ("timezone", "timezone"),
        ("local_date", "local_date"),
        ("level_band", "level_band"),
        ("content_version", "content_version"),
        ("budget_seconds", "budget_seconds"),
        ("estimated_active_seconds", "estimated_active_seconds"),
        ("revision", "revision"),
        ("status", "journey_status"),
    ):
        value = getattr(journey, attribute, None)
        if value is not None and value != "":
            metadata[key] = str(value) if attribute == "id" else value
    scenario = getattr(journey, "scenario_snapshot", None) or {}
    if isinstance(scenario, dict):
        for key in ("scenario_key", "content_version", "level_band"):
            value = scenario.get(key)
            if value and key not in metadata:
                metadata[key] = value
    metadata.update(extra)
    return metadata


def record_generation_fallback(
    db: Session,
    *,
    user_id: UUID | None,
    journey_id: UUID | str | None,
    reason: str,
    scenario_key: str | None = None,
    provider: str | None = None,
    provider_wait_ms: float | None = None,
    attempt: int | None = None,
    **extra: Any,
) -> PilotEvent | None:
    """An authored fallback was served instead of generated content."""

    return _record_named(
        db,
        JourneyEventName.GENERATION_FALLBACK,
        user_id=user_id,
        journey_id=journey_id,
        metadata={
            "reason": reason,
            "scenario_key": scenario_key,
            "provider": provider,
            "provider_wait_ms": provider_wait_ms,
            "attempt": attempt,
            "authored_fallback": True,
            **extra,
        },
    )


def record_provider_failed(
    db: Session,
    *,
    user_id: UUID | None,
    journey_id: UUID | str | None,
    provider: str,
    failure_reason: str,
    scenario_key: str | None = None,
    provider_wait_ms: float | None = None,
    attempt: int | None = None,
    **extra: Any,
) -> PilotEvent | None:
    """A model or network call failed. This is infrastructure, not a learner error."""

    return _record_named(
        db,
        JourneyEventName.PROVIDER_FAILED,
        user_id=user_id,
        journey_id=journey_id,
        metadata={
            "provider": provider,
            "failure_reason": failure_reason,
            "scenario_key": scenario_key,
            "provider_wait_ms": provider_wait_ms,
            "attempt": attempt,
            **extra,
        },
    )


def record_resume_conflict(
    db: Session,
    *,
    user_id: UUID | None,
    journey_id: UUID | str | None,
    conflict_kind: str,
    expected_revision: int | None = None,
    current_revision: int | None = None,
    **extra: Any,
) -> PilotEvent | None:
    """A client came back to a journey holding a stale view of it."""

    return _record_named(
        db,
        JourneyEventName.RESUME_CONFLICT,
        user_id=user_id,
        journey_id=journey_id,
        metadata={
            "conflict_kind": conflict_kind,
            "expected_revision": expected_revision,
            "current_revision": current_revision,
            **extra,
        },
    )


def _record_named(
    db: Session,
    event_name: JourneyEventName,
    *,
    user_id: UUID | None,
    journey_id: UUID | str | None,
    metadata: dict[str, Any],
) -> PilotEvent | None:
    payload = {key: value for key, value in metadata.items() if value is not None}
    if journey_id is not None:
        payload["journey_id"] = str(journey_id)
    source_key = effect_source_key(
        journey_id=journey_id if journey_id is not None else "unknown",
        effect=str(event_name),
    )
    return record_journey_event(
        db,
        event_name=str(event_name),
        user_id=user_id,
        source_key=source_key,
        metadata=payload,
    )


class ProviderWait:
    """Elapsed provider/network time for one call, in milliseconds."""

    __slots__ = ("_started", "_elapsed_ms")

    def __init__(self) -> None:
        self._started = time.monotonic()
        self._elapsed_ms = 0.0

    @property
    def elapsed_ms(self) -> float:
        return round(self._elapsed_ms, 3)

    def _stop(self) -> None:
        self._elapsed_ms = (time.monotonic() - self._started) * 1000.0


@contextmanager
def provider_timer() -> Iterator[ProviderWait]:
    """Time a provider call so its wait is reported apart from learner time.

    ``with provider_timer() as wait: ...`` then pass ``wait.elapsed_ms`` as
    ``provider_wait_ms`` on the event that closes the interval.
    """

    wait = ProviderWait()
    try:
        yield wait
    finally:
        wait._stop()


# --------------------------------------------------------------------------
# Duration measurement (CONTRACTS §9)
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class JourneyDuration:
    """What was actually measured for one journey. Nothing here is an estimate."""

    journey_id: str
    active_seconds: int | None
    measurable: bool
    reason: str | None = None
    events: int = 0
    counted_segments: int = 0
    idle_excluded_seconds: int = 0
    away_excluded_seconds: int = 0
    provider_wait_seconds: float = 0.0
    preparation_wait_seconds: float = 0.0
    skewed_segments: int = 0
    #: Client-reported timings. Diagnostic only; never used above.
    client_reported: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "journey_id": self.journey_id,
            "active_seconds": self.active_seconds,
            "measurable": self.measurable,
            "reason": self.reason,
            "events": self.events,
            "counted_segments": self.counted_segments,
            "idle_excluded_seconds": self.idle_excluded_seconds,
            "away_excluded_seconds": self.away_excluded_seconds,
            "provider_wait_seconds": round(self.provider_wait_seconds, 3),
            "preparation_wait_seconds": round(self.preparation_wait_seconds, 3),
            "skewed_segments": self.skewed_segments,
            "client_reported": dict(self.client_reported),
        }


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat those as UTC."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _segment_ceiling(payload: dict[str, Any]) -> int:
    estimate = payload.get("estimated_seconds")
    if isinstance(estimate, (int, float)) and not isinstance(estimate, bool) and estimate > 0:
        scaled = int(estimate) * IDLE_CEILING_FACTOR
        return max(IDLE_CEILING_MIN_SECONDS, min(IDLE_CEILING_MAX_SECONDS, scaled))
    return IDLE_CEILING_DEFAULT_SECONDS


def _provider_wait_seconds(payload: dict[str, Any]) -> float:
    value = payload.get("provider_wait_ms")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value) / 1000.0
    return 0.0


def journey_events_for(db: Session, journey_id: UUID | str) -> list[PilotEvent]:
    """Every stored event for one journey, oldest first."""

    identifier = str(journey_id)
    with db.no_autoflush:
        rows = (
            db.query(PilotEvent)
            .filter(
                PilotEvent.entity_type == JOURNEY_ENTITY_TYPE,
                PilotEvent.entity_id == identifier,
                PilotEvent.event_type.in_(sorted(JOURNEY_EVENT_NAMES)),
            )
            .all()
        )
    pending = [
        row
        for row in _pending_journey_events(db)
        if row.entity_type == JOURNEY_ENTITY_TYPE and row.entity_id == identifier
    ]
    seen = {id(row) for row in rows}
    rows.extend(row for row in pending if id(row) not in seen)
    return sorted(rows, key=lambda row: (_aware(row.occurred_at) or datetime.min.replace(tzinfo=UTC)))


def measure_journey_duration(
    db: Session,
    *,
    journey_id: UUID | str,
    until: datetime | None = None,
) -> JourneyDuration:
    """Reconstruct active time for one journey from the server's own timestamps.

    Rules, in order:

    * The clock starts at ``journey_started`` (or ``journey_created`` when the
      journey never started). Time spent generating the plan is
      ``preparation_wait_seconds``, not learner time.
    * A segment that opens with ``journey_paused`` is time away and is excluded
      in full.
    * Provider waiting declared on the closing event is subtracted from the
      segment and reported separately, so a slow model is never billed to the
      learner.
    * Whatever remains is capped at three times the step's own estimate; the
      excess is idle time and is excluded.
    * ``until`` closes the final open segment (the finish instant), under the
      same rules. An ``until`` that predates the last event is counted as a
      skewed boundary and contributes nothing.

    When no segment survives, ``active_seconds`` is ``None`` — never the plan's
    estimate, never zero-as-a-guess.
    """

    identifier = str(journey_id)
    events = journey_events_for(db, identifier)
    client_totals: Counter[str] = Counter()
    for event in events:
        reported = (event.payload or {}).get("client")
        if isinstance(reported, dict):
            for key, value in reported.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    client_totals[key] += float(value)
    client_reported = {key: round(value, 3) for key, value in sorted(client_totals.items())}

    if not events:
        return JourneyDuration(
            journey_id=identifier,
            active_seconds=None,
            measurable=False,
            reason="no_events",
            client_reported=client_reported,
        )

    started_at: datetime | None = None
    created_at: datetime | None = None
    anchor_index: int | None = None
    for index, event in enumerate(events):
        moment = _aware(event.occurred_at)
        if event.event_type == str(JourneyEventName.CREATED) and created_at is None:
            created_at = moment
        if event.event_type == str(JourneyEventName.STARTED) and started_at is None:
            started_at = moment
            anchor_index = index
    # A journey that never started has no active time to report. Counting the
    # wait between ``created`` and an abandoned generation as study time would
    # be exactly the dishonesty CONTRACTS §9 forbids.
    preparation = 0.0
    if created_at is not None and started_at is not None:
        preparation = max(0.0, (started_at - created_at).total_seconds())

    if anchor_index is None:
        return JourneyDuration(
            journey_id=identifier,
            active_seconds=None,
            measurable=False,
            reason="no_start_event",
            events=len(events),
            preparation_wait_seconds=preparation,
            client_reported=client_reported,
        )

    active = 0.0
    idle = 0.0
    away = 0.0
    provider_wait = 0.0
    counted = 0
    skewed = 0

    previous = events[anchor_index]
    for event in events[anchor_index + 1 :]:
        previous_at = _aware(previous.occurred_at)
        current_at = _aware(event.occurred_at)
        if previous_at is None or current_at is None:
            previous = event
            continue
        # Events are ordered by their instant, so insertion order cannot distort
        # an interval; ``max`` only guards against a pathological stored value.
        gap = max(0.0, (current_at - previous_at).total_seconds())
        payload = event.payload or {}
        if previous.event_type == str(JourneyEventName.PAUSED):
            away += gap
            previous = event
            continue
        wait = min(_provider_wait_seconds(payload), gap)
        provider_wait += wait
        working = gap - wait
        ceiling = _segment_ceiling(payload)
        if working > ceiling:
            idle += working - ceiling
            working = float(ceiling)
        active += working
        counted += 1
        previous = event

    boundary = _aware(until)
    if boundary is not None and previous.event_type not in TERMINAL_EVENT_NAMES:
        previous_at = _aware(previous.occurred_at)
        if previous_at is not None:
            gap = (boundary - previous_at).total_seconds()
            if gap < 0:
                skewed += 1
            elif previous.event_type == str(JourneyEventName.PAUSED):
                away += gap
            else:
                ceiling = IDLE_CEILING_DEFAULT_SECONDS
                working = gap
                if working > ceiling:
                    idle += working - ceiling
                    working = float(ceiling)
                active += working
                counted += 1

    if counted == 0:
        return JourneyDuration(
            journey_id=identifier,
            active_seconds=None,
            measurable=False,
            reason="no_measurable_segment",
            events=len(events),
            idle_excluded_seconds=int(round(idle)),
            away_excluded_seconds=int(round(away)),
            provider_wait_seconds=provider_wait,
            preparation_wait_seconds=preparation,
            skewed_segments=skewed,
            client_reported=client_reported,
        )

    return JourneyDuration(
        journey_id=identifier,
        active_seconds=int(round(active)),
        measurable=True,
        events=len(events),
        counted_segments=counted,
        idle_excluded_seconds=int(round(idle)),
        away_excluded_seconds=int(round(away)),
        provider_wait_seconds=provider_wait,
        preparation_wait_seconds=preparation,
        skewed_segments=skewed,
        client_reported=client_reported,
    )


def measure_journey_active_seconds(
    db: Session,
    *,
    journey_id: UUID | str,
    until: datetime | None = None,
) -> int | None:
    """``JourneyRecap.active_seconds``: measured, or ``None`` when unmeasurable."""

    return measure_journey_duration(db, journey_id=journey_id, until=until).active_seconds


# --------------------------------------------------------------------------
# Daily digest
# --------------------------------------------------------------------------

def _percentile(values: list[int], fraction: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1)))))
    return ordered[index]


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _event_local_date(event: PilotEvent) -> tuple[date | None, bool]:
    """The learner-local date of the event, in the journey's own IANA snapshot."""

    moment = _aware(event.occurred_at)
    if moment is None:
        return None, False
    zone_name = (event.payload or {}).get("timezone")
    if isinstance(zone_name, str) and zone_name:
        try:
            return moment.astimezone(ZoneInfo(zone_name)).date(), True
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            pass
    return moment.astimezone(ZoneInfo(FALLBACK_TIMEZONE)).date(), False


def journey_daily_rollup(
    db: Session,
    day: date,
    *,
    user_id: UUID | str | None = None,
) -> dict[str, Any]:
    """One learner-day of daily-journey observability.

    Every rate states its denominator, and a day with too few journeys is
    reported as ``insufficient_data`` rather than as a precise-looking number.
    Unknown cost is reported as unknown; it is never summed as zero.
    """

    # Widen the UTC window past every possible offset, then attribute each event
    # in the journey's own zone rather than the server's.
    window_start = datetime.combine(day - timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    window_end = datetime.combine(day + timedelta(days=2), datetime.min.time(), tzinfo=UTC)
    with db.no_autoflush:
        query = db.query(PilotEvent).filter(
            PilotEvent.event_type.in_(sorted(JOURNEY_EVENT_NAMES)),
            PilotEvent.occurred_at >= window_start,
            PilotEvent.occurred_at < window_end,
        )
        if user_id:
            query = query.filter(PilotEvent.user_id == UUID(str(user_id)))
        candidates = query.order_by(PilotEvent.occurred_at).all()

    events: list[PilotEvent] = []
    fallback_zone_events = 0
    for event in candidates:
        local, from_snapshot = _event_local_date(event)
        if local != day:
            continue
        events.append(event)
        if not from_snapshot:
            fallback_zone_events += 1

    by_name: Counter[str] = Counter()
    journeys_by_name: dict[str, set[str]] = defaultdict(set)
    learners: set[str] = set()
    unattributed_learner_events = 0
    retries = 0
    help_by_kind: Counter[str] = Counter()
    journeys_using_help: set[str] = set()
    steps_by_kind: Counter[str] = Counter()
    steps_by_ordinal: Counter[int] = Counter()
    steps_with_unknown_ordinal = 0
    steps_per_journey: Counter[str] = Counter()
    provider_waits_ms: list[float] = []
    known_cost_events = 0
    unknown_cost_events = 0
    known_cost_usd = 0.0
    all_journeys: set[str] = set()
    content_only_events = 0

    for event in events:
        payload = event.payload or {}
        name = event.event_type
        by_name[name] += 1
        retries += int(payload.get("repeats", 0) or 0)
        if event.user_id is None:
            unattributed_learner_events += 1
        else:
            learners.add(str(event.user_id))
        journey_id = payload.get("journey_id") or (
            event.entity_id if event.entity_type == JOURNEY_ENTITY_TYPE else None
        )
        if journey_id:
            all_journeys.add(str(journey_id))
            journeys_by_name[name].add(str(journey_id))
        else:
            content_only_events += 1
        if payload.get("cost_known") is True:
            known_cost_events += 1
            known_cost_usd += float(event.cost_usd or 0.0)
        else:
            unknown_cost_events += 1
        wait = payload.get("provider_wait_ms")
        if isinstance(wait, (int, float)) and not isinstance(wait, bool) and wait >= 0:
            provider_waits_ms.append(float(wait))
        if name == str(JourneyEventName.HELP_USED):
            help_by_kind[str(payload.get("help_kind") or "unknown")] += 1
            if journey_id:
                journeys_using_help.add(str(journey_id))
        if name == str(JourneyEventName.STEP_COMPLETED):
            kind = payload.get("step_kind")
            steps_by_kind[str(kind) if kind else "unknown"] += 1
            ordinal = payload.get("ordinal")
            if isinstance(ordinal, int) and not isinstance(ordinal, bool):
                steps_by_ordinal[ordinal] += 1
            else:
                steps_with_unknown_ordinal += 1
            if journey_id:
                steps_per_journey[str(journey_id)] += 1

    created = len(journeys_by_name[str(JourneyEventName.CREATED)])
    started = len(journeys_by_name[str(JourneyEventName.STARTED)])
    completed = len(journeys_by_name[str(JourneyEventName.COMPLETED)])
    ended_early = len(journeys_by_name[str(JourneyEventName.ENDED_EARLY)])
    finished = completed + ended_early
    still_open = max(0, started - finished)

    durations: list[int] = []
    unmeasurable = 0
    away_total = 0
    idle_total = 0
    preparation_total = 0.0
    for journey_id in sorted(
        journeys_by_name[str(JourneyEventName.COMPLETED)]
        | journeys_by_name[str(JourneyEventName.ENDED_EARLY)]
    ):
        measurement = measure_journey_duration(db, journey_id=journey_id)
        if measurement.active_seconds is None:
            unmeasurable += 1
        else:
            durations.append(measurement.active_seconds)
        idle_total += measurement.idle_excluded_seconds
        away_total += measurement.away_excluded_seconds
        preparation_total += measurement.preparation_wait_seconds

    insufficient = started < MIN_DIGEST_SAMPLE
    drop_off = [
        {
            "ordinal": ordinal,
            "journeys_completing_step": steps_by_ordinal[ordinal],
            "share_of_started": _rate(steps_by_ordinal[ordinal], started),
        }
        for ordinal in sorted(steps_by_ordinal)
    ]

    return {
        "day": day.isoformat(),
        "schema_version": JOURNEY_EVENT_SCHEMA_VERSION,
        "attribution": {
            "basis": "journey-local IANA snapshot",
            "events_attributed_by_fallback_zone": fallback_zone_events,
            "fallback_zone": FALLBACK_TIMEZONE,
        },
        "sample": {
            "journeys": len(all_journeys),
            "learners": len(learners),
            "events": len(events),
            "events_without_a_learner": unattributed_learner_events,
            "events_without_a_journey": content_only_events,
            "minimum_for_rates": MIN_DIGEST_SAMPLE,
            "insufficient_data": insufficient,
        },
        "funnel": {
            "denominator": started,
            "created": created,
            "started": started,
            "completed": completed,
            "ended_early": ended_early,
            "still_open": still_open,
            "completion_rate": None if insufficient else _rate(completed, started),
            "early_stop_rate": None if insufficient else _rate(ended_early, started),
        },
        "step_drop_off": {
            "denominator": started,
            "by_ordinal": drop_off,
            "by_kind": dict(sorted(steps_by_kind.items())),
            "steps_with_unknown_ordinal": steps_with_unknown_ordinal,
            "median_steps_per_journey": _percentile(
                sorted(steps_per_journey.values()), 0.5
            ),
        },
        "help": {
            "denominator": started,
            "events": by_name[str(JourneyEventName.HELP_USED)],
            "journeys_using_help": len(journeys_using_help),
            "by_kind": dict(sorted(help_by_kind.items())),
            "share_of_journeys": None if insufficient else _rate(len(journeys_using_help), started),
        },
        "active_duration": {
            "denominator": finished,
            "measured": len(durations),
            "unmeasurable": unmeasurable,
            "seconds": {
                "min": min(durations) if durations else None,
                "p50": _percentile(durations, 0.5),
                "p90": _percentile(durations, 0.9),
                "max": max(durations) if durations else None,
            },
            "idle_excluded_seconds": idle_total,
            "away_excluded_seconds": away_total,
            "note": "server-measured; client timings are diagnostic and excluded",
        },
        "provider_wait": {
            "events_with_measurement": len(provider_waits_ms),
            "events_without_measurement": len(events) - len(provider_waits_ms),
            "total_seconds": round(sum(provider_waits_ms) / 1000.0, 3),
            "median_ms": _percentile([int(round(value)) for value in provider_waits_ms], 0.5),
            "max_ms": int(round(max(provider_waits_ms))) if provider_waits_ms else None,
            "preparation_seconds": round(preparation_total, 3),
        },
        "reliability": {
            "denominator": created,
            "duplicate_requests_collapsed": retries,
            "generation_fallbacks": by_name[str(JourneyEventName.GENERATION_FALLBACK)],
            "provider_failures": by_name[str(JourneyEventName.PROVIDER_FAILED)],
            "resume_conflicts": by_name[str(JourneyEventName.RESUME_CONFLICT)],
            "fallback_rate": None if insufficient else _rate(
                by_name[str(JourneyEventName.GENERATION_FALLBACK)], max(created, 1)
            ),
        },
        "cost": {
            "currency": "USD",
            "events_with_known_cost": known_cost_events,
            "events_with_unknown_cost": unknown_cost_events,
            "known_cost_usd": round(known_cost_usd, 6),
            "coverage": _rate(known_cost_events, known_cost_events + unknown_cost_events),
            "note": "unknown cost is unknown, not zero",
        },
        "events": dict(sorted(by_name.items())),
    }


def format_journey_digest(section: dict[str, Any]) -> list[str]:
    """Render the journey section as digest lines. Denominators are never hidden."""

    sample = section["sample"]
    funnel = section["funnel"]
    duration = section["active_duration"]
    provider = section["provider_wait"]
    reliability = section["reliability"]
    cost = section["cost"]
    lines = [
        f"Daily journey · {section['day']} · "
        f"journeys {sample['journeys']} · learners {sample['learners']} · events {sample['events']}",
    ]
    if sample["insufficient_data"]:
        lines.append(
            f"  INSUFFICIENT DATA: {funnel['started']} started journeys, "
            f"{sample['minimum_for_rates']} needed before rates are reported. Counts below are raw."
        )

    def pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value * 100:.0f}%"

    lines.append(
        f"  Funnel (n={funnel['denominator']} started): created {funnel['created']} · "
        f"started {funnel['started']} · completed {funnel['completed']} ({pct(funnel['completion_rate'])}) · "
        f"early {funnel['ended_early']} ({pct(funnel['early_stop_rate'])}) · open {funnel['still_open']}"
    )
    drop = section["step_drop_off"]
    reached = ", ".join(
        f"#{row['ordinal']}:{row['journeys_completing_step']}" for row in drop["by_ordinal"]
    ) or "no ordinals recorded"
    kinds = ", ".join(f"{name}:{count}" for name, count in drop["by_kind"].items()) or "none"
    lines.append(f"  Steps completed by ordinal (n={drop['denominator']}): {reached}; by kind: {kinds}")
    help_section = section["help"]
    help_kinds = ", ".join(
        f"{name}:{count}" for name, count in help_section["by_kind"].items()
    ) or "none"
    lines.append(
        f"  Help (n={help_section['denominator']} started): {help_section['events']} uses in "
        f"{help_section['journeys_using_help']} journeys ({pct(help_section['share_of_journeys'])}); {help_kinds}"
    )
    seconds = duration["seconds"]
    if duration["measured"]:
        lines.append(
            f"  Active seconds (measured {duration['measured']}/{duration['denominator']} finished, "
            f"{duration['unmeasurable']} unmeasurable): min {seconds['min']} · p50 {seconds['p50']} · "
            f"p90 {seconds['p90']} · max {seconds['max']} "
            f"[idle excluded {duration['idle_excluded_seconds']}s, away {duration['away_excluded_seconds']}s]"
        )
    else:
        lines.append(
            f"  Active seconds: none measurable "
            f"({duration['unmeasurable']}/{duration['denominator']} finished journeys); reported as unknown, not zero"
        )
    measured_events = provider["events_with_measurement"]
    all_events = measured_events + provider["events_without_measurement"]
    lines.append(
        f"  Provider wait: {measured_events} of {all_events} events carry a measurement · "
        f"total {provider['total_seconds']}s · median {provider['median_ms']}ms · "
        f"plan preparation {provider['preparation_seconds']}s"
    )
    lines.append(
        f"  Reliability (n={reliability['denominator']} created): retries collapsed "
        f"{reliability['duplicate_requests_collapsed']} · fallbacks {reliability['generation_fallbacks']} "
        f"({pct(reliability['fallback_rate'])}) · provider failures {reliability['provider_failures']} · "
        f"resume conflicts {reliability['resume_conflicts']}"
    )
    lines.append(
        f"  Cost coverage: {cost['events_with_known_cost']} known / "
        f"{cost['events_with_unknown_cost']} unknown ({pct(cost['coverage'])}) · "
        f"known ${cost['known_cost_usd']:.4f} · unknown is not zero"
    )
    attribution = section["attribution"]
    if attribution["events_attributed_by_fallback_zone"]:
        lines.append(
            f"  Attribution: {attribution['events_attributed_by_fallback_zone']} events had no journey "
            f"timezone snapshot and fell back to {attribution['fallback_zone']}"
        )
    return lines


__all__ = [
    "CONTENT_ENTITY_TYPE",
    "IDLE_CEILING_DEFAULT_SECONDS",
    "JOURNEY_ENTITY_TYPE",
    "JOURNEY_EVENT_NAMES",
    "JOURNEY_EVENT_SCHEMA_VERSION",
    "MIN_DIGEST_SAMPLE",
    "JourneyDuration",
    "ProviderWait",
    "dedup_key",
    "format_journey_digest",
    "journey_daily_rollup",
    "journey_event_metadata",
    "journey_events_for",
    "measure_journey_active_seconds",
    "measure_journey_duration",
    "provider_timer",
    "record_generation_fallback",
    "record_journey_event",
    "record_provider_failed",
    "record_resume_conflict",
    "sanitize_metadata",
]
