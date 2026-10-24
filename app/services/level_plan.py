"""The level plan: exactly where the learner stands, what is left, and what it costs.

Owner, 2026-10-24: «we always know exactly at which level the learner is
currently so that he also knows that exactly and knows what he has to do and
how much time he has to invest to advance further».

One read, ``GET /api/v1/progress/level``, built on the engine's own numbers
(:func:`app.services.cefr_progress.live_level`: the band and its percent are the
ones Home, the Dossier and Fortschritt print) and spelled out:

* **where** — the band in force and its percent; the ladder of every band
  (closed by an épreuve, credited, below the starting level, in force, ahead)
  with the learner's goal on it;
* **what is left** — each of the band's grammar units with its stage, the
  «Tenue» evidence it still lacks (``concept_life.held_missing``), the soonest
  it can be held (``concept_life.earliest_held_at``) and whether today owes it
  an opportunity (``concept_life.held_opportunity``); the band's words known,
  on their way (a card, not known yet) and not met yet; the épreuve;
* **how long** — WP-L8's forecast (an estimate: the learner's plan before seven
  active days, measured after), the rules' floor (the earliest day, however much
  is practised), what those days cost in practice minutes (measured over the
  last two weeks once the forecast is, else the Tempo sheet's arithmetic for
  the learner's plan), and the practice time already measured in the band;
* **by criterion** — how far the words alone and the rules alone reach.

Read-only: nothing here writes. Every number is the engine's or read from the
learner's own rows; an estimate is labelled one, and nothing is invented.
Design: docs/implementation/atelier-v2/LEVEL-PLAN.md.
"""
from __future__ import annotations

import logging
import math
from bisect import bisect_right
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.daily_journey import DailyJourney
from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization, UserGrammarProgress
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User

logger = logging.getLogger(__name__)

LEVEL_PLAN_VERSION = "level-plan-v1"

#: Ladder states, lowest band first.
LADDER_PASSED = "passed"
LADDER_CREDITED = "credited"
#: Below the level a placement or declaration started the learner at: never
#: closed in the app, and never counted against them.
LADDER_START = "start"
LADDER_CURRENT = "current"
LADDER_AHEAD = "ahead"

