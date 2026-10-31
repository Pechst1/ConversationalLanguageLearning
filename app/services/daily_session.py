"""Round 3 (owner, 2026-10-14): the day as one sequence, with a real daily dose.

«One daily sequence: the photo scene, then words, then grammar. Words and La
Forge are part of the day, not extras. Only after the day's quota is done can
the learner choose to keep going.» And: «Work the daily dose backward from my
level goal … Let the learner pick a pace and show what each pace costs.»

The day is four steps, always in this order:

1. **Szene** — today's journey (or Le Papier on a news day). Its answer to the
   character stays inside it: nothing comes between a character's question and
   the reply.
2. **Wörter** — the day's new words at the learner's pace plus the reviews due,
   the scene's words first (they were introduced by the scene).
3. **Grammatik** — one La Forge séance on the day's rule.
4. **Fertig** — the seal and what the day held. Only now «Noch 10 Wörter».

The pace (:data:`PACES`) is worked back from the level goal. A band is covered
at 80 % of its words and 85 % of its grammar units (``level_coverage``); a unit
counts as held only after unaided use on two days a week apart, about four weeks
after its introduction (``level_forecast.hold_lag_days``). So the rules a week,
not the words, decide when the goal is reached: A1 (504 words, 33 units) takes
about 15, 10½ or 8 weeks at 3, 5 or 8 rules a week.

The costs are the app's own: about 20 s a new word, 6 s a review
(``vocabulary_pace.SECONDS_PER_REVIEW``), 25 s a La Forge item
(``app.core.forge.DEFAULT_SECONDS_PER_ITEM``). A simulation with the app's FSRS
scheduler (retention 0.87) puts the reviews eight weeks in at about 2.85 a day
per daily new word: 57 a day at Normal's 20.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PaceName = Literal["ruhig", "normal", "schnell"]


@dataclass(frozen=True, slots=True)
class Pace:
    name: PaceName
    #: New words a day, the word step and the scene together (one intake pool).
    words: int
    #: New grammar units a week (``concept_life.weekly_concept_rate``).
    rules_per_week: int
    #: One La Forge séance's budget: 12 items at 300 s, 17 at 420 s.
    forge_seconds: int


PACES: dict[PaceName, Pace] = {
    "ruhig": Pace("ruhig", words=10, rules_per_week=3, forge_seconds=300),
    "normal": Pace("normal", words=20, rules_per_week=5, forge_seconds=300),
    "schnell": Pace("schnell", words=40, rules_per_week=8, forge_seconds=420),
}
PACE_NAMES: tuple[PaceName, ...] = ("ruhig", "normal", "schnell")
#: New learners start here (owner, 2026-10-14: Normal unless they say otherwise).
DEFAULT_PACE: PaceName = "normal"

SECONDS_PER_NEW_WORD = 20
#: Reviews a day, eight weeks in, per daily new word (FSRS simulation, see above).
REVIEWS_PER_NEW_WORD_WEEK_8 = 2.85
#: The words a learner keeps (the scheduler's retention).
WORD_RETENTION = 0.87
#: The scene's minutes before today's estimate exists.
DEFAULT_SCENE_SECONDS = 8 * 60
#: «Noch 10 Wörter» after the day.
MORE_WORDS = 10
#: One day deck holds at most this many cards, new words and reviews together
#: (``pages/vocabulary/review.tsx`` asks for it as ``limit``); the reviews past it
#: come tomorrow, the new words are never the ones left out (#279).
DAY_DECK_LIMIT = 100
#: The day deck asks for up to this many new words (``review.tsx``'s ``DAY_DECK_NEW_WORDS``).
DAY_DECK_NEW_WORDS = 50

WORDS_HREF = "/vocabulary/review?day=1"
MORE_WORDS_HREF = f"/vocabulary/review?more={MORE_WORDS}"
FINISH_HREF = "/fertig"
#: The plan_selection key that records the word step as done today.
SESSION_KEY = "session"


# ---------------------------------------------------------------------------
# The pace
# ---------------------------------------------------------------------------


def stored_pace(user: Any) -> PaceName | None:
    value = str(getattr(user, "daily_pace", None) or "").strip().lower()
    return value if value in PACES else None  # type: ignore[return-value]


def pace_for_words(words: int | None) -> PaceName:
    """The pace a stored word count is closest to (a learner who never picked one)."""

    value = int(words or 0)
    if value <= 0:
        return DEFAULT_PACE
    if value <= 14:
        return "ruhig"
    if value <= 29:
        return "normal"
    return "schnell"


def pace_of(user: Any) -> PaceName:
    return stored_pace(user) or pace_for_words(getattr(user, "new_words_per_day", None))


def pace_words(user: Any) -> int | None:
    """The day's new words when the learner picked a pace, else ``None``."""

    name = stored_pace(user)
    return PACES[name].words if name else None


