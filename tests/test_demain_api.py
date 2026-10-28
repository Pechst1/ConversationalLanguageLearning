"""«Demain» through the API: the finished recap offers tomorrow's threads, and the
learner's pick becomes the season's next day and the day's one tomorrow-hook.

The rows are the ones a finished gap day leaves (a played season state, the day's
engine scene and its filed hook, a completed journey with its recap), built here so
the test stays on the seam; ``tests/test_demain.py`` holds the season logic.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.schemas.daily_journey import JourneyRecap
from app.services import story_tomorrow
from app.services.living_story import ENGINE_VERSION_PREFIX
from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
from app.services.season.format import load_season, validate_season
from app.services.serial_notifications import engine_teaser
from app.services.story_page import HOOK_PAYLOAD_KEY, hook_of
from tests.test_daily_journey_api import journey_client, journey_enabled, key, login  # noqa: F401

ENGINE_TEASER = "Dis, j'y repense… C'est peut-être un signe. Tu as promis, hein : « Je viens samedi. »"
FINISHED_ON = date(2026, 11, 26)


def _played(event_id: str) -> list[dict]:
    rows = [{"segment": "t1", "day_in_segment": n, "event_id": f"t1.{n}"} for n in (1, 2)]
    rows += [{"segment": "g1", "day_in_segment": n, "event_id": f"g1.{n}"} for n in range(1, 6)]
    rows += [{"segment": "t2", "day_in_segment": n, "event_id": f"t2.{n}"} for n in (1, 2)]
    return rows + [{"segment": "g2", "day_in_segment": 1, "event_id": event_id}]


def _finished_gap_day(db, user: User, *, status: str = "completed") -> tuple[DailyJourney, GraphicNovelScene]:
    """g2 day 1 played and finished: the box is open, tomorrow is g2 day 2."""

    journey_id = uuid4()
    event_id = f"journey:{journey_id}:story"
    thread = SerialThread(
        user_id=user.id,
        status="active",
        world_bible={},
        state={
            "living_story": {
                season_clock.SEASON_KEY: {
                    "id": "s1",
                    "played": _played(event_id),
                    "premises": [{"gap": "g2", "premise": "la_boite"}],
                },
                "next_teaser": {"text_fr": ENGINE_TEASER, "character_id": "marin_leveque", "date": FINISHED_ON.isoformat()},
            }
        },
        news_seed={},
        current_episode_index=10,
    )
    db.add(thread)
    db.flush()
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=10,
        status="completed",
        cadence="daily",
        title="La boîte",
        brief="",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={HOOK_PAYLOAD_KEY: ENGINE_TEASER, "season": {"id": "s1", "segment": "g2", "kind": "gap"}},
        recap_payload={},
        cache_key=f"demain-{uuid4().hex}",
        prompt_version=f"{ENGINE_VERSION_PREFIX}test",
        image_model="test",
        image_quality="medium",
    )
    db.add(scene)
    db.flush()
    live = thread.state["living_story"]
    journey = DailyJourney(
        id=journey_id,
        user_id=user.id,
        local_date=FINISHED_ON,
        timezone="UTC",
        content_version="test",
        level_band="A2",
        status=status,
        serial_thread_id=str(thread.id),
        scenario_snapshot={
            "scenario_key": "story_next",
            "content_version": "test",
            "title_fr": "La boîte",
            "objective_key": "story",
            "objective_native": "Talk with Marin about the box.",
            "level_band": "A2",
            "character_id": "marin_leveque",
            "character_name": "Marin",
            "location_id": "le_mistral",
            "location_name": "Le Mistral",
            "estimated_seconds": 300,
        },
    )
    journey.steps.append(
        DailyJourneyStep(
            ordinal=0,
            kind="resolution",
            status="completed",
            public_prompt={"outcome_key": "met", "character_line_fr": "À demain !", "summary_native": "You talked."},
            private_task={"scenario_brief": {"story_context": {"scene_id": str(scene.id)}}},
        )
    )
    journey.recap_snapshot = JourneyRecap.model_validate(
        {
            "completion_kind": "complete",
            "objective_outcome": "met",
            "teaser": {"text_fr": ENGINE_TEASER, "character_id": "marin_leveque", "character_name": "Marin", "source": "engine"},
            "teaser_fr": ENGINE_TEASER,
            "tomorrow": story_tomorrow.recap_tomorrow(user, journey, live),
        }
    ).model_dump(mode="json")
    db.add(journey)
    db.commit()
    return journey, scene


@pytest.fixture()
def learner(journey_client, journey_enabled, db_session):  # noqa: F811
    email = f"demain-{uuid4().hex[:8]}@example.com"
    headers = login(journey_client, email)
    user = db_session.scalar(select(User).where(User.email == email))
    return headers, user


def _pick(client, headers, journey: DailyJourney, premise_id: str, *, revision: int | None = None, mutation_id: str | None = None):
    return client.post(
        f"/api/v1/daily-journeys/{journey.id}/tomorrow",
        headers=headers,
        json={
            "mutation_id": mutation_id or key(),
            "expected_revision": journey.revision if revision is None else revision,
            "premise_id": premise_id,
        },
    )


def _season_state(db, user: User) -> dict:
    db.expire_all()
    thread = db.scalar(select(SerialThread).where(SerialThread.user_id == user.id))
    return thread.state["living_story"]


def test_the_finished_recap_offers_tomorrows_threads(journey_client, db_session, learner):  # noqa: F811
    headers, user = learner
    journey, _scene = _finished_gap_day(db_session, user)
    body = journey_client.get(f"/api/v1/daily-journeys/{journey.id}", headers=headers).json()
    assert body["recap"]["tomorrow"] == {
        "options": [
            {"premise_id": "je_peux", "label_fr": "Parler du plan d'Odile avec Marin", "planned": True},
            {"premise_id": "le_diner_rate", "label_fr": "Cuisiner avec Lila", "planned": False},
            {"premise_id": "pour_son_anniversaire", "label_fr": "Fêter l'anniversaire de Gus", "planned": False},
        ],
        "picked": None,
    }


def test_the_finish_writes_the_choice_into_the_recap(journey_client, db_session, learner):  # noqa: F811
    from app.services.achievement_recap import recap_extras

    _headers, user = learner
    journey, _scene = _finished_gap_day(db_session, user)
    extras = recap_extras(db_session, user=user, journey=journey, practiced=[], collectible_ids=[])
    assert [row["premise_id"] for row in extras["tomorrow"]["options"]] == ["je_peux", "le_diner_rate", "pour_son_anniversaire"]
    assert extras["tomorrow"]["picked"] is None


def test_the_pick_is_tomorrows_day_and_the_one_hook_every_surface_reads(journey_client, db_session, learner):  # noqa: F811
    headers, user = learner
    journey, scene = _finished_gap_day(db_session, user)
    revision = journey.revision
    response = _pick(journey_client, headers, journey, "le_diner_rate")
    assert response.status_code == 200, response.text
    body = response.json()
    hook = "On va cuisiner avec Lila."
    assert body["revision"] == revision + 1
    assert body["recap"]["tomorrow"]["picked"] == "le_diner_rate"
    assert body["recap"]["teaser"] == {"text_fr": hook, "character_id": None, "character_name": None, "source": "engine"}
    assert body["recap"]["teaser_fr"] == hook

    live = _season_state(db_session, user)
    assert live[season_clock.SEASON_KEY]["tomorrow"] == {"gap": "g2", "day": 2, "premise": "le_diner_rate"}
    # Home and the morning push read the living story's teaser; the last panel and
    # the Feuilleton read the scene's hook. One line, everywhere.
    assert live["next_teaser"]["text_fr"] == hook
    assert live["next_teaser"]["date"] == FINISHED_ON.isoformat()
    assert engine_teaser(db_session, user)["text_fr"] == hook
    db_session.refresh(scene)
    assert hook_of(scene.script_payload) == hook
    event = db_session.scalar(select(PilotEvent).where(PilotEvent.event_type == story_tomorrow.PICKED_EVENT))
    assert event.payload == {
        "gap": "g2",
        "day": 2,
        "premise": "le_diner_rate",
        "planned": False,
        "options": ["je_peux", "le_diner_rate", "pour_son_anniversaire"],
    }

    # The next day stages the learner's thread, and says which one waits.
    next_morning = datetime.combine(FINISHED_ON + timedelta(days=1), time(9), tzinfo=UTC)
    today = season_runtime.today_for(live, user=user, seed=str(user.id), now=next_morning)
    brief = season_runtime.context_block(today)["brief"]["today"]
    assert brief["required_premise"]["id"] == "le_diner_rate"
    assert brief["picked"]["by_learner"] == "Cuisiner avec Lila"


def test_picking_again_replaces_the_pick_and_its_line(journey_client, db_session, learner):  # noqa: F811
    headers, user = learner
    journey, scene = _finished_gap_day(db_session, user)
    first = _pick(journey_client, headers, journey, "pour_son_anniversaire")
    assert first.status_code == 200
    again = _pick(journey_client, headers, journey, "je_peux", revision=first.json()["revision"])
    assert again.status_code == 200, again.text
    assert again.json()["recap"]["tomorrow"]["picked"] == "je_peux"
    assert again.json()["recap"]["teaser_fr"] == "On va parler du plan d'Odile avec Marin."
    assert _season_state(db_session, user)[season_clock.SEASON_KEY]["tomorrow"]["premise"] == "je_peux"


def test_a_replayed_pick_answers_the_same_and_writes_once(journey_client, db_session, learner):  # noqa: F811
    headers, user = learner
    journey, _scene = _finished_gap_day(db_session, user)
    mutation = key()
    first = _pick(journey_client, headers, journey, "le_diner_rate", mutation_id=mutation)
    second = _pick(journey_client, headers, journey, "le_diner_rate", mutation_id=mutation)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    events = db_session.scalars(select(PilotEvent).where(PilotEvent.event_type == story_tomorrow.PICKED_EVENT)).all()
    assert len(events) == 1


@pytest.mark.parametrize("premise_id", ["bastien_appelle", "la_petition", "nope"])
def test_a_thread_not_on_offer_is_refused_and_nothing_moves(journey_client, db_session, learner, premise_id):  # noqa: F811
    headers, user = learner
    journey, scene = _finished_gap_day(db_session, user)
    response = _pick(journey_client, headers, journey, premise_id)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "journey_not_active"
    live = _season_state(db_session, user)
    assert "tomorrow" not in live[season_clock.SEASON_KEY]
    assert live["next_teaser"]["text_fr"] == ENGINE_TEASER
    db_session.refresh(scene)
    assert hook_of(scene.script_payload) == ENGINE_TEASER


def test_no_pick_once_tomorrows_journey_exists(journey_client, db_session, learner):  # noqa: F811
    """Tomorrow's page may be being written against the story as it stands."""

    headers, user = learner
    journey, _scene = _finished_gap_day(db_session, user)
    db_session.add(DailyJourney(user_id=user.id, local_date=FINISHED_ON + timedelta(days=1), timezone="UTC", status="preparing"))
    db_session.commit()
    response = _pick(journey_client, headers, journey, "le_diner_rate")
    assert response.status_code == 409
    assert "tomorrow" not in _season_state(db_session, user)[season_clock.SEASON_KEY]


