"""Phase 2 «Folge in Akten» — the night writes the acts after the day's first.

The prefetch beat writes a learner's page for tomorrow, as it always has: that page is
the day's first act («Le fil»). With ``ATELIER_STORY_ACTS`` on for the learner, the night
then writes the acts after it — «Le soir» on Soutenu and Intensif, «À côté» on Intensif —
as many as the learner's rhythm and measured pace can play
(``journey_planner.acts_to_write``). Each act is one queued task (``write_story_acts``),
so no task runs longer than a page does today, and each is written against the first act
alone: «Le soir» first, because «À côté» is never played without it.

An act is stored like the page: an append-only row on the pilot ledger, under the day's
key (the first act's cache key), with the act's brief. It is billed when it is served or,
unserved, when it expires (``journey_latency.sweep_expired_prefetches``), like the page.
Every guard is checked before a cent is spent: the switch and its cohort, the first act
still waiting and still current, the act still planned for the learner's rhythm, the
learner's week (with what the night has written and not yet billed) and the service's
day. A later act the writer cannot get past its guards and the critic is dropped, never
replaced by anything weaker.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services.journey_contracts import ACT_DROP_ORDER, ActRole, ScenarioBrief

#: One row per written act, beside the page's ``journey_scene_prefetched`` row.
ACT_PREFETCH_EVENT = "journey_story_act_prefetched"
ACT_ENTITY_TYPE = "journey_story_act"
#: The order the night writes the later acts in: «Le soir» first — «À côté» is never
#: played without it, so it is only paid for once «Le soir» stands.
WRITING_ORDER: tuple[ActRole, ...] = tuple(reversed(ACT_DROP_ORDER))
#: Why a day has no act after it (``living_story.generate_act``): not a failure, the
#: day plays one act.
_ONE_ACT_DAYS = frozenset(
    {
        "act_without_a_written_page",
        "act_not_on_a_gap_day",
        "act_not_on_a_planned_day",
        "act_not_in_a_bottle",
        "act_not_in_a_two_hander",
    }
)


def acts_enabled_for(user: User) -> bool:
    """The switch, its cohort and everything the prefetch itself requires."""

    if not settings.ATELIER_STORY_ACTS:
        return False
    from app.services.journey_latency import prefetch_enabled_for

    if not prefetch_enabled_for(user):
        return False
    raw = (settings.ATELIER_STORY_ACTS_COHORT or "").strip()
    if raw == "*":
        return True
    if not raw:
        # As ATELIER_DAILY_JOURNEY_COHORT: an empty list is everyone in development and
        # nobody in production, where blanking it must never mean «every learner».
        return settings.APP_ENV.strip().lower() != "production"
    allowed = {entry.strip().lower() for entry in raw.split(",") if entry.strip()}
    return bool(allowed & {str(user.id).lower(), (user.email or "").strip().lower()})


def planned_roles(db: Session, user: User) -> tuple[ActRole, ...]:
    """The acts this learner's day can play, in play order (always «Le fil» first):
    their rhythm's ceiling, priced at their band and their measured pace once it is
    trusted (``journey_planner.acts_to_write``)."""

    from app.services.journey_events import MIN_MEASURED_PACE_DAYS, measured_pace
    from app.services.journey_planner import PacingProfile, acts_to_write
    from app.services.journey_rhythm import budget_seconds_for
    from app.services.living_story import learner_level_band

    pace = None
    try:
        measured = measured_pace(db, user_id=user.id)
    except Exception:  # pragma: no cover - a pace read never costs the night its acts
        logger.exception("story_acts: measured pace unavailable")
        measured = None
    if measured is not None and measured.days >= MIN_MEASURED_PACE_DAYS:
        pace = PacingProfile(step_multiplier=measured.step_multiplier, observations=measured.days)
    return acts_to_write(budget_seconds=budget_seconds_for(user), band=learner_level_band(user), pace=pace)


def roles_to_write(db: Session, user: User) -> list[str]:
    """The later acts the night writes for this learner, in :data:`WRITING_ORDER`."""

    planned = set(planned_roles(db, user))
    return [str(role) for role in WRITING_ORDER if role in planned]


def _first_act_row(db: Session, user: User, prefetch_id: str) -> PilotEvent | None:
    from app.services.journey_latency import PREFETCH_EVENT

    try:
        row = db.get(PilotEvent, uuid.UUID(str(prefetch_id)))
    except (TypeError, ValueError):
        return None
    if row is None or row.event_type != PREFETCH_EVENT or str(row.user_id) != str(user.id):
        return None
    return row


def _live(db: Session, rows: list[PilotEvent]) -> list[PilotEvent]:
    """The rows not yet served, discarded or expired."""

    from app.services.journey_latency import _as_aware, _consumed_ids, _ttl_floor

    floor = _ttl_floor()
    spent = _consumed_ids(db, [str(row.id) for row in rows])
    return [
        row
        for row in rows
        if str(row.id) not in spent and (_as_aware(row.occurred_at) or floor) >= floor
    ]


def act_rows(db: Session, user: User, *, prefetch_id: str) -> list[PilotEvent]:
    """The live acts written after the page ``prefetch_id``, oldest first."""

    from app.services.journey_latency import _ttl_floor

    rows = list(
        db.scalars(
            select(PilotEvent)
            .where(
                PilotEvent.event_type == ACT_PREFETCH_EVENT,
                PilotEvent.user_id == user.id,
                # Only an unexpired act can be live: the learner's older acts stay on
                # the ledger and are never read again.
                PilotEvent.occurred_at >= _ttl_floor(),
            )
            .order_by(PilotEvent.occurred_at.asc(), PilotEvent.id.asc())
            .limit(50)
        ).all()
    )
    mine = [row for row in rows if str((row.payload or {}).get("prefetch_id") or "") == str(prefetch_id)]
    return _live(db, mine)


def _unbilled_usd(db: Session, user: User | None = None, *, since: datetime | None = None) -> float:
    """What the night has written and nobody has billed yet: the live pages and acts
    (each is billed when served or when it expires). This learner's, or with no learner
    every learner's; ``since`` leaves out what was written before it."""

    from app.services.journey_latency import PREFETCH_EVENT, _ttl_floor, _usage_cost

    floor = _ttl_floor() if since is None else max(_ttl_floor(), since)
    query = select(PilotEvent).where(
        PilotEvent.event_type.in_([PREFETCH_EVENT, ACT_PREFETCH_EVENT]),
        PilotEvent.occurred_at >= floor,
    )
    if user is not None:
        query = query.where(PilotEvent.user_id == user.id)
    rows = list(db.scalars(query).all())
    return round(sum(_usage_cost(row.payload or {}) for row in _live(db, rows)), 6)


