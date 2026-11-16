"""Phase 2 «Folge in Akten», PR 3a: the morning plays the acts the night wrote.

The night wrote the day's first act (the page) and, with ``ATELIER_STORY_ACTS`` on for
the learner, the acts after it (tests/test_story_acts_night.py). In the morning the page
is served as always, and the acts written after *that* page are taken with it
(``story_acts.take_acts``): the plan keeps the ones the day holds, each kept act is
published as a scene of its own after the first (``living_story.bind_act``), and every
act is closed out — served when the day plays it, billed now when it does not
(``story_acts.close_acts``). Each act has its own reply and its own ending; a later
act's ending settles its own character's scene and never the day, the chapter or the
season, which the first act owns (``living_story.settle_resolution``). A day without
acts — every day while the switch is off — is exactly the day it was.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import coulisses, story_acts, story_lanes, story_memory
from app.services import daily_journey as daily_journey_module
from app.services import living_story as engine
from app.services.journey_contracts import DEFAULT_DAY_SHAPE, StepKind, step_act
from app.services.journey_day_shapes import DayShapeDecision
from app.services.journey_latency import (
    PREFETCH_CONSUMED_EVENT,
    PREFETCH_DISCARDED_EVENT,
    PREFETCH_EVENT,
    prefetch_scene_for,
    sweep_expired_prefetches,
    take_prefetched_scene,
)
from tests import test_journey_end_to_end as support
from tests import test_season_one as season_support
from tests import test_story_acts_night as night_support
from tests.test_season_one import TurnScript
from tests.test_story_acts_night import _learner, _page

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled
season_on = season_support.season_on
night = night_support.night
acts_writer = night_support.acts_writer


def _closing(db_session, row: PilotEvent) -> list[PilotEvent]:
    return list(
        db_session.scalars(
            select(PilotEvent).where(
                PilotEvent.event_type.in_([PREFETCH_CONSUMED_EVENT, PREFETCH_DISCARDED_EVENT]),
                PilotEvent.entity_id == str(row.id),
            )
        ).all()
    )


def _written(db_session, user, roles) -> tuple[PilotEvent, dict[str, PilotEvent]]:
    page = _page(db_session, user)
    for role in roles:
        assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role=role) == "prefetched"
    rows = {str(row.payload["role"]): row for row in story_acts.act_rows(db_session, user, prefetch_id=str(page.id))}
    return page, rows


# ---------------------------------------------------------------------------
# Taking the acts, and closing them out
# ---------------------------------------------------------------------------


def test_the_morning_takes_the_acts_written_after_the_page_it_serves_in_play_order(db_session, night):
    user = _learner(db_session, minutes=30, cefr="B1.1")
    page, rows = _written(db_session, user, ["soir", "cote"])

    served = take_prefetched_scene(db_session, user)
    acts = story_acts.take_acts(db_session, user, served)

    assert [str(act.role) for act in acts] == ["cote", "soir"], "«À côté» is played before «Le soir»"
    assert [act.scenario.story_context[story_acts.ACT_ROW_KEY] for act in acts] == [
        str(rows["cote"].id),
        str(rows["soir"].id),
    ]
    assert all(act.scenario.story_context["act"]["first_scenario_key"] == served.scenario_key for act in acts)
    assert len(story_acts.act_rows(db_session, user, prefetch_id=str(page.id))) == 2, (
        "nothing is closed out before the day is planned"
    )


def test_acts_need_the_switch_and_the_page_they_were_written_after(db_session, night, monkeypatch):
    user = _learner(db_session, minutes=30, cefr="B1.1")
    _written(db_session, user, ["soir"])
    served = take_prefetched_scene(db_session, user)

    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)
    assert story_acts.take_acts(db_session, user, served) == []
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", True)
    unwritten = replace(served, story_context={k: v for k, v in served.story_context.items() if k != "prefetch_id"})
    assert story_acts.take_acts(db_session, user, unwritten) == [], "a page written live has no act after it"
    other = replace(served, story_context={**served.story_context, "prefetch_id": str(uuid.uuid4())})
    assert story_acts.take_acts(db_session, user, other) == [], "only the acts written after this page"


def test_the_acts_the_day_plays_are_served_and_the_ones_it_gives_up_are_billed(db_session, night):
    user = _learner(db_session, minutes=30, cefr="B1.1")
    page, rows = _written(db_session, user, ["soir", "cote"])
    served = take_prefetched_scene(db_session, user)
    acts = story_acts.take_acts(db_session, user, served)
    soir = next(act for act in acts if str(act.role) == "soir")

    story_acts.close_acts(db_session, user, acts, played=[soir])
    db_session.commit()

    [kept] = _closing(db_session, rows["soir"])
    assert kept.event_type == PREFETCH_CONSUMED_EVENT and kept.cost_usd == 0.0, (
        "a played act is billed on the scene it is published as"
    )
    [given_up] = _closing(db_session, rows["cote"])
    assert given_up.event_type == PREFETCH_DISCARDED_EVENT and given_up.payload["reason"] == "not_played"
    assert given_up.cost_usd == pytest.approx(0.004), "an act the day does not play is billed now"
    assert story_acts.act_rows(db_session, user, prefetch_id=str(page.id)) == []
    assert story_acts._unbilled_usd(db_session, user) == 0.0

    # Closed out once: the sweep never bills them again, and a second close writes nothing.
    story_acts.close_acts(db_session, user, acts, played=[])
    db_session.commit()
    assert len(_closing(db_session, rows["cote"])) == 1 and len(_closing(db_session, rows["soir"])) == 1
    for row in (rows["soir"], rows["cote"], page):
        row.occurred_at = row.occurred_at - timedelta(seconds=settings.ATELIER_JOURNEY_PREFETCH_TTL_SECONDS + 60)
    db_session.commit()
    assert sweep_expired_prefetches(db_session) == 0


def test_an_act_that_cannot_be_read_is_closed_out_and_billed(db_session, night):
    user = _learner(db_session, minutes=30, cefr="B1.1")
    _page_row, rows = _written(db_session, user, ["soir"])
    row = rows["soir"]
    row.payload = {**row.payload, "brief": {"not": "a brief"}}
    flag_modified(row, "payload")
    db_session.commit()

    assert story_acts.take_acts(db_session, user, take_prefetched_scene(db_session, user)) == []
    db_session.commit()

    [closed] = _closing(db_session, row)
    assert closed.event_type == PREFETCH_DISCARDED_EVENT and closed.payload["reason"] == "unreadable_brief"


# ---------------------------------------------------------------------------
# The morning: a day of two acts, planned, published and played
# ---------------------------------------------------------------------------


def _standard_day(monkeypatch) -> None:
    """The dice deal today's ordinary practice day: a short day or a letter day plays
    one act (``plan_journey``), and which one a random learner is dealt is not what
    these tests are about."""

    monkeypatch.setattr(
        daily_journey_module,
        "choose_day_shape",
        lambda dice: DayShapeDecision(shape=DEFAULT_DAY_SHAPE, reason="acts_test"),
    )


def _acts_on(monkeypatch) -> None:
    # Acts are played on a practice day, as production plans every day (the suite's
    # default is the classic day, tests/conftest.py).
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS_COHORT", "*")
    # A long day's «Coulisses» is written on a thread once the day is bound; here it is
    # never sent (as in tests/test_wp93_day_rebalance.py), so no thread shares the
    # suite's one connection with the test.
    monkeypatch.setattr(coulisses, "dispatcher", lambda job: None)
    _standard_day(monkeypatch)


def _intensif_learner_on_a_gap_day(assembled_client, db_session):
    """An A2 learner on Intensif, on a generated day of the season: the night writes
    «Le soir» after the page (tests/test_story_acts_night.py)."""

    from app.services.season.admin import jump_to_day

    email = f"acts-morning-{uuid.uuid4()}@example.com"
    headers = support.register(assembled_client, email, cefr="A2.1")
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=14)
    user.daily_goal_minutes = 30
    db_session.commit()
    return user, support.Driver(assembled_client, headers, db=db_session)


def _night(db_session, user) -> tuple[PilotEvent, PilotEvent]:
    assert prefetch_scene_for(db_session, user) == "prefetched"
    page = db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == PREFETCH_EVENT)
    ).one()
    assert story_acts.roles_to_write(db_session, user) == ["soir"]
    assert story_acts.write_act(db_session, user, prefetch_id=str(page.id), role="soir") == "prefetched"
    [act] = story_acts.act_rows(db_session, user, prefetch_id=str(page.id))
    return page, act


def _steps(db_session, journey_id) -> list[DailyJourneyStep]:
    journey = db_session.get(DailyJourney, uuid.UUID(str(journey_id)))
    db_session.refresh(journey)
    return sorted(journey.steps, key=lambda step: step.ordinal)


def _live(db_session, user) -> dict:
    thread = engine._active_thread(db_session, SimpleNamespace(id=user.id))
    db_session.refresh(thread)
    return dict((thread.state or {}).get(engine.STATE_KEY) or {})


@pytest.mark.parametrize("season_on", [False, True], ids=["one-actor", "lanes"], indirect=True)
def test_a_day_of_two_acts_is_planned_published_and_played_act_by_act(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    _acts_on(monkeypatch)
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    page, act_row = _night(db_session, user)
    day_before = int(_live(db_session, user).get("day_index") or 0)

    d.create()

    assert d.journey["status"] == "active", d.journey
    steps = _steps(db_session, d.journey["id"])
    story = [step for step in steps if StepKind(step.kind) in (StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION)]
    assert [(str(step.kind), step_act(step)) for step in story] == [
        ("scene", 1), ("respond", 1), ("resolution", 1), ("scene", 2), ("respond", 2), ("resolution", 2),
    ], "each act is its scene, its reply and its ending, played straight after the one before"
    later_scene = story[3]
    assert later_scene.private_task["act_role"] == "soir"
    act_brief = later_scene.private_task["act_brief"]
    act_scene = db_session.get(GraphicNovelScene, uuid.UUID(act_brief["story_context"]["scene_id"]))
    first_scene = db_session.get(
        GraphicNovelScene, uuid.UUID(story[0].private_task["scenario_brief"]["story_context"]["scene_id"])
    )
    assert act_scene.status == "available" and act_scene.title == "La radio du soir"
    assert act_scene.source_snapshot["act"] == {"number": 2, "role": "soir"}
    assert act_scene.source_snapshot["owns_episode"] is False and act_scene.episode_index is None
    assert act_scene.source_snapshot["serial_episode_id"] == first_scene.source_snapshot["serial_episode_id"]
    assert act_scene.source_snapshot["journey_id"] == d.journey["id"]
    assert len(act_scene.panels) == 4
    # The act was served (its consume row) and billed on its scene.
    [closed] = _closing(db_session, act_row)
    assert closed.event_type == PREFETCH_CONSUMED_EVENT
    costs = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.event_type == "journey_story_scene_cost", PilotEvent.entity_id == str(act_scene.id)
        )
    ).all()
    assert [row.payload["stage"] for row in costs] == ["act"]
    assert story_acts.act_rows(db_session, user, prefetch_id=str(page.id)) == []
    live = _live(db_session, user)
    assert [row.get("act") for row in live["recent_situations"][-2:]] == [None, {"number": 2, "role": "soir"}], (
        "a later page may not repeat today's acts either"
    )
    # The snapshot: the first act's scene carries the day's «Précédemment»; the act's page is its own.
    public = {step["id"]: step for step in d.journey["steps"]}
    assert public[str(later_scene.id)]["prompt"]["setup_fr"] == act_brief["setup_fr"]

    acts_writer.calls.clear()
    acts_writer.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La soirée se termine.", callback_fr="Vous avez écouté.")
    d.play(answer="Une chanson triste.")
    assert d.finish("complete").status_code == 200
    assert d.journey["status"] == "completed"

    # Each reply was to its own act's page: the one actor's turn, or the voice's reply.
    pages = [
        (payload.get("scene") or {}).get("title_fr")
        for schema, payload in acts_writer.calls
        if schema in ("SemanticTurn", "VoiceReply")
    ]
    assert len(set(pages)) == 2 and pages[0] != "La radio du soir" and pages[-1] == "La radio du soir", pages
    assert pages == sorted(pages, key=lambda title: title == "La radio du soir"), "the act is played after the first"
    # The day's reveals are kept in every act's reply and ending, as in the first act's;
    # only the first act moves the season (no flag to settle, no gate, no «cap», no agency).
    endings_written = [
        (payload["story"].get("season_turn") or {})
        for schema, payload in acts_writer.calls
        if schema in ("SemanticTurn", "StoryTurn")
    ]
    first_turn, act_turn = endings_written[0], endings_written[-1]
    assert first_turn.get("must_not"), first_turn
    assert {key: act_turn.get(key) for key in ("season", "gap", "must_not")} == {
        key: first_turn.get(key) for key in ("season", "gap", "must_not")
    }
    assert act_turn["may_set"] == [] and act_turn["gate"] is None
    # How the act's speaker addresses the learner is not a move of the season (#147): it stays.
    assert not {"heading", "agency"} & set(act_turn), act_turn
    if settings.ATELIER_STORY_TURN_LANES_ENABLED:
        reveals = [payload.get("never_reveal") for schema, payload in acts_writer.calls if schema == "VoiceReply"]
        assert reveals[0] and reveals[-1] == reveals[0], "the act's voice keeps the day's reveals"
    steps = _steps(db_session, d.journey["id"])
    endings = [step for step in steps if StepKind(step.kind) is StepKind.RESOLUTION]
    assert all(step.private_task.get("resolution_settled") for step in endings)
    # The act's ending is its own turn's (the one actor's, or the story lane's turn), not
    # the authored fallback.
    lanes = settings.ATELIER_STORY_TURN_LANES_ENABLED
    assert endings[1].public_prompt["character_line_fr"] == ("La journée se termine." if lanes else "La soirée se termine.")
    if lanes:
        assert [step.private_task["story_lane"]["status"] for step in endings] == ["done", "done"]
    assert endings[1].private_task["story_outcome"]["serial_episode_id"] == act_scene.source_snapshot["serial_episode_id"]
    db_session.refresh(act_scene)
    db_session.refresh(first_scene)
    assert act_scene.status == "completed" and first_scene.status == "completed"
    live = _live(db_session, user)
    ids = [row["id"] for row in live["events"]]
    journey_id = d.journey["id"]
    assert f"journey:{journey_id}:story" in ids and f"journey:{journey_id}:story:act2" in ids
    assert int(live["day_index"]) == day_before + 1, "a day of two acts is one day"
    assert act_scene.recap_payload["source_key"] == f"journey:{journey_id}:story:act2"
    assert act_scene.script_payload["page_thread"]["character_id"] == act_brief["character_id"]
    assert all(
        exchange["learner"] == "Une chanson triste."
        for exchange in act_scene.script_payload["page_thread"]["exchanges"]
    )
    remembered = (live.get(story_memory.MEMORY_KEY) or {}).get("days") or []
    assert f"journey:{journey_id}:story" in remembered
    assert f"journey:{journey_id}:story:act2" in remembered, "the act's exchange is remembered for later acts"


@pytest.mark.parametrize("season_on", [False], ids=["one-actor"], indirect=True)
def test_the_app_reads_each_step_s_act_and_each_act_s_page_in_play_order(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    """PR 3b: every public step says its act, and the day's pages come in play order,
    each with its act, so the app reads each act's own page (and an older app, which
    takes the first page, still opens the day on its first act)."""

    _acts_on(monkeypatch)
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    _night(db_session, user)

    d.create()

    stored = {str(step.id): step for step in _steps(db_session, d.journey["id"])}
    public = d.journey["steps"]
    assert [step["act"] for step in public] == [step_act(stored[step["id"]]) for step in public], (
        "the public act, read from the plan's order, is the stored one"
    )
    assert [(step["kind"], step["act"]) for step in public if step["kind"] in ("scene", "respond", "resolution")] == [
        ("scene", 1), ("respond", 1), ("resolution", 1), ("scene", 2), ("respond", 2), ("resolution", 2),
    ]
    assert {step["act"] for step in public if step["kind"] not in ("scene", "respond", "resolution")} <= {1}
    later_reply = next(step for step in public if step["kind"] == "respond" and step["act"] == 2)
    act_brief = next(
        step.private_task["act_brief"] for step in stored.values() if step.private_task.get("act_brief")
    )
    assert later_reply["prompt"]["character_id"] == act_brief["character_id"], "the act's reply is its own character's"

    pages = d.client.get(
        "/api/v1/story-engine/episodes", params={"journey_id": d.journey["id"]}, headers=d.headers
    )
    assert pages.status_code == 200, pages.text
    episodes = pages.json()["episodes"]
    assert [(page["act"], page["act_role"]) for page in episodes] == [(1, None), (2, "soir")]
    assert episodes[1]["title_fr"] == "La radio du soir"
    assert episodes[1]["scene_id"] == act_brief["story_context"]["scene_id"]
    one = d.client.get(f"/api/v1/story-engine/episodes/{episodes[1]['scene_id']}", headers=d.headers)
    assert one.status_code == 200 and one.json()["act"] == 2
    # Every page of a one-act day, the learner's whole archive included, is act 1.
    archive = d.client.get("/api/v1/story-engine/episodes", headers=d.headers).json()["episodes"]
    assert {page["act"] for page in archive if page["journey_id"] != d.journey["id"]} <= {1}


def test_a_day_without_the_switch_plays_its_page_alone_and_leaves_the_acts_to_expire(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    _acts_on(monkeypatch)
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    _page_row, act_row = _night(db_session, user)
    monkeypatch.setattr(settings, "ATELIER_STORY_ACTS", False)

    d.create()

    assert d.journey["status"] == "active", d.journey
    steps = _steps(db_session, d.journey["id"])
    assert {step_act(step) for step in steps} == {1}
    assert [str(step.kind) for step in steps].count("respond") == 1
    assert _closing(db_session, act_row) == [], "the act is billed when it expires (the sweep)"


def test_an_act_the_day_cannot_hold_is_billed_and_the_day_plays_one_act(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    from app.services.journey_contracts import DayShape

    _acts_on(monkeypatch)
    monkeypatch.setattr(
        daily_journey_module,
        "choose_day_shape",
        lambda dice: DayShapeDecision(shape=DayShape.SHORT, reason="acts_test"),
    )
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    _page_row, act_row = _night(db_session, user)

    d.create()

    assert d.journey["status"] == "active", d.journey
    assert {step_act(step) for step in _steps(db_session, d.journey["id"])} == {1}
    [closed] = _closing(db_session, act_row)
    assert closed.event_type == PREFETCH_DISCARDED_EVENT and closed.payload["reason"] == "not_played"
    assert closed.cost_usd == pytest.approx(engine.usage_cost_usd(act_row.payload["brief"]["story_context"]["generation_usage"]))
    assert not db_session.scalars(
        select(GraphicNovelScene).where(GraphicNovelScene.source_snapshot["journey_id"].as_string() == d.journey["id"])
    ).all()[1:], "only the first act was published"


def test_an_act_that_cannot_be_published_costs_the_day_its_acts_never_its_first(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    _acts_on(monkeypatch)
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    _page_row, act_row = _night(db_session, user)

    def broken(*args, **kwargs):
        raise engine.StoryUnavailable("story_thread_changed")

    monkeypatch.setattr(engine, "bind_act", broken)

    d.create()

    assert d.journey["status"] == "active", d.journey
    steps = _steps(db_session, d.journey["id"])
    assert {step_act(step) for step in steps} == {1}
    assert [str(step.kind) for step in steps].count("scene") == 1
    [closed] = _closing(db_session, act_row)
    assert closed.event_type == PREFETCH_DISCARDED_EVENT and closed.payload["reason"] == "not_played"


# ---------------------------------------------------------------------------
# The story lane: each act's ending is its own
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
def test_a_later_act_waits_for_the_ending_before_it(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    """Each act's ending settles against the story as it stands. Two lanes running at
    once would build on the same revision, and the one settling second would be refused
    and lost — the first act's day and season with it (Codex review on #495). The day
    waits for an ending being written before the next act, as the app does."""

    _acts_on(monkeypatch)
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    _night(db_session, user)
    day_before = int(_live(db_session, user).get("day_index") or 0)
    d.create()
    acts_writer.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La soirée se termine.", callback_fr="Vous avez écouté.")
    queued: list = []
    monkeypatch.setattr(story_lanes, "dispatcher", queued.append)

    for _ in range(40):  # the first act, up to its ending
        step = d.current()
        if step["kind"] == "resolution":
            break
        if step["kind"] == "respond":
            response = d.attempt({"mode": "text", "text": "Une chanson triste."})
            assert response.status_code == 200, response.text
            if response.json().get("next_turn"):
                continue
        elif step["kind"] == "recall":
            assert d.attempt(d.recall_answer(step, correct=True)).status_code == 200
        if d.journey.get("current_step_id") == step["id"]:
            d.advance()
    ending = d.current()
    assert step_act(db_session.get(DailyJourneyStep, uuid.UUID(ending["id"]))) == 1
    assert ending["prompt"]["story_pending"] is True
    [job] = queued

    refused = d.client.post(
        f"/api/v1/daily-journeys/{d.id}/advance",
        headers=d.headers,
        json={"mutation_id": support.key(), "expected_revision": d.revision, "current_step_id": ending["id"]},
    )
    assert refused.status_code == 409 and "still being written" in refused.text, refused.text

    assert story_lanes.run_story_job(job) == "done"
    assert int(_live(db_session, user)["day_index"]) == day_before + 1, "the first act counted the day"
    d.journey = d._absorb(d.client.get(f"/api/v1/daily-journeys/{d.id}", headers=d.headers).json())
    d.advance()
    monkeypatch.setattr(story_lanes, "dispatcher", lambda job: story_lanes.run_story_job(job))
    d.play(answer="Une chanson triste.")

    endings = [step for step in _steps(db_session, d.journey["id"]) if StepKind(step.kind) is StepKind.RESOLUTION]
    assert [step.private_task["story_lane"]["status"] for step in endings] == ["done", "done"]
    assert int(_live(db_session, user)["day_index"]) == day_before + 1, "a day of two acts is one day"


@pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
def test_a_dead_lane_on_a_later_act_gets_that_act_s_authored_ending(
    assembled_client, db_session, journey_enabled, clock, acts_writer, monkeypatch
):
    _acts_on(monkeypatch)
    user, d = _intensif_learner_on_a_gap_day(assembled_client, db_session)
    _night(db_session, user)
    d.create()
    acts_writer.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La soirée se termine.", callback_fr="Vous avez écouté.")
    queued: list = []
    # The first act's lane runs; the second act's is lost with its worker.
    monkeypatch.setattr(
        story_lanes,
        "dispatcher",
        lambda job: story_lanes.run_story_job(job) if not queued else None,
    )

    def answer(step):
        if step_act(db_session.get(DailyJourneyStep, uuid.UUID(step["id"]))) == 2:
            queued.append(step["id"])
        return "Une chanson triste."

    d.play(answer=answer)
    steps = _steps(db_session, d.journey["id"])
    first_end, act_end = [step for step in steps if StepKind(step.kind) is StepKind.RESOLUTION]
    assert first_end.private_task["story_lane"]["status"] == "done"
    assert act_end.private_task["story_lane"]["status"] == "pending"

    lane = dict(act_end.private_task["story_lane"])
    lane["dispatched_at"] = (
        story_lanes._now() - timedelta(seconds=story_lanes.CLAIM_GRACE_SECONDS + 5)
    ).isoformat()
    act_end.private_task = {**act_end.private_task, "story_lane": lane}
    flag_modified(act_end, "private_task")
    db_session.commit()

    assert d.client.get(f"/api/v1/daily-journeys/{d.journey['id']}", headers=d.headers).status_code == 200

    first_end, act_end = [step for step in _steps(db_session, d.journey["id"]) if StepKind(step.kind) is StepKind.RESOLUTION]
    assert act_end.private_task["story_lane"]["status"] == "fallback"
    assert act_end.private_task["resolution_settled"] is True
    assert first_end.private_task["story_lane"]["status"] == "done", "the first act's ending stands"
    assert first_end.public_prompt["character_line_fr"] != act_end.public_prompt["character_line_fr"]
