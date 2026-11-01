# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""Round 3 (owner, 2026-10-14): the day as one sequence, with a real daily dose.

* The day is Szene, Wörter, Grammatik, Fertig, in that order, each with its
  state and its minutes; Home's one button opens the first step not done.
* The pace (Ruhig / Normal / Schnell) sets the day's words, the rules a week
  and the séance's length; a new learner starts on Normal.
* The Tempo sheet shows what each pace costs today and in eight weeks, and
  when it reaches the goal; the rules a week, not the words, decide the date.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services import daily_session, forge_picker, vocabulary_pace
from app.services.concept_life import weekly_concept_rate
from app.services.daily_session import PACES, SessionInputs, goal_weeks, pace_option, session_view
from tests.test_journey_end_to_end import (
    assembled_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
)


def _inputs(**overrides) -> SessionInputs:
    base = {
        "pace": "normal",
        "scene_done": False,
        "scene_seconds": 480,
        "quota": 20,
        "introduced": 0,
        "reviews_due": 12,
        "words_marked_done": False,
        "forge_seconds": 300,
        "forge_blocks_today": 0,
        "forge_href": "/atelier?mode=forge&from=day",
        "exercises_today": 0,
    }
    base.update(overrides)
    return SessionInputs(**base)


def test_a_fresh_day_is_four_steps_and_the_scene_comes_first() -> None:
    view = session_view(_inputs())

    assert [step["kind"] for step in view["steps"]] == ["scene", "words", "grammar", "finish"]
    assert [step["state"] for step in view["steps"]] == ["next", "todo", "todo", "todo"]
    assert view["next_kind"] == "scene"
    words = view["steps"][1]
    # 20 new words at 20 s and 12 reviews at 6 s: 400 + 72 s, eight minutes.
    # #143: the step names every card the deck shows, the reviews too.
    assert (words["count"], words["new_left"], words["reviews"], words["minutes"]) == (32, 20, 12, 8)
    grammar = view["steps"][2]
    # 300 s at 25 s an item: twelve items, five minutes.
    assert (grammar["count"], grammar["minutes"]) == (12, 5)
    assert view["minutes_left"] == 8 + 8 + 5


def test_after_the_scene_the_words_are_next_then_the_grammar() -> None:
    view = session_view(_inputs(scene_done=True, introduced=4))
    assert view["next_kind"] == "words"
    assert view["steps"][1]["new_left"] == 16

    view = session_view(_inputs(scene_done=True, introduced=20, words_marked_done=True))
    assert view["next_kind"] == "grammar"
    assert view["steps"][1]["minutes"] == 0


def test_the_day_is_done_only_when_all_three_are_and_then_offers_ten_more_words() -> None:
    view = session_view(
        _inputs(
            scene_done=True,
            introduced=20,
            words_marked_done=True,
            forge_blocks_today=1,
            exercises_today=12,
        )
    )
    assert view["done"] is True
    assert view["next_kind"] is None
    assert view["steps"][-1]["state"] == "done"
    assert view["tally"] == {"scenes": 1, "words": 20, "exercises": 12}
    assert (view["more_words"], view["more_minutes"]) == (10, 4)


def test_the_word_step_names_the_cards_it_will_show_and_the_tally_what_was_done() -> None:
    # #153: the scene already met 3 of the 20 new words, so the deck holds 17.
    mid = session_view(_inputs(scene_done=True, introduced=3, reviews_due=0))
    assert (mid["steps"][1]["count"], mid["steps"][1]["new_left"]) == (17, 17)
    # No new words left but reviews waiting: the step names the reviews.
    reviews = session_view(_inputs(scene_done=True, introduced=20, reviews_due=9))
    assert reviews["steps"][1]["count"] == 9
    # The end screen counts words reviewed, not the pace's target.
    done = session_view(
        _inputs(scene_done=True, introduced=3, words_marked_done=True, words_reviewed_today=17, forge_blocks_today=1)
    )
    assert done["tally"]["words"] == 17


