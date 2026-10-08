"""WP-99 «Pendant votre absence» — what Home can say honestly after a gap.

Three read-only projections for the today envelope and the journey snapshot,
none of which calls a model:

* :func:`absence_view` — from two missed days: how long, the scene's own
  greeting when the engine wrote one (``script_payload.absence.greeting_fr``),
  «Entre-temps» (what the cast did off-screen since the last finished day —
  ``living_story.meanwhile_since``) and the letters that went cold meanwhile;
* :func:`season_premiere_view` — the first scene of a season
  (``script_payload.season_premiere``), so Home can print «Nouvelle saison»;
* :func:`interlude_view` — the story is between seasons (``live["interlude"]``)
  and says when it returns.

Every reader is defensive: the story engine writes these keys, and a key it
has not written yet (or a malformed one) reads as ``None``, never as a 500.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User

#: From this many whole missed days, Home says «Pendant votre absence».
ABSENCE_MIN_MISSED_DAYS = 2
#: «Entre-temps» never runs longer than this.
ENTRE_TEMPS_MAX = 5
TEXT_MAX = 240


def _text(value: Any, limit: int = TEXT_MAX) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"


def _date_of(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if len(raw) >= 10:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            return None
    return None


def _active_thread(db: Session, user_id: Any):
    from app.db.models.serial import SerialThread

    return db.scalar(
        select(SerialThread)
        .where(SerialThread.user_id == user_id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
        .limit(1)
    )


def _live_state(db: Session, user_id: Any) -> dict[str, Any]:
    from app.services.living_story import STATE_KEY

    thread = _active_thread(db, user_id)
    state = thread.state if thread is not None and isinstance(thread.state, dict) else {}
    live = state.get(STATE_KEY)
    return live if isinstance(live, dict) else {}


def last_completed_day(db: Session, user_id: Any, *, before: date) -> date | None:
    """The learner's last finished journey day strictly before ``before``."""

    from app.services.journey_contracts import TERMINAL_JOURNEY_STATUSES

    return db.scalar(
        select(DailyJourney.local_date)
        .where(
            DailyJourney.user_id == user_id,
            DailyJourney.local_date < before,
            DailyJourney.status.in_(tuple(str(value) for value in TERMINAL_JOURNEY_STATUSES)),
        )
        .order_by(DailyJourney.local_date.desc())
        .limit(1)
    )


def _meanwhile_fallback(live: dict[str, Any], since: date) -> list[dict[str, Any]]:
    """``meanwhile`` ledger events dated on or after ``since`` (engine-free)."""

    rows: list[dict[str, Any]] = []
    for event in live.get("events") or []:
        if not isinstance(event, dict) or event.get("kind") != "meanwhile":
            continue
        when = _date_of(event.get("date")) or _date_of(event.get("at"))
        if when is None or when < since:
            continue
        rows.append(
            {
                "text_fr": event.get("summary_fr") or event.get("text_fr"),
                "date": when.isoformat(),
                "character_id": event.get("character_id"),
            }
        )
    return rows


def entre_temps(live: dict[str, Any], since: date) -> list[dict[str, Any]]:
    """«Entre-temps»: at most five off-screen beats dated on or after ``since``, oldest first.

    ``since`` is the last finished day, and it counts: a beat the engine wrote
    as that day's chapter turned happened after the learner left. The story's
    ``meanwhile_since`` reads strictly *after* its date, so it is asked from the
    day before.
    """

    from datetime import timedelta

    from app.services import living_story

    reader = getattr(living_story, "meanwhile_since", None)
    try:
        raw = (
            reader(live, since - timedelta(days=1))
            if callable(reader)
            else _meanwhile_fallback(live, since)
        )
    except Exception:  # pragma: no cover - the story's reader must never cost Home
        logger.exception("journey_absence: meanwhile_since failed")
        raw = _meanwhile_fallback(live, since)
    rows: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        text = _text(item.get("text_fr"))
        if not text:
            continue
        when = _date_of(item.get("date"))
        rows.append(
            {
                "text_fr": text,
                "date": when.isoformat() if when else None,
                "character_id": str(item.get("character_id") or "") or None,
            }
        )
    return rows[-ENTRE_TEMPS_MAX:]


