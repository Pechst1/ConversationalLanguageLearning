"""S5 stage 3 · the next season is written by a job, with retries and caps.

The writer used to get one attempt inside the learner's request (walk #649: 6 of 14
reviewed drafts accepted, and one refusal cost the written season and two weeks).
Now a Celery task writes during the named interlude, retrying until a draft is
accepted or the rollover's budget (attempts and US$) is spent, and logs every
attempt with its refusal reason. The promised date retries once more, then the
reprise begins. No read path reaches the writer or the critic.
"""

from __future__ import annotations

import copy
import json
import time
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.db.models.serial import SerialThread
from app.services import living_story as engine
from app.services import season_rollover, season_writer
from app.services.season.world import season_world_bible
from tests import test_journey_end_to_end as support

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled
clock = support.clock

SINCE = date(2027, 1, 20)


class Director:
    """The season writer's director and critic, scripted per attempt.

    ``verdicts`` is one critic answer per attempt (True accepts); ``cost`` is what
    each call costs."""

    def __init__(self, verdicts, *, cost: float = 0.001):
        self.verdicts = list(verdicts)
        self.cost = cost
        self.calls: list[str] = []

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        self.calls.append(schema)
        if schema == "SeasonDraft":
            ref = source["material"][0]["id"]
            value = {
                "title_fr": "Le pain du dimanche",
                "logline": "The promises of last season come due.",
                "logline_fr": "Les promesses de la saison dernière reviennent.",
                "your_arc": "Keep what you promised, with the people you promised it to.",
                "first_episode_seed": "Sunday morning, bread under your arm.",
                "arcs": [
                    {
                        "id": f"written-arc-{i}",
                        "title_fr": f"Arc écrit {i}",
                        "characters": ["user"],
                        "grounded_in": ref,
                        "stages": [{"id": f"s{j}", "summary": "One sentence of the stage."} for j in range(3)],
                    }
                    for i in range(3)
                ],
                "open_threads": [
                    {"text": "Will the bread arrive?", "text_fr": "Le pain arrivera-t-il ?", "grounded_in": ref}
                ]
                * 3,
            }
        else:
            accept = self.verdicts.pop(0) if self.verdicts else False
            value = {"accepted": accept, "issues": [] if accept else ["the arc repeats season 1"]}
        return SimpleNamespace(
            content=json.dumps(value, ensure_ascii=False), model="fake-season", provider="test",
            total_tokens=10, cost=self.cost,
        )

    def drafts(self) -> int:
        return self.calls.count("SeasonDraft")


