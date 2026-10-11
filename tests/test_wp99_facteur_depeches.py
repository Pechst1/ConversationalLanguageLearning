"""WP-99 «Le facteur et les dépêches» — reasons to come back (the services half).

Nothing here leaves the building: pushes go through a patched sender, the
letter writer is a fake (or absent), and no model is called.

* «Dépêches»: the morning push is the story's teaser in the character's
  register, with their mood portrait, deep-linked to today's scene — and never
  the same teaser twice inside 14 days;
* «Le facteur est passé» / «Dernier jour pour répondre à …»: one Courrier push
  a local day at most, at the learner's own hour, under the daily cap;
* «Pendant votre absence»: from two missed days the snapshot says how long,
  what happened meanwhile, and which letters went cold; the season premiere and
  the interlude are read from the story;
* W13: a learner's first letter is the cast's (Margaux / Romy), French only,
  and a generated letter is written at the learner's band on the first try;
* O-4: free use from 10 days of stability, and the measured avoidance rate in
  the forecast's hold-lag samples.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

import app.services.missions as missions_module
from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.mission import RealWorldMission
from app.db.models.pilot_event import PilotEvent
from app.db.models.push_subscription import PushSubscription
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import journey_absence
from app.services import serial_notifications as copy
from app.services import story_correspondence as courrier
from app.services.living_story import STATE_KEY
from app.services.llm_service import LLMResult
from app.services.missions import (
    FIRST_LETTERS,
    REAL_WORLD_MISSION_DOMAINS,
    MissionGenerator,
    MissionScheduler,
    letter_level_brief,
)
from app.tasks import notifications as tasks


class _FakeNotifications:
    sent: list[dict] = []

    def __init__(self, db) -> None:
        self.db = db

    def send_notification(self, user_id, message, title="L’Atelier", *, data=None) -> int:
        _FakeNotifications.sent.append(
            {"user_id": user_id, "title": title, "message": message, "data": dict(data or {})}
        )
        return 1


@pytest.fixture()
def sent(db_session, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    import app.services.notification_service as notification_service

    _FakeNotifications.sent = []
    monkeypatch.setattr(notification_service, "NotificationService", _FakeNotifications)

    class _Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            return None

    monkeypatch.setattr(tasks, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_DAILY_JOURNEY_COHORT", "")
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    return _FakeNotifications.sent


# WP-116 phase 6: the drawn cast is the default; pushes carry the painted portrait
# or the drawn PNG face. The push tests run under both sets, each pinned explicitly.
@pytest.fixture(params=["painted", "drawn"])
def art_set(request, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "ATELIER_ART_SET", request.param)
    return request.param


def _face(art_set: str, key: str, face: str) -> str:
    if art_set == "drawn":
        return f"/assets/serial/drawn/{key}/portrait-{copy.DRAWN_FACES[face]}.png"
    return f"/assets/serial/characters/{key}/portrait-{face}.webp"


def _learner(db_session, *, tz: str = "Europe/Paris", reminder: str = "08:30", band: str = "A1") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp99-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone=tz,
        reminder_time=reminder,
        cefr_estimate=band,
        proficiency_level=band,
        is_active=True,
        notifications_enabled=True,
        practice_reminders=True,
        streak_notifications=True,
    )
    db_session.add(user)
    db_session.add(
        PushSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            endpoint=f"https://push.test/{uuid.uuid4().hex}",
            keys={"p256dh": "x", "auth": "y"},
        )
    )
    db_session.commit()
    return user


def _thread(db_session, user: User, *, live: dict | None = None, relationships: dict | None = None) -> SerialThread:
    thread = SerialThread(
        id=uuid.uuid4(),
        user_id=user.id,
        status="active",
        world_bible={
            "cast": [
                {"id": "romy_tremblay", "name": "Romy", "role": "journaliste"},
                {"id": "margaux_barman", "name": "Margaux", "role": "serveuse"},
                {"id": "lila_bonnet", "name": "Lila", "role": "peintre"},
            ]
        },
        state={STATE_KEY: {"events": [], "moods": {}, **(live or {})}, "relationships": relationships or {}},
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.commit()
    return thread


def _journey(db_session, user: User, day: date, *, status: str = "completed", character=("romy_tremblay", "Romy")) -> DailyJourney:
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=day,
        timezone=user.timezone,
        status=status,
        budget_seconds=300,
        scenario_snapshot={"character_id": character[0], "character_name": character[1]},
        created_at=datetime.now(UTC),
    )
    db_session.add(journey)
    db_session.commit()
    return journey


def _mine(sent: list[dict], user: User) -> list[dict]:
    return [row for row in sent if row["user_id"] == user.id]


# 06:30 UTC on 1 Oct 2026 is 08:30 in Paris (CEST).
PARIS_0830 = datetime(2026, 10, 1, 6, 30, tzinfo=UTC)


# ---------------------------------------------------------------------------
# «Dépêches» — the morning push
# ---------------------------------------------------------------------------


def test_the_morning_depeche_is_the_teaser_in_the_mood_portrait_deep_linked(db_session, sent, art_set) -> None:
    user = _learner(db_session)
    _journey(db_session, user, date(2026, 9, 30))
    _thread(
        db_session,
        user,
        live={
            "next_teaser": {"text_fr": "Romy a trouvé la lettre. Elle t’attend.", "character_id": "romy_tremblay", "date": "2026-09-30"},
            "moods": {"romy_tremblay": {"mood": 2, "trust": 3}},
        },
        relationships={"romy_tremblay": {"register": "tu"}},
    )

    tasks.send_morning_editions(now=PARIS_0830.isoformat())

    [push] = _mine(sent, user)
    assert push["title"] == "Romy"
    assert push["message"] == "Romy a trouvé la lettre. Elle t’attend."
    data = push["data"]
    assert data["route"] == "/atelier?start=today"
    assert data["kind"] == "morning_teaser" and data["teaser_source"] == "engine"
    assert data["image_url"] == data["image"] == _face(art_set, "romy_tremblay", "happy")
    assert data["mood"] == "happy" and data["register"] == "tu"
    assert data["teaser_date"] == "2026-09-30"


def test_a_teaser_is_never_pushed_twice_inside_fourteen_days(db_session, sent) -> None:
    user = _learner(db_session)
    _journey(db_session, user, date(2026, 9, 30))
    teaser = "Marin cache quelque chose dans la cave."
    _thread(db_session, user, live={"next_teaser": {"text_fr": teaser, "character_id": "marin_leveque"}})

    tasks.send_morning_editions(now=PARIS_0830.isoformat())
    tasks.send_morning_editions(now=(PARIS_0830 + timedelta(days=1)).isoformat())
    later = PARIS_0830 + timedelta(days=15)
    tasks.send_morning_editions(now=later.isoformat())

    first, second, third = _mine(sent, user)
    assert first["message"] == teaser and first["data"]["teaser_source"] == "engine"
    # The story wrote nothing new overnight: the authored line, not the same news.
    assert second["message"] != teaser and second["data"]["teaser_source"] == "authored"
    # …in the voice of the learner's latest scene (Romy), WP-80's fallback.
    assert second["message"] == copy.MORNING_LINES["romy_tremblay"]["A"]
    # Two weeks on, the line is allowed again.
    assert third["message"] == teaser


def test_recent_push_lines_fold_quotes_and_case(db_session) -> None:
    user = _learner(db_session)
    db_session.add(
        PilotEvent(
            user_id=user.id,
            event_type=copy.MORNING_PUSH_EVENT,
            entity_type="notification",
            entity_id="2026-09-28",
            payload={"message": "J'ai une idée."},
        )
    )
    db_session.commit()
    lines = copy.recent_push_lines(db_session, user, today=date(2026, 10, 1))
    assert copy._teaser_key("J’AI une idée !") in lines
    assert not copy.recent_push_lines(db_session, user, today=date(2026, 10, 20))
    assert tasks.MORNING_EVENT == copy.MORNING_PUSH_EVENT


def test_mood_faces_follow_the_courrier_seal_rule(art_set) -> None:
    assert [copy.mood_face(value) for value in (-2, -1, 0, 1, 2, None, "x")] == [
        "cross", "cross", "neutral", "happy", "happy", "neutral", "neutral",
    ]
    assert copy.portrait_path("lila", "cross") == _face(art_set, "lila_bonnet", "cross")
    assert copy.portrait_path("lila", "sulky") == _face(art_set, "lila_bonnet", "neutral")


# ---------------------------------------------------------------------------
# «Le facteur est passé» — the Courrier pushes
# ---------------------------------------------------------------------------


def _letter(db_session, user: User, *, created_at: datetime, expires_at: datetime | None = None,
            correspondent_id: str = "romy_tremblay", name: str = "Romy", status: str = "available") -> RealWorldMission:
    mission = RealWorldMission(
        user_id=user.id,
        status=status,
        cadence="ad_hoc",
        mission_type="message",
        title="Un mot de Romy",
        brief="Romy vous écrit.",
        correspondent_id=correspondent_id,
        chain_id=f"chain:{correspondent_id}:w:1" if expires_at else None,
        chain_index=1 if expires_at else None,
        chain_total=2 if expires_at else None,
        expires_at=expires_at,
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={"messenger": {"contact_name": name}, "correspondence": {"correspondent_id": correspondent_id}},
        recap_payload={},
    )
    db_session.add(mission)
    db_session.commit()
    mission.created_at = created_at
    db_session.add(mission)
    db_session.commit()
    return mission


def _courrier_moment(user: User, day: date) -> datetime:
    """The learner's Courrier minute on ``day``, as a UTC instant (Paris, CEST)."""

    minute = tasks.courrier_push_minute(user)
    local = datetime(day.year, day.month, day.day, minute // 60, minute % 60)
    return (local - timedelta(hours=2)).replace(tzinfo=UTC)


def test_the_courrier_push_is_the_learner_s_midday_in_their_zone() -> None:
    user = User(reminder_time="08:30")
    assert tasks.courrier_push_minute(user) == 13 * 60 + 30
    assert tasks.courrier_push_minute(User(reminder_time="21:00")) == tasks.COURRIER_PUSH_FALLBACK_MINUTE


def test_a_letter_arrives_and_the_postman_says_so_once(db_session, sent, art_set) -> None:
    user = _learner(db_session)
    _thread(db_session, user)
    mission = _letter(db_session, user, created_at=datetime(2026, 10, 1, 7, 0, tzinfo=UTC))

    tasks.send_courrier_pushes(now=(_courrier_moment(user, date(2026, 10, 1)) - timedelta(minutes=20)).isoformat())
    assert not _mine(sent, user), "never before the learner's hour"
    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 1)).isoformat())
    tasks.send_courrier_pushes(now=(_courrier_moment(user, date(2026, 10, 1)) + timedelta(minutes=5)).isoformat())
    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 2)).isoformat())

    [push] = _mine(sent, user)
    assert push["title"] == copy.LETTER_ARRIVED_TITLE
    assert push["message"] == "Romy : « Je vous ai écrit. Vous me répondez ? »"
    data = push["data"]
    assert data["kind"] == "letter_arrived"
    assert data["mission_id"] == str(mission.id)
    assert data["route"] == f"/missions?mission={mission.id}"
    assert data["image_url"] == _face(art_set, "romy_tremblay", "neutral")
    db_session.refresh(mission)
    assert mission.prompt_payload["courrier_push"] == {"arrived": "2026-10-01"}


