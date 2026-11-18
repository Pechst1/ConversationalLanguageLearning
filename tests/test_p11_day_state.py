# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""P11 · the day's state while the learner waits, leaves or comes back.

The 17 Nov experience review (findings 6 and 12):

1. A played scene counts as played: Home's tracker said «Szene — als Nächstes» and
   the Feuilleton did not hold the page until the WHOLE day had ended.
2. Leaving before the scene does not throw the scene away: «Arrêter ici» on the rule
   card ended the day, scene included. «Passer à la scène» skips what is left before
   it (the card unread, no lapse), and a stop there pauses the day.
"""
from __future__ import annotations

import uuid

from app.services.daily_session import SessionInputs, session_view
from tests import test_living_story_longitudinal as story
from tests.test_journey_end_to_end import (  # noqa: F401 - fixtures
    Driver,
    assembled_client,
    clock,
    journey_enabled,
    key,
    learner_id,
    register,
)
from tests.test_living_story_longitudinal import provider  # noqa: F401 - fixture

ANSWER = "Bonjour, un café s'il vous plaît."


def _archive_days(client, d) -> list[dict]:
    response = client.get("/api/v1/story-engine/archive", headers=d.headers)
    assert response.status_code == 200, response.text
    return [
        day
        for season in response.json()["seasons"]
        for chapter in season["chapters"]
        for day in chapter["days"]
    ]


def _scene_step(session: dict) -> dict:
    return next(step for step in session["steps"] if step["kind"] == "scene")


# ---------------------------------------------------------------------------
# 1. A played scene counts as played
# ---------------------------------------------------------------------------


def test_an_acknowledged_ending_is_a_played_scene_and_a_filed_page(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = story.driver(assembled_client, db_session, cefr="A1.1")
    provider.scene = story.SceneScript()
    provider.turn = story.TurnScript()
    d.create()
    d.play(answer=ANSWER)  # the scene, the reply, the ending acknowledged; no finish
    assert d.journey["status"] == "active", "the day is still open"
    assert any(s["kind"] == "resolution" and s["status"] == "completed" for s in d.journey["steps"])

    session = d.today()["session"]
    assert session is not None
    assert _scene_step(session)["state"] == "done", session["steps"]
    assert session["tally"]["scenes"] == 1
    # «Day done» still means the ended day: the finish step waits for it.
    assert session["done"] is False
    assert next(step for step in session["steps"] if step["kind"] == "finish")["state"] == "todo"

    days = _archive_days(assembled_client, d)
    page = next((day for day in days if day["journey_id"] == d.id), None)
    assert page is not None, "the page is filed once its ending was read"
    assert page["today"] is True
    assert ANSWER in page["learner_lines"]


def test_an_unplayed_scene_is_not_filed(assembled_client, db_session, journey_enabled, clock, provider):
    d = story.driver(assembled_client, db_session, cefr="A1.1")
    provider.scene = story.SceneScript()
    provider.turn = story.TurnScript()
    d.create()
    session = d.today()["session"]
    assert _scene_step(session)["state"] == "next"
    assert not [day for day in _archive_days(assembled_client, d) if day["journey_id"] == d.id]


def _inputs(**changes) -> SessionInputs:
    base = {
        "pace": "normal",
        "scene_done": True,
        "scene_seconds": 300,
        "quota": 0,
        "introduced": 0,
        "reviews_due": 0,
        "words_marked_done": True,
        "forge_seconds": 120,
        "forge_blocks_today": 1,
        "forge_href": "/forge",
        "exercises_today": 0,
        "deck": (0, 0),
    }
    return SessionInputs(**{**base, **changes})


def test_the_day_is_done_only_once_the_journey_ended():
    """Every step done, the scene played, the journey still open: not a done day."""

    open_day = session_view(_inputs(day_ended=False))
    assert [step["state"] for step in open_day["steps"][:3]] == ["done", "done", "done"]
    assert open_day["done"] is False
    assert open_day["steps"][-1]["state"] == "todo"

    ended = session_view(_inputs(day_ended=True))
    assert ended["done"] is True and ended["steps"][-1]["state"] == "done"
    # A caller that does not say (the pure tests of before): the scene decides.
    assert session_view(_inputs())["done"] is True


# ---------------------------------------------------------------------------
# 2. Leaving before the scene does not throw the scene away
# ---------------------------------------------------------------------------


def _rule_first_day(client, db_session, monkeypatch):
    """A day that opens on the rule card and its drill, before the scene (WP-93)."""

    from app.config import settings
    from app.services.grammar_catalog import FrenchCoreGrammarCatalog

    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    email = f"p11-{uuid.uuid4().hex[:8]}@example.com"
    d = Driver(client, register(client, email), db=db_session)
    d.create()
    kinds = [step["kind"] for step in sorted(d.journey["steps"], key=lambda s: s["ordinal"])]
    assert "rule" in kinds and kinds.index("rule") < kinds.index("scene"), kinds
    assert "recall" in kinds[: kinds.index("scene")], kinds
    assert d.current()["kind"] != "scene", kinds
    return d, learner_id(db_session, email)


def _post_advance(d, **extra):
    step = d.current()
    return d.client.post(
        f"/api/v1/daily-journeys/{d.id}/advance",
        headers=d.headers,
        json={
            "mutation_id": key(),
            "expected_revision": d.revision,
            "current_step_id": step["id"],
            **extra,
        },
    )


def test_skip_to_the_scene_reads_no_rule_and_books_no_lapse(
    assembled_client, db_session, journey_enabled, monkeypatch
):
    from app.services.daily_journey import DailyJourneyService

    read: list[object] = []
    monkeypatch.setattr(DailyJourneyService, "_mark_rule_read", lambda self, user, step: read.append(step.id))
    d, user_id = _rule_first_day(assembled_client, db_session, monkeypatch)
    lapses_before = _lapses(db_session, user_id)

    response = _post_advance(d, skip_to_scene=True)
    assert response.status_code == 200, response.text
    d.journey = response.json()

    assert d.current()["kind"] == "scene", "the skip lands on the scene"
    by_kind = {step["kind"]: step for step in d.journey["steps"]}
    assert by_kind["rule"]["status"] == "skipped", "the card is not read"
    assert read == [], "a skipped card never marks the rule read"
    pre_scene = [s for s in d.journey["steps"] if s["ordinal"] < by_kind["scene"]["ordinal"]]
    assert all(step["status"] == "skipped" for step in pre_scene), pre_scene
    assert _lapses(db_session, user_id) == lapses_before, "a skipped drill books no lapse"

    # Once the scene is open there is nothing ahead to skip to.
    again = _post_advance(d, skip_to_scene=True)
    assert again.status_code == 409, again.text


def test_skip_from_the_unanswered_drill_lands_on_the_scene(
    assembled_client, db_session, journey_enabled, monkeypatch
):
    d, user_id = _rule_first_day(assembled_client, db_session, monkeypatch)
    while d.current()["kind"] != "recall":
        d.advance()  # the card, read
    lapses_before = _lapses(db_session, user_id)
    plain = _post_advance(d)
    assert plain.status_code == 409, "an unanswered drill item is still not passed by «Continuer»"

    response = _post_advance(d, skip_to_scene=True)
    assert response.status_code == 200, response.text
    d.journey = response.json()
    assert d.current()["kind"] == "scene"
    assert next(s for s in d.journey["steps"] if s["kind"] == "recall")["status"] == "skipped"
    assert _lapses(db_session, user_id) == lapses_before


def test_stop_before_the_scene_pauses_the_day(assembled_client, db_session, journey_enabled, monkeypatch):
    d, _user_id = _rule_first_day(assembled_client, db_session, monkeypatch)
    stopped_on = d.current()["id"]

    response = d.finish("early")
    assert response.status_code == 200, response.text
    assert d.journey["status"] == "paused", "the day is paused, not ended"
    assert d.journey["current_step_id"] == stopped_on
    assert all(step["status"] != "skipped" for step in d.journey["steps"])

    resumed = d.client.post(
        f"/api/v1/daily-journeys/{d.id}/resume",
        headers=d.headers,
        json={"mutation_id": key(), "expected_revision": d.revision},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "active"
    assert resumed.json()["current_step_id"] == stopped_on


def _lapses(db_session, user_id) -> int:
    from sqlalchemy import func, select

    from app.db.models.grammar import UserGrammarProgress

    total = db_session.scalar(
        select(func.coalesce(func.sum(UserGrammarProgress.lapses), 0)).where(UserGrammarProgress.user_id == user_id)
    )
    return int(total or 0)