@pytest.fixture
def writer(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", True)

    def install(director: Director) -> Director:
        monkeypatch.setattr(engine, "_client", lambda: director)
        return director

    return install


@pytest.fixture
def dispatched(monkeypatch):
    """Writer jobs are recorded, and run when the test says so."""

    from app.services import season_writer_job

    queued: list[tuple[str, bool]] = []
    monkeypatch.setattr(season_writer_job, "dispatcher", lambda thread_id, final=False: queued.append((thread_id, final)))
    return queued


def _finished_life() -> dict:
    return {
        "season_index": 1,
        "day_index": 80,
        "world_flags": {"s1.ending": "partager", "lila.in_berlin": True},
        "threads": {},
        "planted": [{"id": "e2:plant", "text_fr": "La clé du compteur.", "status": "open", "day": 9}],
        "commitments": [{"id": "c1", "text_fr": "Réparer la chaise de Gus.", "status": "open"}],
        "consequences": [
            {"id": "e1:branch:0", "kind": "branch", "text_fr": "Tu as couvert Gus.", "weight": 3, "day": 20}
        ],
    }


def _pending_thread(db, user) -> SerialThread:
    live = _finished_life()
    world = copy.deepcopy(season_world_bible("s1"))
    engine.roll_over_season(None, SimpleNamespace(id="t", world_bible=world), live, day=80, today=SINCE.isoformat())
    assert live["rollover"]["state"] == "pending"
    thread = SerialThread(
        user_id=user.id, world_bible=world, state={engine.STATE_KEY: live}, news_seed={},
        current_episode_index=0, status="active",
    )
    db.add(thread)
    db.commit()
    return thread


def _rollover(db, thread_id) -> dict:
    db.expire_all()
    return db.get(SerialThread, thread_id).state[engine.STATE_KEY]["rollover"]


def _user(db):
    from tests.test_living_story_address import make_user

    return make_user(db)


def _factory(db):
    return lambda: db


# ---------------------------------------------------------------------------
# The job: retries, caps, the log
# ---------------------------------------------------------------------------


def test_the_caps_are_settings_with_the_package_proposal():
    assert settings.model_fields["ATELIER_SEASON_WRITER_MAX_ATTEMPTS"].default == 4
    assert settings.model_fields["ATELIER_SEASON_WRITER_MAX_USD"].default == 0.05


def test_the_job_retries_until_a_draft_is_accepted_and_logs_each_refusal(db_session, writer):
    from app.services import season_writer_job

    director = writer(Director([False, False, True]))
    thread = _pending_thread(db_session, _user(db_session))

    assert season_writer_job.run(thread.id, session_factory=_factory(db_session)) == "written"

    row = _rollover(db_session, thread.id)
    assert row["state"] == "written" and row["season_file"]["season_number"] == 2
    assert {arc["id"] for arc in row["season_file"]["season_arcs"]} == {f"written_arc_{i}" for i in range(3)}
    assert [attempt["reason"] for attempt in row["attempts"]] == [
        "critic:the arc repeats season 1", "critic:the arc repeats season 1", "accepted",
    ]
    assert director.drafts() == 3
    logged = db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == "story_season_writer_cost")
    ).all()
    assert [event.payload["reason"] for event in logged] == [a["reason"] for a in row["attempts"]]
    # The date is kept: a written season begins between two days or on the date.
    assert row["returns_on"] == (SINCE + timedelta(days=14)).isoformat()


def test_the_job_stops_at_the_attempt_cap(db_session, writer):
    from app.services import season_writer_job

    director = writer(Director([False] * 10))
    thread = _pending_thread(db_session, _user(db_session))

    assert season_writer_job.run(thread.id, session_factory=_factory(db_session)) == "spent"

    row = _rollover(db_session, thread.id)
    assert director.drafts() == settings.ATELIER_SEASON_WRITER_MAX_ATTEMPTS == 4
    assert row["state"] == "interlude", "nothing is writing any more; the date brings the reprise"
    assert len(row["attempts"]) == 4


def test_the_job_stops_at_the_spend_cap(db_session, writer):
    from app.services import season_writer_job

    # Two calls per attempt at US$0.02 each: the second attempt reaches US$0.08.
    director = writer(Director([False] * 10, cost=0.02))
    thread = _pending_thread(db_session, _user(db_session))

    assert season_writer_job.run(thread.id, session_factory=_factory(db_session)) == "spent"
    assert director.drafts() == 2
    row = _rollover(db_session, thread.id)
    assert round(sum(a["cost_usd"] for a in row["attempts"]), 4) == 0.08


def test_a_hyphenated_draft_is_normalised_not_refused(db_session, writer):
    from app.services import season_writer_job

    writer(Director([True]))
    thread = _pending_thread(db_session, _user(db_session))
    assert season_writer_job.run(thread.id, session_factory=_factory(db_session)) == "written"


# ---------------------------------------------------------------------------
# The sweep dispatches the job; the date retries once, then the reprise
# ---------------------------------------------------------------------------


def test_the_sweep_dispatches_the_writer_once_for_a_pending_rollover(db_session, writer, dispatched):
    from app.tasks import season_rollover as beat

    writer(Director([]))
    thread = _pending_thread(db_session, _user(db_session))
    monkey_today = SINCE + timedelta(days=1)

    beat.advance_all(db_session, today=lambda _thread_id: monkey_today)
    beat.advance_all(db_session, today=lambda _thread_id: monkey_today)

    assert dispatched == [(str(thread.id), False)]
    assert _rollover(db_session, thread.id)["dispatched_at"]