def pace_rules_per_week(user: Any) -> int | None:
    name = stored_pace(user)
    return PACES[name].rules_per_week if name else None


def pace_forge_seconds(user: Any) -> int | None:
    name = stored_pace(user)
    return PACES[name].forge_seconds if name else None


def forge_items(forge_seconds: int) -> int:
    from app.core.forge import DEFAULT_SECONDS_PER_ITEM, seance_length

    return seance_length(forge_seconds, DEFAULT_SECONDS_PER_ITEM)


def words_seconds(new_words: int, reviews: int) -> int:
    from app.services.vocabulary_pace import SECONDS_PER_REVIEW

    return max(0, int(new_words)) * SECONDS_PER_NEW_WORD + max(0, int(reviews)) * SECONDS_PER_REVIEW


def minutes(seconds: float) -> int:
    return max(1, math.ceil(float(seconds) / 60)) if seconds > 0 else 0


# ---------------------------------------------------------------------------
# The day's four steps — pure
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionInputs:
    pace: PaceName
    scene_done: bool
    scene_seconds: int
    #: The day's new words (the pace's, or the learner's own number).
    quota: int
    #: Words introduced today, every surface together.
    introduced: int
    reviews_due: int
    words_marked_done: bool
    forge_seconds: int
    forge_blocks_today: int
    forge_href: str
    exercises_today: int
    #: Distinct words reviewed today, every surface together (the end screen's «Words»).
    words_reviewed_today: int = 0
    #: ``(new, reviews)``: the cards the day deck holds right now (:func:`day_deck`).
    #: ``None`` when it could not be read: the quota less today's words, and the reviews due.
    deck: tuple[int, int] | None = None
    #: How many cards the day's deck was dealt with, the ones already answered
    #: included (:func:`dealt_deck`). ``None`` before any deck was dealt today.
    dealt: int | None = None


def review_room(new_words: int, *, reviews_left: int | None = None, deck_limit: int = DAY_DECK_LIMIT) -> int:
    """How many reviews the day deck holds next to ``new_words`` new ones (#279).

    The reviews fill what the deck's size leaves after the new words: a learner
    back from a week away has more due than a deck holds, and a deck sized by
    its reviews first dealt reviews only while Home promised new words too. None
    past the learner's own «Maximum reviews/day» (``reviews_left``; ``None``
    when it could not be read). ``GET /vocabulary/due-context?drill=session``
    deals with the same room.
    """

    room = max(0, int(deck_limit) - max(0, int(new_words)))
    if reviews_left is not None:
        room = min(room, max(0, int(reviews_left)))
    return room


