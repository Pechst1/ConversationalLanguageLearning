"""S6 stage 2 · who came back, read from real days (the ledger), not from walks.

Learners are seeded with known return patterns under a frozen test clock. Every day is
the learner's own calendar day: a learner in Los Angeles who signs up late in the
evening and comes back the next afternoon has returned on day 1, even when both
moments fall on the same UTC date.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core import test_clock
from app.db.models.pilot_event import PilotEvent
from app.db.models.streak_day import STREAK_DAY_PRACTISED, StreakDay
from app.db.models.user import User
from app.services import cohorts
from app.services.journey_contracts import JourneyEventName
from app.services.journey_events import JOURNEY_ENTITY_TYPE
from tests.test_wp115a_vocabulary_memory import _login

#: Wednesday 24 June 2026, noon UTC. Far from a DST change and from midnight anywhere
#: the seeded learners live.
NOW = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)
PARIS = "Europe/Paris"
LA = "America/Los_Angeles"

STEPS = ("rule", "scene", "recall", "respond", "resolution")


@pytest.fixture()
def frozen() -> Iterator[datetime]:
    test_clock.install()
    test_clock.follow(lambda: NOW)
    try:
        yield NOW
    finally:
        test_clock.uninstall()


def _local(day: date, zone: str, hour: int = 10) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=ZoneInfo(zone)).astimezone(UTC)


def _learner(db, signup: datetime, *, zone: str = PARIS, synthetic: bool = False) -> User:
    user = User(
        email=f"cohort-{uuid4()}@example.com",
        hashed_password="x",  # noqa: S106 - a seeded row, never signed in
        timezone=zone,
        created_at=signup,
        is_synthetic=synthetic,
    )
    db.add(user)
    db.flush()
    return user


def _event(db, user: User, name: str, at: datetime, journey: str, zone: str, **payload) -> None:
    db.add(
        PilotEvent(
            user_id=user.id,
            event_type=name,
            entity_type=JOURNEY_ENTITY_TYPE,
            entity_id=journey,
            payload={"journey_id": journey, "timezone": zone, **payload},
            occurred_at=at,
        )
    )


def _day(db, user: User, start: datetime, *, zone: str = PARIS, steps: int = 5, finish: bool = True) -> None:
    """One journey: started, ``steps`` steps two minutes apart, completed two minutes later.

    A finished five-step day measures 6 × 2 = 12 active minutes.
    """

    journey = str(uuid4())
    _event(db, user, str(JourneyEventName.STARTED), start, journey, zone)
    at = start
    for ordinal in range(steps):
        at += timedelta(minutes=2)
        _event(
            db, user, str(JourneyEventName.STEP_COMPLETED), at, journey, zone,
            step_kind=STEPS[ordinal], ordinal=ordinal, estimated_seconds=120,
        )
    if finish:
        _event(db, user, str(JourneyEventName.COMPLETED), at + timedelta(minutes=2), journey, zone)


def _signup_day(day: date, zone: str = PARIS) -> datetime:
    return _local(day, zone, hour=9)


def _seed(db) -> dict[str, User]:
    w1 = date(2026, 6, 1)  # Monday
    learners: dict[str, User] = {}

    # Week of 1 June: three learners, so raw counts only.
    a = learners["a"] = _learner(db, _signup_day(w1))
    for offset in (0, 1, 3, 7, 14):
        _day(db, a, _local(w1 + timedelta(days=offset), PARIS))
    b = learners["b"] = _learner(db, _signup_day(w1 + timedelta(days=2)))
    _day(db, b, _local(w1 + timedelta(days=2), PARIS))
    # Day 1: two steps, then gone. The day stopped after «scene».
    _day(db, b, _local(w1 + timedelta(days=3), PARIS), steps=2, finish=False)
    c = learners["c"] = _learner(db, _signup_day(w1 + timedelta(days=4)))
    _day(db, c, _local(w1 + timedelta(days=4), PARIS))
    # Day 3 was a Séance only: the streak grid has it, the journey ledger does not.
    db.add(StreakDay(user_id=c.id, local_date=w1 + timedelta(days=7), kind=STREAK_DAY_PRACTISED))

    # A walk account with a perfect record, excluded by default.
    s = learners["synthetic"] = _learner(db, _signup_day(w1), synthetic=True)
    for offset in range(15):
        _day(db, s, _local(w1 + timedelta(days=offset), PARIS))

    # Week of 8 June: five learners, so percentages. Four come back on day 1,
    # one on day 14.
    w2 = date(2026, 6, 8)
    for index in range(5):
        user = learners[f"w2-{index}"] = _learner(db, _signup_day(w2))
        _day(db, user, _local(w2, PARIS))
        if index < 4:
            _day(db, user, _local(w2 + timedelta(days=1), PARIS))
        if index == 0:
            _day(db, user, _local(w2 + timedelta(days=14), PARIS))

    # Week of 25 May, learner-local: signs up Sunday 31 May 23:00 in Los Angeles
    # (1 June 06:00 UTC) and comes back on 1 June at 13:00 there (20:00 UTC, the
    # same UTC date as the sign-up).
    la = learners["la"] = _learner(db, datetime(2026, 6, 1, 6, 0, tzinfo=UTC), zone=LA)
    _day(db, la, datetime(2026, 6, 1, 20, 0, tzinfo=UTC), zone=LA)

    # Week of 22 June: signed up yesterday, so day 1 is today and not yet due.
    late = learners["late"] = _learner(db, _signup_day(date(2026, 6, 23)))
    _day(db, late, _local(date(2026, 6, 23), PARIS))

    db.flush()
    return learners


def _by_week(report: dict) -> dict[str, dict]:
    return {row["week_start"]: row for row in report["cohorts"]}


def test_small_cohort_shows_raw_counts_never_a_percentage(db_session, frozen):
    _seed(db_session)
    report = cohorts.build_cohorts(db_session, weeks=8)
    assert report["today"] == "2026-06-24"
    assert report["min_learners_for_rate"] == 5

    week = _by_week(report)["2026-06-01"]
    assert week["learners"] == 3
    returns = week["returns"]
    assert returns["d1"] == {"returned": 2, "due": 3, "rate": None, "display": "2 of 3"}
    assert returns["d3"] == {"returned": 2, "due": 3, "rate": None, "display": "2 of 3"}
    assert returns["d7"] == {"returned": 1, "due": 3, "rate": None, "display": "1 of 3"}
    assert returns["d14"] == {"returned": 1, "due": 3, "rate": None, "display": "1 of 3"}
    # Journey days: a 5, b 2, c 1 started; b's second day is unfinished.
    assert (week["days_started"], week["days_completed"]) == (8, 7)
    assert week["median_active_minutes"] == 12.0
    assert week["stops"] == [{"after_step": "scene", "days": 1}]


def test_five_learners_give_a_rate(db_session, frozen):
    _seed(db_session)
    week = _by_week(cohorts.build_cohorts(db_session, weeks=8))["2026-06-08"]
    assert week["learners"] == 5
    assert week["returns"]["d1"] == {"returned": 4, "due": 5, "rate": 0.8, "display": "80% (4 of 5)"}
    assert week["returns"]["d3"]["rate"] == 0.0
    assert week["returns"]["d14"] == {"returned": 1, "due": 5, "rate": 0.2, "display": "20% (1 of 5)"}


def test_days_are_the_learners_own_days(db_session, frozen):
    _seed(db_session)
    report = cohorts.build_cohorts(db_session, weeks=8)
    week = _by_week(report)["2026-05-25"]
    assert week["learners"] == 1
    assert week["returns"]["d1"]["returned"] == 1
    [row] = week["learner_rows"]
    assert row["signup_date"] == "2026-05-31"
    assert row["returns"]["d1"] is True


def test_a_day_not_over_yet_is_not_due(db_session, frozen):
    _seed(db_session)
    week = _by_week(cohorts.build_cohorts(db_session, weeks=8))["2026-06-22"]
    assert week["returns"]["d1"] == {"returned": 0, "due": 0, "rate": None, "display": "not due"}
    [row] = week["learner_rows"]
    assert row["returns"] == {"d1": None, "d3": None, "d7": None, "d14": None, "d30": None}


def test_synthetic_accounts_are_left_out_unless_asked(db_session, frozen):
    learners = _seed(db_session)
    synthetic_id = str(learners["synthetic"].id)

    default = cohorts.build_cohorts(db_session, weeks=8)
    ids = {row["user_id"] for week in default["cohorts"] for row in week["learner_rows"]}
    assert synthetic_id not in ids
    assert default["synthetic_excluded"] == 1

    everyone = cohorts.build_cohorts(db_session, weeks=8, include_synthetic=True)
    week = _by_week(everyone)["2026-06-01"]
    assert week["learners"] == 4
    assert week["returns"]["d1"]["display"] == "3 of 4"
    [row] = [r for r in week["learner_rows"] if r["user_id"] == synthetic_id]
    assert row["synthetic"] is True


def test_learner_rows_say_what_each_learner_did(db_session, frozen):
    learners = _seed(db_session)
    rows = {
        row["user_id"]: row
        for week in cohorts.build_cohorts(db_session, weeks=8)["cohorts"]
        for row in week["learner_rows"]
    }
    a = rows[str(learners["a"].id)]
    assert a["returns"] == {"d1": True, "d3": True, "d7": True, "d14": True, "d30": None}
    assert (a["days_started"], a["days_completed"]) == (5, 5)
    assert a["median_active_minutes"] == 12.0
    b = rows[str(learners["b"].id)]
    assert b["returns"] == {"d1": True, "d3": False, "d7": False, "d14": False, "d30": None}
    assert b["stops"] == [{"date": "2026-06-04", "after_step": "scene"}]
    c = rows[str(learners["c"].id)]
    assert c["returns"]["d3"] is True  # the Séance day
    assert (c["days_started"], c["days_completed"]) == (1, 1)


def test_the_table_reads_as_text(db_session, frozen):
    _seed(db_session)
    lines = cohorts.cohort_table_lines(cohorts.build_cohorts(db_session, weeks=8))
    text = "\n".join(lines)
    assert "| 2026-06-01 | 3 | 3 of 3 | 2 of 3 | 2 of 3 | 1 of 3 | 1 of 3 | not due |" in text
    assert "| 2026-06-08 | 5 | 100% (5 of 5) | 80% (4 of 5) |" in text
    # The digest is posted in a public repository: no learner rows, no emails.
    assert "@example.com" not in text


def test_day_thirty_is_reported_once_it_is_over(db_session, frozen):
    signup = date(2026, 5, 4)  # Monday, 51 days before NOW
    back = _learner(db_session, _signup_day(signup))
    _day(db_session, back, _local(signup, PARIS))
    _day(db_session, back, _local(signup + timedelta(days=30), PARIS))
    gone = _learner(db_session, _signup_day(signup))
    _day(db_session, gone, _local(signup, PARIS), steps=1, finish=False)
    db_session.flush()

    week = _by_week(cohorts.build_cohorts(db_session, weeks=8))["2026-05-04"]
    assert week["returns"]["d30"] == {"returned": 1, "due": 2, "rate": None, "display": "1 of 2"}
    # The first day: one finished it, one stopped after the first step.
    assert week["finished_first_day"]["display"] == "1 of 2"
    rows = {row["user_id"]: row for row in week["learner_rows"]}
    assert rows[str(back.id)]["finished_first_day"] is True
    assert rows[str(gone.id)]["finished_first_day"] is False
    assert rows[str(gone.id)]["days_abandoned"] == 1


def test_words_in_and_out_per_active_day(db_session, frozen, monkeypatch):
    from app.db.models.daily_journey import DailyJourney
    from app.db.models.verdict_record import VerdictRecord
    from app.services.story_reading import StoryReading

    signup = date(2026, 6, 15)
    user = _learner(db_session, _signup_day(signup))
    journeys = []
    for offset in (0, 1):
        journey = DailyJourney(
            user_id=user.id, local_date=signup + timedelta(days=offset), timezone=PARIS, status="completed"
        )
        db_session.add(journey)
        db_session.flush()
        journeys.append(journey)
        start = _local(signup + timedelta(days=offset), PARIS)
        _event(db_session, user, str(JourneyEventName.STARTED), start, str(journey.id), PARIS)
        _event(db_session, user, str(JourneyEventName.COMPLETED), start + timedelta(minutes=5), str(journey.id), PARIS)
    words = {journeys[0].id: 120, journeys[1].id: 180}
    monkeypatch.setattr(cohorts, "day_reading", lambda journey: StoryReading(acts=1, words=words[journey.id]))

    def verdict(text: str, at: datetime, **extra) -> VerdictRecord:
        row = VerdictRecord(
            user_id=user.id, surface="journey", subject_type="step", subject_id=str(uuid4()),
            answer_text=text, verdict={}, judge_version="t", created_at=at, **extra,
        )
        db_session.add(row)
        db_session.flush()
        return row

    day0 = _local(signup, PARIS, hour=11)
    verdict("Je voudrais un café", day0)
    # An appealed answer: the superseded row never counts twice.
    old = verdict("Il est parti hier soir", day0)
    new = verdict("Il est parti hier soir", day0, supersedes_id=old.id)
    old.superseded_by_id = new.id
    verdict("Oui", _local(signup + timedelta(days=1), PARIS, hour=11))
    # Re-judged on day 1, given on day 0: its words stay on day 0.
    late_old = verdict("Elle a mangé", day0)
    late_new = verdict("Elle a mangé", _local(signup + timedelta(days=1), PARIS, hour=15), supersedes_id=late_old.id)
    late_old.superseded_by_id = late_new.id
    db_session.flush()

    report = cohorts.build_cohorts(db_session, weeks=8)
    [row] = [r for week in report["cohorts"] for r in week["learner_rows"] if r["user_id"] == str(user.id)]
    # Story words: 120 and 180, median 150. Own words: 4 + 5 + 3 = 12 and 1, median 6.5.
    assert row["median_story_words"] == 150.0
    assert row["median_own_words"] == 6.5
    week = _by_week(report)["2026-06-15"]
    assert week["median_story_words"] == 150.0
    text = "\n".join(cohorts.cohort_table_lines(report))
    assert "Median own words/day" in text


def test_only_the_owner_reads_the_cohorts(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    assert client.get("/api/v1/analytics/pilot-cohorts", headers=headers).status_code == 403
    user.role = "admin"
    db_session.commit()
    response = client.get("/api/v1/analytics/pilot-cohorts", params={"weeks": 2}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["min_learners_for_rate"] == 5
    assert isinstance(body["cohorts"], list)