def test_on_the_promised_date_the_writer_retries_then_the_reprise_begins(db_session, writer, dispatched):
    from app.services import season_writer_job
    from app.tasks import season_rollover as beat

    director = writer(Director([False] * 10))
    thread = _pending_thread(db_session, _user(db_session))
    returns_on = date.fromisoformat(_rollover(db_session, thread.id)["returns_on"])

    beat.advance_all(db_session, today=lambda _thread_id: returns_on)
    assert dispatched == [(str(thread.id), True)], "the date fires the retry, whether or not a chapter closes"
    season_writer_job.run(thread.id, session_factory=_factory(db_session), today=returns_on, final=True)

    assert director.drafts() == 4
    db_session.expire_all()
    stored = db_session.get(SerialThread, thread.id)
    assert stored.state[engine.STATE_KEY]["rollover"]["state"] == "reprise"
    assert stored.state[engine.STATE_KEY]["rollover"]["installed_on"] == returns_on.isoformat()
    assert stored.world_bible["season_number"] == 2


def test_on_the_promised_date_a_spent_budget_goes_straight_to_the_reprise(db_session, writer, dispatched):
    from app.services import season_writer_job
    from app.tasks import season_rollover as beat

    writer(Director([False] * 10))
    thread = _pending_thread(db_session, _user(db_session))
    season_writer_job.run(thread.id, session_factory=_factory(db_session))
    returns_on = date.fromisoformat(_rollover(db_session, thread.id)["returns_on"])

    beat.advance_all(db_session, today=lambda _thread_id: returns_on)
    assert dispatched == []
    assert _rollover(db_session, thread.id)["state"] == "reprise"


# ---------------------------------------------------------------------------
# No read path reaches the writer or the critic
# ---------------------------------------------------------------------------


def test_a_polling_read_that_settles_the_season_never_reaches_the_writer(
    assembled_client, db_session, journey_enabled, clock, monkeypatch
):
    """The polling ``GET`` heals a dead lane (``heal_stale_lane`` →
    ``settle_with_fallback`` → ``settle_resolution``). Here that settle closes the
    life's interlude chapter, which ends the season: the fake provider raises on any
    call made while the GET is served."""

    from uuid import UUID

    from app.db.models.daily_journey import DailyJourneyStep
    from app.services import story_lanes as lanes
    from tests import test_wp87_lanes as wp87
    from tests.test_living_story import driver

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_TURN_LANES_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)
    provider = wp87.LaneProvider()
    reading = {"now": False}
    forbidden: list[str] = []

    class Guarded:
        def generate_chat_completion(self, messages, **kwargs):
            schema = json.loads(messages[0]["content"])["output_schema"]["title"]
            if reading["now"] or schema in ("SeasonDraft", "SeasonReview"):
                # Recorded as well as raised: the writer swallows its own errors.
                forbidden.append(schema)
                raise AssertionError(f"a read path reached the model ({schema})")
            return provider.generate_chat_completion(messages, **kwargs)

    monkeypatch.setattr(engine, "_client", lambda: Guarded())
    queued: list = []
    monkeypatch.setattr(lanes, "dispatcher", queued.append)

    d = driver(assembled_client, db_session)
    step = wp87._to_respond(d)
    # This chapter is an interlude chapter whose end ends the season.
    db_session.expire_all()
    thread = db_session.scalars(select(SerialThread).where(SerialThread.user_id == d.user_id)).one()
    state = dict(thread.state)
    live = dict(state[engine.STATE_KEY])
    live["season_stage"] = "interlude"
    live["interlude"] = season_writer.named_interlude("2020-01-01")
    live["chapter"] = {**(live.get("chapter") or {}), "interlude": True, "resolved": True}
    state[engine.STATE_KEY] = live
    thread.state = state
    # A scripted season: no authored season follows, so only the writer or the
    # reprise can (``roll_over_season``, D8).
    thread.world_bible = {**thread.world_bible, "season_script": "s1"}
    db_session.commit()

    wp87._respond(assembled_client, d, step)
    assert len(queued) == 1
    db_session.expire_all()
    row = db_session.scalars(
        select(DailyJourneyStep).where(
            DailyJourneyStep.journey_id == UUID(d.journey["id"]), DailyJourneyStep.kind == "resolution"
        )
    ).one()
    private = dict(row.private_task)
    private["story_lane"] = {**private["story_lane"], "dispatched_at": "2020-01-01T00:00:00+00:00"}
    row.private_task = private
    db_session.commit()

    reading["now"] = True
    healed = assembled_client.get(f"/api/v1/daily-journeys/{d.journey['id']}", headers=d.headers)
    reading["now"] = False
    assert forbidden == [], "the polling read reached the writer or the critic"
    assert healed.status_code == 200
    assert wp87._resolution(healed.json())["prompt"]["story_pending"] is False
    db_session.expire_all()
    after = db_session.scalars(select(SerialThread).where(SerialThread.user_id == d.user_id)).one()
    rollover = after.state[engine.STATE_KEY].get("rollover") or {}
    assert rollover.get("installed_on") or rollover.get("state") in season_rollover.STATES, (
        "the read settled the season's end (a model-free rollover)"
    )


