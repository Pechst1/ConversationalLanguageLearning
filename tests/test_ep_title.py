"""#577 (child of root cause #143): one title per episode.

Live walk 2026-11-07/08: Home, the scene and the Feuilleton named one day three ways.
Home's headline read the day's scene as «the newest scene of the journey», the
Feuilleton as «the day's first act». On a day of several acts (Phase 2) the two are
different pages, so Home printed a later act's title over the episode the Feuilleton
files under its first act.

Fake models only: nothing is spent.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelScene
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


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_first_act_titles_the_day(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
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

    home = episode_headline(db_session, user, journey, local_date=journey.local_date)
    d.play(answer="Une chanson triste.")
    assert d.finish("complete").status_code == 200
    [filed] = [
        day
        for season in build_archive(db_session, user)["seasons"]
        if season["loaded"]
        for chapter in season["chapters"]
        for day in chapter["days"]
        if day["journey_id"] == d.journey["id"] and day["act"] == 1
    ]
    assert home["title_fr"] == first_page.title == filed["title_fr"], (
        "Home and Feuilleton title one day differently"
    )