def test_words_count_as_done_without_the_mark_once_nothing_is_left() -> None:
    view = session_view(_inputs(scene_done=True, introduced=20, reviews_due=0))
    assert view["steps"][1]["state"] == "done"


def test_the_rules_a_week_decide_when_a1_is_reached() -> None:
    # A1 from nothing: 504 words and 33 units, a 27-day hold lag.
    weeks = {
        name: goal_weeks(words_left=504, units_left=33, pace=PACES[name], hold_lag_days=27)
        for name in PACES
    }
    assert round(weeks["ruhig"]) == 15
    assert round(weeks["normal"], 1) == 10.5
    assert round(weeks["schnell"]) == 8


def test_each_pace_says_what_it_costs_today_and_in_eight_weeks() -> None:
    normal = pace_option(
        PACES["normal"], scene_seconds=480, reviews_due=10, words_left=504, units_left=33, hold_lag_days=27
    )
    assert (normal["words"], normal["rules_per_week"], normal["exercises"]) == (20, 5, 12)
    # 8 min scene + 400 s words + 60 s reviews + 300 s grammar.
    assert normal["minutes_today"] == 21
    assert normal["reviews_week_8"] == 57
    assert normal["minutes_week_8"] > normal["minutes_today"]
    schnell = pace_option(
        PACES["schnell"], scene_seconds=480, reviews_due=10, words_left=504, units_left=33, hold_lag_days=27
    )
    assert schnell["exercises"] == 17
    assert schnell["minutes_today"] > normal["minutes_today"]


def test_a_picked_pace_sets_the_words_the_rules_and_the_seance() -> None:
    user = User(email="pace@example.com", hashed_password="x", daily_goal_minutes=10, new_words_per_day=10)
    assert daily_session.pace_of(user) == "ruhig"
    assert vocabulary_pace._quota(user, 1.0) == 10
    assert forge_picker.forge_budget_seconds(user) == 300

    user.daily_pace = "schnell"
    assert daily_session.pace_of(user) == "schnell"
    assert vocabulary_pace._quota(user, 1.0) == 40
    assert vocabulary_pace._quota(user, 0.5) == 20
    assert daily_session.pace_rules_per_week(user) == 8
    assert forge_picker.forge_budget_seconds(user) == 420
    # With a pace, La Forge is the day's own step, never folded into the scene.
    user.daily_goal_minutes = 30
    assert forge_picker.forge_is_folded(user) is False


def test_the_weekly_concept_rate_follows_the_pace(db_session: Session) -> None:
    from datetime import UTC, datetime

    user = User(email="rules@example.com", hashed_password="x", daily_goal_minutes=10, daily_pace="ruhig")
    db_session.add(user)
    db_session.commit()
    assert weekly_concept_rate(db_session, user, now=datetime.now(UTC)) == 3


def test_a_new_learner_starts_on_normal_and_the_settings_switch_the_pace(
    assembled_client: TestClient, db_session: Session
) -> None:
    headers = register(assembled_client, "round3-settings@example.com")
    user = db_session.get(User, learner_id(db_session, "round3-settings@example.com"))
    assert (user.daily_pace, user.new_words_per_day) == ("normal", 20)

    response = assembled_client.patch("/api/v1/users/me/settings", json={"daily_pace": "schnell"}, headers=headers)
    assert response.status_code == 200, response.text
    assert (response.json()["daily_pace"], response.json()["new_words_per_day"]) == ("schnell", 40)

    # A number typed on its own is a custom intake: the pace no longer speaks for it.
    response = assembled_client.patch("/api/v1/users/me/settings", json={"new_words_per_day": 15}, headers=headers)
    assert (response.json()["daily_pace"], response.json()["new_words_per_day"]) == (None, 15)