def test_no_pick_on_a_day_still_being_played(journey_client, db_session, learner):  # noqa: F811
    headers, user = learner
    journey, _scene = _finished_gap_day(db_session, user, status="active")
    assert _pick(journey_client, headers, journey, "le_diner_rate").status_code == 409


def test_someone_elses_day_is_not_found(journey_client, db_session, learner):  # noqa: F811
    headers, user = learner
    other = User(email=f"other-{uuid4().hex[:8]}@example.com", hashed_password="x", native_language="en", target_language="fr")
    db_session.add(other)
    db_session.flush()
    journey, _scene = _finished_gap_day(db_session, other)
    assert _pick(journey_client, headers, journey, "le_diner_rate").status_code == 404


def test_the_pick_reads_as_tomorrows_line():
    assert story_tomorrow.hook_for("Cuisiner avec Lila") == "On va cuisiner avec Lila."
    assert story_tomorrow.hook_for(" Écrire à  Romy. ") == "On va écrire à Romy."
    assert story_tomorrow.hook_for("") == ""
    season = load_season("s1")
    labels = [beat.pick_fr for gap in season.gaps.values() for beat in gap.days if beat.pick_fr]
    assert len(labels) == 14
    assert all(story_tomorrow.hook_for(label).startswith("On va ") for label in labels)


def test_the_check_refuses_a_pick_label_that_is_not_an_infinitive():
    season = load_season("s1")
    gap = season.gaps["g2"]
    days = [beat.model_copy(update={"pick_fr": "Le dîner chez Lila"}) if beat.premise == "le_diner_rate" else beat for beat in gap.days]
    broken = season.model_copy(update={"gaps": {**season.gaps, "g2": gap.model_copy(update={"days": days})}})
    assert "g2: 'le_diner_rate' pick_fr 'Le dîner chez Lila' is not an infinitive phrase" in validate_season(broken)