#: The word deck's clock: two answers further apart than this are a break.
WORD_GAP_CEILING_SECONDS = 120
#: The measured minutes a day read the same window as the measured forecast.
MINUTES_WINDOW_DAYS = 14
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _iso_day(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        value = _aware(value).date()  # type: ignore[union-attr]
    return value.isoformat()


# ---------------------------------------------------------------------------
# Practice time — measured, never estimated
# ---------------------------------------------------------------------------


def _overlap_seconds(start: datetime, end: datetime, starts: list[datetime], ends: list[datetime]) -> float:
    """How much of ``[start, end]`` the merged windows (sorted, disjoint) cover."""

    covered = 0.0
    index = max(0, bisect_right(starts, start) - 1)
    while index < len(starts) and starts[index] < end:
        covered += max(0.0, (min(ends[index], end) - max(starts[index], start)).total_seconds())
        index += 1
    return covered


def _merged(windows: list[tuple[datetime, datetime]]) -> tuple[list[datetime], list[datetime]]:
    starts: list[datetime] = []
    ends: list[datetime] = []
    for start, end in sorted(windows):
        if starts and start <= ends[-1]:
            ends[-1] = max(ends[-1], end)
        else:
            starts.append(start)
            ends.append(end)
    return starts, ends


def practice_time(db: Session, user: Any, *, since: datetime, until: datetime) -> dict[str, Any]:
    """Measured practice in ``[since, until)``, in seconds, and the days it fell on.

    * **scenes** — each day's measured active time (``recap_snapshot
      ["active_seconds"]``, WP-11: the server's own event timestamps, pauses and
      idle stretches excluded). A day that could not be measured counts nothing.
    * **forge** — each completed séance outside a scene, on its own clock
      (``forge_metrics.active_seconds``: start, answers, end, idle gaps capped).
      A séance folded into a scene is inside the scene's time already.
    * **words** — the word deck: the time between consecutive word answers
      outside those two, each gap at most :data:`WORD_GAP_CEILING_SECONDS` (a
      longer one is a break and counts nothing). «Outside» means outside the
      stretches the two clocks above counted (``journey_events.active_windows``,
      ``forge_metrics.active_windows``): a review made while a scene was paused,
      or after a séance's capped gap, is the deck's.

    The Courrier, Le Papier and the other surfaces keep no clock yet; their time
    is not in here, so the total is a floor.
    """

    from app.services.forge_metrics import active_seconds as seance_seconds
    from app.services.forge_metrics import active_windows as seance_windows
    from app.services.journey_events import active_windows as scene_windows
    from app.services.journey_events import journey_events_by_id
    from app.services.streak import user_timezone

    zone = ZoneInfo(user_timezone(user))
    days: set[date] = set()
    windows: list[tuple[datetime, datetime]] = []

    scenes = 0
    journeys = (
        db.query(DailyJourney)
        .filter(
            DailyJourney.user_id == user.id,
            DailyJourney.completed_at.isnot(None),
            DailyJourney.completed_at >= since,
            DailyJourney.completed_at < until,
        )
        .all()
    )
    events = journey_events_by_id(db, (journey.id for journey in journeys), user_id=user.id)
    for journey in journeys:
        seconds = (journey.recap_snapshot or {}).get("active_seconds") if isinstance(journey.recap_snapshot, dict) else None
        if not (isinstance(seconds, int | float) and not isinstance(seconds, bool) and seconds > 0):
            continue
        finished = _aware(journey.completed_at)
        scenes += int(seconds)
        days.add(finished.astimezone(zone).date())  # type: ignore[union-attr]
        counted = scene_windows(events.get(str(journey.id), []), until=finished)
        if not counted:
            # Measured, but its events are gone: the whole span stays the scene's.
            started = _aware(journey.started_at) or _aware(journey.created_at)
            if started is not None and finished is not None and finished >= started:
                counted = [(started, finished)]
        windows.extend(counted)

    forge = 0
    seances = (
        db.query(AtelierSession)
        .filter(
            AtelierSession.user_id == user.id,
            AtelierSession.status == "completed",
            AtelierSession.completed_at.isnot(None),
            AtelierSession.completed_at >= since,
            AtelierSession.completed_at < until,
        )
        .all()
    )
    standalone = [
        seance
        for seance in seances
        if not (
            isinstance(seance.quote_payload, dict)
            and isinstance(seance.quote_payload.get("forge"), dict)
            and seance.quote_payload["forge"].get("journey_step_id")
        )
    ]
    attempts: dict[Any, list[AtelierAttempt]] = {}
    if standalone:
        for attempt in db.query(AtelierAttempt).filter(
            AtelierAttempt.atelier_session_id.in_([seance.id for seance in standalone])
        ):
            attempts.setdefault(attempt.atelier_session_id, []).append(attempt)
    for seance in standalone:
        rows = attempts.get(seance.id, [])
        seconds = seance_seconds(seance, rows)
        if seconds > 0:
            forge += seconds
            days.add(_aware(seance.completed_at).astimezone(zone).date())  # type: ignore[union-attr]
            windows.extend(seance_windows(seance, rows))

    starts, ends = _merged(windows)
    moments = sorted(
        stamp
        for (value,) in db.query(ReviewLog.review_date)
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            ReviewLog.review_date >= since,
            ReviewLog.review_date < until,
        )
        if (stamp := _aware(value)) is not None
    )
    deck = 0.0
    for earlier, later in zip(moments, moments[1:], strict=False):
        gap = (later - earlier).total_seconds()
        if 0 < gap <= WORD_GAP_CEILING_SECONDS:
            # The part of the gap no scene or séance clock already counted.
            own = gap - _overlap_seconds(earlier, later, starts, ends)
            if own > 0:
                deck += own
                days.add(later.astimezone(zone).date())
    words = int(round(deck))

    return {
        "scenes_seconds": scenes,
        "forge_seconds": forge,
        "words_seconds": words,
        "total_seconds": scenes + forge + words,
        "days": sorted(days),
    }


# ---------------------------------------------------------------------------
# The parts of the plan
# ---------------------------------------------------------------------------


