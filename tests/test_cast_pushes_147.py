"""ROOT CAUSE #147: a push is said by someone the learner has met.

The morning push, the streak push and the recap teaser each took their speaker from
the scene's snapshot or the engine's teaser, and each kept its own table of lines per
character. Nothing asked the cast registry whether the learner had met that person, so
Romy greeted on the lock screen on day 1, three tentpoles before she is in the story
(#124, #155). The push now asks ``cast_registry.has_met`` and a person not met yet is
replaced by one the learner knows.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import serial_notifications as copy

TODAY = date(2026, 9, 22)
#: The learner has played the first page of tentpole 1: Margaux, Gus, Marin and Lila are
#: met; Romy comes with tentpole 4.
DAY_1 = {"living_story": {"season_script": {"id": "s1", "played": [{"segment": "t1", "day_in_segment": 1}]}}}


@pytest.fixture(autouse=True)
def _journey_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")


def _learner(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"push-147-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone="Europe/Paris",
        cefr_estimate="A1",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _thread(db_session, user: User, teaser: dict | None = None) -> None:
    live = dict(DAY_1["living_story"])
    if teaser:
        live["next_teaser"] = teaser
    db_session.add(SerialThread(id=uuid.uuid4(), user_id=user.id, status="active", state={"living_story": live}))
    db_session.commit()


def _scene(db_session, user: User, character: tuple[str, str]) -> None:
    db_session.add(
        DailyJourney(
            id=uuid.uuid4(),
            user_id=user.id,
            local_date=date(2026, 9, 21),
            timezone=user.timezone,
            status="completed",
            budget_seconds=300,
            scenario_snapshot={"character_id": character[0], "character_name": character[1]},
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()


def test_a_teaser_from_someone_not_met_yet_is_not_pushed(db_session) -> None:
    user = _learner(db_session)
    _thread(db_session, user, {"text_fr": "J’ai une question pour vous, demain.", "character_id": "romy_tremblay"})

    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)

    assert push is not None
    assert push.character_id != "romy_tremblay", "Romy greets on day 1, three tentpoles before the story meets her"
    assert push.title != "Romy"
    assert push.source == "authored"


def test_the_scene_s_speaker_not_met_yet_does_not_speak_the_push(db_session) -> None:
    user = _learner(db_session)
    _thread(db_session, user)
    _scene(db_session, user, ("romy_tremblay", "Romy"))

    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)

    assert push is not None
    assert push.character_id != "romy_tremblay"
    assert copy.streak_at_risk_push(db_session, user, days=3).character_id != "romy_tremblay"


def test_someone_the_learner_has_met_still_speaks(db_session) -> None:
    user = _learner(db_session)
    _thread(db_session, user, {"text_fr": "Demain, je vous montre la lettre.", "character_id": "lila_bonnet"})

    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)

    assert push is not None
    assert (push.title, push.source) == ("Lila", "engine")


def test_voices_and_push_tables_read_the_registry_s_aliases() -> None:
    """A nickname the registry knows for a voiced person is the voice's too, and the push
    tables hold exactly the registry's people (no second list to drift)."""

    from app.services import cast_registry
    from app.services.cast_voices import CAST_ALIASES, CAST_VOICES, cast_id_for

    for alias, cast_id in cast_registry.aliases().items():
        if cast_id in CAST_VOICES:
            assert CAST_ALIASES[alias] == cast_id
            assert cast_id_for(alias) == cast_id
    assert set(CAST_ALIASES) <= set(cast_registry.aliases())
    for key in copy.CHARACTER_NAMES:
        assert cast_registry.member(key) is not None
        assert copy.CHARACTER_NAMES[key] == cast_registry.display_name(key)
    assert set(copy.PORTRAIT_CHARACTERS.values()) <= set(copy.CHARACTER_NAMES)


def test_a_thread_without_a_season_is_not_filtered(db_session) -> None:
    """An older story has no canon of who comes when; the push keeps the scene's speaker."""

    user = _learner(db_session)
    _scene(db_session, user, ("romy_tremblay", "Romy"))

    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)

    assert push is not None and push.character_id == "romy_tremblay"
