"""#397: the Courrier opens the mission that belongs to the day, not the oldest open thread.

``MissionScheduler.today`` used to hand the page the most recently *updated*
``in_progress`` mission before anything else. A thread the learner had answered
three nights ago therefore outranked the message opened after tonight's scene,
and the page reopened it with its replies from earlier nights. The mission the
page opens is the open one with the freshest life: created or answered last.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

REPLY = "Bonjour, je voudrais prendre le pain demain matin, s'il vous plaît."


def _headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(client)}"}


def _create(client: TestClient, headers: dict[str, str], cadence: str) -> str:
    response = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": cadence, "use_news": False},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["mission"]["id"]


def _age(db_session, mission_id: str, *, days: int) -> None:
    """Make the whole thread `days` old: the mission and every reply in it."""
    then = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days)
    mission = db_session.get(RealWorldMission, UUID(mission_id))
    mission.created_at = then
    mission.updated_at = then
    for turn in db_session.query(RealWorldMissionTurn).filter(RealWorldMissionTurn.mission_id == mission.id):
        turn.created_at = then
    db_session.commit()


def test_the_courrier_opens_the_message_after_tonights_scene_not_an_old_thread(
    client: TestClient, db_session, monkeypatch
):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers = _headers(client)

    old = _create(client, headers, "ad_hoc")
    reply = client.post(f"/api/v1/missions/{old}/turns", json={"text": REPLY, "mode": "chat"}, headers=headers)
    assert reply.status_code == 200
    assert reply.json()["mission"]["status"] == "in_progress"
    _age(db_session, old, days=3)

    tonight = _create(client, headers, "post_session")

    today = client.get("/api/v1/missions/today", headers=headers).json()

    assert today["active_mission"]["id"] == tonight, "the Courrier reopened the thread from three nights ago"


def test_a_thread_answered_today_stays_open_over_an_older_unread_message(
    client: TestClient, db_session, monkeypatch
):
    """The other way round: the learner is mid-conversation, so the thread they were
    just writing in is what the Courrier opens."""
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers = _headers(client)

    unread = _create(client, headers, "post_session")
    _age(db_session, unread, days=2)
    thread = _create(client, headers, "ad_hoc")
    client.post(f"/api/v1/missions/{thread}/turns", json={"text": REPLY, "mode": "chat"}, headers=headers)

    today = client.get("/api/v1/missions/today", headers=headers).json()

    assert today["active_mission"]["id"] == thread