def test_the_last_day_to_answer_is_said_once_in_the_character_s_tu(db_session, sent) -> None:
    user = _learner(db_session)
    _thread(db_session, user, relationships={"romy_tremblay": {"register": "tu"}})
    # Arrived three days ago (already announced), due on 3 Oct at 10:00 Paris.
    mission = _letter(
        db_session,
        user,
        created_at=datetime(2026, 9, 29, 7, 0, tzinfo=UTC),
        expires_at=datetime(2026, 10, 3, 8, 0, tzinfo=UTC),
    )

    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 1)).isoformat())
    assert not _mine(sent, user), "two days before the deadline is not the last day"
    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 2)).isoformat())
    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 3)).isoformat())

    [push] = _mine(sent, user)
    assert push["title"] == "Dernier jour pour répondre à Romy"
    assert push["message"] == copy.LETTER_DEADLINE_LINES["tu"]
    assert push["data"]["kind"] == "letter_deadline" and push["data"]["register"] == "tu"
    assert push["data"]["mission_id"] == str(mission.id)


def test_one_courrier_push_a_day_and_the_deadline_comes_first(db_session, sent) -> None:
    user = _learner(db_session)
    _thread(db_session, user)
    due = _letter(
        db_session, user, created_at=datetime(2026, 9, 28, 7, 0, tzinfo=UTC),
        expires_at=datetime(2026, 10, 2, 9, 0, tzinfo=UTC),
    )
    fresh = _letter(
        db_session, user, created_at=datetime(2026, 10, 1, 6, 0, tzinfo=UTC),
        correspondent_id="lila_bonnet", name="Lila",
    )

    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 1)).isoformat())
    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 2)).isoformat())

    first, second = _mine(sent, user)
    assert (first["data"]["kind"], first["data"]["mission_id"]) == ("letter_deadline", str(due.id))
    assert (second["data"]["kind"], second["data"]["mission_id"]) == ("letter_arrived", str(fresh.id))
    assert second["message"].startswith("Lila : ")


