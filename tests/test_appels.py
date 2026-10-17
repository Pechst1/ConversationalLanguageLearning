"""Les appels — the cast phones the learner.

Through the real router with the fake caller (no provider is ever called):

1. nothing rings until today's journey is completed and its scene settled, and only
   someone who heard the learner calls (Romy first);
2. picking up gives the caller's opening; each line gets an answer; the last allowed
   line ends the call;
3. a finished call is in the story: the learner's lines in the memory (heard by the
   caller only), one ``events[]`` row from «appel», and the story fingerprint does
   not move while the call is ringing or live;
4. declining leaves a voicemail and writes nothing into the memory;
5. the cost ceiling and an outage end the call with an authored goodbye;
6. the flag off: every route is a 404 and nothing rings;
7. a spoken line is transcribed on the ``appel`` surface and booked on the call.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.appels import get_call_provider
from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.pilot_event import PilotEvent
from app.db.models.serial import SerialThread
from app.services import appels, living_story, story_memory
from app.services.daily_journey import local_date_for
from app.services.spoken_reply import FAKE_TRANSCRIPT_MARKER
from tests.test_journey_end_to_end import learner_id, register

API = "/api/v1/appels"


@pytest.fixture()
def calls_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_CALLS_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_CALLS_MAX_TURNS", 3)
    monkeypatch.setattr(settings, "ATELIER_CALLS_MAX_USD", 0.06)


@pytest.fixture()
def caller(client: TestClient):
    fake = appels.FakeCallProvider()
    client.app.dependency_overrides[get_call_provider] = lambda: fake
    yield fake
    client.app.dependency_overrides.pop(get_call_provider, None)


def _learner(client: TestClient, db: Session, *, heard_by: str = "romy_tremblay", status: str = "completed",
             settled: bool = True) -> tuple[dict[str, str], uuid.UUID, DailyJourney]:
    email = f"appel-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(client, email, cefr="A2.1")
    user_id = learner_id(db, email)
    journey = DailyJourney(
        user_id=user_id, local_date=local_date_for("UTC"), timezone="UTC", status=status
    )
    db.add(journey)
    db.flush()
    event_id = f"journey:{journey.id}:story" if settled else "journey:elsewhere:story"
    memory = story_memory.after_day(
        None,
        story_memory.Day(
            event_id=event_id,
            day=4,
            date=journey.local_date.isoformat(),
            speaker=heard_by,
            witnesses=(heard_by,),
            exchanges=({"learner": "Je m'appelle Lena. Je cherche ma sœur.", "character": "Enchantée, Lena !"},),
            opening_fr="Tu t'appelles comment ?",
        ),
    )
    thread = SerialThread(
        user_id=user_id,
        world_bible={},
        state={living_story.STATE_KEY: {"day_index": 4, "events": [], story_memory.MEMORY_KEY: memory}},
        news_seed={},
        current_episode_index=0,
        status="active",
    )
    db.add(thread)
    db.flush()
    return headers, user_id, journey


def _thread(db: Session, user_id: uuid.UUID) -> SerialThread:
    thread = db.query(SerialThread).filter(SerialThread.user_id == user_id).one()
    db.refresh(thread)
    return thread


def _today(client: TestClient, headers: dict[str, str]) -> dict[str, Any] | None:
    response = client.get(f"{API}/today", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["call"]


def test_rings_only_after_the_settled_day_and_romy_calls(client, db_session, calls_on, caller):
    headers, _, journey = _learner(client, db_session, status="active")
    assert _today(client, headers) is None  # the day is not done yet
    journey.status = "completed"
    db_session.flush()
    call = _today(client, headers)
    assert call["status"] == "ringing"
    assert call["caller"]["id"] == "romy_tremblay" and call["caller"]["name"] == "Romy"
    assert call["turns"] == [] and call["reason_en"] is None
    assert caller.calls == []  # ringing costs nothing
    assert _today(client, headers)["id"] == call["id"]  # one call a day


def test_no_call_when_the_scene_was_not_settled(client, db_session, calls_on, caller):
    headers, _, _ = _learner(client, db_session, settled=False)
    assert _today(client, headers) is None


def test_the_caller_is_someone_who_heard_the_learner(client, db_session, calls_on, caller):
    headers, _, _ = _learner(client, db_session, heard_by="lila_bonnet")
    assert _today(client, headers)["caller"]["id"] == "lila_bonnet"


def test_a_call_goes_into_the_story(client, db_session, calls_on, caller):
    headers, user_id, _ = _learner(client, db_session)
    call = _today(client, headers)
    before = living_story._fingerprint(_thread(db_session, user_id))

    picked = client.post(f"{API}/{call['id']}/answer", headers=headers).json()["call"]
    assert picked["status"] == "live"
    assert picked["turns"][0]["who"] == "caller" and picked["turns"][0]["text_fr"].startswith("Allô")
    assert picked["turns_left"] == 3
    # A ringing or live call never moves the story revision a page is written against.
    assert living_story._fingerprint(_thread(db_session, user_id)) == before

    caller.replies.append(
        {
            "reply_fr": "Ta sœur ? Elle s'appelle comment ?",
            "ends": False,
            "learned": [
                {"key": "why_here", "fact_fr": "L'apprenant cherche sa sœur Inès.", "quote": "je cherche ma sœur Inès", "value": "Inès"},
                {"key": "job", "fact_fr": "L'apprenant est pilote.", "quote": "je suis pilote", "value": None},
            ],
        }
    )
    after = client.post(
        f"{API}/{call['id']}/say", headers=headers, json={"text": "Oui, ça va. Je cherche ma sœur Inès."}
    ).json()["call"]
    assert [turn["who"] for turn in after["turns"]] == ["caller", "learner", "caller"]
    assert after["turns_left"] == 2
    client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "Elle s'appelle Inès.", "mode": "voice"})
    ended = client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "Merci, à demain !"}).json()["call"]
    assert ended["status"] == "ended" and ended["turns_left"] == 0
    assert ended["reason_en"]  # shown once the call is over
    assert caller.calls[-1][1]["turns_left"] == 0

    live = _thread(db_session, user_id).state[living_story.STATE_KEY]
    event = live["events"][-1]
    assert event["id"] == f"appel:{call['id']}" and event["source"] == "appel"
    assert event["witnesses"] == ["romy_tremblay"]
    memory = live[story_memory.MEMORY_KEY]
    said = [row for row in memory["said"] if row["event_id"] == event["id"]]
    assert [row["quote"] for row in said] == [
        "Oui, ça va. Je cherche ma sœur Inès.",
        "Elle s'appelle Inès.",
        "Merci, à demain !",
    ]
    assert all(row["heard_by"] == ["romy_tremblay"] for row in said)
    facts = {row["key"]: row for row in memory["facts"]}
    assert facts["why_here"]["known_by"] == ["romy_tremblay"]
    assert "job" not in facts  # «je suis pilote» was never said: dropped
    assert facts["name"]["value"] == "Lena"  # the earlier day's memory is kept
    # Settling twice writes nothing twice.
    client.post(f"{API}/{call['id']}/hang-up", headers=headers)
    live = _thread(db_session, user_id).state[living_story.STATE_KEY]
    assert [row["id"] for row in live["events"]].count(event["id"]) == 1


def test_hanging_up_early_settles_what_was_said(client, db_session, calls_on, caller):
    headers, user_id, _ = _learner(client, db_session)
    call = _today(client, headers)
    client.post(f"{API}/{call['id']}/answer", headers=headers)
    client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "Je suis fatiguée ce soir."})
    ended = client.post(f"{API}/{call['id']}/hang-up", headers=headers).json()["call"]
    assert ended["status"] == "ended"
    live = _thread(db_session, user_id).state[living_story.STATE_KEY]
    assert live["events"][-1]["summary_fr"].startswith("Romy t'a téléphoné")
    assert client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "Allô ?"}).status_code == 409


def test_a_declined_call_leaves_a_voicemail_and_no_memory(client, db_session, calls_on, caller):
    headers, user_id, _ = _learner(client, db_session)
    before = dict(_thread(db_session, user_id).state[living_story.STATE_KEY])
    call = _today(client, headers)
    missed = client.post(f"{API}/{call['id']}/decline", headers=headers).json()["call"]
    assert missed["status"] == "missed"
    assert missed["voicemail"]["text_fr"].startswith("Allô, c'est Romy")
    assert _thread(db_session, user_id).state[living_story.STATE_KEY] == before
    assert client.post(f"{API}/{call['id']}/answer", headers=headers).status_code == 409
    assert _today(client, headers)["status"] == "missed"


def test_the_ceiling_ends_the_call_without_a_provider(client, db_session, calls_on, caller, monkeypatch):
    headers, user_id, _ = _learner(client, db_session)
    call = _today(client, headers)
    client.post(f"{API}/{call['id']}/answer", headers=headers)
    monkeypatch.setattr(settings, "ATELIER_CALLS_MAX_USD", 0.0005)
    calls_before = len(caller.calls)
    ended = client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "Oui, ça va bien."}).json()["call"]
    assert len(caller.calls) == calls_before
    assert ended["status"] == "ended"
    assert ended["turns"][-1]["text_fr"] == appels.FALLBACK_GOODBYE_VOUS
    booked = db_session.query(PilotEvent).filter(PilotEvent.entity_type == "appel", PilotEvent.entity_id == call["id"]).all()
    assert booked and all(row.user_id == user_id for row in booked)


def test_an_outage_answers_with_authored_lines(client, db_session, calls_on):
    class Down:
        name = "down"

        def opening(self, context):
            raise RuntimeError("provider down")

        reply = opening

    client.app.dependency_overrides[get_call_provider] = lambda: Down()
    try:
        headers, _, _ = _learner(client, db_session)
        call = _today(client, headers)
        picked = client.post(f"{API}/{call['id']}/answer", headers=headers).json()["call"]
        # No season here, so Romy is on «vous» (``address.character_register``).
        assert picked["turns"][0]["text_fr"] == appels.FALLBACK_OPENING_VOUS.format(name="Romy")
        ended = client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "Oui !"}).json()["call"]
        assert ended["status"] == "ended"
    finally:
        client.app.dependency_overrides.pop(get_call_provider, None)


def test_flag_off_is_a_404(client, db_session, caller, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_CALLS_ENABLED", True)
    from app.db.models.user import User

    headers, user_id, _ = _learner(client, db_session)
    monkeypatch.setattr(settings, "ATELIER_CALLS_ENABLED", False)
    assert client.get(f"{API}/today", headers=headers).status_code == 404
    assert client.post(f"{API}/x/answer", headers=headers).status_code == 404
    assert appels.today(db_session, db_session.get(User, user_id)) is None
    # The flag runs before auth: without a token the feature is still a plain 404.
    assert client.get(f"{API}/today").status_code == 404
    assert client.post(f"{API}/x/say", json={"text": "Allô"}).status_code == 404


def test_a_long_typed_line_is_kept_whole(client, db_session, calls_on, caller):
    headers, user_id, _ = _learner(client, db_session)
    call = _today(client, headers)
    client.post(f"{API}/{call['id']}/answer", headers=headers)
    long_line = ("Je suis restée tard au café parce que la pluie ne s'arrêtait pas. " * 8).strip()
    assert 240 < len(long_line) <= appels.LEARNER_CHARS
    after = client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": long_line})
    assert after.status_code == 200, after.text
    assert after.json()["call"]["turns"][1]["text_fr"] == long_line
    too_long = client.post(f"{API}/{call['id']}/say", headers=headers, json={"text": "a" * (appels.LEARNER_CHARS + 1)})
    assert too_long.status_code == 422


def test_another_learners_call_is_not_found(client, db_session, calls_on, caller):
    headers, _, _ = _learner(client, db_session)
    call = _today(client, headers)
    other, _, _ = _learner(client, db_session)
    assert client.post(f"{API}/{call['id']}/answer", headers=other).status_code == 404


def test_a_spoken_line_is_transcribed_on_the_call(client, db_session, calls_on, caller, monkeypatch):
    from app.api.deps import get_llm_service
    from app.services.spoken_reply import FakeTranscriber

    fake = FakeTranscriber()
    client.app.dependency_overrides[get_llm_service] = lambda: fake
    try:
        headers, user_id, _ = _learner(client, db_session)
        call = _today(client, headers)
        upload = FAKE_TRANSCRIPT_MARKER + b"Je vais bien, merci." + b"\x00" * 20000
        refused = client.post(
            "/api/v1/audio/transcribe",
            headers=headers,
            files={"file": ("a.webm", upload, "audio/webm")},
            data={"surface": "appel", "call_id": call["id"]},
        )
        assert refused.status_code == 409  # still ringing
        client.post(f"{API}/{call['id']}/answer", headers=headers)
        heard = client.post(
            "/api/v1/audio/transcribe",
            headers=headers,
            files={"file": ("a.webm", upload, "audio/webm")},
            data={"surface": "appel", "call_id": call["id"]},
        )
        assert heard.status_code == 200, heard.text
        assert heard.json()["text"] == "Je vais bien, merci."
        row = (
            db_session.query(PilotEvent)
            .filter(PilotEvent.entity_type == "appel", PilotEvent.entity_id == call["id"], PilotEvent.user_id == user_id)
            .filter(PilotEvent.event_type != appels.MODEL_EVENT_TYPE)
            .one()
        )
        assert row.cost_usd > 0
    finally:
        client.app.dependency_overrides.pop(get_llm_service, None)


def test_pick_caller_prefers_romy_then_falls_back():
    memory = {"said": [{"to": "marin_leveque", "heard_by": ["marin_leveque", "romy_tremblay"]}]}
    assert appels.pick_caller(memory) == "romy_tremblay"
    assert appels.pick_caller({"said": [{"to": "landlord_marchand", "heard_by": ["landlord_marchand"]}]}) == "landlord_marchand"
    assert appels.pick_caller({"said": [{"to": "mme_diallo", "heard_by": ["mme_diallo", "odile_ferrand"]}]}) is None
    assert appels.pick_caller(None) is None


# ---------------------------------------------------------------------------
# «Romy t'appelle»: the evening push for a call still ringing
# ---------------------------------------------------------------------------


@pytest.fixture()
def pushes(db_session, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    import app.services.notification_service as notification_service
    from app.tasks import notifications as tasks

    sent: list[dict] = []

    class _Fake:
        def __init__(self, db) -> None:
            pass

        def send_notification(self, user_id, message, title="L’Atelier", *, data=None) -> int:
            sent.append({"user_id": user_id, "title": title, "message": message, "data": dict(data or {})})
            return 1

    class _Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            return None

    monkeypatch.setattr(notification_service, "NotificationService", _Fake)
    monkeypatch.setattr(tasks, "SessionLocal", lambda: _Session())
    return sent


def _pushable(client, db_session, **kwargs):
    from app.db.models.push_subscription import PushSubscription
    from app.db.models.user import User

    headers, user_id, journey = _learner(client, db_session, **kwargs)
    user = db_session.get(User, user_id)
    user.timezone = "UTC"
    db_session.add(
        PushSubscription(
            id=uuid.uuid4(), user_id=user_id, endpoint=f"https://push.test/{uuid.uuid4().hex}",
            keys={"p256dh": "x", "auth": "y"},
        )
    )
    db_session.commit()
    return headers, user, journey


def _evening(journey, minute: int = 0):
    from datetime import UTC, datetime, timedelta

    from app.tasks import notifications as tasks

    day = journey.local_date
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(minutes=tasks.APPEL_PUSH_MINUTE)
    return (start + timedelta(minutes=minute)).isoformat()


def test_a_call_still_ringing_in_the_evening_is_pushed_once(client, db_session, calls_on, pushes):
    from app.tasks import notifications as tasks

    _, user, journey = _pushable(client, db_session)
    tasks.send_appel_pushes(now=_evening(journey, -20))
    assert not [row for row in pushes if row["user_id"] == user.id], "never before the evening"
    tasks.send_appel_pushes(now=_evening(journey))
    tasks.send_appel_pushes(now=_evening(journey, 5))

    [push] = [row for row in pushes if row["user_id"] == user.id]
    assert push["title"] == "Romy t’appelle"
    assert push["message"] == "« Vous avez une minute ? Je voulais vous parler. »"
    assert push["data"]["route"] == "/appel" and push["data"]["kind"] == "appel_ringing"
    # The push rang the call: it is the one the home and /appel show.
    call = (_thread(db_session, user.id).state.get(appels.STATE_KEY) or {}).get("calls")[-1]
    assert push["data"]["call_id"] == call["id"] and call["status"] == "ringing"
    assert tasks.pushes_sent_on(db_session, user, journey.local_date) == 1


def test_no_push_once_the_call_was_picked_up_or_declined(client, db_session, calls_on, caller, pushes):
    from app.tasks import notifications as tasks

    headers, user, journey = _pushable(client, db_session)
    call = _today(client, headers)
    client.post(f"{API}/{call['id']}/decline", headers=headers)
    tasks.send_appel_pushes(now=_evening(journey))
    assert not [row for row in pushes if row["user_id"] == user.id]


def test_no_push_without_a_settled_day_or_with_the_flag_off(client, db_session, calls_on, pushes, monkeypatch):
    from app.tasks import notifications as tasks

    _, user, journey = _pushable(client, db_session, status="in_progress")
    tasks.send_appel_pushes(now=_evening(journey))
    _, other, other_journey = _pushable(client, db_session)
    monkeypatch.setattr(settings, "ATELIER_CALLS_ENABLED", False)
    tasks.send_appel_pushes(now=_evening(other_journey))
    assert not [row for row in pushes if row["user_id"] in {user.id, other.id}]


def test_the_beat_schedules_the_call_pushes():
    from app.celery_app import celery_app

    assert "app.tasks.notifications.send_appel_pushes" in {
        entry["task"] for entry in celery_app.conf.beat_schedule.values()
    }