def _ladder(
    rows: dict[str, Any], *, band: str, goal: str | None
) -> tuple[list[dict[str, Any]], datetime | None]:
    """Every band with its state; and when the band in force began (the last close below it)."""

    from app.services.level_checkpoint import CLOSED_STATES, STATE_CREDITED
    from app.services.level_coverage import SUB_BANDS, band_index

    current = band_index(band)
    began: datetime | None = None
    ladder: list[dict[str, Any]] = []
    for index, name in enumerate(SUB_BANDS):
        row = rows.get(name)
        closed = row is not None and row.status in CLOSED_STATES
        on = _aware(getattr(row, "passed_at", None)) if closed else None
        if name == band:
            state = LADDER_CURRENT
        elif closed:
            state = LADDER_CREDITED if row.status == STATE_CREDITED else LADDER_PASSED
        elif index < current:
            state = LADDER_START
        else:
            state = LADDER_AHEAD
        if closed and index < current and on is not None and (began is None or on > began):
            began = on
        ladder.append({"band": name, "state": state, "on": _iso_day(on), "goal": name == goal})
    return ladder, began


def _localized_titles(db: Session, concepts: dict[int, GrammarConcept]) -> dict[int, dict[str, str]]:
    """Each unit's title per locale, as the notebook names it (``grammar_units.localized_titles``)."""

    from app.services.grammar_units import localized_titles

    rows: dict[int, dict[str, str]] = {}
    if concepts:
        for row in db.query(GrammarConceptLocalization).filter(
            GrammarConceptLocalization.concept_id.in_(list(concepts))
        ):
            if row.title:
                rows.setdefault(int(row.concept_id), {})[str(row.locale)] = str(row.title)
    return {unit_id: localized_titles(concept, rows.get(unit_id)) for unit_id, concept in concepts.items()}


def _rules(
    db: Session,
    user: Any,
    *,
    unit_ids: list[int],
    coverage: dict[str, Any],
    rules_per_week: float,
    now: datetime,
) -> dict[str, Any]:
    """The band's grammar units, one by one, and what each still needs."""

    from app.services.concept_life import (
        HELD_SPACED_AFTER_DAYS,
        STAGE_HELD,
        STAGE_INTRODUCED,
        STAGE_NEW,
        STAGE_PRACTISING,
        earliest_held_at,
        held_missing,
        held_opportunity,
        progress_stage,
    )

    concepts = {
        concept.id: concept
        for concept in db.query(GrammarConcept).filter(GrammarConcept.id.in_(unit_ids))
    } if unit_ids else {}
    progress = {
        row.concept_id: row
        for row in db.query(UserGrammarProgress).filter(
            UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id.in_(unit_ids)
        )
    } if unit_ids else {}
    titles = _localized_titles(db, concepts)
    spacing = 7.0 / rules_per_week if rules_per_week > 0 else None
    counts = {STAGE_NEW: 0, STAGE_INTRODUCED: 0, STAGE_PRACTISING: 0, STAGE_HELD: 0}
    items: list[dict[str, Any]] = []
    waiting_new = 0
    for unit_id in unit_ids:
        concept = concepts.get(unit_id)
        if concept is None:
            continue
        row = progress.get(unit_id)
        stage = progress_stage(row)
        counts[stage] = counts.get(stage, 0) + 1
        item: dict[str, Any] = {
            "id": unit_id,
            "external_id": concept.external_id,
            "name": concept.name,
            "titles": titles.get(unit_id, {}),
            "stage": stage,
            "missing": held_missing(row),
            "owed_today": held_opportunity(row, now=now) if row is not None and stage != STAGE_HELD else None,
            "earliest_held_on": None,
            "introduce_from": None,
            "held_on": _iso_day(row.held_at) if row is not None and row.held_at is not None else None,
        }
        if stage == STAGE_NEW:
            # Introduced at the plan's intake, the first today: a floor too.
            if spacing is not None:
                opens = now + timedelta(days=waiting_new * spacing)
                item["introduce_from"] = _iso_day(opens)
                item["earliest_held_on"] = _iso_day(opens + timedelta(days=HELD_SPACED_AFTER_DAYS))
            waiting_new += 1
        elif stage != STAGE_HELD:
            item["earliest_held_on"] = _iso_day(earliest_held_at(row, now=now))
        items.append(item)

    def order(item: dict[str, Any]) -> tuple[int, str, int]:
        if item["stage"] == STAGE_HELD:
            return (3, item["held_on"] or "", 0)
        if item["stage"] == STAGE_NEW:
            return (2, "", 0)
        return (0 if item["owed_today"] else 1, item["earliest_held_on"] or "9999", 0)

    ordered = sorted(items, key=order)
    units = coverage.get("units") if isinstance(coverage.get("units"), dict) else {}
    held = int(units.get("held") or counts[STAGE_HELD])
    required = int(units.get("required") or 0)
    return {
        "held": held,
        "required": required,
        "total": int(units.get("total") or len(items)),
        "to_go": max(0, required - held),
        "met": bool(units.get("met")),
        "practising": counts[STAGE_PRACTISING],
        "introduced": counts[STAGE_INTRODUCED],
        "not_started": counts[STAGE_NEW],
        "owed_today": sum(1 for item in items if item["owed_today"]),
        "per_week": round(float(rules_per_week), 2),
        "items": ordered,
    }


