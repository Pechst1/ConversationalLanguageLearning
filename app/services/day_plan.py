"""S2.1 · one stored day plan, written by events and compared in the shadow.

Home, La Forge and the Done screen disagreed about the day because ``DaySession``
(:mod:`app.services.daily_session`) is recomputed on every read from several
stores. This module keeps the day as one stored record instead: the steps in the
owner's order (``DAY_STEP_ORDER``), each with a stable id, its planned size and
minutes, and a status that only events write.

Where it lives: ``DailyJourney.plan_selection["day_plan"]``, the journey row's
existing JSON. One journey is one learner day, the row already holds the day's
other planning facts (``session.words_done``, ``time_budget``, ``dealt_shape``),
and a JSON key needs no migration. A day without a journey row has no plan.

Who writes it (``DAY_PLAN_STORED`` on, :func:`note_flush` and :func:`apply_flush`, called from
:mod:`app.db.day_plan_listener` on every flush, so no write path can skip it):

* the journey is planned (``preparing`` → ``active``): the plan is created and
  the scene is started;
* ``active`` → ``paused`` / ``paused`` → ``active``: the scene is paused / resumed
  (its status stays ``doing``);
* → ``completed``: the scene is done; → ``ended_early``: the scene is skipped;
* a Forge séance is opened today: grammar started; one finishes (or a rule check
  is passed): grammar done;
* ``POST /daily-journeys/session/words-done`` (:func:`daily_session.mark_words_done`):
  words done.

Stage S2.1 is a shadow: :func:`shadow_compare` reads the stored plan beside the
recomputed ``session_view`` and logs ``day_plan_shadow_mismatch`` with each field
that differs. The API keeps serving the recomputed view. Old rows (planned before
the flag) carry no plan and are never backfilled.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.daily_journey import DAY_STEP_ORDER

logger = logging.getLogger(__name__)

#: The ``plan_selection`` key the plan is stored under.
PLAN_KEY = "day_plan"
PLAN_VERSION = 1
#: The log event (``record.day_plan_mismatch`` carries the fields) on a shadow mismatch.
MISMATCH_EVENT = "day_plan_shadow_mismatch"

StepStatus = Literal["todo", "doing", "done", "skipped"]
StepKind = Literal["scene", "grammar", "words"]
EventName = Literal["step_started", "step_finished", "step_skipped", "step_paused", "step_resumed", "words_done"]

#: The working steps, in the owner's order («finish» is the seal, not a step).
WORKING_KINDS: tuple[str, ...] = tuple(kind for kind in DAY_STEP_ORDER if kind != "finish")
#: A step that is over: today's view calls both «done» (a scene left early counts).
CLOSED: frozenset[str] = frozenset({"done", "skipped"})
#: How many applied events the plan keeps (idempotency keys and the audit trail).
EVENT_LOG_LIMIT = 40

_FORGE_DONE_STATUSES = ("completed", "test_out_done")


def enabled() -> bool:
    return bool(getattr(settings, "DAY_PLAN_STORED", False))


def _now() -> datetime:
    """The journey service's clock (one seam: the tests and the walk freeze it)."""

    from app.services import daily_journey

    return daily_journey._utcnow()


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PlanStep:
    id: str
    kind: str
    #: Items the step holds when planned (grammar: séance items, words: cards).
    #: ``None`` for the scene, whose length is its minutes.
    size: int | None
    seconds: int
    minutes: int
    status: str = "todo"
    started_at: str | None = None
    finished_at: str | None = None
    skipped_at: str | None = None
    paused_at: str | None = None
    pauses: int = 0
    reason: str | None = None

    @property
    def closed(self) -> bool:
        return self.status in CLOSED


@dataclass(slots=True)
class DayPlan:
    journey_id: str
    local_date: str
    created_at: str
    steps: list[PlanStep]
    version: int = PLAN_VERSION
    #: Idempotency keys of the events applied, newest last (bounded).
    events: list[dict[str, Any]] = field(default_factory=list)

    def step(self, kind: str) -> PlanStep | None:
        return next((step for step in self.steps if step.kind == kind), None)

    @property
    def done(self) -> bool:
        return all(step.closed for step in self.steps)

    @property
    def minutes_left(self) -> int:
        return sum(step.minutes for step in self.steps if not step.closed)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: Any) -> DayPlan | None:
        if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
            return None
        try:
            steps = [PlanStep(**step) for step in raw["steps"] if isinstance(step, dict)]
            return cls(
                journey_id=str(raw.get("journey_id") or ""),
                local_date=str(raw.get("local_date") or ""),
                created_at=str(raw.get("created_at") or ""),
                steps=steps,
                version=int(raw.get("version") or PLAN_VERSION),
                events=[event for event in raw.get("events") or [] if isinstance(event, dict)],
            )
        except TypeError:
            logger.warning("day_plan: a stored plan could not be read", exc_info=True)
            return None


