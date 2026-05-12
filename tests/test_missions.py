"""Regression tests for real-world scenario missions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.atelier import AtelierScheduler
from app.services.news_service import NewsService


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    password = "mission-secure"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


async def _fake_france_context(self, interests=None, limit=3, prefer_paris=True):
    return {
        "mode": "live_france_rss",
        "digest": "Paris transport workers announced a short strike notice, and the city expects delays.",
        "items": [
            {
                "title": "Préavis de grève dans les transports parisiens",
                "summary": "Des perturbations sont attendues dans Paris.",
                "source": "RFI",
                "url": "https://www.rfi.fr/france",
                "published_at": "2026-05-04T08:00:00+00:00",
                "region_tags": ["france", "paris"],
            }
        ],
        "fetched_at": "2026-05-04T08:10:00+00:00",
        "source_policy": "RSS snapshot for tests.",
    }


def _concept(db_session) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.external_id == "FR_B1_COND_001", GrammarConcept.active.is_(True))
        .one()
    )


def _user_from_token(db_session, token: str) -> User:
    payload = decode_token(token)
    user = db_session.get(User, UUID(str(payload["sub"])))
    assert user is not None
    return user


def test_weekly_mission_is_created_once(client: TestClient, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)

    first = client.get("/api/v1/missions/today", headers={"Authorization": f"Bearer {token}"})
    second = client.get("/api/v1/missions/today", headers={"Authorization": f"Bearer {token}"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["weekly_mission"]["id"] == second.json()["weekly_mission"]["id"]
    assert first.json()["weekly_mission"]["cadence"] == "weekly"


def test_create_mission_uses_concept_erratum_and_news(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    concept = _concept(db_session)
    user = _user_from_token(db_session, token)
    erratum = UserError(
        user_id=user.id,
        concept_id=concept.id,
        error_category="grammar",
        display_label="Future result",
        original_text="si je viens, je reste",
        correction="si je viens, je resterai",
        why_wrong="You used present in the result clause.",
        repair_hint="Put the consequence in future simple.",
        source_type="atelier",
        next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(erratum)
    db_session.commit()

    response = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "news_summary",
            "cadence": "ad_hoc",
            "preferred_concept_ids": [concept.id],
            "preferred_errata_ids": [str(erratum.id)],
            "use_news": True,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    mission = response.json()["mission"]
    assert concept.id in mission["selected_concept_ids"]
    assert str(erratum.id) in mission["target_errata_ids"]
    assert mission["source_snapshot"]["mode"] == "live_france_rss"
    assert any(item["kind"] == "source" for item in mission["objectives"])
    assert mission["prompt_payload"]["experience"] == "reality_messenger"
    assert mission["prompt_payload"]["messenger"]["contact_name"] == "Mina"
    assert mission["prompt_payload"]["messenger"]["quick_replies"]


def test_custom_mission_builds_personal_thread(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)

    response = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "custom_scenario": "I need to text my landlord because the heating in my apartment is broken.",
            "desired_outcome": "The landlord understands the problem and agrees on a repair time.",
            "relationship": "landlord",
            "register": "polite formal",
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    mission = response.json()["mission"]
    assert mission["prompt_payload"]["custom_context"]["source"] == "learner_custom"
    assert mission["prompt_payload"]["messenger"]["contact_name"] == "Mme Laurent"
    assert mission["prompt_payload"]["messenger"]["success_signal"] == "The landlord understands the problem and agrees on a repair time."
    assert any(item["id"] == "custom_real_life_outcome" for item in mission["objectives"])


def test_mission_submit_and_turns_are_persisted(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    concept = _concept(db_session)
    create = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "preferred_concept_ids": [concept.id], "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    mission_id = create.json()["mission"]["id"]

    submit = client.post(
        f"/api/v1/missions/{mission_id}/submit",
        json={"text": "Bonjour, je vais vérifier le trajet et je vous répondrai demain.", "mode": "writing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    turn = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je peux expliquer le plan en détail.", "mode": "chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    duplicate_submit = client.post(
        f"/api/v1/missions/{mission_id}/submit",
        json={"text": "Bonjour, je vais vérifier le trajet et je vous répondrai demain.", "mode": "writing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    duplicate_turn = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Je peux expliquer le plan en détail.", "mode": "chat"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert submit.status_code == 200
    assert submit.json()["correction"]["verdict"] in {"accepted", "partial", "needs_revision"}
    assert "the learner" not in str(submit.json()["correction"]).lower()
    assert turn.status_code == 200
    assert turn.json()["user_turn"]["role"] == "user"
    assert turn.json()["assistant_turn"]["role"] == "assistant"
    assert len(turn.json()["mission"]["turns"]) == 2
    assert duplicate_submit.status_code == 200
    assert len(duplicate_submit.json()["mission"]["attempts"]) == 1
    assert duplicate_turn.status_code == 200
    assert len(duplicate_turn.json()["mission"]["turns"]) == 2


def test_mission_completion_returns_recap(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    concept = _concept(db_session)
    create = client.post(
        "/api/v1/missions/",
        json={"mission_type": "travel_work", "cadence": "ad_hoc", "preferred_concept_ids": [concept.id], "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    mission_id = create.json()["mission"]["id"]

    response = client.post(
        f"/api/v1/missions/{mission_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["mission"]["status"] == "completed"
    assert "completed_at" in response.json()["recap"]
    assert response.json()["recap"]["readiness"]["overall"] >= 0
    assert response.json()["recap"]["saved_to_srs"]["saved_count"] >= 1
