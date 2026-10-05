"""WP-124b: recovery that cannot stall the season.

WP-124a made a lost gap day honest — the learner re-reads the last season page —
but it does not move the season, so a gap whose generation keeps failing re-read
the same page forever. WP-133a measured the loss at 4 of 19 generated days (21 %,
four different guard reasons), so two lost days in a row inside one gap are not
rare: at p = 0.21 a 6-day gap holds a run of two 18 % of the time, and about three
lives in four meet at least one such run over the season's seven gaps (1.3 runs a
life on average). Every gap that holds a required moment therefore needs a bridge.

**The policy** (owner decision 1(b), made a recovery with prerequisites, never a
blind cursor jump), decided only when today's generated day has just failed:

1. The first lost day of a run is the WP-124a reprise (``REPRISES_BEFORE_RECOVERY``).
2. The next consecutive lost day in the same gap (``RECOVER_AT_FAILURE``) is an
   authored continuation, served with no model at all:

   * **the next tentpole's Day A**, when every moment the gap marks ``required``
     (the tentpole's prerequisites: a gate of Lila's path, the usual order, the
     roof…) has already been staged;
   * otherwise **the gap's bridge** (``season.bridges``): one short page that
     stages exactly the moments still owed — the learner answers each one, their
     own reply sets what it sets — and then the gap is closed, so the next day is
     the tentpole;
   * with no bridge data for that gap (the bridges are an owner-approval item and
     ship apart from this code), the reprise stays: the cursor never jumps over a
     moment the story needs.

A "lost day" is a learner day whose plan is a reprise or a recovery (or that was
left unavailable); a day the director wrote breaks the run, which is the counter's
reset. The run is read from the learner's own journeys, never stored: a reload,
a second request or a retry of the same day reads the same rows, so the decision
is the same (the plan itself is chosen once, under the generation claim).

**Edge cases.** The first gap after T1 has a page to re-read (T1 B), so it follows
the policy like any gap. A tentpole day is authored and does not fail; if one
cannot be served, the day is a reprise. **After the finale** there is no season
left to stall: a lost day re-reads the last page and nothing moves (the epilogue,
WP-132B, owns what comes after T8). A prefetched generated scene is keyed on the
story revision, which any settled bridge or tentpole changes, so it is discarded
rather than served over a closed gap.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import replace as dc_replace
from typing import Any

from app.services.season.clock import Position, played_log, shortened_gaps
from app.services.season.director import used_premises
from app.services.season.format import Season

logger = logging.getLogger(__name__)

#: How many lost days in a row inside one gap are re-read before the season moves on.
REPRISES_BEFORE_RECOVERY = 1
#: The consecutive lost day (1-based) that is served the authored continuation.
RECOVER_AT_FAILURE = REPRISES_BEFORE_RECOVERY + 1
#: The walk's bound: never more reprises in a row inside one gap than this.
MAX_CONSECUTIVE_REPRISES = REPRISES_BEFORE_RECOVERY
#: How many of the learner's earlier days are read to count the run.
FAILURE_SCAN_LIMIT = 14
#: ``plan_selection["generation_fallback"]["kind"]`` of a recovered day.
RECOVERY_FALLBACK_KIND = "season_recovery"
#: ``story_context["season"][RECOVERY_KEY]`` marks a recovered day (and why).
RECOVERY_KEY = "recovery"
#: ``story_context["season"][BRIDGE_KEY]``: the bridge's moments, for ``runtime.settle``.
BRIDGE_KEY = "bridge"

#: The honest one-line note on a recovered day, in the learner's language (no praise;
#: the shape of ``learner_copy.LEARNER_COPY`` rows, like ``reprise.REPRISE_COPY``).
RECOVERY_COPY: dict[str, dict[str, str]] = {
    "season_recovery_bridge": {
        "en": "The story moves on faster today: a few days, told in one page.",
        "de": "Die Geschichte geht heute schneller weiter: ein paar Tage auf einer Seite.",
        "fr": "Aujourd'hui, l'histoire avance plus vite : quelques jours en une page.",
    },
    "season_recovery_tentpole": {
        "en": "A few days of the story went by without an episode.",
        "de": "Ein paar Tage der Geschichte sind ohne Folge vergangen.",
        "fr": "Quelques jours de l'histoire ont passé sans épisode.",
    },
}


def recovery_text(key: str, language: str | None) -> str:
    from app.services.learner_copy import copy_language

    row = RECOVERY_COPY[key]
    return row.get(copy_language(language)) or row["en"]


@dataclass(frozen=True)
class Decision:
    """What a lost day becomes."""

    #: "reprise" (WP-124a), "tentpole" (the next Day A) or "bridge".
    kind: str
    reason: str
    #: The gap the run is in (``None`` off a gap: a tentpole day, the finale).
    gap: str | None
    #: This lost day's place in the run (1 = the first).
    failure: int
    #: The day to serve: the tentpole's Day A, or the gap day the bridge stands in for.
    position: Position | None = None
    #: The required moments still owed (the bridge's blocks).
    missing: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reason": self.reason,
            "gap": self.gap,
            "failure": self.failure,
            "position": self.position.key if self.position else None,
            "missing": list(self.missing),
        }


# ---------------------------------------------------------------------------
# The policy (pure)
# ---------------------------------------------------------------------------


def missing_required(season: Season, state: dict | None, gap_id: str) -> list[str]:
    """The gap's required moments not yet staged, in the gap's order."""

    gap = season.gaps.get(gap_id)
    if gap is None:
        return []
    done = used_premises(state, gap_id)
    return [need.premise for need in gap.required if need.premise not in done]


def prerequisites_hold(season: Season, state: dict | None, gap_id: str) -> bool:
    """May the season move from this gap to the next tentpole? Only once every
    moment the gap marks ``required`` has happened (the choices, gates and scenes
    the tentpole reads)."""

    return not missing_required(season, state, gap_id)


def next_tentpole(season: Season, pos: Position, state: dict | None) -> Position | None:
    """Day A of the tentpole after the gap at ``pos``."""

    index = pos.segment_index + 1
    if pos.segment is None or index >= len(season.segments):
        return None
    following = season.segments[index]
    if following.kind != "tentpole":
        return None
    return Position(season.id, following, index, 1, len(played_log(state)) + 1)


def decide(
    season: Season,
    state: dict | None,
    pos: Position,
    *,
    failures_before: int,
    bridge_gaps: set[str] | frozenset[str] = frozenset(),
) -> Decision:
    """Today's lost day: a reprise, the next tentpole or the gap's bridge.

    ``failures_before`` is the run of lost days just before today in this gap;
    ``bridge_gaps`` the gaps the season has a bridge for."""

    failure = int(failures_before) + 1
    if pos.finished or pos.segment is None:
        return Decision("reprise", "season_finished", None, failure)
    if not pos.is_gap:
        return Decision("reprise", "not_a_gap_day", None, failure)
    gap_id = pos.segment.id
    if gap_id in shortened_gaps(state):  # pragma: no cover - the clock is past it already
        return Decision("reprise", "gap_already_closed", gap_id, failure)
    if failure < RECOVER_AT_FAILURE:
        return Decision("reprise", "first_lost_day", gap_id, failure)
    missing = tuple(missing_required(season, state, gap_id))
    if not missing:
        target = next_tentpole(season, pos, state)
        if target is None:
            return Decision("reprise", "no_next_tentpole", gap_id, failure)
        return Decision("tentpole", "prerequisites_hold", gap_id, failure, target)
    if gap_id not in bridge_gaps:
        # Safe without the bridges: a tentpole whose prerequisites do not hold is
        # never served; the learner re-reads, and the gap stays open.
        return Decision("reprise", "no_bridge_for_missing_moments", gap_id, failure, None, missing)
    return Decision("bridge", "missing_moments", gap_id, failure, pos, missing)


# ---------------------------------------------------------------------------
# The run, read from the learner's days
# ---------------------------------------------------------------------------


def _lost(row: Any, gap_id: str | None) -> bool | None:
    """True for a lost day of this gap, False for a day that breaks the run,
    None for a lost day of another gap (it breaks the run too)."""

    from app.services.season.reprise import REPRISE_FALLBACK_KIND

    marker = ((row.plan_selection or {}) if isinstance(row.plan_selection, dict) else {}).get("generation_fallback")
    marker = marker if isinstance(marker, dict) else {}
    if marker.get("kind") in (REPRISE_FALLBACK_KIND, RECOVERY_FALLBACK_KIND):
        other = marker.get("gap")
        if other and gap_id and other != gap_id:
            return None
        return True
    if str(row.status) == "unavailable" and not marker:
        # The honest dead end (nothing could be served): a lost day all the same.
        return True
    return False


def failures_before(db, user, journey, *, gap_id: str | None) -> int:
    """The run of lost days in this gap just before ``journey`` (its own day excluded)."""

    from sqlalchemy import select

    from app.db.models.daily_journey import DailyJourney

    rows = db.scalars(
        select(DailyJourney)
        .where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date < journey.local_date,
            DailyJourney.id != journey.id,
        )
        .order_by(DailyJourney.local_date.desc())
        .limit(FAILURE_SCAN_LIMIT)
    ).all()
    count = 0
    for row in rows:
        if _lost(row, gap_id) is not True:
            break
        count += 1
    return count


# ---------------------------------------------------------------------------
# Today's decision and its brief
# ---------------------------------------------------------------------------


def decide_today(db, user, journey, *, now: Any = None) -> tuple[Decision | None, Any]:
    """``(decision, today)`` for a lost day of a season life (``(None, None)`` off one)."""

    from app.services import living_story as engine
    from app.services.season import runtime as season_runtime
    from app.services.season.bridges import load_bridges

    thread = engine._active_thread(db, user)
    live = ((thread.state or {}) if thread else {}).get(engine.STATE_KEY) or {}
    today = season_runtime.today_for(live, user=user, seed=str(user.id), now=now)
    if today is None:
        return None, None
    gap_id = today.pos.segment.id if today.pos.is_gap and today.pos.segment else None
    before = failures_before(db, user, journey, gap_id=gap_id)
    bridges = set(load_bridges(today.season.id)) if gap_id else set()
    return decide(today.season, today.state, today.pos, failures_before=before, bridge_gaps=bridges), today


def recovery_brief(db, user, decision: Decision, *, now: Any = None):
    """The authored continuation as a brief the journey plans, binds and settles
    (``None`` when it cannot be built: the caller keeps the reprise)."""

    from app.services import living_story as engine
    from app.services.season import runtime as season_runtime
    from app.services.season.bridges import bridge_page, load_bridges

    if decision.kind not in ("tentpole", "bridge") or decision.position is None:
        return None
    context = engine.story_context(db, user, now=now)
    today = context.get(engine.SEASON_TODAY_KEY)
    if today is None:
        return None
    marker = decision.as_dict()
    if decision.kind == "tentpole":
        moved = dc_replace(today, pos=decision.position)
        context["season_script"] = season_runtime.context_block(moved)
        brief = season_runtime.tentpole_brief(moved, context, season_extra={RECOVERY_KEY: marker})
        note = recovery_text("season_recovery_tentpole", today.language)
    else:
        bridge = load_bridges(today.season.id).get(str(decision.gap))
        if bridge is None:
            return None
        page = bridge_page(
            today.season,
            bridge,
            list(decision.missing),
            flags=today.flags,
            band=today.band,
            language=today.language,
        )
        if page is None:
            return None
        moved = dc_replace(today, pos=decision.position)
        extra = {
            RECOVERY_KEY: marker,
            BRIDGE_KEY: {"gap": bridge.gap, "moments": page["moments"]},
        }
        brief = season_runtime.tentpole_brief(moved, context, page=page, season_extra=extra)
        note = recovery_text("season_recovery_bridge", today.language)
    if brief is None:
        return None
    # The honest line on the day's task: the story moved on, and how.
    objective = f"{note} {brief.objective_native}".strip()[:320]
    task = dc_replace(brief.response_task, objective_native=objective)
    return dc_replace(brief, objective_native=objective, response_task=task)


def is_recovery(story_context: dict[str, Any] | None) -> bool:
    from app.services.season.runtime import SEASON_CONTEXT_KEY

    season_ctx = (story_context or {}).get(SEASON_CONTEXT_KEY) if isinstance(story_context, dict) else None
    return isinstance(season_ctx, dict) and isinstance(season_ctx.get(RECOVERY_KEY), dict)


__all__ = [
    "BRIDGE_KEY",
    "Decision",
    "FAILURE_SCAN_LIMIT",
    "MAX_CONSECUTIVE_REPRISES",
    "RECOVERY_COPY",
    "RECOVERY_FALLBACK_KIND",
    "RECOVERY_KEY",
    "RECOVER_AT_FAILURE",
    "REPRISES_BEFORE_RECOVERY",
    "decide",
    "decide_today",
    "failures_before",
    "is_recovery",
    "missing_required",
    "next_tentpole",
    "prerequisites_hold",
    "recovery_brief",
    "recovery_text",
]