def step_id(local_date: str, kind: str) -> str:
    """Stable for the day: ``2026-03-10:grammar``. The next stage's URL names it."""

    return f"{local_date}:{kind}"


def _minutes(seconds: int) -> int:
    from app.services.daily_session import minutes

    return minutes(seconds)


def new_plan(
    *,
    journey_id: str,
    local_date: date | str,
    scene_seconds: int,
    grammar_items: int,
    words_new: int,
    words_reviews: int,
    now: datetime | None = None,
    pace: Any = None,
) -> DayPlan:
    """The day's plan with every step ``todo``. Pure: sizes come from the caller,
    and the seconds from ``pace`` (R2 (7): ``day_pace.DayPace``, the view's own;
    ``None``: the calibrated defaults)."""

    from app.services.daily_session import words_seconds
    from app.services.day_pace import DEFAULT_PACE

    pace = pace or DEFAULT_PACE
    day = local_date.isoformat() if isinstance(local_date, date) else str(local_date)
    scene_seconds = pace.scene_seconds(scene_seconds)
    grammar_seconds = pace.forge_seconds(grammar_items)
    words_secs = words_seconds(words_new, words_reviews, pace)
    by_kind = {
        "scene": PlanStep(step_id(day, "scene"), "scene", None, int(scene_seconds), _minutes(scene_seconds)),
        "grammar": PlanStep(
            step_id(day, "grammar"), "grammar", int(grammar_items), grammar_seconds, _minutes(grammar_seconds)
        ),
        "words": PlanStep(
            step_id(day, "words"),
            "words",
            max(0, int(words_new)) + max(0, int(words_reviews)),
            words_secs,
            _minutes(words_secs),
        ),
    }
    return DayPlan(
        journey_id=str(journey_id),
        local_date=day,
        created_at=_iso(now or _now()) or "",
        steps=[by_kind[kind] for kind in WORKING_KINDS],
    )


def read_plan(journey: Any) -> DayPlan | None:
    """The stored plan, or ``None`` (no journey, an old row, the flag was off)."""

    selection = getattr(journey, "plan_selection", None) if journey is not None else None
    if not isinstance(selection, dict):
        return None
    return DayPlan.from_json(selection.get(PLAN_KEY))


def store_plan(journey: Any, plan: DayPlan) -> None:
    from sqlalchemy.orm.attributes import flag_modified

    selection = dict(getattr(journey, "plan_selection", None) or {})
    selection[PLAN_KEY] = plan.to_json()
    journey.plan_selection = selection
    try:
        flag_modified(journey, "plan_selection")
    except Exception:  # noqa: BLE001 - a plain object in a pure test has no state
        logger.debug("day_plan: %r is not a mapped row", type(journey).__name__)


# ---------------------------------------------------------------------------
# Events — the only writers of a step's status
# ---------------------------------------------------------------------------


