"""S5 stage 2 · the season ends in the request; the next one begins from stored state.

The season-end walk (draft PR #649) measured 40–66 s from the last answer to the
ending: ``settle_resolution`` called the season writer with the user and the
resolution rows locked. Here the rollover makes no model call. The life stores
one rollover state (``pending``, ``written``, ``interlude``, ``reprise``), and the
screens read it instead of inferring it. The interlude's promised date starts the
next season whether or not a chapter closes.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.db.models.serial import SerialThread
from app.services import living_story as engine
from app.services import season_writer
from app.services.season.world import season_world_bible

SINCE = date(2027, 1, 20)


def _no_model(*_args, **_kwargs):
    raise AssertionError("the rollover made a model call")


@pytest.fixture
def writer_on(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", True)
    monkeypatch.setattr(season_writer, "draft_next_season", _no_model)
    monkeypatch.setattr(engine, "_client", _no_model)


def _finished_life() -> dict:
    """A season-1 life after its finale, with enough material for a next season."""

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


def _written_file(world: dict, live: dict) -> dict:
    material = season_writer.season_material(live, world)
    draft = season_writer.SeasonDraft.model_validate(
        {
            "title_fr": "Le pain du dimanche",
            "logline": "A season grown from the learner's own open rows.",
            "logline_fr": "Une saison qui part de ta vie au quartier.",
            "your_arc": "From guest to the one who keeps the bread.",
            "first_episode_seed": "Sunday morning, the bakery is closed.",
            "arcs": [
                {
                    "id": f"written_arc_{i}",
                    "title_fr": "Le pain",
                    "characters": ["user"],
                    "grounded_in": material[0]["id"],
                    "stages": [{"id": f"s{j}", "summary": "One sentence of the stage."} for j in range(3)],
                }
                for i in range(3)
            ],
            "open_threads": [
                {"text": "Will the bread come?", "text_fr": "Le pain arrivera-t-il ?", "grounded_in": material[0]["id"]}
            ]
            * 3,
        }
    )
    return season_writer.season_file_from_draft(draft, number=2, source="written")


def test_the_season_ends_without_a_model_call_and_stores_pending(writer_on):
    world = copy.deepcopy(season_world_bible("s1"))
    thread = SimpleNamespace(id="thread-pending", world_bible=world)
    live = _finished_life()

    assert engine.roll_over_season(None, thread, live, day=80, today=SINCE.isoformat()) is False

    rollover = live["rollover"]
    assert rollover["state"] == "pending", "the writer works after the request, not in it"
    assert rollover["season"] == 2
    assert rollover["since"] == SINCE.isoformat()
    assert rollover["returns_on"] == (SINCE + timedelta(days=season_writer.INTERLUDE_WAIT_DAYS)).isoformat()
    assert live["interlude"]["returns_on"] == rollover["returns_on"]


def test_with_the_writer_off_the_state_is_a_plain_interlude(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", False)
    thread = SimpleNamespace(id="thread-off", world_bible=copy.deepcopy(season_world_bible("s1")))
    live = _finished_life()
    engine.roll_over_season(None, thread, live, day=80, today=SINCE.isoformat())
    assert live["rollover"]["state"] == "interlude"


def test_a_written_season_waiting_in_the_state_is_installed_before_the_date(writer_on):
    world = copy.deepcopy(season_world_bible("s1"))
    thread = SimpleNamespace(id="thread-written", world_bible=world)
    live = _finished_life()
    engine.roll_over_season(None, thread, live, day=80, today=SINCE.isoformat())
    live["rollover"] = {**live["rollover"], "state": "written", "season_file": _written_file(world, live)}

    tomorrow = (SINCE + timedelta(days=1)).isoformat()
    assert engine.roll_over_season(None, thread, live, day=81, today=tomorrow) is True

    assert thread.world_bible["season_number"] == 2 and thread.world_bible["season_source"] == "written"
    assert live["rollover"]["state"] == "written" and live["rollover"]["installed_on"] == tomorrow
    assert "season_file" not in live["rollover"], "the installed file lives in the world bible, once"
    assert live["season_premiere"]["source"] == "written" and live["season_premiere"]["pending"] is True
    assert "interlude" not in live


def _stored_thread(db, user, live: dict) -> SerialThread:
    thread = SerialThread(
        user_id=user.id,
        world_bible=copy.deepcopy(season_world_bible("s1")),
        state={engine.STATE_KEY: live},
        news_seed={},
        current_episode_index=0,
        status="active",
    )
    db.add(thread)
    db.commit()
    return thread


def test_the_promised_date_starts_the_next_season_whether_or_not_a_chapter_closes(db_session, writer_on, monkeypatch):
    # The writer's budget is spent: the date goes straight to the next season (the
    # retry the date fires while budget remains is tests/test_season_writer_job.py).
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_MAX_ATTEMPTS", 0, raising=False)
    from app.services import season_rollover
    from tests.test_living_story_address import make_user

    user = make_user(db_session)
    live = _finished_life()
    engine.roll_over_season(None, SimpleNamespace(id="t", world_bible=season_world_bible("s1")), live,
                            day=80, today=SINCE.isoformat())
    # An interlude chapter is open, half played: no chapter closes on the promised day.
    live["chapter"] = {"id": "ch-i", "interlude": True, "scene_count": 1, "resolved": False, "title_fr": "Un soir"}
    thread = _stored_thread(db_session, user, live)
    returns_on = date.fromisoformat(live["rollover"]["returns_on"])

    # Before the date the season does not begin (stage 3 queues its writer here).
    assert season_rollover.advance(db_session, thread.id, today=returns_on - timedelta(days=1)) in (
        "waiting", "dispatch",
    )
    db_session.expire_all()
    assert db_session.get(SerialThread, thread.id).state[engine.STATE_KEY]["rollover"]["state"] == "pending"

    assert season_rollover.advance(db_session, thread.id, today=returns_on) == "reprise"
    db_session.expire_all()
    stored = db_session.get(SerialThread, thread.id)
    after = stored.state[engine.STATE_KEY]
    assert after["rollover"]["state"] == "reprise"
    assert after["rollover"]["installed_on"] == returns_on.isoformat()
    assert stored.world_bible["season_number"] == 2 and stored.world_bible["season_source"] == "reprise"
    assert after["chapter"]["resolved"] is True, "the interlude chapter does not outlive its season"
    assert engine.season_phase(after) == "running"
    # Asked again, nothing moves: the state says the season began.
    assert season_rollover.advance(db_session, thread.id, today=returns_on + timedelta(days=1)) == "idle"


def test_the_sweep_finds_the_lives_whose_rollover_is_open(db_session, writer_on):
    from app.services import season_rollover
    from tests.test_living_story_address import make_user

    waiting = _finished_life()
    engine.roll_over_season(None, SimpleNamespace(id="t", world_bible=season_world_bible("s1")), waiting,
                            day=80, today=SINCE.isoformat())
    open_thread = _stored_thread(db_session, make_user(db_session), waiting)
    _stored_thread(db_session, make_user(db_session), {"season_index": 1, "day_index": 3})

    assert season_rollover.open_rollovers(db_session) == [open_thread.id]


def test_the_sweep_runs_on_the_beat():
    from app.celery_app import celery_app

    tasks = {row["task"] for row in celery_app.conf.beat_schedule.values()}
    assert "app.tasks.season_rollover.advance_due_rollovers" in tasks


def test_home_reads_the_interlude_and_the_premiere_from_the_stored_state(db_session, writer_on, monkeypatch):
    # The writer's budget is spent: the date goes straight to the next season (the
    # retry the date fires while budget remains is tests/test_season_writer_job.py).
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_MAX_ATTEMPTS", 0, raising=False)
    from app.services import journey_absence, season_rollover
    from tests.test_living_story_address import make_user

    user = make_user(db_session)
    live = _finished_life()
    engine.roll_over_season(None, SimpleNamespace(id="t", world_bible=season_world_bible("s1")), live,
                            day=80, today=SINCE.isoformat())
    thread = _stored_thread(db_session, user, live)
    interlude = journey_absence.interlude_view(db_session, user.id)
    assert interlude["returns_on"] == live["rollover"]["returns_on"] and interlude["reason_fr"]

    returns_on = date.fromisoformat(live["rollover"]["returns_on"])
    season_rollover.advance(db_session, thread.id, today=returns_on)
    db_session.expire_all()
    assert journey_absence.interlude_view(db_session, user.id) is None
    # No scene of the new season exists yet: Home still says a season began.
    premiere = journey_absence.season_premiere_view(db_session, None, user_id=user.id)
    assert premiere is not None and premiere["number"] == 2 and premiere["title_fr"]