def _words(
    *, band: str, coverage: dict[str, Any], lemmas: Any, words_per_day: float
) -> dict[str, Any]:
    """The band's words: known, on their way, not met yet, and the new ones still needed."""

    from app.services.level_coverage import band_words

    words = band_words(band)
    block = coverage.get("words") if isinstance(coverage.get("words"), dict) else {}
    known = int(block.get("known") or 0)
    required = int(block.get("required") or 0)
    total = int(block.get("total") or len(words))
    on_the_way = len((lemmas.carded - lemmas.known) & words) if lemmas is not None else 0
    on_the_way = min(on_the_way, max(0, total - known))
    to_go = max(0, required - known)
    new_needed = max(0, to_go - on_the_way)
    per_day = max(0, int(round(words_per_day)))
    return {
        "known": known,
        "required": required,
        "total": total,
        "to_go": to_go,
        "met": bool(block.get("met")) if block else total == 0,
        "on_the_way": on_the_way,
        "not_met": max(0, total - known - on_the_way),
        "new_needed": new_needed,
        "from_reading": len(lemmas.read & words) if lemmas is not None else 0,
        "per_day": per_day,
        "days_for_new": math.ceil(new_needed / per_day) if new_needed and per_day else 0,
    }


def _epreuve(checkpoint: dict[str, Any] | None, band: str) -> dict[str, Any]:
    view = checkpoint if isinstance(checkpoint, dict) else {}
    return {
        "band": str(view.get("band") or band),
        "state": str(view.get("state") or "locked"),
        "attempts": int(view.get("attempts") or 0),
        "retry_after": view.get("retry_after"),
        "staged_in_story": bool(view.get("staged_in_story")),
        "can_dos": len(view.get("can_dos") or []),
    }


def _criterion_reach(steps: list[tuple[str, int, int]]) -> dict[str, Any]:
    """``steps``: ``(band, have, required)`` from A1.1 up. How far one criterion alone reaches."""

    covered: str | None = None
    for band, have, required in steps:
        if required <= 0:
            # The list ends here (the core lexicon stops at B1).
            return {"covered": covered, "working": None, "percent": None, "list_ends": True}
        if have >= required:
            covered = band
            continue
        return {
            "covered": covered,
            "working": band,
            "percent": int(math.floor(min(1.0, have / required) * 100 + 1e-9)),
            "list_ends": False,
        }
    return {"covered": covered, "working": None, "percent": None, "list_ends": False}


def _skills(
    db: Session, user: Any, *, lemmas: Any, band: str, goal: str | None
) -> tuple[dict[str, Any], tuple[int, int]]:
    """The words alone and the rules alone, band by band (WP-L7's two coverage
    criteria); and ``(words, units)`` still needed from the band in force up to
    the goal, every band counted the way its coverage counts it."""

    from app.services.level_coverage import (
        SUB_BANDS,
        UNITS_HELD_SHARE,
        WORDS_KNOWN_SHARE,
        _french_units,
        _units_of_band,
        band_index,
        band_words,
        held_unit_ids,
    )

    concepts = _french_units(db)
    held = held_unit_ids(db, user)
    known = lemmas.known if lemmas is not None else frozenset()
    word_steps: list[tuple[str, int, int]] = []
    rule_steps: list[tuple[str, int, int]] = []
    goal_words = goal_units = 0
    for name in SUB_BANDS:
        words = band_words(name)
        units = set(_units_of_band(concepts, name))
        known_here, words_required = len(known & words), math.ceil(len(words) * WORDS_KNOWN_SHARE) if words else 0
        held_here, units_required = len(held & units), math.ceil(len(units) * UNITS_HELD_SHARE) if units else 0
        word_steps.append((name, known_here, words_required))
        rule_steps.append((name, held_here, units_required))
        if goal is not None and band_index(band) <= band_index(name) <= band_index(goal):
            goal_words += max(0, words_required - known_here)
            goal_units += max(0, units_required - held_here)
    return {"words": _criterion_reach(word_steps), "rules": _criterion_reach(rule_steps)}, (goal_words, goal_units)


