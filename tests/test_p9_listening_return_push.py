"""Pilot P9 stage 2 — the listening day, the return card and the morning push.

* decision 7: no «listen first» day before the learner's 8th played day;
* the return card («Entre-temps») says where the story stood when the learner left,
  from stored text only, in the learner's interface language;
* a push a beginner can read: a hook about a character goes out under the serial's
  name, and below B1 only with its stored gloss — else the character's authored line.

No model call anywhere: stored rows and fixtures only.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import journey_absence
from app.services import serial_notifications as copy
from app.services.journey_day_shapes import (
    LISTEN_FIRST_MIN_PLAYED_DAY,
    DayShape,
    DayShapeInputs,
    choose_day_shape,
    is_listen_first_day,
    played_day_from_story,
)
from app.services.living_story import STATE_KEY

# ---------------------------------------------------------------------------
# 1. The listening day waits for the learner's day 8
# ---------------------------------------------------------------------------


def _cadence_day(user_id: str) -> date:
    """A date on which this learner's every-third-day cadence falls."""

    start = date(2026, 11, 2)
    return next(
        start + timedelta(days=offset)
        for offset in range(3)
        if is_listen_first_day(
            DayShapeInputs(user_id=user_id, local_date=start + timedelta(days=offset),
                           audio_available=True, budget_seconds=1200)
        )
    )


def _deal(user_id: str, day: date, played_day: int | None) -> DayShape:
    return choose_day_shape(
        DayShapeInputs(
            user_id=user_id, local_date=day, audio_available=True,
            budget_seconds=1200, played_day=played_day,
        )
    ).shape


@pytest.mark.parametrize("user_id", ["p9-a", "p9-b", "p9-c"])
def test_no_listening_day_before_the_learners_day_8(user_id) -> None:
    day = _cadence_day(user_id)
    assert _deal(user_id, day, played_day=3) is not DayShape.LISTENING
    assert _deal(user_id, day, played_day=LISTEN_FIRST_MIN_PLAYED_DAY - 1) is not DayShape.LISTENING
    assert _deal(user_id, day, played_day=9) is DayShape.LISTENING
    assert _deal(user_id, day, played_day=LISTEN_FIRST_MIN_PLAYED_DAY) is DayShape.LISTENING
    # Nor do the dice draw one on any of the first seven days.
    for offset in range(21):
        assert _deal(user_id, day + timedelta(days=offset), played_day=5) is not DayShape.LISTENING


def test_the_played_day_is_read_from_the_seasons_position() -> None:
    assert played_day_from_story({"season": {"kind": "gap", "position": {"season_day": 3}}}) == 3
    assert played_day_from_story({"season": {"position": {"season_day": "9"}}}) == 9
    assert played_day_from_story({}) is None
    assert played_day_from_story(None) is None
    assert played_day_from_story({"season": {"position": {"season_day": "x"}}}) is None


# ---------------------------------------------------------------------------
# 2. The return card says where the story stood
# ---------------------------------------------------------------------------


def _user(db_session, *, band: str, native: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"p9-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language=native,
        target_language="fr",
        timezone="Europe/Paris",
        cefr_estimate=band,
        proficiency_level=band,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _played_day(db_session, user: User, day: date, *, summary: str | None, teaser: dict | None) -> None:
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=day,
        timezone=user.timezone,
        status="completed",
        budget_seconds=600,
        recap_snapshot={"teaser": teaser} if teaser else {},
        created_at=datetime.now(UTC),
    )
    db_session.add(journey)
    db_session.flush()
    prompt = {"outcome_key": "ok", "character_line_fr": "Merci.", "summary_native": summary or ""}
    db_session.add(
        DailyJourneyStep(
            id=uuid.uuid4(), journey_id=journey.id, ordinal=4, kind="resolution",
            status="completed", public_prompt=prompt, private_task={},
        )
    )
    db_session.commit()


def _view(db_session, user: User) -> dict:
    view = journey_absence.absence_view(
        db_session, user_id=user.id, local_date=date(2026, 10, 6), missed_days=4,
        now=datetime(2026, 10, 6, 8, 0, tzinfo=UTC),
    )
    assert view is not None
    return view


