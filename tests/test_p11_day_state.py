# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""P11 · the day's state while the learner waits, leaves or comes back.

The 17 Nov experience review (findings 6 and 12):

1. A played scene counts as played: Home's tracker said «Szene — als Nächstes» and
   the Feuilleton did not hold the page until the WHOLE day had ended.
"""
from __future__ import annotations

from app.services.daily_session import SessionInputs, session_view
from tests import test_living_story_longitudinal as story
from tests.test_journey_end_to_end import (  # noqa: F401 - fixtures
    assembled_client,
    clock,
    journey_enabled,
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
