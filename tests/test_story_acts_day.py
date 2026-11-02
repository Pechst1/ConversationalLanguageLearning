"""Phase 2 «Folge in Akten», PR 4: what reads a day after its acts were played.

A day may play up to three acts, each its scene, its reply and its ending, back to back
(tests/test_story_acts_morning.py). The places that used to read «the day's scene» read
each act's own: a line is spoken in the voice of its own act's character
(``line_audio.step_lines``), the Feuilleton files a planche per act the day played
(``story_archive.build_archive``), and the call rings after the last act
(tests/test_appels.py). A day of one act — every day while ``ATELIER_STORY_ACTS`` is
off — reads exactly as it did.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelScene
from app.services.cast_voices import NARRATOR_ID
from app.services.episode_audio import episode_lines
from app.services.journey_contracts import StepKind, step_act
from app.services.line_audio import _match_form, match_line, step_lines
from app.services.story_archive import build_archive
from tests import test_story_acts_morning as morning
from tests.test_season_one import TurnScript

assembled_client = morning.assembled_client
clock = morning.clock
journey_enabled = morning.journey_enabled
season_on = morning.season_on
acts_writer = morning.acts_writer

STORY = (StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION)
ANSWER = "Une chanson triste."


def _two_act_day(assembled_client, db_session, acts_writer, monkeypatch):
    """A learner on Intensif whose day plays «Le fil», then «Le soir»."""

    morning._acts_on(monkeypatch)
    user, d = morning._intensif_learner_on_a_gap_day(assembled_client, db_session)
    morning._night(db_session, user)
    d.create()
    assert d.journey["status"] == "active", d.journey
    acts_writer.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La soirée se termine.", callback_fr="Vous avez écouté.")
    return user, d


def _journey(db_session, d) -> DailyJourney:
    journey = db_session.get(DailyJourney, uuid.UUID(str(d.journey["id"])))
    db_session.refresh(journey)
    return journey


def _scene(db_session, brief: dict) -> GraphicNovelScene:
    return db_session.get(GraphicNovelScene, uuid.UUID(brief["story_context"]["scene_id"]))


# ---------------------------------------------------------------------------
# Vorlesen: each act's lines, in its own character's voice
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_a_later_act_speaks_its_own_page_reply_and_ending_in_its_character_s_voice(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    user, d = _two_act_day(assembled_client, db_session, acts_writer, monkeypatch)
    d.play(answer=ANSWER)
    assert d.finish("complete").status_code == 200

    journey = _journey(db_session, d)
    scene1, reply1, end1, scene2, reply2, end2 = [step for step in journey.steps if StepKind(step.kind) in STORY]
    assert [step_act(step) for step in (scene1, scene2)] == [1, 2]
    first_brief = scene1.private_task["scenario_brief"]
    act_brief = scene2.private_task["act_brief"]
    first_page, act_page = _scene(db_session, first_brief), _scene(db_session, act_brief)
    lead, first_lead = act_brief["character_id"], first_brief["character_id"]
    assert lead != first_lead

    # The act's scene speaks its own page, every line in its speaker's voice.
    act_lines = step_lines(db_session, journey, scene2)
    page = episode_lines(act_page)
    assert page
    for line in page:
        hit = match_line(act_lines, line.text_fr, line.character_id)
        assert hit is not None and hit.character_id == line.character_id, line.text_fr
    assert match_line(act_lines, "Elle marche encore !").character_id == lead
    # The first act's page is not this act's: none of its own lines is spoken here.
    shared = {_match_form(line.text_fr) for line in page}
    only_first = [line for line in episode_lines(first_page) if _match_form(line.text_fr) not in shared]
    assert only_first and all(match_line(act_lines, line.text_fr) is None for line in only_first)
    # And the day's first scene still speaks the first act's page.
    first_lines = step_lines(db_session, journey, scene1)
    assert all(match_line(first_lines, line.text_fr) is not None for line in episode_lines(first_page))

    # Each act's reply and ending are its own character's.
    replies = step_lines(db_session, journey, reply2)
    assert replies and {line.character_id for line in replies if line.character_id != NARRATOR_ID} == {lead}
    [ending] = step_lines(db_session, journey, end2)
    assert (ending.character_id, ending.text_fr) == (lead, end2.public_prompt["character_line_fr"])
    [first_ending] = step_lines(db_session, journey, end1)
    assert first_ending.character_id == first_lead
    assert {line.character_id for line in step_lines(db_session, journey, reply1) if line.character_id != NARRATOR_ID} == {
        first_lead
    }


# ---------------------------------------------------------------------------
# Archiv: a planche per act the day played
# ---------------------------------------------------------------------------


def _filed(db_session, user, journey_id: str) -> tuple[list[dict], dict]:
    archive = build_archive(db_session, user)
    [season] = [season for season in archive["seasons"] if season["loaded"]]
    rows = [day for chapter in season["chapters"] for day in chapter["days"] if day["journey_id"] == journey_id]
    return rows, season


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_the_feuilleton_files_a_planche_per_act_with_its_own_page_reply_and_ending(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    user, d = _two_act_day(assembled_client, db_session, acts_writer, monkeypatch)
    d.play(answer=ANSWER)
    assert d.finish("complete").status_code == 200

    journey = _journey(db_session, d)
    scene1, reply1, end1, scene2, reply2, end2 = [step for step in journey.steps if StepKind(step.kind) in STORY]
    first_page = _scene(db_session, scene1.private_task["scenario_brief"])
    act_brief = scene2.private_task["act_brief"]
    act_page = _scene(db_session, act_brief)

    rows, season = _filed(db_session, user, d.journey["id"])
    first, act = rows
    assert [(row["act"], row["act_role"]) for row in rows] == [(1, None), (2, "soir")]
    assert first["scene_id"] == str(first_page.id) and act["scene_id"] == str(act_page.id)
    assert act["title_fr"] == "La radio du soir" and first["title_fr"] == first_page.title
    assert act["character_id"] == act_brief["character_id"]
    assert {key: act[key] for key in ("date", "journey_id", "edition_no")} == {
        key: first[key] for key in ("date", "journey_id", "edition_no")
    }, "one day, one date, one Nº"
    said = lambda reply: [turn["learner"] for turn in reply.private_task["turns"]]  # noqa: E731
    assert act["learner_lines"] == said(reply2) and first["learner_lines"] == said(reply1)
    assert act["learner_lines"] and set(act["learner_lines"]) == {ANSWER}
    assert first["ending_fr"] == end1.public_prompt["character_line_fr"]
    assert act["ending_fr"] == end2.public_prompt["character_line_fr"] == "La soirée se termine."
    assert act["hook_fr"] is None, "the day's tomorrow-hook is its first act's"
    # The volume counts each act as a planche; every earlier day of this life is act 1.
    filed = [day for chapter in season["chapters"] for day in chapter["days"]]
    assert season["day_count"] == len(filed)
    assert {day["act"] for day in filed if day["journey_id"] != d.journey["id"]} <= {1}

    # Through the route, as the app reads it.
    response = d.client.get("/api/v1/story-engine/archive", headers=d.headers)
    assert response.status_code == 200, response.text
    public = [
        day
        for season in response.json()["seasons"]
        for chapter in season["chapters"]
        for day in chapter["days"]
        if day["journey_id"] == d.journey["id"]
    ]
    assert [(day["act"], day["scene_id"]) for day in public] == [(1, str(first_page.id)), (2, str(act_page.id))]


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_an_act_the_day_never_reached_is_no_planche(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    user, d = _two_act_day(assembled_client, db_session, acts_writer, monkeypatch)
    for _ in range(40):  # the first act, up to its ending
        step = d.current()
        if step["kind"] == "resolution":
            break
        if step["kind"] == "respond":
            response = d.attempt({"mode": "text", "text": ANSWER})
            assert response.status_code == 200, response.text
            if response.json().get("next_turn"):
                continue
        elif step["kind"] == "recall":
            assert d.attempt(d.recall_answer(step, correct=True)).status_code == 200
        if d.journey.get("current_step_id") == step["id"]:
            d.advance()
    assert d.current()["act"] == 1
    assert d.finish("early").status_code == 200

    journey = _journey(db_session, d)
    assert journey.status == "ended_early"
    act_scene = next(step for step in journey.steps if StepKind(step.kind) is StepKind.SCENE and step_act(step) == 2)
    assert act_scene.started_at is None and act_scene.status == "skipped"
    rows, season = _filed(db_session, user, d.journey["id"])
    assert [row["act"] for row in rows] == [1], "the act it never opened is not filed"
    assert season["day_count"] == len([day for chapter in season["chapters"] for day in chapter["days"]])


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_a_day_of_one_act_is_filed_as_it_always_was(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    morning._acts_on(monkeypatch)
    user, d = morning._intensif_learner_on_a_gap_day(assembled_client, db_session)
    # No act written after the page: the day plays its page alone.
    from app.services.journey_latency import prefetch_scene_for

    assert prefetch_scene_for(db_session, user) == "prefetched"
    d.create()
    d.play(answer=ANSWER)
    assert d.finish("complete").status_code == 200
    journey = _journey(db_session, d)
    assert [str(step.kind) for step in journey.steps].count("scene") == 1

    rows, _season = _filed(db_session, user, d.journey["id"])
    [row] = rows
    assert (row["act"], row["act_role"]) == (1, None)
    scenes = db_session.scalars(
        select(GraphicNovelScene).where(GraphicNovelScene.user_id == user.id)
    ).all()
    assert row["scene_id"] in {str(scene.id) for scene in scenes}