def apply_event(
    plan: DayPlan,
    event: EventName,
    kind: str,
    *,
    key: str | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> bool:
    """Apply one event to one step. ``True`` when the plan changed.

    Idempotent twice over: an event whose ``key`` was already applied is a no-op,
    and so is an event that cannot move the step (a finish on a done step, a
    start on a started one). A finish wins over a skip (a scene left early and
    then finished), never the other way round.
    """

    step = plan.step("words" if event == "words_done" else kind)
    if step is None:
        return False
    if key and any(entry.get("key") == key for entry in plan.events):
        return False
    stamp = _iso(now or _now())
    changed = False
    if event == "step_started":
        if step.status == "todo":
            step.status, step.started_at, changed = "doing", stamp, True
    elif event in ("step_finished", "words_done"):
        if step.status != "done":
            step.status, step.finished_at, changed = "done", stamp, True
            step.started_at = step.started_at or stamp
            step.paused_at = None
    elif event == "step_skipped":
        if step.status in ("todo", "doing"):
            step.status, step.skipped_at, step.reason, changed = "skipped", stamp, reason, True
    elif event == "step_paused":
        if step.status == "doing" and step.paused_at is None:
            step.paused_at, step.pauses, changed = stamp, step.pauses + 1, True
    elif event == "step_resumed":
        if step.paused_at is not None:
            step.paused_at, changed = None, True
    if changed:
        plan.events.append({"event": event, "step": step.id, "key": key, "at": stamp})
        del plan.events[:-EVENT_LOG_LIMIT]
    return changed


def apply_to_journey(journey: Any, event: EventName, kind: str, **kwargs: Any) -> bool:
    """:func:`apply_event` on the journey's stored plan, stored back when it moved."""

    plan = read_plan(journey)
    if plan is None:
        return False
    changed = apply_event(plan, event, kind, **kwargs)
    if changed:
        store_plan(journey, plan)
    return changed


# ---------------------------------------------------------------------------
# The flush listener: journey and Forge transitions
# ---------------------------------------------------------------------------
#
# Two phases. ``after_flush`` still sees each attribute's history (what this flush
# changed), so it notes the transitions; ``after_flush_postexec`` applies them once
# the rows are written, so the plan is sized against the state the transition
# produced (the words the journey reserved, its stored core). What it writes is
# flushed by the commit's next round (``Session.commit`` flushes until clean), or
# by the caller's next flush.

#: ``session.info`` key holding the transitions noted in ``after_flush``.
_PENDING_KEY = "day_plan_transitions"


@dataclass(slots=True)
class _Transition:
    target: Any
    old: str | None
    new: str | None
    #: A plan this flush's ``plan_selection`` rewrite dropped (journeys only).
    dropped_plan: dict[str, Any] | None = None


def _status_change(session: Session, obj: Any) -> tuple[str | None, str | None] | None:
    """``(old, new)`` when this flush changes ``obj.status`` (call in ``after_flush``)."""

    from sqlalchemy import inspect

    if obj in session.new:
        return None, getattr(obj, "status", None)
    history = inspect(obj).attrs.status.history
    if not history.added:
        return None
    old = history.deleted[0] if history.deleted else None
    new = history.added[0]
    return (None if old is None else str(old)), (None if new is None else str(new))


def _dropped_plan(session: Session, journey: Any) -> dict[str, Any] | None:
    """The plan a rewrite of ``plan_selection`` in this flush dropped, if any."""

    from sqlalchemy import inspect

    if journey in session.new:
        return None
    history = inspect(journey).attrs.plan_selection.history
    if not history.deleted:
        return None
    old = history.deleted[0]
    current = journey.plan_selection if isinstance(journey.plan_selection, dict) else {}
    if isinstance(old, dict) and isinstance(old.get(PLAN_KEY), dict) and PLAN_KEY not in current:
        return dict(old[PLAN_KEY])
    return None


def note_flush(session: Session) -> None:
    """``after_flush``: note this flush's journey and Forge transitions (flag on only)."""

    if not enabled():
        return
    from app.db.models.atelier import AtelierSession
    from app.db.models.daily_journey import DailyJourney

    noted: list[_Transition] = session.info.setdefault(_PENDING_KEY, [])
    for obj in (*session.new, *session.dirty):
        if not isinstance(obj, (DailyJourney, AtelierSession)):
            continue
        try:
            change = _status_change(session, obj)
            dropped = _dropped_plan(session, obj) if isinstance(obj, DailyJourney) else None
        except Exception:  # noqa: BLE001 - the shadow plan never costs a write
            logger.warning("day_plan: a transition could not be read", exc_info=True)
            continue
        if change is None and dropped is None:
            continue
        old, new = change if change is not None else (None, None)
        noted.append(_Transition(obj, old, new, dropped))


def forget_flush(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


class _DbOnly:
    """The one attribute ``DailyJourneyService._forge_blocks_on`` reads."""

    def __init__(self, db: Session) -> None:
        self.db = db


def _sizes_for(session: Session, journey: Any, user: Any, *, now: datetime) -> tuple[int, int, int, int]:
    """``(scene_seconds, grammar_items, words_new, words_reviews)`` as the day is planned.

    The same inputs ``daily_session.build_session`` prices the steps with: the
    plan's stored core, the learner's séance budget (priced by ``day_pace``), and the day
    deck as it would be dealt now. The deck is read inside a savepoint: a query
    that fails costs the words their size, never the journey its commit.
    """

    from app.services.daily_journey import _due_word_count, _stored_core_seconds
    from app.services.daily_session import DEFAULT_SCENE_SECONDS, day_deck, forge_items
    from app.services.forge_picker import forge_budget_seconds

    scene_seconds = int(_stored_core_seconds(journey) or DEFAULT_SCENE_SECONDS)
    from app.services.forge import seance_max_items

    grammar_items = forge_items(forge_budget_seconds(user), seance_max_items(user))
    words_new = words_reviews = 0
    try:
        with session.connection().begin_nested():
            words_new, words_reviews = day_deck(
                session, user, reviews_due=_due_word_count(session, user), now=now
            )
    except Exception:  # noqa: BLE001 - a size that cannot be read never costs the day
        logger.warning("day_plan: the word deck could not be sized", exc_info=True)
    return scene_seconds, grammar_items, int(words_new), int(words_reviews)


def create_for_journey(session: Session, journey: Any, *, now: datetime | None = None) -> DayPlan | None:
    """Plan the day on the journey row (once). Seeds what already happened today:
    a Forge séance finished before the scene, words marked done."""

    from app.db.models.user import User
    from app.services.daily_journey import DailyJourneyService
    from app.services.daily_session import words_marked_done

    if read_plan(journey) is not None:
        return None
    user = session.get(User, journey.user_id)
    if user is None:
        return None
    now = now or _now()
    # The deck is read on the clock ``build_session`` reads it on (the wall clock;
    # the journey's own seam only decides which day the journey is).
    scene_seconds, grammar_items, words_new, words_reviews = _sizes_for(
        session, journey, user, now=datetime.now(UTC)
    )
    from app.services.day_pace import day_pace

    plan = new_plan(
        journey_id=str(journey.id),
        local_date=journey.local_date,
        scene_seconds=scene_seconds,
        grammar_items=grammar_items,
        words_new=words_new,
        words_reviews=words_reviews,
        now=now,
        pace=day_pace(session, user),
    )
    try:
        blocks = DailyJourneyService._forge_blocks_on(  # type: ignore[arg-type]
            _DbOnly(session), user, str(journey.timezone or "UTC"), journey.local_date
        )
    except Exception:  # noqa: BLE001
        logger.warning("day_plan: today's Forge could not be read", exc_info=True)
        blocks = 0
    if blocks > 0:
        apply_event(plan, "step_finished", "grammar", key="seed:grammar", now=now)
    if words_marked_done(journey):
        apply_event(plan, "words_done", "words", key="seed:words", now=now)
    store_plan(journey, plan)
    return plan


def _on_journey(session: Session, item: _Transition, now: datetime) -> None:
    from app.services.journey_contracts import JourneyStatus

    journey = item.target
    if item.dropped_plan is not None and read_plan(journey) is None:
        restored = DayPlan.from_json(item.dropped_plan)
        if restored is not None:
            store_plan(journey, restored)
    old, new = item.old, item.new
    if new is None:
        return
    if new == JourneyStatus.ACTIVE and old in (None, JourneyStatus.PREPARING, JourneyStatus.UNAVAILABLE):
        # The day is planned: the plan is made with it, and the scene opens.
        create_for_journey(session, journey, now=now)
        apply_to_journey(journey, "step_started", "scene", key="journey:started", now=now)
        return
    if new == JourneyStatus.PAUSED:
        apply_to_journey(journey, "step_paused", "scene", now=now)
    elif new == JourneyStatus.ACTIVE and old == JourneyStatus.PAUSED:
        apply_to_journey(journey, "step_resumed", "scene", now=now)
    elif new == JourneyStatus.COMPLETED:
        apply_to_journey(journey, "step_finished", "scene", key="journey:completed", now=now)
    elif new == JourneyStatus.ENDED_EARLY:
        apply_to_journey(journey, "step_skipped", "scene", key="journey:ended_early", reason="ended_early", now=now)
    # Any other row without a plan (an old one) is left alone: no backfill.


def _todays_journey(session: Session, user_id: Any, moment: datetime) -> Any:
    from sqlalchemy import select

    from app.db.models.daily_journey import DailyJourney
    from app.services.daily_journey import local_date_for

    journey = session.execute(
        select(DailyJourney).where(DailyJourney.user_id == user_id).order_by(DailyJourney.local_date.desc()).limit(1)
    ).scalar_one_or_none()
    if journey is None:
        return None
    if journey.local_date != local_date_for(str(journey.timezone or "UTC"), now=moment):
        return None
    return journey


def _forge_passed(atelier_session: Any, status: str) -> bool:
    if status == "completed":
        return True
    recap = atelier_session.recap_payload if isinstance(atelier_session.recap_payload, dict) else {}
    result = recap.get("test_out")
    return isinstance(result, dict) and bool(result.get("passed"))


def _on_forge(session: Session, item: _Transition, now: datetime) -> None:
    from app.services.forge import FORGE_KEY, TEST_OUT_DONE_STATUS

    atelier_session = item.target
    payload = atelier_session.quote_payload if isinstance(atelier_session.quote_payload, dict) else {}
    if not payload.get(FORGE_KEY) and atelier_session.status != TEST_OUT_DONE_STATUS:
        return
    old, new = item.old, item.new
    finished = new in _FORGE_DONE_STATUSES and _forge_passed(atelier_session, str(new))
    if not finished and old is not None:
        return  # left, failed, or any other move: the step keeps its status
    moment = atelier_session.completed_at or now
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    journey = _todays_journey(session, atelier_session.user_id, moment)
    if journey is None:
        return
    ref = str(atelier_session.id)
    if finished:
        apply_to_journey(journey, "step_finished", "grammar", key=f"forge:done:{ref}", now=now)
    else:
        apply_to_journey(journey, "step_started", "grammar", key=f"forge:open:{ref}", now=now)


def apply_flush(session: Session) -> None:
    """``after_flush_postexec``: write the plan from the noted transitions."""

    noted: list[_Transition] = session.info.pop(_PENDING_KEY, None) or []
    if not noted or not enabled():
        return
    from app.db.models.daily_journey import DailyJourney

    now = _now()
    with session.no_autoflush:
        for item in noted:
            try:
                if isinstance(item.target, DailyJourney):
                    _on_journey(session, item, now)
                else:
                    _on_forge(session, item, now)
            except Exception:  # noqa: BLE001 - the shadow plan never costs a write
                logger.warning("day_plan: a transition could not be written", exc_info=True)


# ---------------------------------------------------------------------------
# The shadow: stored plan against today's recomputed view
# ---------------------------------------------------------------------------


def compare(plan: DayPlan, view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every field where the stored plan and ``session_view`` disagree.

    Keys: ``order``, ``done.<kind>``, ``count.<kind>``, ``minutes.<kind>``,
    ``minutes_left``, ``day_done``. Each value says ``{"plan": …, "view": …}``.
    Counts and minutes are compared on open steps only: once a step is closed
    today's view prints what was done, the plan what was planned.
    """

    diffs: dict[str, dict[str, Any]] = {}
    view_steps = {step["kind"]: step for step in view.get("steps") or [] if step.get("kind") != "finish"}
    plan_order = [step.kind for step in plan.steps]
    view_order = [step["kind"] for step in view.get("steps") or [] if step.get("kind") != "finish"]
    if plan_order != view_order:
        diffs["order"] = {"plan": plan_order, "view": view_order}
    for step in plan.steps:
        seen = view_steps.get(step.kind)
        if seen is None:
            continue
        view_done = seen.get("state") == "done"
        if step.closed != view_done:
            diffs[f"done.{step.kind}"] = {"plan": step.status, "view": seen.get("state")}
        if step.closed or view_done:
            continue
        if step.size is not None and "count" in seen and int(seen["count"]) != step.size:
            diffs[f"count.{step.kind}"] = {"plan": step.size, "view": int(seen["count"])}
        if int(seen.get("minutes") or 0) != step.minutes:
            diffs[f"minutes.{step.kind}"] = {"plan": step.minutes, "view": int(seen.get("minutes") or 0)}
    if plan.minutes_left != int(view.get("minutes_left") or 0):
        diffs["minutes_left"] = {"plan": plan.minutes_left, "view": int(view.get("minutes_left") or 0)}
    if plan.done != bool(view.get("done")):
        diffs["day_done"] = {"plan": plan.done, "view": bool(view.get("done"))}
    return diffs


def shadow_compare(journey: Any, view: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
    """Read the stored plan beside the view; log one event when they differ.

    ``None`` when there is nothing to compare (flag off, no journey, an old row).
    Never raises and never changes ``view``.
    """

    if not enabled() or journey is None:
        return None
    try:
        plan = read_plan(journey)
        if plan is None:
            return None
        diffs = compare(plan, view)
    except Exception:  # noqa: BLE001 - the shadow never costs Home its day
        logger.warning("day_plan: the shadow comparison failed", exc_info=True)
        return None
    if diffs:
        logger.warning(
            "%s journey=%s fields=%s",
            MISMATCH_EVENT,
            plan.journey_id,
            ",".join(sorted(diffs)),
            extra={
                "event": MISMATCH_EVENT,
                "journey_id": plan.journey_id,
                "local_date": plan.local_date,
                "day_plan_mismatch": diffs,
            },
        )
    return diffs


__all__ = [
    "CLOSED",
    "DayPlan",
    "MISMATCH_EVENT",
    "PLAN_KEY",
    "PlanStep",
    "WORKING_KINDS",
    "apply_event",
    "apply_to_journey",
    "compare",
    "create_for_journey",
    "enabled",
    "new_plan",
    "apply_flush",
    "forget_flush",
    "note_flush",
    "read_plan",
    "shadow_compare",
    "step_id",
    "store_plan",
]
