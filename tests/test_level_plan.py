"""The level plan: exactly where the learner stands, what is left, and what it costs.

Owner, 2026-10-24: «we always know exactly at which level the learner is
currently so that he also knows that exactly and knows what he has to do and
how much time he has to invest to advance further».

Pins:
1. one level everywhere: ``/progress/cefr``, ``/progress/level`` and the
   Dossier read the same live band and percent, and opening the plan writes
   nothing;
2. what is left: each unit with its stage, the «Tenue» evidence it lacks, its
   soonest day and whether today owes it an opportunity; the band's words
   known, on their way and not met yet;
3. the floor: ``concept_life.earliest_held_at`` and
   ``level_forecast.earliest_cover_days``;
4. time: the measured practice clock (scenes, séances, the word deck, nothing
   counted twice) and what the days left cost in minutes;
5. the ladder and how far each criterion reaches alone.
"""
from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.cefr import UserCEFRProgressHistory, UserLevelCheckpoint
from app.db.models.daily_journey import DailyJourney
from app.db.models.grammar import UserGrammarProgress
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.main import create_app
from app.services import concept_life, journey_events, level_forecast, level_plan
from app.services.cefr_progress import DECLARED_LEVEL_EVIDENCE_ATTEMPTS, CEFRProgressService
from app.services.forge_metrics import active_seconds
from app.services.journey_contracts import JourneyEventName, effect_source_key
from app.services.journey_events import record_journey_event
from tests.test_wp_l7_level_coverage import (
    BAND_WORDS,
    NOW,
    _hold,
    _know,
    _user,
    isolated_catalog,  # noqa: F401 - fixture: parks the shared catalogue for the test
    small_band,  # noqa: F401 - fixture: a five-word A1.1 vocabulary
)

TEST_PASSWORD = "securepass123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _progress(**fields) -> SimpleNamespace:
    row = {
        "held_at": None,
        "introduced_at": None,
        "created_at": None,
        "last_review": None,
        "free_use_first_at": None,
        "free_use_last_at": None,
        "spaced_success_at": None,
        "reps": 1,
    }
    row.update(fields)
    return SimpleNamespace(**row)


def _practising(db_session, user, concept, **fields) -> None:
    row = {
        "user_id": user.id,
        "concept_id": concept.id,
        "score": 6.0,
        "reps": 1,
        "state": "lernend",
        "stability": 2.0,
        "difficulty": 5.0,
        "lapses": 0,
        "last_review": NOW - timedelta(hours=1),
        "next_review": NOW + timedelta(days=1),
        "introduced_at": NOW - timedelta(days=3),
    }
    row.update(fields)
    db_session.add(UserGrammarProgress(**row))
    db_session.commit()


def _day(value: datetime) -> str:
    return value.date().isoformat()


@pytest.fixture()
def plan_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"level-plan-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "target_language": "fr",
            "native_language": "en",
            "proficiency_level": "A1",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


# ---------------------------------------------------------------------------
# 1. One level everywhere, and a read that writes nothing
# ---------------------------------------------------------------------------


def test_the_plan_needs_a_learner(plan_client):
    assert plan_client.get("/api/v1/progress/level").status_code in {401, 403}


def test_every_surface_reads_the_same_live_level_and_the_plan_writes_nothing(
    plan_client, db_session, isolated_catalog, small_band
):
    headers, email = _login(plan_client)
    user = db_session.query(User).filter(User.email == email).one()
    units = [isolated_catalog("A1", order) for order in (1, 2, 3, 4)]
    _hold(db_session, user, units[0])
    for lemma in ("bonjour", "merci"):
        _know(db_session, user, lemma)

    history = db_session.query(UserCEFRProgressHistory).filter_by(user_id=user.id).count()
    stored = dict(user.cefr_estimate_payload or {})
    first = plan_client.get("/api/v1/progress/level", headers=headers)
    second = plan_client.get("/api/v1/progress/level", headers=headers)
    assert first.status_code == second.status_code == 200
    db_session.refresh(user)
    assert db_session.query(UserCEFRProgressHistory).filter_by(user_id=user.id).count() == history
    assert db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id).count() == 0
    assert dict(user.cefr_estimate_payload or {}) == stored

    plan = first.json()
    cefr = plan_client.get("/api/v1/progress/cefr", headers=headers).json()
    dossier = plan_client.get("/api/v1/dossier/state", headers=headers).json()["dossier"]["level"]
    assert plan["band"] == cefr["estimate"] == dossier["estimate"] == "A1.1"
    assert plan["percent"] == cefr["coverage"]["percent"] == dossier["coverage"]["percent"]
    assert plan["label"] == cefr["level_label"]
    # A1.1 is the first two of four A1 units: one held of the two needed.
    assert (plan["rules"]["held"], plan["rules"]["required"]) == (1, 2)
    assert (plan["words"]["known"], plan["words"]["required"]) == (2, 4)
    assert 0 < plan["percent"] < 90