def test_the_daily_cap_keeps_the_courrier_quiet(db_session, sent) -> None:
    user = _learner(db_session)
    _thread(db_session, user)
    _letter(db_session, user, created_at=datetime(2026, 10, 1, 6, 0, tzinfo=UTC))
    for event in (tasks.MORNING_EVENT, tasks.STREAK_REMINDER_EVENT, tasks.REVIEW_REMINDER_EVENT):
        db_session.add(
            PilotEvent(user_id=user.id, event_type=event, entity_type="notification", entity_id="2026-10-01", payload={})
        )
    db_session.commit()
    assert tasks.pushes_sent_on(db_session, user, date(2026, 10, 1)) == tasks.DAILY_PUSH_CAP

    tasks.send_courrier_pushes(now=_courrier_moment(user, date(2026, 10, 1)).isoformat())
    assert not _mine(sent, user)


def test_the_beat_schedules_the_courrier_pushes() -> None:
    from app.celery_app import celery_app

    tasks_scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "app.tasks.notifications.send_courrier_pushes" in tasks_scheduled


def test_every_courrier_line_is_french_without_emoji() -> None:
    emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
    for line in [*copy.LETTER_ARRIVED_LINES.values(), *copy.LETTER_DEADLINE_LINES.values()]:
        assert not emoji.search(line)
    assert re.search(r"\bvous\b|\bvotre\b", copy.LETTER_ARRIVED_LINES["vous"] + copy.LETTER_DEADLINE_LINES["vous"])
    assert not re.search(r"\bvous\b|\bvotre\b", copy.LETTER_ARRIVED_LINES["tu"] + copy.LETTER_DEADLINE_LINES["tu"])