def test_no_module_on_a_request_path_calls_the_season_writer():
    """The writer and its critic are called from the job only."""

    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    callers = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if name in ("draft_next_season", "write_attempt"):
                    callers.append(str(path.relative_to(root)))
    assert sorted(set(callers)) <= ["services/season_writer.py", "services/season_writer_job.py"], callers


# ---------------------------------------------------------------------------
# Done when (the package): the ending is released at once
# ---------------------------------------------------------------------------


def test_a_slow_writer_never_holds_the_ending(db_session, writer, monkeypatch):
    """With the writer delayed 60 s, the season's end returns at once."""

    def slow(*args, **kwargs):
        time.sleep(60)
        raise AssertionError("the writer ran in the request")

    monkeypatch.setattr(season_writer, "write_attempt", slow, raising=False)
    monkeypatch.setattr(season_writer, "draft_next_season", slow)
    live = _finished_life()
    # A scripted season: no authored season follows, so only the writer or the reprise can.
    world = {**copy.deepcopy(season_world_bible("s1")), "season_script": "s1"}
    thread = SimpleNamespace(id="slow", world_bible=world)
    started = time.monotonic()
    assert engine.roll_over_season(None, thread, live, day=80, today=SINCE.isoformat()) is False
    assert time.monotonic() - started < 2
    assert live["rollover"]["state"] == "pending"


def test_the_promised_date_is_the_first_day_of_the_next_season(db_session, writer, dispatched):
    """The interlude says «l'histoire reprend le 3 février»: the sweep at that local
    date begins season 2, so the first scene written that day is season 2's."""

    from app.services import season_writer_job
    from app.tasks import season_rollover as beat

    writer(Director([False] * 10))
    thread = _pending_thread(db_session, _user(db_session))
    row = _rollover(db_session, thread.id)
    returns_on = date.fromisoformat(row["returns_on"])
    assert row["reason_fr"].endswith(f"{season_writer.french_date(returns_on)}.")

    for day in range(15):
        today = SINCE + timedelta(days=day)
        beat.advance_all(db_session, today=lambda _thread_id, today=today: today)
        for thread_id, final in list(dispatched):
            season_writer_job.run(thread_id, session_factory=_factory(db_session), today=today, final=final)
        dispatched.clear()
        db_session.expire_all()
        season = db_session.get(SerialThread, thread.id).world_bible["season_number"]
        assert season == (2 if today >= returns_on else 1), today
