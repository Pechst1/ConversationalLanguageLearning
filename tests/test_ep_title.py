"""#577 (child of root cause #143): one title per episode.

Live walk 2026-11-07/09: Home, the scene and the Feuilleton named one day three ways.
Each surface picked «the day's page» by its own rule: Home took the newest scene of the
journey (the last act's page on a several-act day) or, with no scene, the season's
planned tentpole; the Feuilleton took the first act, else the title stored when the
day was planned; the scene reader took the page of the act it plays. The episode title
is now read through one function (``journey_contracts.episode_title``) from one record,
the day's first-act page (else what the journey stored at planning).

Fake models only: nothing is spent.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelScene
from app.services import story_headline
from app.services.journey_contracts import StepKind
from app.services.story_archive import build_archive
from app.services.story_headline import episode_headline
from tests import test_story_acts_morning as morning
from tests.test_season_one import TurnScript

assembled_client = morning.assembled_client
clock = morning.clock
journey_enabled = morning.journey_enabled
season_on = morning.season_on
acts_writer = morning.acts_writer


def _planned_day(assembled_client, db_session, monkeypatch, acts_writer):
    """A learner whose day plans two acts: (user, driver, journey, first page, act page)."""

    morning._acts_on(monkeypatch)
    user, d = morning._intensif_learner_on_a_gap_day(assembled_client, db_session)
    morning._night(db_session, user)
    d.create()
    assert d.journey["status"] == "active", d.journey
    acts_writer.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La soirée se termine.", callback_fr="Vous avez écouté.")
    journey = db_session.get(DailyJourney, uuid.UUID(str(d.journey["id"])))
    scene_steps = [step for step in journey.steps if StepKind(step.kind) == StepKind.SCENE]
    first_page = db_session.get(
        GraphicNovelScene, uuid.UUID(scene_steps[0].private_task["scenario_brief"]["story_context"]["scene_id"])
    )
    act_page = db_session.get(
        GraphicNovelScene, uuid.UUID(scene_steps[1].private_task["act_brief"]["story_context"]["scene_id"])
    )
    assert first_page.title != act_page.title, "the day needs two differently titled acts"
    assert act_page.created_at >= first_page.created_at
    return user, d, journey, first_page, act_page


def _feuilleton_title(db_session, user, journey_id, act: int = 1) -> str:
    [filed] = [
        day
        for season in build_archive(db_session, user)["seasons"]
        if season["loaded"]
        for chapter in season["chapters"]
        for day in chapter["days"]
        if day["journey_id"] == str(journey_id) and day["act"] == act
    ]
    return filed["title_fr"]


def _scene_header_title(assembled_client, d, act: int = 1) -> str:
    """The title the scene reader prints for the act it plays (the page of that act)."""

    page = assembled_client.get(f"/api/v1/story-engine/episodes?journey_id={d.journey['id']}", headers=d.headers)
    assert page.status_code == 200, page.text
    [episode] = [row for row in page.json()["episodes"] if (row.get("act") or 1) == act]
    return episode["title_fr"]


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_home_scene_header_and_feuilleton_title_a_day_from_its_first_act(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    user, d, journey, first_page, _act_page = _planned_day(assembled_client, db_session, monkeypatch, acts_writer)

    home = episode_headline(db_session, user, journey, local_date=journey.local_date)["title_fr"]
    header = _scene_header_title(assembled_client, d)
    d.play(answer="Une chanson triste.")
    assert d.finish("complete").status_code == 200
    feuilleton = _feuilleton_title(db_session, user, d.journey["id"])

    assert home == header == feuilleton == first_page.title, (
        f"one episode, three titles: Home {home!r}, scene {header!r}, Feuilleton {feuilleton!r}"
    )


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_home_titles_a_planned_day_from_the_journey_not_the_season_plan(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    """A day whose page is not in the engine's scenes (an authored stand-in) still has
    a title, stored when it was planned. Home named it by the season's planned tentpole
    instead: the scene header and the Feuilleton said the journey's own."""

    user, d, journey, first_page, _act_page = _planned_day(assembled_client, db_session, monkeypatch, acts_writer)
    stored = str(journey.scenario_snapshot["title_fr"])
    assert stored == first_page.title
    for scene in db_session.scalars(select(GraphicNovelScene).where(GraphicNovelScene.user_id == user.id)).all():
        db_session.delete(scene)
    db_session.flush()
    monkeypatch.setattr(
        story_headline, "_tentpole", lambda live, user: ("Le titre prévu par la saison", [], "La saison", None)
    )

    home = episode_headline(db_session, user, journey, local_date=journey.local_date)["title_fr"]
    header = d.journey["scenario"]["title_fr"]
    journey.status = "completed"
    db_session.flush()
    feuilleton = _feuilleton_title(db_session, user, journey.id)

    assert home == header == feuilleton == stored, (
        f"one episode, three titles: Home {home!r}, scene {header!r}, Feuilleton {feuilleton!r}"
    )


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_home_headlines_the_day_until_its_last_act_is_over(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    """The headline is over (None: the finished card speaks) when every act's page is
    settled, not when the title page alone is: an open later act is still today."""

    user, d, journey, first_page, act_page = _planned_day(assembled_client, db_session, monkeypatch, acts_writer)

    first_page.status = "completed"
    db_session.flush()
    open_act = episode_headline(db_session, user, journey, local_date=journey.local_date)
    assert open_act is not None and open_act["title_fr"] == first_page.title, "act 2 is still ahead"

    act_page.status = "completed"
    db_session.flush()
    assert episode_headline(db_session, user, journey, local_date=journey.local_date) is None

    first_page.status = "available"
    db_session.flush()
    reopened = episode_headline(db_session, user, journey, local_date=journey.local_date)
    assert reopened is not None and reopened["title_fr"] == first_page.title