def _pace(user: Any, *, words_per_day: float, rules_per_week: float) -> Any:
    """The learner's plan as a Tempo-sheet pace (``daily_session.Pace``)."""

    from app.services.daily_session import Pace, pace_of
    from app.services.forge_picker import forge_budget_seconds

    return Pace(
        name=pace_of(user),
        words=max(1, int(round(words_per_day))),
        rules_per_week=max(1, int(round(rules_per_week))),
        forge_seconds=forge_budget_seconds(user),
    )


def _goal(
    user: Any,
    *,
    band: str,
    goal: str | None,
    left: tuple[int, int],
    words_per_day: float,
    rules_per_week: float,
) -> dict[str, Any] | None:
    """The learner's goal level (Réglages), what stands before it, and the Tempo
    sheet's weeks to it at the learner's pace (``daily_session.goal_weeks``)."""

    from app.services.cefr_progress import level_index
    from app.services.daily_session import goal_weeks
    from app.services.level_forecast import hold_lag_days

    if goal is None:
        return None
    words_left, units_left = left
    weeks = goal_weeks(
        words_left=words_left,
        units_left=units_left,
        pace=_pace(user, words_per_day=words_per_day, rules_per_week=rules_per_week),
        hold_lag_days=hold_lag_days(),
    )
    return {
        "band": goal,
        "bands_left": max(0, level_index(goal) - level_index(band)),
        "words_left": words_left,
        "units_left": units_left,
        "weeks": round(weeks, 1),
    }


def _planned_minutes(user: Any, *, words_per_day: float, rules_per_week: float) -> int:
    """The Tempo sheet's arithmetic for this learner's plan, once the reviews have built up."""

    from app.services.daily_session import DEFAULT_SCENE_SECONDS, pace_option

    option = pace_option(
        _pace(user, words_per_day=words_per_day, rules_per_week=rules_per_week),
        scene_seconds=DEFAULT_SCENE_SECONDS,
        reviews_due=0,
        words_left=0,
        units_left=0,
        hold_lag_days=0,
    )
    return int(option["minutes_week_8"])