def test_a_unit_held_since_the_snapshot_moves_the_level_at_once(db_session, isolated_catalog, small_band):
    """The stored payload is a snapshot; the plan and the level read the work as it is now."""

    user = _user(db_session)
    units = [isolated_catalog("A1", order) for order in (1, 2)]
    service = CEFRProgressService(db_session)
    before = service.recompute(user, source="test")["coverage"]["percent"]
    _hold(db_session, user, units[0])
    for lemma in ("bonjour", "merci", "café", "pain"):
        _know(db_session, user, lemma)
    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    assert plan["percent"] == 90 > before
    assert plan["rules"]["met"] and plan["words"]["met"]
    # Coverage met, the épreuve is next; nothing was written to say so.
    assert plan["epreuve"]["state"] == "ready"
    assert db_session.query(UserLevelCheckpoint).filter_by(user_id=user.id).count() == 0


def test_a_declared_level_is_not_presented_as_verified(db_session, isolated_catalog):
    user = _user(db_session, declared="B1")
    isolated_catalog("B1", 1)
    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    assert plan["band"] == "B1.1"
    assert plan["estimate_source"] == "declared"
    assert plan["verified"] is False
    assert plan["evidence"] == {
        "attempts_required": DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
        "attempts_counted": 0,
    }
    states = {step["band"]: step["state"] for step in plan["ladder"]}
    # Below the declared start: never closed in the app, never counted against them.
    assert states["A1.1"] == states["A2.2"] == "start"
    assert states["B1.1"] == "current" and states["B1.2"] == "ahead"


# ---------------------------------------------------------------------------
# 2. What is left, item by item
# ---------------------------------------------------------------------------


