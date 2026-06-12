"""Regression tests for real-world scenario missions."""
from __future__ import annotations

import json
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import AtelierScheduler
from app.services.llm_service import LLMResult
from app.services.missions import MissionConversationService, MissionCorrectionService, MissionGenerator
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


def _mission_for_correction() -> RealWorldMission:
    return RealWorldMission(
        user_id=uuid4(),
        cadence="ad_hoc",
        mission_type="message",
        title="Message Before Arrival",
        brief="Write a short French message.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[
            {
                "id": "real_world_task",
                "label": "Write a message someone could actually send",
                "target_count": 1,
                "kind": "communication",
                "required": True,
            }
        ],
        prompt_payload={},
        recap_payload={},
    )


class _AcceptedMissionLLM:
    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResult(
            provider="stub",
            model="stub-correction",
            content=json.dumps(
                {
                    "verdict": "accepted",
                    "score_0_4": 4,
                    "corrected_answer": "Vous avet un probleme?",
                    "objective_progress": [
                        {
                            "id": "real_world_task",
                            "label": "Write a message someone could actually send",
                            "met": True,
                            "note": "Submitted",
                        }
                    ],
                    "concept_hits": [],
                    "missing_targets": [],
                    "errata": [],
                    "vocabulary_links": [],
                }
            ),
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0,
            raw_response={},
        )


