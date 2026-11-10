"""S5 · one season's end, through the HTTP API, the beat and the real task dispatch.

The learner's last answer of the season goes through the assembled daily-journey
API (``POST …/steps/{id}/attempts``: the answer that closes the season's last
chapter). The model is the scripted fake; Celery runs eager, so the beat task
(``advance_due_rollovers``) queues the writer through the real dispatcher
(``write_next_season.delay``) and the writer job runs on its own session, as a
worker would. What the learner sees is read back through ``GET /today``.

* the answer that ends the season returns at once, with the ending, and calls no
  season writer or critic;
* ``GET /today`` right after reads the stored rollover: the named interlude and
  its date, with no model call;
* the job writes; once a draft is accepted the next ``GET /today`` shows the
  premiere, and once the budget is spent it shows the interlude and its date;
* a broker that refuses the task leaves the learner on the interlude, never on a
  ``pending`` nothing is writing.
"""

from __future__ import annotations

import json
import time
from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialThread
from app.services import living_story as engine
from tests import test_journey_end_to_end as support
from tests.test_living_story import FakeProvider, driver
from tests.test_season_writer_job import Director, _finished_life
from tests.test_wp87_lanes import _respond, _to_respond, _walk_to_end

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled
clock = support.clock

TODAY_ROUTE = "/api/v1/daily-journeys/today"
SEASON_SCHEMAS = ("SeasonDraft", "SeasonReview")


class Story:
    """The story's fake provider, with the season writer's director behind it.

    ``guard`` is on while a learner's request is served: then no season writer or
    critic call may happen (recorded, since the writer swallows its own errors)."""

    def __init__(self, director: Director) -> None:
        self.story = FakeProvider()
        self.director = director
        self.guard = False
        self.forbidden: list[str] = []
        self.reads: list[str] = []

    def generate_chat_completion(self, messages, **kwargs):
        schema = json.loads(messages[0]["content"])["output_schema"]["title"]
        if schema in SEASON_SCHEMAS:
            if self.guard:
                self.forbidden.append(schema)
                raise AssertionError(f"a learner's request reached the season writer ({schema})")
            return self.director.generate_chat_completion(messages, **kwargs)
        return self.story.generate_chat_completion(messages, **kwargs)


@pytest.fixture
def season(monkeypatch, db_engine):
    """The engine on, lanes off (the answer settles in its own request), the writer
    on, Celery eager, and the worker's sessions on the test database."""

    from app.celery_app import celery_app
    from app.db import session as db_session_module
    from app.tasks import season_writer as writer_task

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_TURN_LANES_ENABLED", False)
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)
    monkeypatch.setitem(celery_app.conf, "task_always_eager", True)
    worker_sessions = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    monkeypatch.setattr(db_session_module, "SessionLocal", worker_sessions)
    monkeypatch.setattr(writer_task, "SessionLocal", worker_sessions)

    from app.tasks import season_rollover as sweep_task

    monkeypatch.setattr(sweep_task, "SessionLocal", worker_sessions)

    def install(director: Director) -> Story:
        story = Story(director)
        monkeypatch.setattr(engine, "_client", lambda: story)
        return story

    return install


def _thread(db, user_id) -> SerialThread:
    db.expire_all()
    return db.scalars(select(SerialThread).where(SerialThread.user_id == user_id)).one()


def _rollover(db, user_id) -> dict:
    return dict(_thread(db, user_id).state[engine.STATE_KEY].get("rollover") or {})


def _to_the_last_answer(client, db):
    """A learner whose next answer closes the season's last chapter."""

    d = driver(client, db)
    step = _to_respond(d)
    thread = _thread(db, d.user_id)
    state = dict(thread.state)
    live = dict(state[engine.STATE_KEY])
    # The life a season leaves behind: enough of it for the writer to ground arcs in.
    finished = _finished_life()
    for key in ("world_flags", "planted", "commitments", "consequences"):
        live[key] = [*(live.get(key) or []), *finished[key]] if isinstance(finished[key], list) else {
            **(live.get(key) or {}), **finished[key]
        }
    live["season_stage"] = "interlude"
    # The season's last chapter: today's scene closes it, and with it the season.
    live["chapter"] = {**(live.get("chapter") or {}), "interlude": True, "resolved": True}
    state[engine.STATE_KEY] = live
    thread.state = state
    # A scripted season: no authored season follows, so only the writer or the
    # reprise can (``roll_over_season``).
    thread.world_bible = {**thread.world_bible, "season_script": "s1"}
    db.commit()
    return d, step


def _end_the_season(client, db, story: Story, d, step) -> dict:
    """The last answer: returns at once, with the ending, no writer in it."""

    story.guard = True
    started = time.monotonic()
    route, _body, answered = _respond(client, d, step)
    served = time.monotonic() - started
    story.guard = False
    assert answered.status_code == 200, answered.text
    assert served < 2, f"the season's last answer took {served:.1f} s"
    assert story.forbidden == [], "the last answer reached the season writer"
    resolution = next(s for s in answered.json()["journey"]["steps"] if s["kind"] == "resolution")
    assert resolution["prompt"].get("story_pending") is not True, "the ending is in the answer"
    assert resolution["prompt"].get("character_line_fr"), "the ending is in the answer"
    rollover = _rollover(db, d.user_id)
    assert rollover["state"] == "pending" and rollover["returns_on"]
    return rollover


def _today(client, d, story: Story) -> dict:
    story.guard = True
    started = time.monotonic()
    response = client.get(TODAY_ROUTE, headers=d.headers)
    served = time.monotonic() - started
    story.guard = False
    assert response.status_code == 200, response.text
    assert served < 2, f"GET /today took {served:.1f} s"
    assert story.forbidden == [], "GET /today reached the season writer"
    return response.json()