# ---------------------------------------------------------------------------
# «Pendant votre absence» — the snapshot's frame
# ---------------------------------------------------------------------------


def test_an_absence_of_two_days_or_more_says_what_happened_meanwhile(db_session) -> None:
    user = _learner(db_session)
    _journey(db_session, user, date(2026, 9, 25))
    beats = [
        {"id": f"meanwhile:lila:{i}", "kind": "meanwhile", "character_id": "lila_bonnet",
         "summary_fr": f"Lila a peint le mur {i}.", "at": f"2026-09-{26 + i:02d}T10:00:00+00:00"}
        for i in range(3)
    ] + [
        {"id": "meanwhile:marin:old", "kind": "meanwhile", "character_id": "marin_leveque",
         "summary_fr": "Marin est parti à Lyon.", "at": "2026-09-01T10:00:00+00:00"},
    ]
    _thread(db_session, user, live={"events": beats})
    lapsed = _letter(
        db_session, user, created_at=datetime(2026, 9, 22, 7, 0, tzinfo=UTC),
        expires_at=datetime(2026, 9, 27, 7, 0, tzinfo=UTC),
    )

    view = journey_absence.absence_view(
        db_session, user_id=user.id, local_date=date(2026, 10, 1), missed_days=5,
        now=datetime(2026, 10, 1, 8, 0, tzinfo=UTC),
    )

    assert view["days"] == 5 and view["greeting_fr"] is None
    assert [beat["text_fr"] for beat in view["entre_temps"]] == [
        "Lila a peint le mur 0.", "Lila a peint le mur 1.", "Lila a peint le mur 2.",
    ]
    assert view["entre_temps"][0] == {"text_fr": "Lila a peint le mur 0.", "date": "2026-09-26", "character_id": "lila_bonnet"}
    assert view["lapsed_letters"] == [{"mission_id": str(lapsed.id), "correspondent_name": "Romy"}]
    assert journey_absence.absence_view(db_session, user_id=user.id, local_date=date(2026, 10, 1), missed_days=1) is None