class _ExplodingMissionLLM:
    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("near-real-time mission correction should not call the LLM")


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
    vocab_word = VocabularyWord(
        language="fr",
        word="prévoir",
        normalized_word="prevoir",
        frequency_rank=120,
        german_translation="vorsehen",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    preferred_word = VocabularyWord(
        language="fr",
        word="constater",
        normalized_word="constater",
        frequency_rank=80,
        german_translation="feststellen",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add_all([erratum, vocab_word, preferred_word])
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=vocab_word.id,
            scheduler="anki",
            state="reviewing",
            phase="review",
            due_at=datetime.now(timezone.utc) - timedelta(days=1),
            due_date=(datetime.now(timezone.utc) - timedelta(days=1)).date(),
            last_review_date=datetime.now(timezone.utc) - timedelta(days=5),
            stability=2.0,
            difficulty=7.0,
            interval_days=2,
            scheduled_days=2,
            reps=5,
            proficiency_score=42,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "news_summary",
            "cadence": "ad_hoc",
            "preferred_concept_ids": [concept.id],
            "preferred_errata_ids": [str(erratum.id)],
            "preferred_vocabulary_ids": [preferred_word.id],
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
    assert mission["target_vocabulary_ids"][0] == preferred_word.id
    assert mission["target_vocabulary"][0]["word"] == "constater"
    assert mission["target_vocabulary"][0]["bucket"] == "preferred"
    assert vocab_word.id in mission["target_vocabulary_ids"]
    assert any(item["word"] == "prévoir" for item in mission["target_vocabulary"])
    assert any(item["translation"] == "vorsehen" for item in mission["prompt_payload"]["target_vocabulary"])
    assert any(item["kind"] == "vocabulary" and item["word_id"] == vocab_word.id for item in mission["objectives"])
    assert any(
        item["word_id"] == vocab_word.id
        for item in mission["prompt_payload"]["messenger"]["vocabulary_focus"]
    )
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


def test_custom_mission_e2e_create_turn_complete_and_queue(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    target_word = VocabularyWord(
        language="fr",
        word="constater",
        normalized_word="constater",
        frequency_rank=80,
        german_translation="feststellen",
        example_sentence="Je constate que le rendez-vous a changé.",
        example_translation="I notice that the appointment has changed.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(target_word)
    db_session.commit()

    create = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "custom_scenario": "I need to text my landlord because the heating in my apartment stopped last night.",
            "desired_outcome": "The landlord confirms a repair appointment this week.",
            "relationship": "landlord",
            "register": "polite formal",
            "preferred_vocabulary_ids": [target_word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert create.status_code == 200
    mission = create.json()["mission"]
    assert mission["status"] == "available"
    assert target_word.id in mission["target_vocabulary_ids"]

    today_after_create = client.get("/api/v1/missions/today", headers={"Authorization": f"Bearer {token}"})
    assert today_after_create.status_code == 200
    assert today_after_create.json()["active_mission"]["id"] == mission["id"]

    turn = client.post(
        f"/api/v1/missions/{mission['id']}/turns",
        json={
            "text": "Bonjour Madame Laurent, je dois constater que le chauffage ne fonctionne plus depuis hier soir. Pourriez-vous proposer un créneau de réparation cette semaine ?",
            "mode": "chat",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert turn.status_code == 200
    assert turn.json()["mission"]["status"] == "in_progress"
    assert turn.json()["assistant_turn"]["role"] == "assistant"
    assert any(event["word_id"] == target_word.id and event["event_type"] == "produced_correct" for event in turn.json()["correction"]["vocabulary_events"])

    today_after_turn = client.get("/api/v1/missions/today", headers={"Authorization": f"Bearer {token}"})
    assert today_after_turn.status_code == 200
    assert today_after_turn.json()["active_mission"]["id"] == mission["id"]
    assert today_after_turn.json()["active_mission"]["status"] == "in_progress"

    complete = client.post(
        f"/api/v1/missions/{mission['id']}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert complete.status_code == 200
    recap = complete.json()["recap"]
    assert complete.json()["mission"]["status"] == "completed"
    assert recap["turns"] == 1
    assert recap["readiness"]["overall"] >= 0
    assert recap["vocabulary_credit"]["produced_correct"] >= 1
    assert recap["saved_to_srs"]["saved_count"] >= 1


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


def test_mission_missing_target_vocabulary_creates_credit_erratum(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    user = _user_from_token(db_session, token)
    target_word = VocabularyWord(
        language="fr",
        word="constater",
        normalized_word="constater",
        frequency_rank=80,
        german_translation="feststellen",
        example_sentence="Je constate que le rendez-vous a changé.",
        example_translation="I notice that the appointment has changed.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(target_word)
    db_session.commit()

    create = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "preferred_vocabulary_ids": [target_word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    mission_id = create.json()["mission"]["id"]

    submit = client.post(
        f"/api/v1/missions/{mission_id}/submit",
        json={
            "text": "Bonjour, je vous écris demain pour confirmer le rendez-vous avec votre équipe.",
            "mode": "writing",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert submit.status_code == 200
    correction = submit.json()["correction"]
    assert any(
        event["word_id"] == target_word.id and event["event_type"] == "missed_target"
        for event in correction["vocabulary_events"]
    )
    assert any(
        item["linked_word_id"] == target_word.id and item["error_category"] == "vocabulary"
        for item in correction["errata"]
    )
    assert any(item["linked_word_id"] == target_word.id for item in submit.json()["errata"])
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == target_word.id)
        .one()
    )
    assert progress.state == "relearning"
    assert progress.phase == "relearn"

    complete = client.post(
        f"/api/v1/missions/{mission_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert complete.status_code == 200
    assert complete.json()["recap"]["vocabulary_credit"]["missed_target"] >= 1


def test_mission_correction_catches_obvious_vous_avet_when_llm_accepts(db_session):
    user = User(id=uuid4(), email="mission-correction@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()

    correction = MissionCorrectionService(db_session, llm_service=_AcceptedMissionLLM()).correct_submission(
        user=user,
        mission=mission,
        text="Vous avet un probleme?",
        mode="writing",
    )

    assert correction["verdict"] == "needs_revision"
    assert correction["corrected_answer"] == "Vous avez un problème?"
    assert any(item["learner_text"] == "Vous avet" and item["corrected_target"] == "Vous avez" for item in correction["errata"])
    assert any(item["learner_text"] == "probleme" and item["corrected_target"] == "problème" for item in correction["errata"])


def test_mission_near_realtime_correction_uses_local_rules_without_llm(db_session):
    user = User(id=uuid4(), email="mission-fast@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()

    correction = MissionCorrectionService(db_session, llm_service=_ExplodingMissionLLM()).correct_submission(
        user=user,
        mission=mission,
        text="Vous avet un probleme?",
        mode="chat",
        near_realtime=True,
    )

    assert correction["verdict"] == "needs_revision"
    assert correction["corrected_answer"] == "Vous avez un problème?"
    assert correction["correction_debug"]["prompt_version"] == "mission-correction-fast-v1"
    assert correction["correction_debug"]["near_realtime"] is True


def test_mission_stakes_tiers_change_objectives_and_word_count(db_session):
    user = User(id=uuid4(), email="stakes@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.commit()
    generator = MissionGenerator(db_session)

    tier_1 = asyncio.run(
        generator.build_payload(user=user, mission_type="message", cadence="ad_hoc", use_news=False, stakes_level=1)
    )
    tier_2 = asyncio.run(
        generator.build_payload(user=user, mission_type="message", cadence="ad_hoc", use_news=False, stakes_level=2)
    )
    tier_3 = asyncio.run(
        generator.build_payload(user=user, mission_type="message", cadence="ad_hoc", use_news=False, stakes_level=3)
    )

    assert len(tier_1["objectives"]) < len(tier_2["objectives"]) < len(tier_3["objectives"])
    assert tier_1["prompt_payload"]["min_words"] < tier_2["prompt_payload"]["min_words"] < tier_3["prompt_payload"]["min_words"]
    assert tier_3["prompt_payload"]["branching"]["tone_failures_matter"] is True


def test_serial_mission_reply_and_outcome_branch_on_objectives(db_session):
    user = User(id=uuid4(), email="serial-mission@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.flush()
    mission = RealWorldMission(
        user_id=user.id,
        serial_thread_id=uuid4(),
        cadence="ad_hoc",
        mission_type="message",
        title="Heating message",
        brief="Tell the landlord the heating is broken.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[
            {"id": "describe_problem", "label": "Describe the heating problem", "kind": "communication", "required": True},
            {"id": "make_request", "label": "Ask for a repair time", "kind": "pragmatics", "required": True},
        ],
        prompt_payload={"messenger": {"realism_rules": ["Use a formal register."]}},
        recap_payload={},
    )
    mission.turns = [
        RealWorldMissionTurn(
            mission_id=mission.id,
            user_id=user.id,
            turn_index=1,
            role="user",
            mode="chat",
            text="Bonjour, le chauffage est en panne. Pourriez-vous envoyer quelqu'un demain matin ?",
            correction_payload={
                "objective_progress": [
                    {"id": "describe_problem", "label": "Describe the heating problem", "met": True, "note": "ok"},
                    {"id": "make_request", "label": "Ask for a repair time", "met": True, "note": "ok"},
                ],
                "score_0_4": 4,
            },
        )
    ]
    service = MissionConversationService(db_session, llm_service=None)
    met_reply = service.respond(user=user, mission=mission, user_text=mission.turns[0].text)
    mission.turns[0].correction_payload["objective_progress"][1]["met"] = False
    unmet_reply = service.respond(user=user, mission=mission, user_text=mission.turns[0].text)

    assert met_reply != unmet_reply
    assert "envoie" in met_reply or "clair" in met_reply
    assert "manque" in unmet_reply


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