def test_each_unit_reads_its_stage_what_it_lacks_and_its_soonest_day(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    # Eight A1 units: A1.1 is the first four in teaching order.
    units = [isolated_catalog("A1", order) for order in range(1, 9)]
    held, owed, recent, new = units[:4]
    _hold(db_session, user, held)
    _hold(db_session, user, owed, held=False)  # introduced 40 days ago, never used freely
    _practising(db_session, user, recent)  # introduced three days ago

    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    rules = plan["rules"]
    assert (rules["held"], rules["required"], rules["total"], rules["to_go"]) == (1, 4, 4, 3)
    assert (rules["practising"], rules["not_started"], rules["owed_today"]) == (2, 1, 1)
    # Owed today first, then the soonest, then the units not met yet, the held ones last.
    assert [item["id"] for item in rules["items"]] == [owed.id, recent.id, new.id, held.id]
    by_id = {item["id"]: item for item in rules["items"]}

    assert by_id[owed.id]["owed_today"] in {concept_life.OPPORTUNITY_FREE_USE, concept_life.OPPORTUNITY_SPACED}
    assert [entry["code"] for entry in by_id[owed.id]["missing"]] == [
        concept_life.MISSING_FIRST_FREE_USE,
        concept_life.MISSING_SPACED,
    ]
    # No free use yet: the first can come today, the second a week later.
    assert by_id[owed.id]["earliest_held_on"] == _day(NOW + timedelta(days=7))

    assert by_id[recent.id]["owed_today"] is None
    # The spaced item waits for day 14 after the introduction.
    assert by_id[recent.id]["earliest_held_on"] == _day(NOW - timedelta(days=3) + timedelta(days=14))

    assert by_id[new.id]["stage"] == concept_life.STAGE_NEW
    assert by_id[new.id]["introduce_from"] == _day(NOW)
    assert by_id[new.id]["earliest_held_on"] == _day(NOW + timedelta(days=14))

    # Titled as the notebook titles a unit: every locale, English at least.
    assert by_id[new.id]["titles"]["en"] == new.name

    assert by_id[held.id]["stage"] == concept_life.STAGE_HELD
    assert by_id[held.id]["held_on"] == _day(NOW - timedelta(days=2))
    assert by_id[held.id]["missing"] == [] and by_id[held.id]["earliest_held_on"] is None


def test_the_units_not_met_yet_open_at_the_plans_weekly_intake(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    units = [isolated_catalog("A1", order) for order in range(1, 7)]
    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    per_week = plan["rules"]["per_week"]
    assert per_week == level_forecast.planned_intake(user)[1] > 0
    opens = [item["introduce_from"] for item in plan["rules"]["items"]]
    assert opens == [_day(NOW + timedelta(days=k * 7.0 / per_week)) for k in range(3)]
    assert {item["id"] for item in plan["rules"]["items"]} == {unit.id for unit in units[:3]}


def test_the_bands_words_split_into_known_on_their_way_and_not_met(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    isolated_catalog("A1", 1)
    for lemma in ("bonjour", "merci"):
        _know(db_session, user, lemma)
    _know(db_session, user, "café", reps=1)  # a card, not settled yet
    words = level_plan.build_level_plan(db_session, user, now=NOW)["words"]
    assert words["total"] == len(BAND_WORDS)
    assert (words["known"], words["required"], words["to_go"]) == (2, 4, 2)
    assert (words["on_the_way"], words["new_needed"], words["not_met"]) == (1, 1, 2)
    assert words["per_day"] == 10 and words["days_for_new"] == 1
    assert words["met"] is False


# ---------------------------------------------------------------------------
# 3. The rules' floor
# ---------------------------------------------------------------------------


def test_earliest_held_at_is_the_last_condition_to_open():
    now = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
    week_on = datetime(2026, 10, 31, tzinfo=UTC)

    fresh = _progress(introduced_at=now - timedelta(days=3), last_review=now - timedelta(hours=1))
    assert concept_life.earliest_held_at(fresh, now=now) == now + timedelta(days=11)

    # Spaced success in; one free use two days ago: the second a week after it.
    spaced = _progress(
        introduced_at=now - timedelta(days=30),
        spaced_success_at=now - timedelta(days=5),
        free_use_first_at=now - timedelta(days=2),
        free_use_last_at=now - timedelta(days=2),
    )
    assert concept_life.earliest_held_at(spaced, now=now) == datetime(2026, 10, 29, tzinfo=UTC)

    # Free use done; the spaced item waits 20 hours after the last contact.
    used = _progress(
        introduced_at=now - timedelta(days=30),
        free_use_first_at=now - timedelta(days=20),
        free_use_last_at=now - timedelta(days=10),
        last_review=now - timedelta(hours=2),
    )
    assert concept_life.earliest_held_at(used, now=now) == now + timedelta(hours=18)

    # Nothing yet, long ago introduced: a free use today, the second a week on.
    idle = _progress(introduced_at=now - timedelta(days=60), last_review=now - timedelta(days=9))
    assert concept_life.earliest_held_at(idle, now=now) == week_on

    assert concept_life.earliest_held_at(_progress(held_at=now, introduced_at=now), now=now) is None
    assert concept_life.earliest_held_at(None, now=now) is None


def test_earliest_cover_days_takes_the_soonest_units_and_the_words_quota():
    floor = level_forecast.earliest_cover_days
    one = level_forecast.CHECKPOINT_DAYS
    # Two units needed: the second soonest of those on their way, then the épreuve.
    assert floor(units_needed=2, pending_earliest_days=(20.0, 3.0, 10.0)) == 10 + one
    # One on its way (day 5) and four not met at one a day, each held 14 days in.
    assert floor(units_needed=3, pending_earliest_days=(5.0,), units_remaining=4, units_per_week=7) == 15 + one
    # Not enough units at this intake: no floor to promise.
    assert floor(units_needed=3, pending_earliest_days=(1.0,)) is None
    # 30 words to go, 10 on their way, 10 new a day: two days; a failed épreuve's week wins.
    assert floor(units_needed=0, words_needed=30, words_on_the_way=10, words_per_day=10) == 2 + one
    assert (
        floor(units_needed=0, words_needed=30, words_on_the_way=10, words_per_day=10, checkpoint_floor_days=7)
        == 7 + one
    )
    assert floor(units_needed=0, words_needed=5, words_per_day=0) is None


def test_the_range_never_starts_before_the_floor():
    assert level_forecast.forecast_range(10, capped=False) == (8, 13)
    assert level_forecast.forecast_range(10, capped=False, earliest_days=12.2) == (13, 13)
    assert level_forecast.forecast_range(10, capped=True, earliest_days=12.2) == (
        level_forecast.CAP_DAYS,
        level_forecast.CAP_DAYS,
    )


# ---------------------------------------------------------------------------
# 4. Time: measured practice, and what the days left cost
# ---------------------------------------------------------------------------


def _journey(db_session, user, *, start: datetime, minutes: int, active: int) -> DailyJourney:
    journey = DailyJourney(
        user_id=user.id,
        local_date=start.date(),
        status="completed",
        started_at=start,
        completed_at=start + timedelta(minutes=minutes),
        recap_snapshot={"active_seconds": active},
    )
    db_session.add(journey)
    db_session.commit()
    return journey


def _seance(db_session, user, *, start: datetime, answers: list[int], end: int, in_journey: bool = False):
    seance = AtelierSession(
        user_id=user.id,
        status="completed",
        started_at=start,
        completed_at=start + timedelta(minutes=end),
        quote_payload={"forge": {"journey_step_id": str(uuid.uuid4())}} if in_journey else {"forge": {}},
    )
    db_session.add(seance)
    db_session.flush()
    rows = []
    for minute in answers:
        attempt = AtelierAttempt(
            atelier_session_id=seance.id,
            user_id=user.id,
            round="forge",
            mode="transform",
            exercise_id=f"ex-{minute}",
            created_at=start + timedelta(minutes=minute),
        )
        db_session.add(attempt)
        rows.append(attempt)
    db_session.commit()
    return seance, rows


def _reviews(db_session, user, moments: list[datetime]) -> None:
    lemma = f"mot{uuid.uuid4().hex[:6]}"
    word = VocabularyWord(language="fr", word=lemma, normalized_word=lemma, difficulty_level=1)
    db_session.add(word)
    db_session.flush()
    progress = UserVocabularyProgress(user_id=user.id, word_id=word.id, reps=len(moments), state="reviewing")
    db_session.add(progress)
    db_session.flush()
    for moment in moments:
        db_session.add(ReviewLog(progress_id=progress.id, review_date=moment, rating=3))
    db_session.commit()


def test_practice_time_counts_each_minute_once(db_session):
    user = _user(db_session)
    start = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    _journey(db_session, user, start=start, minutes=15, active=600)
    # A séance the scene ran is inside the scene's time already.
    _seance(db_session, user, start=start + timedelta(minutes=5), answers=[6, 7], end=10, in_journey=True)
    seance, attempts = _seance(db_session, user, start=start + timedelta(hours=1), answers=[2, 5], end=10)
    _reviews(
        db_session,
        user,
        [
            # Inside the scene: its clock has them.
            start + timedelta(minutes=2),
            start + timedelta(minutes=3),
            # In the séance's capped gap (its clock stops at 10:08): 30 of
            # these 60 seconds and the next 30 are the deck's.
            start + timedelta(hours=1, minutes=7, seconds=30),
            start + timedelta(hours=1, minutes=8, seconds=30),
            start + timedelta(hours=1, minutes=9),
            # The word deck on its own: three 30-second gaps...
            start + timedelta(hours=2),
            start + timedelta(hours=2, seconds=30),
            start + timedelta(hours=2, seconds=60),
            start + timedelta(hours=2, seconds=90),
            # ...a break (counts nothing), then 20 seconds more.
            start + timedelta(hours=2, minutes=30),
            start + timedelta(hours=2, minutes=30, seconds=20),
        ],
    )
    measured = level_plan.practice_time(
        db_session, user, since=start - timedelta(days=1), until=start + timedelta(days=1)
    )
    assert measured["scenes_seconds"] == 600
    assert measured["forge_seconds"] == active_seconds(seance, attempts) == 480
    assert measured["words_seconds"] == 60 + 110
    assert measured["total_seconds"] == 600 + 480 + 60 + 110
    assert measured["days"] == [start.date()]
    # Outside the window: nothing.
    later = level_plan.practice_time(db_session, user, since=start + timedelta(days=1), until=start + timedelta(days=2))
    assert later["total_seconds"] == 0 and later["days"] == []


def _emit(db_session, journey, name: JourneyEventName, at: datetime, **metadata) -> None:
    event = record_journey_event(
        db_session,
        event_name=str(name),
        user_id=journey.user_id,
        source_key=effect_source_key(journey_id=journey.id, effect=f"{name}:{at.isoformat()}"),
        metadata={"journey_id": str(journey.id), **metadata},
    )
    assert event is not None
    event.occurred_at = at


def test_a_review_made_while_the_scene_was_paused_is_the_decks(db_session):
    """Only the stretches the scene's clock counted are the scene's, not its whole span."""

    user = _user(db_session)
    start = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    journey = _journey(db_session, user, start=start, minutes=9 * 60 + 2, active=300)
    _emit(db_session, journey, JourneyEventName.STARTED, start)
    _emit(db_session, journey, JourneyEventName.STEP_COMPLETED, start + timedelta(minutes=2), step_id="s0", estimated_seconds=60)
    _emit(db_session, journey, JourneyEventName.PAUSED, start + timedelta(minutes=3), revision=2)
    # Nine hours away, then the last step and the finish.
    _emit(db_session, journey, JourneyEventName.STEP_COMPLETED, start + timedelta(hours=9), step_id="s1", estimated_seconds=60)
    _emit(db_session, journey, JourneyEventName.COMPLETED, start + timedelta(hours=9, minutes=2))
    db_session.commit()
    _reviews(
        db_session,
        user,
        [
            # In a stretch the scene counted: its clock has them.
            start + timedelta(seconds=30),
            start + timedelta(seconds=60),
            # While the scene was paused: the deck's.
            start + timedelta(hours=3),
            start + timedelta(hours=3, seconds=30),
            start + timedelta(hours=3, seconds=60),
        ],
    )
    # The windows are the measurement's own segments: 120 + 60 + 120 seconds.
    windows = journey_events.active_windows(
        journey_events.journey_events_for(db_session, journey.id), until=journey.completed_at
    )
    measurement = journey_events.measure_journey_duration(db_session, journey_id=journey.id, until=journey.completed_at)
    assert sum((end - begin).total_seconds() for begin, end in windows) == measurement.active_seconds == 300
    measured = level_plan.practice_time(
        db_session, user, since=start - timedelta(days=1), until=start + timedelta(days=1)
    )
    assert measured["scenes_seconds"] == 300
    assert measured["words_seconds"] == 60


def _forecast(status: str, low: int, high: int) -> dict:
    return {
        "status": status,
        "range_days": [low, high],
        "projected_dates": [_day(NOW + timedelta(days=low)), _day(NOW + timedelta(days=high))],
        "capped": False,
        "earliest_days": low - 5,
        "earliest_date": _day(NOW + timedelta(days=low - 5)),
        "basis": {"active_days": 9, "active_days_required": 7},
    }


def test_measured_days_cost_the_learners_own_minutes(db_session):
    user = _user(db_session)
    # 140 minutes measured over the last fortnight: ten a day.
    _journey(db_session, user, start=NOW - timedelta(days=1), minutes=150, active=140 * 60)
    time, invested = level_plan._time(
        db_session,
        user,
        forecast=_forecast("available", 30, 40),
        band_since=None,
        words_per_day=10,
        rules_per_week=4,
        now=NOW,
    )
    assert time["status"] == "measured"
    assert (time["minutes_per_day"], time["minutes_source"]) == (10, "measured")
    assert time["hours"] == [5, 7]
    assert time["range_days"] == [30, 40] and time["earliest_days"] == 25
    assert (time["active_days"], time["active_days_required"]) == (9, 7)
    assert invested["band_minutes"] == 140 and invested["scenes_minutes"] == 140
    assert invested["band_days"] == 1
    assert invested["recent_minutes_per_day"] == 10.0


def test_before_the_forecast_is_measured_the_minutes_are_the_plans(db_session):
    user = _user(db_session)
    time, invested = level_plan._time(
        db_session,
        user,
        forecast=_forecast("prior", 60, 98),
        band_since=None,
        words_per_day=10,
        rules_per_week=4,
        now=NOW,
    )
    planned = time["planned_minutes_per_day"]
    assert time["status"] == "plan" and time["minutes_source"] == "plan"
    assert time["minutes_per_day"] == planned > 0
    assert time["hours"] == [round(60 * planned / 60), round(98 * planned / 60)]
    assert invested["band_minutes"] == 0 and invested["band_days"] == 0


def test_a_capped_forecast_promises_no_hours(db_session):
    user = _user(db_session)
    capped = {**_forecast("available", 730, 730), "capped": True}
    time, _invested = level_plan._time(
        db_session, user, forecast=capped, band_since=None, words_per_day=10, rules_per_week=4, now=NOW
    )
    assert time["capped"] is True and time["hours"] is None
    nothing, _invested = level_plan._time(
        db_session, user, forecast=None, band_since=None, words_per_day=10, rules_per_week=4, now=NOW
    )
    assert nothing["status"] == "none" and nothing["range_days"] is None and nothing["hours"] is None


def test_the_plan_reads_a_fresh_learners_time_from_their_plan(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    isolated_catalog("A1", 1)
    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    time = plan["time"]
    assert time["status"] == "plan"
    assert time["minutes_source"] == "plan" and time["minutes_per_day"] == time["planned_minutes_per_day"]
    assert time["range_days"][0] >= time["earliest_days"] > 0
    assert (time["words_per_day"], time["rules_per_week"]) == level_forecast.planned_intake(user)
    assert plan["invested"]["band_minutes"] == 0


# ---------------------------------------------------------------------------
# 5. The ladder, and each criterion alone
# ---------------------------------------------------------------------------


def test_the_ladder_names_every_band_and_when_the_current_one_began():
    passed_on = datetime(2026, 8, 1, tzinfo=UTC)
    credited_on = datetime(2026, 9, 1, tzinfo=UTC)
    rows = {
        "A1.1": SimpleNamespace(status="passed", passed_at=passed_on),
        "A1.2": SimpleNamespace(status="credited", passed_at=credited_on),
        "A2.2": SimpleNamespace(status="failed", passed_at=None),
    }
    ladder, began = level_plan._ladder(rows, band="A2.2", goal="B1.2")
    states = {step["band"]: step for step in ladder}
    assert states["A1.1"]["state"] == "passed" and states["A1.1"]["on"] == "2026-08-01"
    assert states["A1.2"]["state"] == "credited" and states["A1.2"]["on"] == "2026-09-01"
    assert states["A2.1"]["state"] == "start" and states["A2.1"]["on"] is None
    assert states["A2.2"]["state"] == "current"
    assert states["B1.1"]["state"] == "ahead" and not states["B1.1"]["goal"]
    assert states["B1.2"]["goal"] is True
    assert began == credited_on


def test_each_criterion_alone_reaches_as_far_as_its_counts():
    reach = level_plan._criterion_reach
    assert reach([("A1.1", 300, 253), ("A1.2", 100, 260), ("A2.1", 0, 300)]) == {
        "covered": "A1.1",
        "working": "A1.2",
        "percent": 38,
        "list_ends": False,
    }
    assert reach([("A1.1", 0, 253)])["covered"] is None
    # The core lexicon stops: past it, no band to read.
    assert reach([("A1.1", 300, 253), ("A1.2", 0, 0)]) == {
        "covered": "A1.1",
        "working": None,
        "percent": None,
        "list_ends": True,
    }


def test_the_plans_goal_is_a_band_above_the_current_one(db_session, isolated_catalog):
    user = _user(db_session)
    isolated_catalog("A1", 1)
    user.cefr_target_level = "B1.1"
    db_session.commit()
    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    goal = plan["goal"]
    assert (goal["band"], goal["bands_left"]) == ("B1.1", 4)
    # A1.1 to B1.1: every band's words and units as their coverage counts them.
    assert goal["units_left"] == plan["rules"]["to_go"] > 0
    assert goal["words_left"] >= plan["words"]["to_go"] > 0
    assert goal["weeks"] > 0
    assert [step["band"] for step in plan["ladder"] if step["goal"]] == ["B1.1"]
    user.cefr_target_level = "A1.1"
    db_session.commit()
    plan = level_plan.build_level_plan(db_session, user, now=NOW)
    assert plan["goal"] is None
    assert not any(step["goal"] for step in plan["ladder"])


def test_the_skills_read_the_words_and_the_rules_band_by_band(db_session, isolated_catalog, small_band):
    user = _user(db_session)
    units = [isolated_catalog("A1", order) for order in (1, 2)]
    _hold(db_session, user, units[0])
    for lemma in ("bonjour", "merci", "café", "pain"):
        _know(db_session, user, lemma)
    skills = level_plan.build_level_plan(db_session, user, now=NOW)["skills"]
    # A1.1 is covered on both counts; the rules' next band is A1.2, the small
    # band's vocabulary has no A1.2 words: the list ends.
    assert skills["rules"]["covered"] == "A1.1" and skills["rules"]["working"] == "A1.2"
    assert skills["rules"]["percent"] == 0
    assert skills["words"] == {"covered": "A1.1", "working": None, "percent": None, "list_ends": True}