def session_view(inputs: SessionInputs) -> dict[str, Any]:
    """The day's steps with their state (done / next / todo), minutes and links."""

    fallback_new = max(0, inputs.quota - inputs.introduced)
    new_left, reviews = inputs.deck or (fallback_new, min(max(0, inputs.reviews_due), review_room(fallback_new)))
    words_done = inputs.words_marked_done or (new_left == 0 and reviews == 0)
    # What was done, not what was planned: new words met or words reviewed.
    words_met = max(inputs.introduced, inputs.words_reviewed_today)
    # #396: once the deck is gone through, the step and the end screen say the
    # size of the deck that was dealt, the number the button and the review's
    # header showed. Not every word touched today: the scene's own words and La
    # Forge's reviews are not cards of this deck.
    words_done_count = inputs.dealt if inputs.dealt else words_met
    grammar_done = inputs.forge_blocks_today > 0
    items = forge_items(inputs.forge_seconds)
    raw = [
        {
            "kind": "scene",
            "done": inputs.scene_done,
            "minutes": minutes(inputs.scene_seconds),
            "href": None,
        },
        {
            "kind": "words",
            "done": words_done,
            "minutes": 0 if words_done else minutes(words_seconds(new_left, reviews)),
            "href": WORDS_HREF,
            # #153: the number the learner will meet, not the pace's target. The
            # scene already introduced some of the quota; «20 words» over a
            # deck of 17 was the plan and the screen disagreeing. #143: every
            # card of the deck counts, its reviews too, and once done the step
            # says what the end screen says, not the pace's 20.
            "count": words_done_count if words_done else new_left + reviews,
            "new_left": new_left,
            "reviews": reviews,
        },
        {
            "kind": "grammar",
            "done": grammar_done,
            "minutes": 0 if grammar_done else minutes(items * 25),
            "href": inputs.forge_href,
            "count": items,
        },
    ]
    all_done = all(step["done"] for step in raw)
    steps: list[dict[str, Any]] = []
    next_seen = False
    for step in raw:
        state = "done" if step["done"] else ("todo" if next_seen else "next")
        next_seen = next_seen or state == "next"
        steps.append({key: value for key, value in step.items() if key != "done"} | {"state": state})
    steps.append(
        {
            "kind": "finish",
            "state": "done" if all_done else "todo",
            "minutes": 0,
            "href": FINISH_HREF,
        }
    )
    total = sum(step["minutes"] for step in steps if step["state"] != "done")
    return {
        "pace": inputs.pace,
        "steps": steps,
        "next_kind": next((step["kind"] for step in steps if step["state"] == "next"), None),
        "minutes_left": total,
        "done": all_done,
        "tally": {
            "scenes": 1 if inputs.scene_done else 0,
            "words": words_done_count if words_done else words_met,
            "exercises": max(0, inputs.exercises_today),
        },
        "more_words": MORE_WORDS,
        "more_minutes": minutes(words_seconds(MORE_WORDS, 0)),
        "more_href": MORE_WORDS_HREF,
    }


# ---------------------------------------------------------------------------
# What each pace costs, and when it reaches the goal — pure
# ---------------------------------------------------------------------------


def goal_weeks(
    *,
    words_left: int,
    units_left: int,
    pace: Pace,
    hold_lag_days: int,
) -> float:
    """Weeks to the goal at ``pace``: the words' and the rules' own clocks, the
    slower one. A rule introduced on the last day still needs its hold lag."""

    words_days = words_left / max(1e-9, pace.words * WORD_RETENTION) if words_left > 0 else 0.0
    units_days = (units_left / pace.rules_per_week * 7 + hold_lag_days) if units_left > 0 else 0.0
    return max(words_days, units_days) / 7


def pace_option(
    pace: Pace,
    *,
    scene_seconds: int,
    reviews_due: int,
    grammar_seconds_override: int | None = None,
    words_left: int,
    units_left: int,
    hold_lag_days: int,
) -> dict[str, Any]:
    grammar = forge_items(grammar_seconds_override or pace.forge_seconds) * 25
    reviews = min(max(0, reviews_due), DAY_DECK_LIMIT)
    today = scene_seconds + words_seconds(pace.words, reviews) + grammar
    week8_reviews = round(pace.words * REVIEWS_PER_NEW_WORD_WEEK_8)
    week8 = scene_seconds + words_seconds(pace.words, week8_reviews) + grammar
    return {
        "pace": pace.name,
        "words": pace.words,
        "rules_per_week": pace.rules_per_week,
        "exercises": forge_items(pace.forge_seconds),
        "minutes_today": minutes(today),
        "minutes_week_8": max(minutes(today), minutes(week8)),
        "reviews_week_8": week8_reviews,
        "goal_weeks": round(goal_weeks(words_left=words_left, units_left=units_left, pace=pace, hold_lag_days=hold_lag_days), 1),
    }


# ---------------------------------------------------------------------------
# Reading the learner's day
# ---------------------------------------------------------------------------


def _local_window(user: Any, now: datetime) -> tuple[datetime, datetime]:
    from app.services.vocabulary_pace import _local_window as window

    return window(user, now)


def exercises_today(db: Session, user: Any, *, now: datetime | None = None) -> int:
    from app.db.models.atelier import AtelierAttempt

    now = now or datetime.now(UTC)
    start, end = _local_window(user, now)
    return int(
        db.execute(
            select(func.count(AtelierAttempt.id)).where(
                AtelierAttempt.user_id == user.id,
                AtelierAttempt.created_at >= start,
                AtelierAttempt.created_at < end,
            )
        ).scalar_one()
        or 0
    )


