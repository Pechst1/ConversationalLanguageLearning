"""WP-L6 — the vocabulary pace: «Nouveaux mots par jour», one intake pool.

Owner decision 2026-09-23 (§5.1 of WORK-PACKAGES-2026-09-23-learning): the
learner sets how many new words a day they take in (``users.new_words_per_day``,
1–50), independently of the rhythm, and the day and the word drill share that
one quota:

* **one intake pool** — a word is introduced once, by the word drill or by a
  scene, and the day's quota counts both. A word is *introduced* the moment
  the learner owns a progress row for it (``UserVocabularyProgress.created_at``
  falls on their local today), plus the words today's journey planned as new
  and has not credited yet (``plan_selection["new_word_ids"]``, a reservation);
* **the journey takes its share first** — until today's journey is planned the
  drill leaves the rhythm's share of new words free for it
  (:attr:`~app.services.journey_contracts.RhythmCaps.journey_new_words`);
  once it is planned, its actual new words are the reservation;
* **no double introduction** — the drill never offers a word the journey has
  reserved, and the journey never meets a word the drill introduced as new
  (it has a progress row, so it is a review).

The auto-throttle (§2.2: intake halves when the backlog outgrows capacity or
accuracy drops) lives in :mod:`app.services.intake_throttle`;
:func:`intake_throttle_factor` is its door here. It halves the learner's own
quota *and* the journey's rhythm share of it.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.progress import UserVocabularyProgress
from app.services.journey_contracts import rhythm_caps
from app.services.journey_rhythm import budget_seconds_for
from app.services.streak import local_today, user_timezone

DEFAULT_NEW_WORDS_PER_DAY = 10
#: 2026-10-03 (owner): the rhythm sets the default daily intake; a learner's own
#: ``new_words_per_day`` setting still wins, and the throttle still halves it.
RHYTHM_NEW_WORDS: dict[str, int] = {"leger": 5, "regulier": 10, "soutenu": 18, "intensif": 30}
#: The plan_selection key holding the vocabulary ids today's journey introduces.
JOURNEY_NEW_WORDS_KEY = "new_word_ids"
#: §5.1's honest cost, as a planning prior: each new word a day costs about
#: eight to ten reviews a day once the schedule reaches its steady state
#: (≈ 150–200 reviews at 20 new words). An estimate, labelled as one.
REVIEWS_PER_NEW_WORD_LOW = 8
REVIEWS_PER_NEW_WORD_HIGH = 10
#: §5.1's own arithmetic (150–200 reviews ≈ 15–20 min): about six seconds a review.
SECONDS_PER_REVIEW = 6


def intake_throttle_factor(db: Session, user: Any, *, now: datetime | None = None) -> float:
    """WP-L6 auto-throttle: the multiplier on today's new intake (1.0 = none).

    §2.2: when the due backlog exceeds 1.5 days of review capacity, new intake
    halves until it recovers (with hysteresis) and the learner reads «Cette
    semaine, on consolide.» WP-131: 7-day review accuracy scales intake
    continuously, from full at 85 % to half at 70 %, so an average learner's
    intake no longer swings on noise. See :mod:`app.services.intake_throttle`.
    """

    from app.services.intake_throttle import throttle_factor

    return throttle_factor(db, user, now=now)


def journey_word_share(user: Any, factor: float = 1.0) -> int:
    """The rhythm's share of new words for the day, throttled."""

    share = rhythm_caps(budget_seconds_for(user)).journey_new_words
    if factor >= 1.0:
        return share
    return max(1, int(share * max(0.0, factor))) if share else 0


