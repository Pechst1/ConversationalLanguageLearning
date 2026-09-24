"""WP-L6 §2.2 — the auto-throttle, with simulated backlogs.

* Engages when the due backlog is over 1.5 days of review capacity, or 7-day
  review accuracy is under 80 %; new intake halves — words (the owner's pace
  and the journey's share) and grammar (``concept_life`` → ``forge_plan``).
* Hysteresis: holds ≥ 3 days, releases only at ≤ 1 day of backlog and ≥ 85 %
  accuracy, so it does not flap at the threshold.
* Every change writes one ``intake_throttle`` pilot event; Home's
  ``/atelier/today`` and the recap carry the notice.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.grammar import UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import concept_life, intake_throttle, vocabulary_pace
from app.services.intake_throttle import ThrottleSignals, decide
from tests.test_journey_events import make_user

NOW = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)


def _learner(db: Session, *, quota: int = 10, minutes: int = 10) -> User:
    user = make_user(db, f"throttle-{uuid.uuid4().hex[:8]}@example.com")
    user.new_words_per_day = quota
    user.daily_goal_minutes = minutes
    user.timezone = "Europe/Paris"
    db.flush()
    return user


def _words(db: Session, user: User, count: int, *, due: datetime) -> list[UserVocabularyProgress]:
    rows = []
    for index in range(count):
        word = VocabularyWord(
            word=f"thr{uuid.uuid4().hex[:6]}{index}",
            normalized_word=f"thr{index}",
            language="fr",
            english_translation="x",
        )
        db.add(word)
        db.flush()
        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=word.id,
            reps=3,
            state="review",
            due_at=due,
            next_review_date=due,
            created_at=NOW - timedelta(days=30),
        )
        db.add(progress)
        rows.append(progress)
    db.flush()
    return rows


def _reviews(db: Session, rows: list[UserVocabularyProgress], *, right: int, wrong: int, at: datetime) -> None:
    for index in range(right + wrong):
        db.add(
            ReviewLog(
                progress_id=rows[index % len(rows)].id,
                rating=2 if index < right else 0,
                review_date=at,
            )
        )
    db.flush()


def _clear(db: Session, rows: list[UserVocabularyProgress]) -> None:
    for row in rows:
        row.due_at = NOW + timedelta(days=30)
        row.next_review_date = NOW + timedelta(days=30)
    db.flush()


def _events(db: Session, user: User) -> list[PilotEvent]:
    return (
        db.query(PilotEvent)
        .filter(PilotEvent.user_id == user.id, PilotEvent.event_type == intake_throttle.EVENT_TYPE)
        .order_by(PilotEvent.occurred_at)
        .all()
    )


# ---------------------------------------------------------------------------
# The rule, pure
# ---------------------------------------------------------------------------


def _signals(days: float, accuracy: float | None = None) -> ThrottleSignals:
    return ThrottleSignals(
        backlog_seconds=int(days * 1000),
        capacity_seconds=1000,
        backlog_days=days,
        due_counts={},
        accuracy=accuracy,
        reviews=50 if accuracy is not None else 0,
    )


def test_the_rule_engages_on_backlog_or_accuracy() -> None:
    assert decide(_signals(1.4), was_active=False, since=None, now=NOW) == (False, ())
    assert decide(_signals(1.6), was_active=False, since=None, now=NOW) == (True, ("backlog",))
    assert decide(_signals(0.2, 0.79), was_active=False, since=None, now=NOW) == (True, ("accuracy",))
    assert decide(_signals(0.2, 0.81), was_active=False, since=None, now=NOW)[0] is False


def test_the_rule_has_hysteresis() -> None:
    since = NOW - timedelta(days=4)
    # Between the thresholds, an engaged throttle stays engaged…
    assert decide(_signals(1.2), was_active=True, since=since, now=NOW)[0] is True
    assert decide(_signals(0.5, 0.82), was_active=True, since=since, now=NOW)[0] is True
    # …and an idle one stays idle.
    assert decide(_signals(1.2, 0.82), was_active=False, since=None, now=NOW)[0] is False
    # Released only when both have recovered, and never inside the hold.
    assert decide(_signals(0.9, 0.9), was_active=True, since=since, now=NOW) == (False, ("recovered",))
    assert decide(_signals(0.0, 0.99), was_active=True, since=NOW - timedelta(days=1), now=NOW) == (
        True,
        ("holding",),
    )


# ---------------------------------------------------------------------------
# Simulated backlogs
# ---------------------------------------------------------------------------


def test_capacity_follows_rhythm_and_word_pace(db_session: Session) -> None:
    regulier = _learner(db_session, quota=10, minutes=10)
    # 35 % of 600 s + 10 words × 10 reviews × 6 s.
    assert intake_throttle.review_capacity_seconds(regulier) == 210 + 600
    owner = _learner(db_session, quota=20, minutes=30)
    assert intake_throttle.review_capacity_seconds(owner) == 630 + 1200


def test_a_backlog_halves_word_intake_and_writes_one_event(db_session: Session) -> None:
    user = _learner(db_session, quota=20, minutes=10)  # the owner's 20 words a day
    capacity = intake_throttle.review_capacity_seconds(user)  # 210 + 1200 = 1410 s
    under = int(1.4 * capacity / 6)
    rows = _words(db_session, user, under, due=NOW - timedelta(days=1))
    assert vocabulary_pace.intake_throttle_factor(db_session, user, now=NOW) == 1.0
    assert vocabulary_pace.daily_quota(db_session, user, now=NOW) == 20
    assert _events(db_session, user) == []

    rows += _words(db_session, user, 40, due=NOW - timedelta(days=1))  # > 1.5 days now
    status = intake_throttle.throttle_status(db_session, user, now=NOW)
    assert status.active and status.reasons == ("backlog",)
    assert status.signals.backlog_days > 1.5
    assert vocabulary_pace.daily_quota(db_session, user, now=NOW) == 10
    # The journey's rhythm share halves too (Régulier: 4 → 2).
    assert vocabulary_pace.journey_word_share(user, 0.5) == 2
    assert vocabulary_pace.journey_new_word_room(db_session, user, now=NOW) == 2
    # Evaluated many times, recorded once.
    for _ in range(3):
        vocabulary_pace.daily_quota(db_session, user, now=NOW)
    events = _events(db_session, user)
    assert len(events) == 1 and events[0].payload["state"] == "on"
    assert events[0].payload["reasons"] == ["backlog"]

    # The learner clears the pile the same day: the hold keeps it on.
    _clear(db_session, rows)
    assert vocabulary_pace.intake_throttle_factor(db_session, user, now=NOW + timedelta(hours=6)) == 0.5
    # Three days later, recovered → released, one more event.
    later = NOW + timedelta(days=3, hours=1)
    assert vocabulary_pace.intake_throttle_factor(db_session, user, now=later) == 1.0
    events = _events(db_session, user)
    assert [event.payload["state"] for event in events] == ["on", "off"]


def test_a_backlog_between_the_thresholds_does_not_flap(db_session: Session) -> None:
    user = _learner(db_session, quota=10, minutes=10)
    capacity = intake_throttle.review_capacity_seconds(user)  # 810 s
    rows = _words(db_session, user, int(1.6 * capacity / 6) + 1, due=NOW - timedelta(days=1))
    assert intake_throttle.throttle_factor(db_session, user, now=NOW) == 0.5
    # The pile shrinks to 1.2 days: above the release line, still on.
    keep = int(1.2 * capacity / 6)
    for row in rows[keep:]:
        row.due_at = NOW + timedelta(days=20)
        row.next_review_date = NOW + timedelta(days=20)
    db_session.flush()
    for day in range(3, 8):
        assert intake_throttle.throttle_factor(db_session, user, now=NOW + timedelta(days=day)) == 0.5
    assert len(_events(db_session, user)) == 1


def test_low_accuracy_throttles_and_needs_85_to_release(db_session: Session) -> None:
    user = _learner(db_session, quota=10, minutes=10)
    rows = _words(db_session, user, 5, due=NOW + timedelta(days=5))
    # Too few reviews say nothing.
    _reviews(db_session, rows, right=5, wrong=10, at=NOW - timedelta(days=1))
    assert intake_throttle.review_accuracy(db_session, user, now=NOW) == (None, 15)
    assert intake_throttle.throttle_factor(db_session, user, now=NOW) == 1.0
    _reviews(db_session, rows, right=10, wrong=0, at=NOW - timedelta(days=1))
    accuracy, reviews = intake_throttle.review_accuracy(db_session, user, now=NOW)
    assert reviews == 25 and accuracy == 15 / 25
    status = intake_throttle.throttle_status(db_session, user, now=NOW)
    assert status.active and status.reasons == ("accuracy",)
    # A week later the bad day has left the window, but 82 % is not enough.
    later = NOW + timedelta(days=8)
    _reviews(db_session, rows, right=41, wrong=9, at=later - timedelta(days=1))
    assert intake_throttle.throttle_factor(db_session, user, now=later) == 0.5
    _reviews(db_session, rows, right=40, wrong=0, at=later - timedelta(hours=1))
    assert intake_throttle.throttle_factor(db_session, user, now=later) == 1.0


def test_grammar_intake_halves_with_the_throttle(db_session: Session, monkeypatch) -> None:
    for minutes, full, halved in ((5, 1.0, 0.5), (10, 2.0, 1.0), (20, 3.0, 1.5), (30, 4.0, 2.0)):
        user = _learner(db_session, minutes=minutes)
        monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *a, **k: 1.0)
        assert concept_life.weekly_concept_rate(db_session, user, now=NOW) == full
        monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *a, **k: 0.5)
        assert concept_life.weekly_concept_rate(db_session, user, now=NOW) == halved


def test_leger_throttled_introduces_one_unit_every_two_weeks(db_session: Session, monkeypatch) -> None:
    from app.db.models.grammar import GrammarConcept

    user = _learner(db_session, minutes=5)
    concept = GrammarConcept(name=f"thr-{uuid.uuid4().hex[:6]}", level="A1", language="fr", active=True)
    db_session.add(concept)
    db_session.flush()
    db_session.add(
        UserGrammarProgress(user_id=user.id, concept_id=concept.id, introduced_at=NOW - timedelta(days=8))
    )
    db_session.flush()
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *a, **k: 1.0)
    assert concept_life.introduction_due(db_session, user, now=NOW) is True
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *a, **k: 0.5)
    assert concept_life.introduction_due(db_session, user, now=NOW) is False
    assert concept_life.introduction_due(db_session, user, now=NOW + timedelta(days=6)) is True


def test_the_notice_payload(db_session: Session) -> None:
    user = _learner(db_session, quota=10, minutes=10)
    _words(db_session, user, 300, due=NOW - timedelta(days=2))
    notice = intake_throttle.intake_notice(db_session, user, now=NOW)
    assert notice is not None
    assert notice["consolidating"] is True and notice["factor"] == 0.5
    assert notice["due_counts"]["vocab"] == 300
    assert notice["backlog_days"] > 1.5