def test_the_story_s_own_meanwhile_reader_is_used_when_it_exists(db_session, monkeypatch) -> None:
    from app.services import living_story

    calls: list[date] = []

    def reader(live, since):
        calls.append(since)
        return [{"text_fr": f"Beat {i}", "date": "2026-09-30", "character_id": "romy_tremblay"} for i in range(8)]

    monkeypatch.setattr(living_story, "meanwhile_since", reader, raising=False)
    rows = journey_absence.entre_temps({}, date(2026, 9, 25))
    assert calls == [date(2026, 9, 24)], "the last finished day's own beats count"
    assert [row["text_fr"] for row in rows] == [f"Beat {i}" for i in range(3, 8)]


def test_the_interlude_and_the_premiere_are_read_honestly(db_session) -> None:
    user = _learner(db_session)
    _thread(db_session, user, live={"interlude": {"since": "2026-09-20", "returns_on": "2026-10-12", "reason_fr": "La troupe part en tournée."}})
    assert journey_absence.interlude_view(db_session, user.id) == {
        "returns_on": "2026-10-12", "reason_fr": "La troupe part en tournée.",
    }
    other = _learner(db_session)
    _thread(db_session, other, live={"interlude": "soon"})
    assert journey_absence.interlude_view(db_session, other.id) is None
    assert journey_absence.season_premiere_view(db_session, None) is None


def test_the_snapshot_and_the_envelope_carry_the_frame(db_session) -> None:
    from app.schemas.daily_journey import JourneySnapshot, TodayEnvelope

    for model in (JourneySnapshot, TodayEnvelope):
        assert {"absence", "season_premiere", "interlude"} <= set(model.model_fields)


# ---------------------------------------------------------------------------
# W13 — the Courrier belongs to the cast from day 1
# ---------------------------------------------------------------------------

_ENGLISH = re.compile(r"\b(the|your|you|with|is|of|to|at|and|one|before|after)\b", re.IGNORECASE)
_PRINTED = ("title", "brief", "contact_role", "scene_anchor", "twist", "channel_label", "label")


def test_the_built_in_letters_are_french_only() -> None:
    for letter in [*REAL_WORLD_MISSION_DOMAINS, *FIRST_LETTERS.values()]:
        for key in _PRINTED:
            value = str(letter.get(key) or "")
            assert not _ENGLISH.search(value), (letter["domain"], key, value)
        for cue in letter.get("ambient_cues") or []:
            assert not _ENGLISH.search(cue), (letter["domain"], cue)
    assert all(letter["contact_name"] != "Service Client" for letter in FIRST_LETTERS.values())


def _new_learner(db_session, band: str = "A1") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp99-first-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level=band,
        cefr_estimate=band,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.parametrize(("band", "writer", "name"), [("A1", "margaux_barman", "Margaux"), ("B1", "romy_tremblay", "Romy")])
def test_the_first_letter_is_the_cast_s_authored_letter(db_session, monkeypatch, band, writer, name) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: calls.append(1))  # would be a paid call
    user = _new_learner(db_session, band)

    today = asyncio.run(MissionScheduler(db_session).today(user))

    rows = db_session.query(RealWorldMission).filter(RealWorldMission.user_id == user.id).all()
    assert len(rows) == 1, "the first letter arrives alone"
    [letter] = rows
    assert letter.cadence == "weekly" and letter.iso_week is not None
    assert letter.correspondent_id == writer
    assert today["weekly_mission"]["id"] == str(letter.id)
    messenger = letter.prompt_payload["messenger"]
    assert messenger["contact_name"] == name != "Service Client"
    assert letter.prompt_payload["correspondence"]["origin"] == "cast"
    assert letter.prompt_payload["slim_payload"]["ask_by_language"]["en"]
    assert not calls, "the authored letter costs no model call"
    for key in ("contact_role", "scene_anchor", "twist"):
        assert not _ENGLISH.search(str(messenger.get(key) or "")), (key, messenger.get(key))


