"""WP-L6 §2.2 — the auto-throttle: «Cette semaine, on consolide.»

When the reviews outgrow the time the learner gives them, new intake halves
until they catch up. Two signals, both read from what the learner really did:

* **due backlog vs capacity** — everything the unified queue has due now
  (words, grammar units, errata, conjugations), costed in seconds, against one
  day of *review capacity*:

  - the séance's Rappel, :data:`RAPPEL_SHARE` (≈ 35 %, §2.1) of the rhythm's
    budget, and
  - the word drill the learner signed up for with «Nouveaux mots par jour»:
    the honest cost the setting shows (``new_words_per_day`` ×
    :data:`~app.services.vocabulary_pace.REVIEWS_PER_NEW_WORD_HIGH` reviews ×
    :data:`~app.services.vocabulary_pace.SECONDS_PER_REVIEW`).

  A due word costs a drill review (6 s — word reviews live mostly in the word
  drill, §5.1); a unit, an erratum and a conjugation cost their Rappel item
  (``RAPPEL_ITEM_SECONDS``: 40 / 25 / 20 s).
* **7-day review accuracy** — the share of word reviews over the last seven
  days not rated *Again* (``review_logs``: 0 is Again on both schedulers).
  Grammar keeps no per-review log, so it enters through the backlog (a lapse
  makes the unit due tomorrow). Fewer than :data:`ACCURACY_MIN_REVIEWS`
  reviews say nothing.

**Hysteresis** — the throttle engages above 1.5 days of backlog or below 80 %
accuracy, and releases only once the backlog is back to ≤ 1 day *and* accuracy
is ≥ 85 % (or unmeasured), and not before it has held for
:data:`MIN_HOLD_DAYS`. So a learner who clears the pile at 1.4 days does not
flip back and forth every morning.

**State** is the learner's last ``intake_throttle`` pilot event
(``payload.state`` = ``on`` / ``off``): every change writes one, which is both
the pilot's record and the hysteresis memory — no column, no migration.

While engaged, :func:`intake_throttle_factor` is :data:`THROTTLE_FACTOR` (0.5):
the vocabulary pace (the owner's up-to-20 words a day and the journey's rhythm
share) and the grammar quota (``concept_life`` → ``forge_plan``) both halve.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import ReviewLog, UserVocabularyProgress

#: The multiplier on new intake while the throttle is engaged («halves»).
THROTTLE_FACTOR = 0.5
#: Engage above this many days of review capacity due…
BACKLOG_ENTER_DAYS = 1.5
#: …release only at or below this many.
BACKLOG_EXIT_DAYS = 1.0
#: Engage below this 7-day review accuracy…
ACCURACY_ENTER = 0.80
#: …release only at or above this one.
ACCURACY_EXIT = 0.85
ACCURACY_WINDOW_DAYS = 7
#: Below this many reviews in the window, accuracy is not measured.
ACCURACY_MIN_REVIEWS = 20
#: Once engaged, the throttle holds at least this long («cette semaine»).
MIN_HOLD_DAYS = 3
#: §2.1 — the Rappel's share of the séance's budget.
RAPPEL_SHARE = 0.35

EVENT_TYPE = "intake_throttle"


@dataclass(frozen=True)
class ThrottleSignals:
    backlog_seconds: int
    capacity_seconds: int
    backlog_days: float
    due_counts: dict[str, int]
    accuracy: float | None
    reviews: int


@dataclass(frozen=True)
class ThrottleStatus:
    active: bool
    factor: float
    reasons: tuple[str, ...]
    signals: ThrottleSignals
    since: datetime | None = None

    def as_payload(self) -> dict[str, Any]:
        signals = asdict(self.signals)
        signals["backlog_days"] = round(self.signals.backlog_days, 2)
        if self.signals.accuracy is not None:
            signals["accuracy"] = round(self.signals.accuracy, 3)
        return {
            "consolidating": self.active,
            "factor": self.factor,
            "reasons": list(self.reasons),
            "since": self.since.isoformat() if self.since else None,
            **signals,
        }


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


def review_capacity_seconds(user: Any) -> int:
    """One day of review capacity: the Rappel's share + the word drill's."""

    from app.services.journey_rhythm import budget_seconds_for
    from app.services.vocabulary_pace import (
        DEFAULT_NEW_WORDS_PER_DAY,
        REVIEWS_PER_NEW_WORD_HIGH,
        SECONDS_PER_REVIEW,
    )

    raw = getattr(user, "new_words_per_day", None)
    words = int(raw) if raw else DEFAULT_NEW_WORDS_PER_DAY
    rappel = RAPPEL_SHARE * budget_seconds_for(user)
    drill = max(0, words) * REVIEWS_PER_NEW_WORD_HIGH * SECONDS_PER_REVIEW
    return max(60, int(round(rappel + drill)))


def due_backlog(db: Session, user: Any, *, now: datetime) -> tuple[int, dict[str, int]]:
    """``(seconds, counts)`` of everything the unified queue has due at ``now``."""

    from app.services.unified_srs import RAPPEL_ITEM_SECONDS, ItemType, UnifiedSRSService
    from app.services.vocabulary_pace import SECONDS_PER_REVIEW

    service = UnifiedSRSService(db)
    language = service._target_language(user.id)
    counts = {
        "vocab": service._due_vocab_query(user.id, now.date(), now, language).count(),
        "grammar": service._due_grammar_query(user.id, now, language).count(),
        "errors": service._due_error_query(user.id, now).count(),
        "conjugation": service._due_conjugation_query(user.id, now).count(),
    }
    seconds = (
        counts["vocab"] * SECONDS_PER_REVIEW
        + counts["grammar"] * RAPPEL_ITEM_SECONDS[ItemType.GRAMMAR]
        + counts["errors"] * RAPPEL_ITEM_SECONDS[ItemType.ERROR]
        + counts["conjugation"] * RAPPEL_ITEM_SECONDS[ItemType.CONJUGATION]
    )
    return int(seconds), counts


def review_accuracy(db: Session, user: Any, *, now: datetime) -> tuple[float | None, int]:
    """``(accuracy, reviews)`` over the last :data:`ACCURACY_WINDOW_DAYS`."""

    since = now - timedelta(days=ACCURACY_WINDOW_DAYS)
    ratings = db.execute(
        select(ReviewLog.rating)
        .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
        .where(
            UserVocabularyProgress.user_id == user.id,
            ReviewLog.review_date > since,
            ReviewLog.review_date <= now,
        )
    ).scalars().all()
    total = len(ratings)
    if total < ACCURACY_MIN_REVIEWS:
        return None, total
    right = sum(1 for rating in ratings if rating is not None and int(rating) > 0)
    return right / total, total


def read_signals(db: Session, user: Any, *, now: datetime) -> ThrottleSignals:
    backlog, counts = due_backlog(db, user, now=now)
    capacity = review_capacity_seconds(user)
    accuracy, reviews = review_accuracy(db, user, now=now)
    return ThrottleSignals(
        backlog_seconds=backlog,
        capacity_seconds=capacity,
        backlog_days=backlog / capacity if capacity else 0.0,
        due_counts=counts,
        accuracy=accuracy,
        reviews=reviews,
    )


# ---------------------------------------------------------------------------
# The rule (pure)
# ---------------------------------------------------------------------------


def enter_reasons(signals: ThrottleSignals) -> tuple[str, ...]:
    reasons: list[str] = []
    if signals.backlog_days > BACKLOG_ENTER_DAYS:
        reasons.append("backlog")
    if signals.accuracy is not None and signals.accuracy < ACCURACY_ENTER:
        reasons.append("accuracy")
    return tuple(reasons)


def recovered(signals: ThrottleSignals) -> bool:
    accuracy_ok = signals.accuracy is None or signals.accuracy >= ACCURACY_EXIT
    return signals.backlog_days <= BACKLOG_EXIT_DAYS and accuracy_ok


def decide(
    signals: ThrottleSignals,
    *,
    was_active: bool,
    since: datetime | None,
    now: datetime,
) -> tuple[bool, tuple[str, ...]]:
    """``(active, reasons)`` — the hysteresis rule, no I/O."""

    if not was_active:
        reasons = enter_reasons(signals)
        return bool(reasons), reasons
    if since is not None and now - since < timedelta(days=MIN_HOLD_DAYS):
        return True, ("holding",)
    if recovered(signals):
        return False, ("recovered",)
    return True, enter_reasons(signals) or ("recovering",)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def last_state(db: Session, user: Any) -> tuple[bool, datetime | None]:
    row = db.execute(
        select(PilotEvent)
        .where(PilotEvent.user_id == user.id, PilotEvent.event_type == EVENT_TYPE)
        .order_by(PilotEvent.occurred_at.desc(), PilotEvent.id.desc())
        .limit(1)
    ).scalars().first()
    if row is None:
        return False, None
    payload = row.payload or {}
    active = str(payload.get("state") or "") == "on"
    since = payload.get("since") or None
    stamp: datetime | None = None
    if isinstance(since, str):
        try:
            stamp = _aware(datetime.fromisoformat(since))
        except ValueError:
            stamp = None
    return active, stamp or _aware(row.occurred_at)


def throttle_status(
    db: Session,
    user: Any,
    *,
    now: datetime | None = None,
    record: bool = True,
) -> ThrottleStatus:
    """Evaluate the throttle; a change of state writes one pilot event."""

    now = _aware(now) or datetime.now(UTC)
    signals = read_signals(db, user, now=now)
    was_active, since = last_state(db, user)
    active, reasons = decide(signals, was_active=was_active, since=since, now=now)
    if active != was_active:
        since = now if active else None
        if record:
            from app.services.pilot_events import PilotEventService

            status = ThrottleStatus(active, THROTTLE_FACTOR if active else 1.0, reasons, signals, since)
            PilotEventService(db).record(
                EVENT_TYPE,
                user_id=user.id,
                entity_type="user",
                entity_id=user.id,
                payload={
                    "state": "on" if active else "off",
                    "since": now.isoformat(),
                    **{key: value for key, value in status.as_payload().items() if key not in {"since"}},
                },
                occurred_at=now,
            )
            db.flush()
    return ThrottleStatus(
        active=active,
        factor=THROTTLE_FACTOR if active else 1.0,
        reasons=reasons,
        signals=signals,
        since=since if active else None,
    )


def throttle_factor(db: Session, user: Any, *, now: datetime | None = None) -> float:
    if not getattr(user, "id", None):
        return 1.0
    return throttle_status(db, user, now=now).factor


def intake_notice(db: Session, user: Any, *, now: datetime | None = None) -> dict[str, Any] | None:
    """The payload Home and the recap read; ``None`` when it cannot be read."""

    if not getattr(user, "id", None):
        return None
    try:
        with db.begin_nested():
            return throttle_status(db, user, now=now).as_payload()
    except Exception:  # noqa: BLE001 - a notice is never worth the page
        return None


__all__ = [
    "ACCURACY_ENTER",
    "ACCURACY_EXIT",
    "BACKLOG_ENTER_DAYS",
    "BACKLOG_EXIT_DAYS",
    "EVENT_TYPE",
    "MIN_HOLD_DAYS",
    "THROTTLE_FACTOR",
    "ThrottleSignals",
    "ThrottleStatus",
    "decide",
    "due_backlog",
    "intake_notice",
    "review_accuracy",
    "review_capacity_seconds",
    "throttle_factor",
    "throttle_status",
]