def _time(
    db: Session,
    user: Any,
    *,
    forecast: dict[str, Any] | None,
    band_since: datetime | None,
    words_per_day: float,
    rules_per_week: float,
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(time, invested)``: the days left and what they cost; the time already put in."""

    from app.services.daily_session import pace_of, stored_pace

    # No band closed below the one in force: everything since the learner began.
    in_band = practice_time(db, user, since=band_since or EPOCH, until=now + timedelta(seconds=1))
    recent = practice_time(
        db, user, since=now - timedelta(days=MINUTES_WINDOW_DAYS), until=now + timedelta(seconds=1)
    )
    measured_minutes = recent["total_seconds"] / 60.0 / MINUTES_WINDOW_DAYS
    planned_minutes = _planned_minutes(user, words_per_day=words_per_day, rules_per_week=rules_per_week)

    fc = forecast if isinstance(forecast, dict) else {}
    status = {"available": "measured", "prior": "plan"}.get(str(fc.get("status") or ""), "none")
    capped = bool(fc.get("capped"))
    range_days = [int(value) for value in (fc.get("range_days") or [])][:2] if status != "none" else []
    if status == "measured" and measured_minutes >= 1:
        minutes_per_day, minutes_source = int(round(measured_minutes)), "measured"
    else:
        minutes_per_day, minutes_source = planned_minutes, "plan"
    hours: list[int] | None = None
    if len(range_days) == 2 and not capped and minutes_per_day > 0:
        hours = [
            max(1, int(round(range_days[0] * minutes_per_day / 60))),
            max(1, int(round(range_days[1] * minutes_per_day / 60))),
        ]
    time = {
        "status": status,
        "range_days": range_days if len(range_days) == 2 else None,
        "dates": list(fc.get("projected_dates") or [])[:2] or None,
        "capped": capped,
        "earliest_days": fc.get("earliest_days"),
        "earliest_on": fc.get("earliest_date"),
        "minutes_per_day": minutes_per_day,
        "minutes_source": minutes_source,
        "planned_minutes_per_day": planned_minutes,
        "hours": hours,
        "active_days_required": int((fc.get("basis") or {}).get("active_days_required") or 7),
        "active_days": int((fc.get("basis") or {}).get("active_days") or 0),
        "pace": pace_of(user),
        "pace_chosen": stored_pace(user) is not None,
        "words_per_day": int(round(words_per_day)),
        "rules_per_week": round(float(rules_per_week), 2),
    }
    invested = {
        "band_since": _iso_day(band_since),
        "band_minutes": int(in_band["total_seconds"] // 60),
        "band_days": len(in_band["days"]),
        "scenes_minutes": int(in_band["scenes_seconds"] // 60),
        "forge_minutes": int(in_band["forge_seconds"] // 60),
        "words_minutes": int(in_band["words_seconds"] // 60),
        "recent_minutes_per_day": round(measured_minutes, 1),
    }
    return time, invested


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------


def build_level_plan(db: Session, user: User, *, now: datetime | None = None) -> dict[str, Any]:
    """The learner's level plan (module docstring). Read-only."""

    from app.services import level_checkpoint as checkpoints
    from app.services.cefr_progress import (
        DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
        CEFRProgressService,
        level_index,
        live_level,
        next_cefr_level,
        with_can_do_line,
    )
    from app.services.level_coverage import band_unit_ids, lemma_states
    from app.services.level_forecast import planned_intake

    now = _aware(now) or datetime.now(UTC)
    service = CEFRProgressService(db)
    payload = with_can_do_line(db, user, live_level(db, user, write_first=False, service=service))
    band = str(payload.get("estimate") or "A1.1")
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    lemmas = service.lemmas
    if lemmas is None:
        lemmas = lemma_states(db, user, now=now)
    unit_ids = (
        [int(unit) for unit in service.coverage.unit_ids]
        if service.coverage is not None and service.coverage.band == band
        else band_unit_ids(db, band)
    )
    words_per_day, rules_per_week = planned_intake(user)
    rows = checkpoints.rows_by_band(db, user.id)
    raw_goal = str(getattr(user, "cefr_target_level", None) or "").strip().upper()
    goal = raw_goal if raw_goal and level_index(raw_goal) > level_index(band) else None
    ladder, band_since = _ladder(rows, band=band, goal=goal)
    time, invested = _time(
        db,
        user,
        forecast=payload.get("forecast"),
        band_since=band_since,
        words_per_day=words_per_day,
        rules_per_week=rules_per_week,
        now=now,
    )
    skills, goal_left = _skills(db, user, lemmas=lemmas, band=band, goal=goal)
    breakdown = payload.get("breakdown") if isinstance(payload.get("breakdown"), dict) else {}
    signals = payload.get("signals") if isinstance(payload.get("signals"), dict) else {}
    estimate_source = str(payload.get("estimate_source") or "measured")
    percent = int(coverage.get("percent") or 0)
    return {
        "version": LEVEL_PLAN_VERSION,
        "generated_at": now.isoformat(),
        "band": band,
        "next_band": next_cefr_level(band),
        "percent": percent,
        "label": str(coverage.get("label") or payload.get("level_label") or band),
        "estimate_source": estimate_source,
        # WP-25: a declared or placed level is not what the app has verified.
        "verified": str(breakdown.get("status") or estimate_source) == "measured",
        "placement_taken_at": (payload.get("placement") or {}).get("taken_at")
        if isinstance(payload.get("placement"), dict)
        else None,
        "goal": _goal(
            user,
            band=band,
            goal=goal,
            left=goal_left,
            words_per_day=words_per_day,
            rules_per_week=rules_per_week,
        ),
        "ladder": ladder,
        "rules": _rules(
            db, user, unit_ids=unit_ids, coverage=coverage, rules_per_week=rules_per_week, now=now
        ),
        "words": _words(band=band, coverage=coverage, lemmas=lemmas, words_per_day=words_per_day),
        "epreuve": _epreuve(payload.get("checkpoint"), band),
        "time": time,
        "invested": invested,
        "skills": skills,
        # WP-45: what turns a declared or placed level into a measured one.
        "evidence": {
            "attempts_required": DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
            "attempts_counted": int(signals.get("recent_attempt_count") or 0),
        },
        "can_dos": {
            "stamped": int(payload.get("can_dos_stamped") or 0),
            "total": int(payload.get("can_dos_total") or 0),
            "next": payload.get("next_can_do"),
        },
    }


__all__ = [
    "LEVEL_PLAN_VERSION",
    "WORD_GAP_CEILING_SECONDS",
    "build_level_plan",
    "practice_time",
]
