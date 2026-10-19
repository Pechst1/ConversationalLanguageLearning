"""One tomorrow-hook per episode (#237, a child of root cause #145).

Live walk 2026-10-19: the last panel and Home promised «Qui était Odile…» while the
finished card and the Feuilleton showed another question. The hook was written for
each surface from its own source. A settled day now files ONE hook
(``script_payload.next_teaser_fr``, written when the resolution settles) and every
surface reads that string.

Fake models only: nothing is spent.
"""
from __future__ import annotations

import pytest

from app.db.models.user import User
from app.services import living_story as engine
from app.services.story_headline import episode_headline
from tests import test_living_story_longitudinal as story
from tests.test_journey_end_to_end import (  # noqa: F401 - fixtures
    assembled_client,
    clock,
    journey_enabled,
)
from tests.test_living_story_longitudinal import provider  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def one_exchange(monkeypatch):
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)


def _play(d, provider, day: int):
    """One whole day; returns the finish response (the finished card's recap)."""

    provider.scene = story.SceneScript()
    provider.turn = story.TurnScript(
        callback_fr=f"Vous avez aidé le jour {day}.",
        commitment_text=f"Passer au marché le jour {day + 3}.",
    )
    d.create()
    d.play(answer=f"Je peux aider, jour {day}.")
    response = d.finish("complete")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_last_panel_home_the_finished_card_and_the_feuilleton_say_one_hook(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = story.driver(assembled_client, db_session, cefr="A1.1")
    recap = None
    for day in range(1, 5):  # day 4 closes the chapter, as day 8 did in the live walk
        recap = _play(d, provider, day)["recap"]
        if day < 4:
            clock.advance(days=1)
    journey_id = d.journey["id"]
    assert recap["chapter_closed"], "the walk's day closed a chapter"

    scene = story.scenes_of(db_session, d)[-1]
    stored = (scene.script_payload or {}).get("next_teaser_fr")
    assert stored, "the settled day filed no tomorrow-hook"
    assert story.live_state(db_session, d)["next_teaser"]["text_fr"] == stored

    # Last panel (the finished page's «À suivre…»).
    page = assembled_client.get(f"/api/v1/story-engine/episodes/{scene.id}", headers=d.headers).json()["page"]
    assert page["a_suivre_fr"] == stored

    # The finished card's «La suite demain».
    assert recap["teaser"]["text_fr"] == stored

    # Home, the next morning.
    clock.advance(days=1)
    user = db_session.get(User, d.user_id)
    headline = episode_headline(db_session, user, None, local_date=clock.moment.date().isoformat())
    assert headline["teaser_fr"] == stored

    # The Feuilleton files the same string against the day, not another question.
    archive = assembled_client.get("/api/v1/story-engine/archive", headers=d.headers).json()
    day_row = next(
        row
        for season in archive["seasons"]
        for chapter in season["chapters"]
        for row in chapter["days"]
        if row["journey_id"] == journey_id
    )
    assert day_row.get("hook_fr") == stored, (
        "the Feuilleton's day does not carry the hook the last panel, Home and the card promised"
    )