def test_the_return_card_carries_two_lines_in_the_interface_language(db_session) -> None:
    # A1, German: the end card's own summary (written in the interface language) and
    # the hook's stored German rendering.
    user = _user(db_session, band="A1", native="de")
    _played_day(
        db_session, user, date(2026, 10, 1),
        summary="Du hast Marin geholfen, den Schlüssel zu finden. Er traut Lila nicht.",
        teaser={"text_fr": "Marin attend ta réponse.", "open_fr": "Qui a pris la clé ?",
                "open_native": "Wer hat den Schlüssel genommen?", "source": "engine"},
    )
    assert _view(db_session, user)["where_left"] == [
        "Du hast Marin geholfen, den Schlüssel zu finden. Er traut Lila nicht.",
        "Wer hat den Schlüssel genommen?",
    ]


def test_a_beginner_is_not_handed_an_untranslated_french_hook(db_session) -> None:
    user = _user(db_session, band="A1", native="de")
    _played_day(
        db_session, user, date(2026, 10, 1),
        summary="Du hast Marin geholfen.",
        teaser={"text_fr": "Marin attend ta réponse.", "open_fr": "Qui a pris la clé ?", "source": "engine"},
    )
    assert _view(db_session, user)["where_left"] == ["Du hast Marin geholfen."]


def test_a_french_interface_reads_the_hook_as_it_was_written(db_session) -> None:
    user = _user(db_session, band="B1", native="en")
    _played_day(
        db_session, user, date(2026, 10, 1),
        summary="Tu as aidé Marin à trouver la clé.",
        teaser={"text_fr": "Marin attend ta réponse.", "open_fr": "Qui a pris la clé ?", "source": "engine"},
    )
    assert _view(db_session, user)["where_left"] == ["Tu as aidé Marin à trouver la clé.", "Qui a pris la clé ?"]


def test_no_stored_summary_no_lines(db_session) -> None:
    user = _user(db_session, band="A1", native="de")
    _played_day(
        db_session, user, date(2026, 10, 1), summary=None,
        teaser={"text_fr": "Marin attend.", "open_native": "Wer hat den Schlüssel genommen?", "source": "engine"},
    )
    assert _view(db_session, user)["where_left"] == []
    nobody = _user(db_session, band="A1", native="de")
    assert _view(db_session, nobody)["where_left"] == []


# ---------------------------------------------------------------------------
# 3. A push a beginner can read
# ---------------------------------------------------------------------------


@pytest.fixture()
def cohort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")


def _teaser_thread(db_session, user: User, teaser: dict) -> None:
    db_session.add(
        SerialThread(
            id=uuid.uuid4(), user_id=user.id, status="active", world_bible={},
            state={STATE_KEY: {"events": [], "moods": {}, "next_teaser": teaser}, "relationships": {}},
            news_seed={}, current_episode_index=0,
        )
    )
    db_session.commit()


TODAY = date(2026, 11, 13)
# Observed for an A1 German learner (review finding 13): a narrator's question about
# Marin, sent under Marin's name.
OBSERVED = "Comment Marin peut-il t'aider avec ta peur de l'avion ?"


def test_a_hook_naming_its_sender_goes_out_under_the_serials_title(db_session, cohort) -> None:
    user = _user(db_session, band="B1", native="de")
    _teaser_thread(db_session, user, {"text_fr": OBSERVED, "character_id": "marin_leveque"})
    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)
    assert push is not None and push.source == "engine"
    assert push.title != "Marin"
    assert push.title == copy.serial_title(db_session, user)
    assert copy.hook_is_said_by("Je te garde une place.", "marin_leveque", "Marin")
    assert not copy.hook_is_said_by(OBSERVED, "marin_leveque", "Marin")
    assert not copy.hook_is_said_by("Qui a pris la clé ?", None, "")


def test_an_a1_german_push_has_a_german_second_line(db_session, cohort) -> None:
    user = _user(db_session, band="A1", native="de")
    _teaser_thread(
        db_session, user,
        {"text_fr": "Demain, je te montre la lettre.", "text_native": "Morgen zeige ich dir den Brief.",
         "character_id": "marin_leveque"},
    )
    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)
    assert push is not None
    assert push.message == "Demain, je te montre la lettre.\nMorgen zeige ich dir den Brief."
    assert len(push.message) <= copy.engine_teaser_chars()
    assert push.title == "Marin"


def test_an_a1_push_without_a_gloss_is_the_characters_authored_line(db_session, cohort) -> None:
    user = _user(db_session, band="A1", native="de")
    _teaser_thread(db_session, user, {"text_fr": OBSERVED, "character_id": "marin_leveque"})
    push = copy.daily_journey_morning_push(db_session, user, today=TODAY)
    assert push is not None
    assert push.message != OBSERVED
    assert push.source == "authored"
    assert push.message == copy.MORNING_LINES["marin_leveque"]["A"]
    assert push.title == "Marin"
