"""#397 (child of #333): the stock «je l'ai bien lu» line is never stored as the correspondent's turn.

When no character reply could be produced (no model, a failed call, a draft the voice guard
rejected twice) the Courrier used to store the stock acknowledgement as a real turn from Gus.
The thread then read as if Gus had answered, and the letter could close «Promise kept» on
a reply nobody gave. A reply that was not produced is shown as «not answered yet», and the same
text sent again asks the correspondent again.
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.db.models.mission import RealWorldMissionTurn
from app.services.missions import MissionConversationService, _unassessed_acknowledgement
from app.services.news_service import NewsService
from tests.test_missions import _fake_france_context, _token

TEXT = "Oui, je vais parler à Lila demain matin."


def _setup(client: TestClient, monkeypatch) -> tuple[dict[str, str], str]:
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    headers = {"Authorization": f"Bearer {_token(client)}"}
    created = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "use_news": False},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    return headers, created.json()["mission"]["id"]


def _assistant_texts(db_session) -> list[str]:
    db_session.expire_all()
    return [row.text for row in db_session.query(RealWorldMissionTurn).filter(RealWorldMissionTurn.role == "assistant")]


def test_the_stock_acknowledgement_is_not_stored_as_a_correspondent_turn(client, db_session, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    stock = _unassessed_acknowledgement(SimpleNamespace(prompt_payload={}))
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_kw: stock)

    response = client.post(f"/api/v1/missions/{mission_id}/turns", json={"text": TEXT, "mode": "chat"}, headers=headers)

    assert response.status_code == 200, response.text
    assert stock not in _assistant_texts(db_session), "Gus 'answered' with the stock acknowledgement"
    body = response.json()
    assert body["assistant_turn"] == {}
    assert body["outcome"]["reply_state"] == "pending"
    assert not any(t["role"] == "assistant" for t in body["mission"]["turns"])


def test_sending_the_same_text_again_asks_the_correspondent_again(client, db_session, monkeypatch):
    headers, mission_id = _setup(client, monkeypatch)
    stock = _unassessed_acknowledgement(SimpleNamespace(prompt_payload={}))
    real = "Ah, tu vas parler à Lila ? Bonne idée, dis-moi comment ça se passe."
    answers = iter([stock, real])
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_kw: next(answers))

    url = f"/api/v1/missions/{mission_id}/turns"
    client.post(url, json={"text": TEXT, "mode": "chat"}, headers=headers)
    second = client.post(url, json={"text": TEXT, "mode": "chat"}, headers=headers)

    assert second.status_code == 200, second.text
    assert second.json()["assistant_turn"]["text"] == real
    assert _assistant_texts(db_session) == [real]
    assert "reply_state" not in second.json()["outcome"]


def test_every_register_of_the_stock_line_is_recognised():
    from app.services.missions import is_stock_reply

    tu = SimpleNamespace(prompt_payload={"messenger": {"target_register": "tu / registre familier"}})
    vous = SimpleNamespace(prompt_payload={"messenger": {"target_register": "vous / registre poli"}})

    assert is_stock_reply(_unassessed_acknowledgement(tu))
    assert is_stock_reply(_unassessed_acknowledgement(vous))
    assert is_stock_reply("  Merci pour votre message, je l'ai bien lu.   Je vous réponds rapidement. ")
    assert not is_stock_reply("Merci pour ton message ! Je viens samedi.")