def daily_quota(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """The day's dose: the new words the learner's own number (or pace) brings
    today, throttled, all surfaces together. The day deck and Home count this;
    the ceiling on introductions is :func:`effective_new_word_cap`."""

    return effective_new_word_cap(db, user, now=now, extras=False)


#: Owner request, 2 Nov 2026: «Noch 5 neue Wörter» — one tap adds this many new
#: words to today's cap, after the day's deck (and after the day, on Fertig).
EXTRA_WORDS_STEP = 5
#: A day's extras stop here: ten taps, a long day's worth on top of any pace.
MAX_EXTRA_NEW_WORDS = 50


def extra_new_words_today(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """The new words the learner asked for today on top of their own number."""

    from app.services import drill_batch

    if not getattr(user, "id", None):
        return 0
    batch = drill_batch.load_batch(db, user, local_today(user, now or datetime.now(UTC)))
    return max(0, int(getattr(batch, "extra_new_words", 0) or 0)) if batch is not None else 0


def effective_new_word_cap(
    db: Session,
    user: Any,
    *,
    now: datetime | None = None,
    factor: float | None = None,
    extras: bool = True,
) -> int:
    """How many new words this learner may take in today: the one answer.

    The day's dose (their own number or pace, throttled) plus the extras they
    asked for today («Noch 5 neue Wörter»). Every room for new words — the word
    drill's, the journey's — is this cap less what today already introduced.
    The extras are the learner's explicit choice, so the throttle never halves
    them. ``factor``: the throttle already read by the caller.

    ``extras=False`` is the day's dose alone: the day deck's plan
    (``day_words.make_plan`` → ``plan["quota"]``) and Home's count take it, so
    the extras are always the learner's continuation after the day's deck,
    never part of the day's count.
    """

    if factor is None:
        factor = intake_throttle_factor(db, user, now=now)
    dose = _quota(user, factor)
    return dose + extra_new_words_today(db, user, now=now) if extras else dose


def extra_words_available(db: Session, user: Any, *, limit: int, now: datetime | None = None) -> int:
    """How many new words the word drill could still deal today, up to ``limit``.

    Asks the deck's own reader (``ProgressService.get_vocabulary_recommendations``)
    with the deck's own exclusions, so the number is the pool the extra deck will
    draw from, never a second opinion about it.
    """

    from app.services import drill_batch
    from app.services.progress import ProgressService

    if limit <= 0 or not getattr(user, "id", None):
        return 0
    now = now or datetime.now(UTC)
    _room, reserved = drill_new_word_room(db, user, now=now)
    exclude = set(reserved)
    batch = drill_batch.load_batch(db, user, local_today(user, now))
    if batch is not None:
        exclude |= {int(item["word_id"]) for item in batch.items or [] if item.get("list") == "new_words"}
    stored = getattr(user, "default_vocab_direction", None)
    recommendations = ProgressService(db).get_vocabulary_recommendations(
        user=user,
        limit=limit,
        due_limit=0,
        fragile_limit=0,
        new_limit=limit,
        direction=stored if stored in {"fr_to_de", "de_to_fr"} else None,
        now=now,
        exclude_new_word_ids=exclude,
    )
    return sum(1 for item in recommendations["items"] if item.get("bucket") == "new")


def next_extra_step(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """#563: the new words the next «Noch 5 neue Wörter» tap really brings.

    :data:`EXTRA_WORDS_STEP`, less what the day's last step leaves
    (:data:`MAX_EXTRA_NEW_WORDS`), less what the pool cannot supply. The one
    number of the extras: the button's label, the grant (the cap, so the deck's
    room) and the goal line's «Mit N Wörtern am Tag» all read it, so the offer
    cannot promise five and deal one. ``0``: nothing to offer.
    """

    step = min(EXTRA_WORDS_STEP, MAX_EXTRA_NEW_WORDS - extra_new_words_today(db, user, now=now))
    return extra_words_available(db, user, limit=step, now=now) if step > 0 else 0


def grant_extra_new_words(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """One «Noch 5 neue Wörter» tap: today's extras grow by :func:`next_extra_step`
    (at most :data:`EXTRA_WORDS_STEP`, up to :data:`MAX_EXTRA_NEW_WORDS`, and never
    past what the pool can deal). Returns today's extras. Flushes, never commits.

    The extras live on the day's batch row (one per learner and day), so they
    start from zero every day and a reload never grants twice: only this call
    raises them.
    """

    from app.services import day_words, drill_batch

    now = now or datetime.now(UTC)
    day = local_today(user, now)
    batch = day_words.ensure_plan(db, user, now=now, commit=False) or drill_batch.load_batch(db, user, day)
    if batch is None:
        batch = drill_batch.save_batch(db, user, day, [], new_limit=0, new_dealt=0, batch=None)
    if batch is None:
        return 0
    current = max(0, int(batch.extra_new_words or 0))
    batch.extra_new_words = min(MAX_EXTRA_NEW_WORDS, current + next_extra_step(db, user, now=now))
    db.flush([batch])
    return int(batch.extra_new_words)


def is_extra_new_word(db: Session, user: Any, word_id: int, *, now: datetime | None = None) -> bool:
    """Was ``word_id`` introduced today past the day's dose, inside the extras the
    learner asked for? The words introduced today, in the order they were met,
    fill the dose first (the scene's words included); the next ones, up to
    today's extras, are the extra words that earn their own gold."""

    now = now or datetime.now(UTC)
    extras = extra_new_words_today(db, user, now=now)
    if extras <= 0:
        return False
    start, end = _local_window(user, now)
    rows = db.execute(
        select(UserVocabularyProgress.word_id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.created_at >= start,
            UserVocabularyProgress.created_at < end,
        )
        .order_by(UserVocabularyProgress.created_at, UserVocabularyProgress.id)
    ).all()
    order = [int(row[0]) for row in rows if row[0] is not None]
    if int(word_id) not in order:
        return False
    dose = daily_quota(db, user, now=now)
    return dose <= order.index(int(word_id)) < dose + extras


def planned_new_words(user: Any) -> int:
    """The day's new words as planned, before the throttle: the forecast's prior."""

    return _quota(user, 1.0)


def _quota(user: Any, factor: float) -> int:
    from app.services.daily_session import pace_words
    from app.services.journey_rhythm import rhythm_of

    # Round 3: a pace picked on the Tempo sheet sets the day's words.
    raw = pace_words(user) or getattr(user, "new_words_per_day", None)
    quota = int(raw) if raw else RHYTHM_NEW_WORDS.get(rhythm_of(user), DEFAULT_NEW_WORDS_PER_DAY)
    return max(0, int(quota * factor))


def _local_window(user: Any, now: datetime) -> tuple[datetime, datetime]:
    zone = ZoneInfo(user_timezone(user))
    day = local_today(user, now)
    start = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
    return start, start + timedelta(days=1)


def introduced_today(db: Session, user: Any, *, now: datetime | None = None) -> set[int]:
    """Word ids whose progress row was created on the learner's local today."""

    now = now or datetime.now(UTC)
    start, end = _local_window(user, now)
    rows = db.execute(
        select(UserVocabularyProgress.word_id).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.created_at >= start,
            UserVocabularyProgress.created_at < end,
        )
    ).all()
    return {int(row[0]) for row in rows if row[0] is not None}


DEFAULT_MAX_REVIEWS_PER_DAY = 200


def reviews_left_today(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """WP-115a: how many word reviews the learner's own cap still allows today
    (Anki's «Maximum reviews/day»): the cap minus today's review log, all surfaces."""

    from sqlalchemy import func

    from app.db.models.progress import ReviewLog

    now = now or datetime.now(UTC)
    cap = int(getattr(user, "max_reviews_per_day", None) or DEFAULT_MAX_REVIEWS_PER_DAY)
    start, end = _local_window(user, now)
    done = db.execute(
        select(func.count(ReviewLog.id))
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            ReviewLog.review_date >= start,
            ReviewLog.review_date < end,
        )
    ).scalar_one()
    return max(0, cap - int(done or 0))


def todays_journey(db: Session, user: Any, *, now: datetime | None = None) -> DailyJourney | None:
    now = now or datetime.now(UTC)
    return db.execute(
        select(DailyJourney).where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date == local_today(user, now),
        )
    ).scalars().first()


def journey_reservation(
    db: Session, user: Any, *, now: datetime | None = None
) -> tuple[bool, set[int]]:
    """``(planned, word_ids)``: has today's journey been planned, and which
    new words it introduces."""

    journey = todays_journey(db, user, now=now)
    selection = dict(getattr(journey, "plan_selection", None) or {}) if journey else {}
    if JOURNEY_NEW_WORDS_KEY not in selection:
        return False, set()
    ids: set[int] = set()
    for value in selection.get(JOURNEY_NEW_WORDS_KEY) or []:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return True, ids


def journey_new_word_room(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """How many new words today's journey may introduce: what the quota has
    left after everything already introduced today."""

    factor = intake_throttle_factor(db, user, now=now)
    cap = effective_new_word_cap(db, user, now=now, factor=factor)
    room = max(0, cap - len(introduced_today(db, user, now=now)))
    if factor < 1.0:
        room = min(room, journey_word_share(user, factor))
    return room


def drill_new_word_room(
    db: Session, user: Any, *, now: datetime | None = None
) -> tuple[int, set[int]]:
    """``(room, excluded_word_ids)`` for the word drill.

    The drill gets what the quota leaves after today's introductions and the
    journey's share — its reservation once planned, its rhythm's share before.
    ``excluded_word_ids`` are the journey's reserved words: never offered as
    new by the drill.
    """

    factor = intake_throttle_factor(db, user, now=now)
    quota = effective_new_word_cap(db, user, now=now, factor=factor)
    introduced = introduced_today(db, user, now=now)
    planned, reserved = journey_reservation(db, user, now=now)
    taken = len(introduced | reserved)
    pending = 0 if planned else min(quota, journey_word_share(user, factor))
    return max(0, quota - taken - pending), reserved - introduced


def review_load_estimate(new_words_per_day: int) -> dict[str, int]:
    """The steady-state review load a vocabulary pace costs — an estimate."""

    words = max(0, int(new_words_per_day))
    low = words * REVIEWS_PER_NEW_WORD_LOW
    high = words * REVIEWS_PER_NEW_WORD_HIGH
    return {
        "reviews_low": low,
        "reviews_high": high,
        "minutes_low": round(low * SECONDS_PER_REVIEW / 60),
        "minutes_high": round(high * SECONDS_PER_REVIEW / 60),
    }




def vocabulary_pace_limit(db: Session, user: Any, requested: int) -> tuple[int, set[int]]:
    """The word drill's ``new_limit``, clamped to the learner's pace.

    ``(min(requested, room), reserved_ids)``. A pace that cannot be read (a
    demo account, a broken read) leaves the request as it was: the pace is a
    ceiling, never a reason to lose the deck.
    """

    limit, reserved, _room = vocabulary_pace_allowance(db, user, requested)
    return limit, reserved


#: WP-131 (owner decision 9): one drill session introduces at most this many new
#: words (``pages/vocabulary/review.tsx`` asks for it). What the day's allowance
#: still holds after it is offered as an explicit, bounded continuation («Encore
#: N mots»), never forced into one long session.
DRILL_SESSION_NEW_WORDS = 8


def vocabulary_pace_allowance(
    db: Session, user: Any, requested: int
) -> tuple[int, set[int], int | None]:
    """``(new_limit, reserved_ids, room)`` for the word drill.

    ``room`` is what the day's allowance leaves the drill right now (the quota,
    throttled, minus today's introductions and the journey's reservation or
    pending share); ``None`` when it was not read — a review-only request
    («Encore 5 minutes», ``requested == 0``), a demo account, a broken read.
    """

    if not getattr(user, "id", None) or requested <= 0:
        return max(0, requested), set(), None
    try:
        with db.begin_nested():
            room, reserved = drill_new_word_room(db, user)
    except Exception:  # noqa: BLE001 - the deck is worth more than the ceiling
        return requested, set(), None
    return min(requested, room), reserved, room


def new_words_left_today(room: int | None, new_limit: int, served: int) -> int | None:
    """WP-131: what the day's allowance still holds after this deck's new words.

    ``None`` when the room was not read. ``0`` when the deck served fewer new
    words than it was allowed: the supply ran out, so a continuation would be
    an empty deck.
    """

    if room is None:
        return None
    if served < new_limit:
        return 0
    return max(0, room - served)


__all__ = [
    "DEFAULT_NEW_WORDS_PER_DAY",
    "DRILL_SESSION_NEW_WORDS",
    "EXTRA_WORDS_STEP",
    "JOURNEY_NEW_WORDS_KEY",
    "MAX_EXTRA_NEW_WORDS",
    "daily_quota",
    "drill_new_word_room",
    "effective_new_word_cap",
    "extra_new_words_today",
    "extra_words_available",
    "grant_extra_new_words",
    "intake_throttle_factor",
    "introduced_today",
    "is_extra_new_word",
    "journey_new_word_room",
    "journey_reservation",
    "journey_word_share",
    "new_words_left_today",
    "next_extra_step",
    "planned_new_words",
    "review_load_estimate",
    "todays_journey",
    "vocabulary_pace_allowance",
    "vocabulary_pace_limit",
]