def test_the_first_letter_is_story_born_when_romy_or_margaux_was_there(db_session, monkeypatch) -> None:
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _new_learner(db_session, "A2")
    _thread(
        db_session,
        user,
        live={
            "events": [
                {"id": "journey:1:story", "scene_id": str(uuid.uuid4()), "witnesses": ["margaux_barman"],
                 "summary_fr": "Vous avez commandé un café au comptoir.", "source_quotes": [], "outcome": "met",
                 "at": datetime.now(UTC).isoformat()},
                {"id": "journey:2:story", "scene_id": str(uuid.uuid4()), "witnesses": ["lila_bonnet"],
                 "summary_fr": "Lila vous a montré son atelier.", "source_quotes": [], "outcome": "met",
                 "at": datetime.now(UTC).isoformat()},
            ]
        },
    )

    today = asyncio.run(MissionScheduler(db_session).today(user))
    again = asyncio.run(MissionScheduler(db_session).today(user))

    [letter] = db_session.query(RealWorldMission).filter(RealWorldMission.user_id == user.id).all()
    assert letter.correspondent_id == "margaux_barman"
    # Ad hoc, so «jour de lettre» can answer it; the week's letter waits for it.
    assert letter.cadence == "ad_hoc" and letter.prompt_payload["first_letter"] is True
    assert today["active_mission"]["id"] == again["active_mission"]["id"] == str(letter.id)
    assert today["weekly_mission"] is None and again["weekly_mission"] is None
    assert letter.prompt_payload["correspondence"]["origin"] == "story_born"
    assert "comptoir" in letter.brief and not letter.title.startswith("Real Mission")
    messenger = letter.prompt_payload["messenger"]
    assert messenger["contact_role"] == "serveuse au Mistral"
    for key in ("scene_anchor", "channel_label", "thread_title"):
        assert not _ENGLISH.search(str(messenger.get(key) or "")), (key, messenger.get(key))
    ledger = courrier.correspondence_state(db_session.get(SerialThread, letter_thread(db_session, user))).get("story_born")
    assert [row["event_id"] for row in ledger] == ["journey:1:story"]


def letter_thread(db_session, user: User):
    return db_session.query(SerialThread.id).filter(SerialThread.user_id == user.id).scalar()


A1_REPLY = {
    "title": "Un paquet pour vous",
    "brief": "Le paquet est chez la voisine. Répondez et dites quand vous êtes là.",
    "contact_name": "Inès",
    "contact_role": "une amie",
    "contact_initials": "IN",
    "scene_anchor": "Le soir, dans la rue, devant la porte",
    "thread_title": "Inès · le paquet",
    "opening_message": "Bonsoir ! J'ai votre paquet chez moi. Vous êtes là ce soir ?",
    "ambient_cues": ["un petit paquet", "une porte bleue", "le soir"],
    "quick_replies": ["Oui, je suis là...", "Merci beaucoup !", "Je viens à..."],
    "success_signal": "Inès sait quand vous venez.",
    "success_signal_en": "Inès knows when you are coming.",
    "success_signal_de": "Inès weiß, wann Sie kommen.",
    "inbox_context": "Elle veut savoir quand vous venez.",
    "domain": "deliveries_admin",
    "channel": "sms",
    "tone": "light_warm",
    "twist": "Le paquet est très grand.",
    "mission_format": "chat_message",
}
B1_REPLY = {**A1_REPLY, "brief": "Ils minimisent la panne : exigez un geste commercial.",
            "opening_message": "Nous vous proposons un geste commercial sous réserve de justificatif."}