def words_reviewed_today(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """Distinct words with a review logged on the learner's local today."""

    from app.db.models.progress import ReviewLog
    from app.db.models.progress import UserVocabularyProgress as Progress

    now = now or datetime.now(UTC)
    start, end = _local_window(user, now)
    return int(
        db.execute(
            select(func.count(func.distinct(Progress.word_id)))
            .select_from(ReviewLog)
            .join(Progress, ReviewLog.progress_id == Progress.id)
            .where(Progress.user_id == user.id, ReviewLog.review_date >= start, ReviewLog.review_date < end)
        ).scalar_one()
        or 0
    )


def words_marked_done(journey: Any) -> bool:
    selection = getattr(journey, "plan_selection", None) if journey is not None else None
    session = (selection or {}).get(SESSION_KEY) if isinstance(selection, dict) else None
    return bool(isinstance(session, dict) and session.get("words_done"))


def mark_words_done(db: Session, journey: Any) -> None:
    """The word step is done for today: the learner finished the day's deck."""

    from sqlalchemy.orm.attributes import flag_modified

    selection = dict(journey.plan_selection or {})
    session = dict(selection.get(SESSION_KEY) or {})
    session["words_done"] = True
    selection[SESSION_KEY] = session
    journey.plan_selection = selection
    flag_modified(journey, "plan_selection")
    db.add(journey)
    db.flush([journey])


def day_deck(db: Session, user: Any, *, reviews_due: int, now: datetime | None = None) -> tuple[int, int]:
    """#143: ``(new, reviews)`` — the cards the day deck (``WORDS_HREF``) holds
    if it is opened now, read the way ``GET /vocabulary/due-context`` deals it.

    «Weiter: 20 Wörter» opened «0/19»: Home took the quota less today's
    introductions, while the drill also leaves out the new words today's journey
    reserved and has not introduced yet (WP-L6). The deck's own reads decide
    here: the rest of today's dealt batch and the day's words it was not dealt
    with (the batch the Lexique dealt first, eight new words, is topped up to
    the day's dose when the day deck opens it), else a fresh deal's — the
    drill's room for new words and the reviews due.
    """

    from app.services import drill_batch
    from app.services.streak import local_today
    from app.services.vocabulary_pace import drill_new_word_room, reviews_left_today

    now = now or datetime.now(UTC)
    room, reserved = drill_new_word_room(db, user, now=now)
    batch = drill_batch.load_batch(db, user, local_today(user, now))
    new_limit = min(room, DAY_DECK_NEW_WORDS)
    if batch is not None:
        remaining = drill_batch.remaining_items(db, user, list(batch.items or []), reserved_new=reserved)
        if remaining:
            new = sum(1 for item in remaining if item.get("list") == "new_words")
            top_up = drill_batch.top_up_new_words(room, batch, remaining, new_limit)
            return new + top_up, len(remaining) - new
    reviews = min(max(0, reviews_due), review_room(new_limit, reviews_left=reviews_left_today(db, user, now=now)))
    return new_limit, reviews


def dealt_deck(db: Session, user: Any, *, now: datetime | None = None) -> int | None:
    """#396: how many cards today's word deck was dealt with, answered ones included.

    ``None`` while no deck was dealt (the review was not opened today). The
    batch is what ``GET /vocabulary/due-context?drill=session`` dealt and keeps;
    its answered cards and the ones still to answer are the deck the learner
    went through, and the review's header opened on exactly that number.
    """

    from app.services import drill_batch
    from app.services.streak import local_today
    from app.services.vocabulary_pace import drill_new_word_room

    now = now or datetime.now(UTC)
    batch = drill_batch.load_batch(db, user, local_today(user, now))
    items = list(batch.items or []) if batch is not None else []
    if not items:
        return None
    _room, reserved = drill_new_word_room(db, user, now=now)
    answered = drill_batch.answered_word_ids(db, user, items)
    remaining = drill_batch.remaining_items(db, user, items, reserved_new=reserved)
    return len(answered) + len(remaining) or None


def _dealt_deck_or_none(db: Session, user: Any, *, now: datetime) -> int | None:
    if not getattr(user, "id", None):
        return None
    try:
        with db.begin_nested():
            return dealt_deck(db, user, now=now)
    except Exception:  # noqa: BLE001 - a count that cannot be read never costs Home its day
        logger.warning("daily_session: the dealt deck could not be read", exc_info=True)
        return None


def _day_deck_or_none(db: Session, user: Any, *, reviews_due: int, now: datetime) -> tuple[int, int] | None:
    if not getattr(user, "id", None):
        return None
    try:
        with db.begin_nested():
            return day_deck(db, user, reviews_due=reviews_due, now=now)
    except Exception:  # noqa: BLE001 - a count that cannot be read never costs Home its day
        logger.warning("daily_session: the day deck could not be read", exc_info=True)
        return None


def build_session(
    db: Session,
    user: Any,
    *,
    journey: Any,
    scene_done: bool,
    scene_seconds: int | None,
    reviews_due: int,
    forge_href: str,
    forge_blocks_today: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    from app.services.forge_picker import forge_budget_seconds
    from app.services.vocabulary_pace import daily_quota, introduced_today

    now = now or datetime.now(UTC)
    return session_view(
        SessionInputs(
            pace=pace_of(user),
            scene_done=scene_done,
            scene_seconds=int(scene_seconds or DEFAULT_SCENE_SECONDS),
            quota=daily_quota(db, user, now=now),
            introduced=len(introduced_today(db, user, now=now)),
            reviews_due=reviews_due,
            words_marked_done=words_marked_done(journey),
            forge_seconds=forge_budget_seconds(user),
            forge_blocks_today=forge_blocks_today,
            forge_href=forge_href,
            exercises_today=exercises_today(db, user, now=now),
            words_reviewed_today=words_reviewed_today(db, user, now=now),
            deck=_day_deck_or_none(db, user, reviews_due=reviews_due, now=now),
            dealt=_dealt_deck_or_none(db, user, now=now),
        )
    )


def goal_gap(db: Session, user: Any, *, now: datetime | None = None) -> tuple[str, int, int]:
    """``(goal_band, words_left, units_left)``: what stands between the learner and
    their goal level, every band from the one in force up to the goal's last."""

    from app.services.level_coverage import (
        band_coverage,
        band_index,
        held_unit_ids,
        known_lemmas,
        next_band,
    )

    now = now or datetime.now(UTC)
    current = str(getattr(user, "cefr_estimate", None) or "A1.1")
    goal = str(getattr(user, "cefr_target_level", None) or "A1.2")
    if band_index(goal) < band_index(current):
        goal = next_band(current) or current
    held = held_unit_ids(db, user, now=now)
    known = known_lemmas(db, user, now=now)
    words_left = units_left = 0
    band: str | None = current
    while band is not None and band_index(band) <= band_index(goal):
        coverage = band_coverage(db, user, band, now=now, held=held, known=known)
        words_left += max(0, coverage.words_required - coverage.words_known)
        units_left += max(0, coverage.units_required - coverage.units_held)
        band = next_band(band)
    return goal, words_left, units_left


def pace_options(
    db: Session,
    user: Any,
    *,
    scene_seconds: int | None,
    reviews_due: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    from app.services.level_forecast import hold_lag_days

    goal, words_left, units_left = goal_gap(db, user, now=now)
    lag = hold_lag_days()
    return {
        "current": pace_of(user),
        "chosen": stored_pace(user) is not None,
        "goal": goal,
        "words_left": words_left,
        "units_left": units_left,
        "options": [
            pace_option(
                PACES[name],
                scene_seconds=int(scene_seconds or DEFAULT_SCENE_SECONDS),
                reviews_due=reviews_due,
                words_left=words_left,
                units_left=units_left,
                hold_lag_days=lag,
            )
            for name in PACE_NAMES
        ],
    }


__all__ = [
    "DEFAULT_PACE",
    "PACES",
    "PACE_NAMES",
    "Pace",
    "PaceName",
    "SessionInputs",
    "build_session",
    "day_deck",
    "dealt_deck",
    "review_room",
    "goal_gap",
    "goal_weeks",
    "mark_words_done",
    "pace_for_words",
    "pace_forge_seconds",
    "pace_of",
    "pace_option",
    "pace_options",
    "pace_rules_per_week",
    "pace_words",
    "session_view",
    "stored_pace",
    "words_marked_done",
]