def test_today_carries_the_session_and_the_tempo_sheet_switches_it(
    assembled_client: TestClient, db_session: Session, journey_enabled: None
) -> None:
    headers = register(assembled_client, "round3-today@example.com")

    today = assembled_client.get("/api/v1/daily-journeys/today", headers=headers)
    assert today.status_code == 200, today.text
    session = today.json()["session"]
    assert session["pace"] == "normal"
    assert [step["kind"] for step in session["steps"]] == ["scene", "words", "grammar", "finish"]
    assert session["next_kind"] == "scene"
    # #143/#396: the day's words, the scene's share of the 20 included: the
    # scene's words are cards of the deck once it met them, so Home's number does
    # not move when the scene is played. The drill alone leaves that share to the
    # journey until it is planned (WP-L6).
    user = db_session.get(User, learner_id(db_session, "round3-today@example.com"))
    room, _reserved = vocabulary_pace.drill_new_word_room(db_session, user)
    assert 0 < room < 20
    assert session["steps"][1]["count"] == 20
    assert session["steps"][2]["href"].endswith("&from=day")

    sheet = assembled_client.get("/api/v1/daily-journeys/session/pace", headers=headers)
    assert sheet.status_code == 200, sheet.text
    body = sheet.json()
    assert body["current"] == "normal"
    assert [option["pace"] for option in body["options"]] == ["ruhig", "normal", "schnell"]
    assert [option["words"] for option in body["options"]] == [10, 20, 40]
    weeks = [option["goal_weeks"] for option in body["options"]]
    assert weeks[0] > weeks[1] > weeks[2]

    switched = assembled_client.put(
        "/api/v1/daily-journeys/session/pace", json={"pace": "ruhig"}, headers=headers
    )
    assert switched.status_code == 200, switched.text
    assert switched.json()["current"] == "ruhig"
    today = assembled_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    db_session.refresh(user)
    room, _reserved = vocabulary_pace.drill_new_word_room(db_session, user)
    assert 0 < room < 10
    # A pace changed before the deck is dealt re-plans the day.
    assert today["session"]["steps"][1]["count"] == 10


def test_the_word_step_can_be_marked_done(
    assembled_client: TestClient, db_session: Session, journey_enabled: None
) -> None:
    headers = register(assembled_client, "round3-words@example.com")
    # No journey today yet: the mark has nowhere to live and the step stays open.
    response = assembled_client.post("/api/v1/daily-journeys/session/words-done", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["steps"][1]["state"] in {"todo", "next"}


def test_a_word_count_sent_at_registration_is_kept_as_a_custom_intake(
    assembled_client: TestClient, db_session: Session
) -> None:
    response = assembled_client.post(
        "/api/v1/auth/register",
        json={"email": "round3-custom@example.com", "password": "Round3-Custom-Aa1!", "new_words_per_day": 7},
    )
    assert response.status_code in {200, 201}, response.text
    user = db_session.get(User, learner_id(db_session, "round3-custom@example.com"))
    assert (user.daily_pace, user.new_words_per_day) == (None, 7)


def test_yesterdays_unfinished_scene_carries_no_sequence(
    assembled_client: TestClient, db_session: Session, journey_enabled: None
) -> None:
    from datetime import timedelta

    from app.db.models.daily_journey import DailyJourney

    headers = register(assembled_client, "round3-midnight@example.com")
    created = assembled_client.post(
        "/api/v1/daily-journeys",
        json={"mutation_id": "round3-midnight", "timezone": "UTC", "budget_seconds": 300, "preferred_input_mode": "text"},
        headers=headers,
    )
    assert created.status_code in {200, 201, 202}, created.text
    journey = db_session.get(DailyJourney, uuid.UUID(created.json()["id"]))
    journey.local_date = journey.local_date - timedelta(days=1)
    db_session.commit()

    today = assembled_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    assert today["journey"]["id"] == str(journey.id)
    # The late scene closes yesterday's day; today's sequence starts after it.
    assert today["session"] is None