class _BandFollowingWriter:
    """Writes at A1 only when the prompt carries the band's word list."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_chat_completion(self, messages, **_: Any) -> LLMResult:
        payload = json.loads(messages[-1]["content"])
        self.calls.append(payload)
        limits = payload.get("level_limits") or {}
        letter = A1_REPLY if "bonjour" in (limits.get("allowed_words") or []) else B1_REPLY
        return LLMResult(provider="fake", model="fake", content=json.dumps(letter, ensure_ascii=False),
                         prompt_tokens=0, completion_tokens=0, total_tokens=0, cost=0.0, raw_response={})


def test_an_a1_letter_is_written_at_the_band_on_the_first_try(db_session, monkeypatch) -> None:
    writer = _BandFollowingWriter()
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: writer)
    user = _new_learner(db_session, "A1.1")

    payload = asyncio.run(
        MissionGenerator(db_session).build_payload(
            user=user, mission_type="message", cadence="ad_hoc", use_news=False, seed=("wp99",)
        )
    )

    assert len(writer.calls) == 1, "no rejected draft"
    limits = writer.calls[0]["level_limits"]
    assert limits["band"] == "A1" and limits["max_words_outside_the_list"] == 1
    assert limits["known_word_floor_percent"] == 90
    assert payload["prompt_payload"]["messenger"]["opening_message"] == A1_REPLY["opening_message"]


def test_the_level_brief_lists_words_only_up_to_a2() -> None:
    from app.services.lexical_coverage import load_lexicon

    a1 = letter_level_brief(None, "A1.1")
    assert set(a1["allowed_words"]) == set(load_lexicon().core_lemmas("A1"))
    assert len(letter_level_brief(None, "A2")["allowed_words"]) == missions_module.LETTER_ALLOWED_WORDS_MAX
    assert "allowed_words" not in letter_level_brief(None, "B1")


# ---------------------------------------------------------------------------
# O-4 — free use from 10 days, avoidance in the forecast
# ---------------------------------------------------------------------------


def test_free_use_starts_at_the_live_planner_s_threshold() -> None:
    from app.core.srs.memory import EvidenceFormat
    from app.core.srs.simulation import FREE_USE_STABILITY_DAYS, rappel_format
    from app.services.grammar_items import REEMPLOI_STABILITY_DAYS, review_band

    assert FREE_USE_STABILITY_DAYS == REEMPLOI_STABILITY_DAYS == 10.0
    assert review_band(10.0) == "high"
    assert rappel_format(9.9) is EvidenceFormat.TRANSFORM
    assert rappel_format(10.0) is EvidenceFormat.PRODUCE
    # Still owed its «Tenue» spaced item: the transform Rappel, not free use.
    assert rappel_format(12.0, spaced_done=False) is EvidenceFormat.TRANSFORM


def test_measured_avoidance_slows_the_forecast_hold_lag() -> None:
    from app.services import level_forecast as lf

    assert lf.hold_lag_days(1.0) == 41
    assert lf.hold_lag_days(0.85) == 41  # was 64 with free use from 15 days
    assert lf.hold_lag_days(0.85, avoidance=0.2) == 47
    assert lf.hold_lag_days(0.85, avoidance=1.0) >= 365  # never held without free use
    base = {"words_needed": 0, "words_per_day": 4.0, "word_retention": 0.9, "units_required": 6,
            "units_held": 0, "units_total": 6, "units_introduced": 0, "units_per_week": 2.0,
            "unit_retention": 0.85}
    clean, _ = lf.forecast_days(lf.ForecastInputs(**base))
    avoided, _ = lf.forecast_days(lf.ForecastInputs(**base, avoidance=0.2))
    assert avoided > clean


def test_the_forecast_reads_the_measured_avoidance(db_session, monkeypatch) -> None:
    from app.services import journey_learning
    from app.services import level_forecast as lf

    monkeypatch.setattr(journey_learning, "measured_avoidance_rate", lambda db, **_: {"rate": 0.2, "total": 40})
    assert lf.measured_avoidance(db_session) == 0.2
    monkeypatch.setattr(journey_learning, "measured_avoidance_rate", lambda db, **_: {"rate": None, "total": 3})
    assert lf.measured_avoidance(db_session) is None


def test_a_strong_unit_owed_its_spaced_item_keeps_the_transform_rappel(db_session) -> None:
    from app.db.models.grammar import GrammarConcept, UserGrammarProgress
    from app.services.journey_learning import spaced_item_pending

    user = _new_learner(db_session)
    concept = GrammarConcept(
        language="fr", level="A1", difficulty_order=990, is_foundation=False, active=True,
        name=f"wp99-{uuid.uuid4().hex[:6]}", category="verbs",
    )
    db_session.add(concept)
    db_session.commit()
    progress = UserGrammarProgress(user_id=user.id, concept_id=concept.id, stability=12.0, reps=4)
    db_session.add(progress)
    db_session.commit()

    brief = spaced_item_pending(db_session, user=user, brief={"concept_id": concept.id, "stability": 12.0})
    assert brief["spaced_item_pending"] is True and brief["stability"] < 10 and brief["stability_measured"] == 12.0

    progress.spaced_success_at = datetime.now(UTC)
    db_session.commit()
    brief = spaced_item_pending(db_session, user=user, brief={"concept_id": concept.id, "stability": 12.0})
    assert brief == {"concept_id": concept.id, "stability": 12.0}