def write_act(db: Session, user: User, *, prefetch_id: str, role: str) -> str:
    """Write one later act of the day whose first act is the page ``prefetch_id``.
    Returns a status word.

    ``skipped_disabled`` — the switch or its cohort; ``skipped_stale`` — the first act
    was served, discarded or expired, or its key moved (it will never be served);
    ``cached`` — this act is already written; ``skipped_rhythm`` — the learner's rhythm
    and pace no longer play it; ``skipped_budget`` — the learner's week, counting what
    the night has written and not yet billed, or the service's day; ``skipped_day`` —
    the day plays one act (a tentpole, an épreuve, a bottle chapter …);
    ``unavailable`` — the writer or the critic refused every attempt: the act is
    dropped; ``prefetched`` — the act was written and stored.
    """

    from app.services.journey_latency import (
        _brief_codec,
        _live_prefetch_rows,
        _usage_cost,
        _weekly_spend_usd,
        scene_cache_key,
    )

    if not acts_enabled_for(user):
        return "skipped_disabled"
    try:
        wanted = ActRole(str(role))
    except ValueError:
        return "skipped_rhythm"
    if wanted not in WRITING_ORDER:
        # «Le fil» is the page itself, never an act written after it.
        return "skipped_rhythm"
    first_row = _first_act_row(db, user, prefetch_id)
    if first_row is None or first_row.id not in {
        row.id for row in _live_prefetch_rows(db, user, cache_key=first_row.entity_id)
    }:
        # This page itself must still be waiting, not just one under its key: a page
        # written again after this one expired is another first act.
        return "skipped_stale"
    if first_row.entity_id != scene_cache_key(db, user):
        # The morning would discard the page as stale, and every act with it.
        return "skipped_stale"
    if any(str((row.payload or {}).get("role")) == str(wanted) for row in act_rows(db, user, prefetch_id=prefetch_id)):
        return "cached"
    if wanted not in planned_roles(db, user):
        return "skipped_rhythm"

    guardrail = float(settings.PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD or 0.0)
    page_cost = _usage_cost(first_row.payload or {})
    if guardrail > 0 and _weekly_spend_usd(db, user) + _unbilled_usd(db, user) + page_cost >= guardrail:
        # An act costs about what the page did: one that would take the week past its
        # guardrail is not written (acts doc: «Reicht das Geld nicht, schreibt er weniger»).
        return "skipped_budget"
    from app.services.spend_guard import day_bounds, service_budget_reached, service_daily_cap_usd

    # The service's day, like the learner's week, counts what the night has written
    # today and nobody has billed yet (every learner's), and this act.
    pending = _unbilled_usd(db, since=day_bounds()[0]) + page_cost if service_daily_cap_usd() > 0 else 0.0
    if service_budget_reached(db, pending_usd=pending):
        return "skipped_budget"

    try:
        first = _brief_codec()[1](dict((first_row.payload or {}).get("brief") or {}))
    except Exception:  # pragma: no cover - an unreadable page is the morning's to discard
        logger.exception("story_acts: the first act's brief is unreadable")
        return "skipped_stale"

    from app.services.journey_contracts import ContentUnavailable
    from app.services.living_story import generate_act, written_ahead_of_time

    started = time.monotonic()
    with written_ahead_of_time():
        result = generate_act(db, user=user, first=first, role=str(wanted))
    elapsed = time.monotonic() - started
    if isinstance(result, ContentUnavailable) or not isinstance(result, ScenarioBrief):
        db.commit()
        reason = str(getattr(result, "reason", "") or "")
        if reason in _ONE_ACT_DAYS:
            return "skipped_day"
        logger.info("story_acts: act «{}» dropped ({})", wanted, reason)
        return "unavailable"
    db.add(
        PilotEvent(
            user_id=user.id,
            event_type=ACT_PREFETCH_EVENT,
            entity_type=ACT_ENTITY_TYPE,
            entity_id=first_row.entity_id,
            payload={
                "prefetch_id": str(first_row.id),
                "role": str(wanted),
                "cache_key": first_row.entity_id,
                "prompt_version": str(result.content_version),
                "generated_seconds": round(elapsed, 3),
                "brief": _brief_codec()[0](result),
            },
            # Billed once, when served or on its discard row (as the page is).
            cost_usd=0.0,
        )
    )
    db.commit()
    return "prefetched"


def act_payloads(rows: list[PilotEvent]) -> list[dict[str, Any]]:
    """What a row holds, for reports: the role, the time it took, its title."""

    return [
        {
            "role": (row.payload or {}).get("role"),
            "generated_seconds": (row.payload or {}).get("generated_seconds"),
            "title_fr": ((row.payload or {}).get("brief") or {}).get("title_fr"),
        }
        for row in rows
    ]


__all__ = [
    "ACT_ENTITY_TYPE",
    "ACT_PREFETCH_EVENT",
    "WRITING_ORDER",
    "act_payloads",
    "act_rows",
    "acts_enabled_for",
    "planned_roles",
    "roles_to_write",
    "write_act",
]