def _finish_the_day(client, db, d) -> None:
    """The rest of the day, so the next season can begin between two days."""

    from app.db.models.daily_journey import OCCUPYING_STATUS_VALUES

    _walk_to_end(d)
    db.expire_all()
    journey = db.get(DailyJourney, UUID(d.journey["id"]))
    if journey.status in OCCUPYING_STATUS_VALUES:
        finished = d.finish()
        assert finished.status_code == 200, finished.text
    db.expire_all()
    assert db.get(DailyJourney, UUID(d.journey["id"])).status not in OCCUPYING_STATUS_VALUES


def _beat():
    """The beat's task, through Celery (eager): it queues the writer through the real
    dispatcher."""

    from app.tasks.season_rollover import advance_due_rollovers

    return advance_due_rollovers.delay().get()


def _interlude_on(view: dict, rollover: dict) -> None:
    interlude = view.get("interlude")
    assert interlude is not None, "Home shows the named interlude"
    assert interlude["returns_on"] == rollover["returns_on"] and interlude["reason_fr"]
    assert view.get("season_premiere") is None


def test_an_accepted_draft_reaches_home_as_the_premiere(assembled_client, db_session, journey_enabled, clock, season):
    story = season(Director([False, True]))
    d, step = _to_the_last_answer(assembled_client, db_session)
    rollover = _end_the_season(assembled_client, db_session, story, d, step)

    _interlude_on(_today(assembled_client, d, story), rollover)

    _finish_the_day(assembled_client, db_session, d)
    assert _beat().get("dispatch") == 1
    written = _rollover(db_session, d.user_id)
    assert written["state"] == "written" and written.get("season_file")
    assert [a["reason"] for a in written["attempts"]] == ["critic:the arc repeats season 1", "accepted"]
    # Between two days, the next sweep begins the written season.
    clock.advance(minutes=15)
    assert _beat().get("written") == 1

    view = _today(assembled_client, d, story)
    assert view.get("interlude") is None
    premiere = view.get("season_premiere")
    assert premiere is not None and premiere["number"] == 2 and premiere["title_fr"] == "Le pain du dimanche"
    thread = _thread(db_session, d.user_id)
    assert thread.world_bible["season_source"] == "written"


def test_a_spent_budget_leaves_home_on_the_interlude_until_its_date(
    assembled_client, db_session, journey_enabled, clock, season
):
    story = season(Director([False] * 10))
    d, step = _to_the_last_answer(assembled_client, db_session)
    rollover = _end_the_season(assembled_client, db_session, story, d, step)
    _finish_the_day(assembled_client, db_session, d)

    assert _beat().get("dispatch") == 1
    spent = _rollover(db_session, d.user_id)
    assert spent["state"] == "interlude"
    assert len(spent["attempts"]) == settings.ATELIER_SEASON_WRITER_MAX_ATTEMPTS
    assert story.director.drafts() == settings.ATELIER_SEASON_WRITER_MAX_ATTEMPTS
    _interlude_on(_today(assembled_client, d, story), rollover)

    # The promised date: the reprise begins, and Home says a season began.
    returns_on = date.fromisoformat(rollover["returns_on"])
    clock.moment = clock.moment.replace(year=returns_on.year, month=returns_on.month, day=returns_on.day)
    assert _beat().get("reprise") == 1
    assert story.director.drafts() == settings.ATELIER_SEASON_WRITER_MAX_ATTEMPTS, "no attempt past the cap"
    view = _today(assembled_client, d, story)
    assert view.get("interlude") is None and view.get("season_premiere") is not None


def test_a_broker_that_refuses_the_task_leaves_the_learner_on_the_interlude(
    assembled_client, db_session, journey_enabled, clock, season, monkeypatch
):
    from kombu.exceptions import OperationalError

    from app.tasks import season_writer as writer_task

    def refused(*_args, **_kwargs):
        raise OperationalError("broker unreachable")

    monkeypatch.setattr(writer_task.write_next_season, "delay", refused)
    story = season(Director([True]))
    d, step = _to_the_last_answer(assembled_client, db_session)
    rollover = _end_the_season(assembled_client, db_session, story, d, step)
    _finish_the_day(assembled_client, db_session, d)

    _beat()
    after = _rollover(db_session, d.user_id)
    assert after["state"] == "interlude", "nothing is writing: the state says so"
    assert after.get("dispatch_error")
    _interlude_on(_today(assembled_client, d, story), rollover)
    # The next sweep does not pretend either.
    clock.advance(minutes=15)
    _beat()
    assert _rollover(db_session, d.user_id)["state"] == "interlude"

    # The promised date: the broker still refuses, and the reprise begins on that date.
    returns_on = date.fromisoformat(rollover["returns_on"])
    clock.moment = clock.moment.replace(year=returns_on.year, month=returns_on.month, day=returns_on.day)
    _beat()
    began = _rollover(db_session, d.user_id)
    assert began["state"] == "reprise" and began["installed_on"] == returns_on.isoformat()
    assert story.director.drafts() == 0
    assert _today(assembled_client, d, story).get("interlude") is None


def test_the_writer_task_is_where_the_worker_loads_tasks():
    from app.celery_app import celery_app

    assert "app.tasks.season_writer" in celery_app.conf.include
    assert "app.tasks.season_rollover" in celery_app.conf.include
    celery_app.loader.import_default_modules()
    assert "app.tasks.season_writer.write_next_season" in celery_app.tasks
    assert "app.tasks.season_rollover.advance_due_rollovers" in celery_app.tasks