def lapsed_letters(db: Session, user_id: Any, *, since: date, now: datetime | None = None) -> list[dict[str, Any]]:
    """Letters that went cold while the learner was away.

    Lapsed ones (``recap_payload.lapsed_at`` on or after ``since``) and open ones
    whose soft deadline has already passed (the Courrier's sweep lapses those
    the next time it opens; the absence page is read first).
    """

    from app.db.models.mission import RealWorldMission
    from app.services import story_correspondence as courrier

    now = now or datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    missions = (
        db.query(RealWorldMission)
        .filter(
            RealWorldMission.user_id == user_id,
            RealWorldMission.status.in_(["lapsed", "available", "in_progress"]),
            RealWorldMission.cadence != "weekly",
            RealWorldMission.chain_id.isnot(None),
        )
        .all()
    )
    for mission in missions:
        if mission.status == "lapsed":
            when = _date_of((mission.recap_payload or {}).get("lapsed_at"))
            if when is None or when < since:
                continue
        else:
            deadline = mission.expires_at
            if deadline is None:
                continue
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            if deadline > now or deadline.date() < since:
                continue
        name = str(courrier.correspondent_of(mission).get("name") or "").strip()
        rows.append({"mission_id": str(mission.id), "correspondent_name": name or None})
    return rows


def _scene_payload(db: Session, journey: DailyJourney | None) -> dict[str, Any]:
    if journey is None:
        return {}
    from app.services.daily_journey import _journey_story_context, _owned_engine_scene

    scene_id = _journey_story_context(journey).get("scene_id")
    if not scene_id:
        return {}
    scene = _owned_engine_scene(db, journey.user_id, scene_id)
    payload = scene.script_payload if scene is not None else None
    return payload if isinstance(payload, dict) else {}


def absence_view(
    db: Session,
    *,
    user_id: Any,
    local_date: date,
    missed_days: int,
    journey: DailyJourney | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """``{days, greeting_fr, entre_temps, lapsed_letters}`` from two missed days, else ``None``."""

    if int(missed_days or 0) < ABSENCE_MIN_MISSED_DAYS:
        return None
    user = db.get(User, user_id)
    fallback = getattr(user, "grammar_last_review_date", None) if user is not None else None
    since = last_completed_day(db, user_id, before=local_date) or _date_of(fallback)
    if since is None:
        from datetime import timedelta

        since = local_date - timedelta(days=int(missed_days) + 1)
    absence = _scene_payload(db, journey).get("absence")
    greeting = _text(absence.get("greeting_fr")) if isinstance(absence, dict) else ""
    return {
        "days": int(missed_days),
        "greeting_fr": greeting or None,
        "entre_temps": entre_temps(_live_state(db, user_id), since),
        "lapsed_letters": lapsed_letters(db, user_id, since=since, now=now),
    }


def season_premiere_view(db: Session, journey: DailyJourney | None) -> dict[str, Any] | None:
    """``{number, title_fr, logline_fr}`` when today's scene opens a season."""

    premiere = _scene_payload(db, journey).get("season_premiere")
    if not isinstance(premiere, dict):
        return None
    try:
        number = int(premiere.get("number"))
    except (TypeError, ValueError):
        return None
    title = _text(premiere.get("title_fr"), 120)
    if number <= 0 or not title:
        return None
    return {"number": number, "title_fr": title, "logline_fr": _text(premiere.get("logline_fr")) or None}


def interlude_view(db: Session, user_id: Any) -> dict[str, Any] | None:
    """``{returns_on, reason_fr}`` while the story is between seasons, else ``None``."""

    interlude = _live_state(db, user_id).get("interlude")
    if not isinstance(interlude, dict):
        return None
    returns_on = _date_of(interlude.get("returns_on"))
    reason = _text(interlude.get("reason_fr"))
    if returns_on is None and not reason:
        return None
    return {"returns_on": returns_on.isoformat() if returns_on else None, "reason_fr": reason or None}


def story_frame_fields(
    db: Session,
    *,
    user_id: Any,
    local_date: date,
    missed_days: int,
    journey: DailyJourney | None,
) -> dict[str, Any]:
    """The three fields together; each one ``None`` when it cannot be read."""

    from app.db.savepoint import run_best_effort

    return {
        "absence": run_best_effort(
            db,
            "journey_absence: absence",
            lambda: absence_view(
                db, user_id=user_id, local_date=local_date, missed_days=missed_days, journey=journey
            ),
            default=None,
        ),
        "season_premiere": run_best_effort(
            db, "journey_absence: season premiere", lambda: season_premiere_view(db, journey), default=None
        ),
        "interlude": run_best_effort(
            db, "journey_absence: interlude", lambda: interlude_view(db, user_id), default=None
        ),
    }


__all__ = [
    "ABSENCE_MIN_MISSED_DAYS",
    "ENTRE_TEMPS_MAX",
    "absence_view",
    "entre_temps",
    "interlude_view",
    "lapsed_letters",
    "season_premiere_view",
    "story_frame_fields",
]
