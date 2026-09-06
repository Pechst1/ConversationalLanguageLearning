"""Regression tests for real-world scenario missions."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.db.models.progress import UserVocabularyProgress
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import AtelierScheduler
from app.services.llm_service import LLMResult
from app.services.missions import (
    MissionConversationService,
    MissionCorrectionService,
    MissionGenerator,
    MissionScheduler,
)
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


def test_food_vocabulary_builds_food_domain_mission(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = User(
        id=uuid4(),
        email=f"food-mission-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    word = VocabularyWord(
        language="fr",
        word="marché",
        normalized_word="marche",
        part_of_speech="noun",
        topic_tags=["food_drink"],
        frequency_rank=75,
        german_translation="Markt",
        direction="fr_to_de",
        is_anki_card=True,
    )
    db_session.add_all([user, word])
    db_session.commit()

    payload = asyncio.run(
        MissionGenerator(db_session).build_payload(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            preferred_vocabulary_ids=[word.id],
            use_news=False,
        )
    )

    assert payload["prompt_payload"]["variety"]["domain"] == "food_dining"
    assert payload["prompt_payload"]["messenger"]["contact_name"] == "Samira"
    assert "pain" in payload["prompt_payload"]["messenger"]["opening_message"].lower()
    assert payload["target_vocabulary_ids"] == [word.id]


def test_consecutive_standalone_missions_vary_domain_contact_and_channel(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = User(
        id=uuid4(),
        email=f"variety-mission-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    scheduler = MissionScheduler(db_session)

    first = asyncio.run(scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False))
    second = asyncio.run(scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False))
    first_variety = first.prompt_payload["variety"]
    second_variety = second.prompt_payload["variety"]

    assert first_variety["domain"] != second_variety["domain"]
    assert first_variety["contact"] != second_variety["contact"]
    assert first_variety["channel"] != second_variety["channel"]


def test_eight_standalone_missions_keep_setups_fresh(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = User(
        id=uuid4(),
        email=f"eight-variety-mission-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    scheduler = MissionScheduler(db_session)

    missions = [
        asyncio.run(scheduler.create(user=user, mission_type="message", cadence="ad_hoc", use_news=False))
        for _ in range(8)
    ]
    varieties = [mission.prompt_payload["variety"] for mission in missions]

    assert len({item["domain"] for item in varieties}) == 8
    assert len({item["contact"] for item in varieties}) == 8
    assert len({item["channel"] for item in varieties}) >= 6
    assert len({item["tone"] for item in varieties}) >= 6
    assert {item["fuel_source"] for item in varieties} == {"vocab", "theme", "news_seed"}


def test_missions_today_excludes_serial_linked_acts(db_session, monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = User(
        id=uuid4(),
        email=f"today-standalone-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    thread = SerialThread(user_id=user.id, world_bible={}, state={}, news_seed={}, current_episode_index=0)
    db_session.add_all([user, thread])
    db_session.flush()
    db_session.add(
        RealWorldMission(
            user_id=user.id,
            serial_thread_id=thread.id,
            status="in_progress",
            cadence="ad_hoc",
            mission_type="message",
            title="Serial act",
            brief="Reply inside the serial.",
            selected_concept_ids=[],
            target_errata_ids=[],
            target_vocabulary_ids=[],
            source_snapshot={},
            objectives=[],
            prompt_payload={"variety": {"domain": "serial"}},
            recap_payload={},
        )
    )
    db_session.commit()

    today = asyncio.run(MissionScheduler(db_session).today(user))

    assert today["weekly_mission"]["serial_thread_id"] is None
    assert today["active_mission"] is None or today["active_mission"]["serial_thread_id"] is None
    assert all(item["serial_thread_id"] is None for item in today["recent_completed"])


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
        next_review_date=datetime.now(UTC) - timedelta(days=1),
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
            due_at=datetime.now(UTC) - timedelta(days=1),
            due_date=(datetime.now(UTC) - timedelta(days=1)).date(),
            last_review_date=datetime.now(UTC) - timedelta(days=5),
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
    assert recap["objective_results"]
    assert all("met" in item and "label" in item for item in recap["objective_results"])
    assert recap["vocabulary_credit"]["produced_correct"] >= 1
    assert recap["saved_to_srs"]["saved_count"] >= 1
    assert recap["minted_collectibles"][0]["kind"] == "logo_token"
    assert recap["minted_collectibles"][0]["source_kind"] == "mission"


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
        json={"text": "Bonjour, vous avet un probleme avec ce trajet ?", "mode": "chat"},
        headers={"Authorization": f"Bearer {token}"},
    )
    duplicate_submit = client.post(
        f"/api/v1/missions/{mission_id}/submit",
        json={"text": "Bonjour, je vais vérifier le trajet et je vous répondrai demain.", "mode": "writing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    duplicate_turn = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Bonjour, vous avet un probleme avec ce trajet ?", "mode": "chat"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert submit.status_code == 200
    assert submit.json()["correction"]["verdict"] in {"accepted", "partial", "needs_revision"}
    assert "the learner" not in str(submit.json()["correction"]).lower()
    assert turn.status_code == 200
    assert turn.json()["user_turn"]["role"] == "user"
    assert turn.json()["assistant_turn"]["role"] == "assistant"
    assert len(turn.json()["mission"]["turns"]) == 2
    assert turn.json()["correction"]["persistence"]["saved_count"] >= 2
    assert len(turn.json()["correction"]["persistence"]["error_ids"]) >= 2
    assert turn.json()["user_turn"]["correction"]["persistence"] == turn.json()["correction"]["persistence"]
    assert duplicate_submit.status_code == 200
    assert len(duplicate_submit.json()["mission"]["attempts"]) == 1
    assert duplicate_turn.status_code == 200
    assert len(duplicate_turn.json()["mission"]["turns"]) == 2
    assert duplicate_turn.json()["correction"]["persistence"]["saved_count"] >= 2


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


class _EchoMissionLLM:
    """Reproduces the live bug: corrected_target merely repeats the learner's
    sentence (curly apostrophe, extra period) and why_wrong leaks a corrector
    meta-instruction instead of learner-facing feedback."""

    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResult(
            provider="stub",
            model="stub-correction",
            content=json.dumps(
                {
                    "verdict": "needs_revision",
                    "score_0_4": 2,
                    "corrected_answer": "J'ai reçu ta carte postale hier matin",
                    "objective_progress": [],
                    "concept_hits": [],
                    "missing_targets": [],
                    "errata": [
                        {
                            "display_label": "Repeated sentence",
                            "learner_text": "J'ai reçu ta carte postale hier matin",
                            "corrected_target": "J’ai reçu ta carte postale hier matin.",
                            "why_wrong": "The message repeats the problem; only one short fragment should be corrected.",
                            "repair_hint": "Only one short fragment should be corrected.",
                            "severity": 2,
                            "recurring": False,
                            "task_error_type": "word_choice",
                            "external_id": "",
                        }
                    ],
                    "vocabulary_links": [],
                }
            ),
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0,
            raw_response={},
        )


def test_mission_correction_drops_erratum_whose_corrected_text_repeats_the_learner(db_session):
    user = User(id=uuid4(), email="mission-echo@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    service = MissionCorrectionService(db_session, llm_service=_EchoMissionLLM())

    correction = service.correct_submission(
        user=user,
        mission=mission,
        text="J'ai reçu ta carte postale hier matin",
        mode="chat",
    )

    # The identical-text "correction" vanishes entirely: no card payload, no leaked meta note.
    assert correction["errata"] == []
    assert "repeats the problem" not in json.dumps(correction)

    # And nothing is persisted, so the UI repair counter cannot increment.
    persisted = service.persist_errata(
        user=user,
        mission=mission,
        correction=correction,
        mode="chat",
        source_id="turn-echo",
    )
    assert persisted == []


def test_mission_correction_keeps_real_fix_while_dropping_echo(db_session):
    class _MixedMissionLLM:
        def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            return LLMResult(
                provider="stub",
                model="stub-correction",
                content=json.dumps(
                    {
                        "verdict": "needs_revision",
                        "score_0_4": 2,
                        "corrected_answer": "Ma carte est jolie et j'ai reçu ta lettre.",
                        "objective_progress": [],
                        "concept_hits": [],
                        "missing_targets": [],
                        "errata": [
                            {
                                "display_label": "Echoed fragment",
                                "learner_text": "j'ai reçu ta lettre",
                                "corrected_target": "J’ai reçu ta lettre",
                                "why_wrong": "The message repeats the problem; only one short fragment should be corrected.",
                                "repair_hint": "Only correct one fragment.",
                                "severity": 1,
                                "recurring": False,
                                "task_error_type": "word_choice",
                                "external_id": "",
                            },
                            {
                                "display_label": "Gender agreement",
                                "learner_text": "Mon carte",
                                "corrected_target": "Ma carte",
                                "why_wrong": "carte is feminine: ma carte.",
                                "repair_hint": "Use ma before feminine nouns.",
                                "severity": 2,
                                "recurring": False,
                                "task_error_type": "gender_agreement",
                                "external_id": "",
                            },
                        ],
                        "vocabulary_links": [],
                    }
                ),
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost=0,
                raw_response={},
            )

    user = User(id=uuid4(), email="mission-mixed@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()

    correction = MissionCorrectionService(db_session, llm_service=_MixedMissionLLM()).correct_submission(
        user=user,
        mission=mission,
        text="Mon carte est jolie et j'ai reçu ta lettre.",
        mode="chat",
    )

    assert [item["corrected_target"] for item in correction["errata"]] == ["Ma carte"]
    assert "repeats the problem" not in json.dumps(correction["errata"])


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


def test_mission_correction_keeps_full_reply_when_provider_returns_excerpt(db_session):
    class _ExcerptMissionLLM:
        def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            return LLMResult(
                provider="stub",
                model="stub-correction",
                content=json.dumps(
                    {
                        "verdict": "needs_revision",
                        "score_0_4": 2,
                        "corrected_answer": "Bonjour Monsieur Marchand.",
                        "objective_progress": [],
                        "concept_hits": [],
                        "missing_targets": [],
                        "errata": [
                            {
                                "display_label": "Word choice",
                                "learner_text": "radiator",
                                "corrected_target": "radiateur",
                                "why_wrong": "Use the French word radiateur.",
                                "repair_hint": "Replace the English noun.",
                                "severity": 2,
                                "recurring": False,
                                "task_error_type": "word_choice",
                            }
                        ],
                        "vocabulary_links": [],
                    }
                ),
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
                cost=0,
                raw_response={},
            )

    user = User(id=uuid4(), email="mission-full-rewrite@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    learner_text = (
        "Bonjour Monsieur Marchand. Malheureusement le radiator ne marche pas. "
        "Pourriez-vous organiser une réparation demain matin ?"
    )

    correction = MissionCorrectionService(db_session, llm_service=_ExcerptMissionLLM()).correct_submission(
        user=user,
        mission=mission,
        text=learner_text,
        mode="chat",
    )

    assert correction["corrected_answer"].startswith("Bonjour Monsieur Marchand.")
    assert "radiateur" in correction["corrected_answer"]
    assert "demain matin" in correction["corrected_answer"]


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
    assert response.json()["recap"]["minted_collectibles"][0]["kind"] == "logo_token"

    again = client.post(
        f"/api/v1/missions/{mission_id}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 200
    assert again.json()["recap"] == response.json()["recap"]


class _StubMissionLLM:
    """A correction LLM whose payload the test supplies verbatim."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.system_prompts: list[str] = []

    def generate_error_detection(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.system_prompts.append(str(kwargs.get("system_prompt") or ""))
        return LLMResult(
            provider="stub",
            model="stub-correction",
            content=json.dumps(self.payload),
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0,
            raw_response={},
        )


def _correction_payload(errata: list[dict], *, corrected_answer: str, **extra) -> dict:
    return {
        "verdict": "needs_revision",
        "score_0_4": 2,
        "corrected_answer": corrected_answer,
        "objective_progress": [],
        "concept_hits": [],
        "missing_targets": [],
        "errata": errata,
        "vocabulary_links": [],
        **extra,
    }


def test_mission_correction_drops_sentence_wide_rewrites_of_correct_french(db_session):
    """Live regression: on a clean reply the corrector returned three "errata"
    whose corrected_target was a rewritten sentence — content and style
    preferences dressed up as language repairs."""
    user = User(id=uuid4(), email="mission-rewrite@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    learner_text = (
        "Bonjour, la photo ne correspond pas à mon immeuble : ma porte est verte, pas bleue. "
        "Mon adresse est 14 rue des Lilas, 75011 Paris, troisième étage. "
        "Si vous retrouvez le colis, pouvez-vous me le renvoyer cette semaine ?"
    )
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Address form",
                    "learner_text": "Mon adresse est 14 rue des Lilas, 75011 Paris, troisième étage.",
                    "corrected_target": "Mon adresse est le 14 rue des Lilas, 75011 Paris, au troisième étage.",
                    "why_wrong": "Missing article and preposition for address and floor",
                    "repair_hint": "Use le/la/au with street and floor.",
                    "severity": 1,
                    "task_error_type": "grammar",
                },
                {
                    "display_label": "Request",
                    "learner_text": "Si vous retrouvez le colis, pouvez-vous me le renvoyer cette semaine ?",
                    "corrected_target": "Pouvez-vous le renvoyer rapidement ?",
                    "why_wrong": "Too vague timing; keep a concrete request",
                    "repair_hint": "Add a concrete request and timeframe.",
                    "severity": 1,
                    "task_error_type": "grammar",
                },
            ],
            corrected_answer=learner_text,
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text=learner_text, mode="chat"
    )

    assert correction["errata"] == []
    # Nothing changed, so the page shows no repair card at all.
    assert correction["corrected_answer"] == learner_text


def test_mission_correction_narrows_a_sentence_correction_to_the_changed_fragment(db_session):
    user = User(id=uuid4(), email="mission-narrow@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    learner_text = "J adore le fromage et les chats."
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Apostrophe",
                    "learner_text": "J adore le fromage et les chats.",
                    "corrected_target": "J’adore le fromage et les chats.",
                    "why_wrong": "Apostrophe manquante",
                    "repair_hint": "Écrivez j’adore.",
                    "severity": 1,
                    "task_error_type": "orthography",
                }
            ],
            corrected_answer="J’adore le fromage et les chats.",
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text=learner_text, mode="chat"
    )

    assert len(correction["errata"]) == 1
    erratum = correction["errata"][0]
    assert erratum["learner_text"] == "J adore"
    assert erratum["corrected_target"] == "J’adore"


def test_mission_correction_refuses_an_invented_answer_for_a_one_word_reply(db_session):
    """"Oui." came back "corrected" into a whole new message carrying a literal
    "[votre adresse]" placeholder, which the repair card printed as the learner's
    own polished reply."""
    user = User(id=uuid4(), email="mission-invent@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    invented = (
        "Bonjour, le colis a été livré à une mauvaise porte (bleue). Mon adresse est : [votre adresse]. "
        "Pouvez-vous renvoyer le colis à la bonne porte ou le récupérer ? Merci."
    )
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Too short",
                    "learner_text": "Oui.",
                    "corrected_target": invented,
                    "why_wrong": "Too short and lacks content; needs address and action.",
                    "repair_hint": "State the issue and a concrete next step.",
                    "severity": 2,
                    "task_error_type": "grammar",
                }
            ],
            corrected_answer=invented,
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text="Oui.", mode="chat"
    )

    assert correction["errata"] == []
    assert "[votre adresse]" not in correction["corrected_answer"]
    assert correction["corrected_answer"] == "Oui."


def test_mission_correction_drops_meta_commentary_and_fabricated_quotes(db_session):
    user = User(id=uuid4(), email="mission-meta@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    learner_text = "Le colis est chez le voisin."
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Note",
                    "learner_text": "chez le voisin",
                    "corrected_target": "chez la voisine",
                    "why_wrong": "Only one short fragment should be corrected.",
                    "repair_hint": "Keep it to one fragment.",
                    "severity": 1,
                    "task_error_type": "gender_agreement",
                },
                {
                    "display_label": "Ghost quote",
                    "learner_text": "je voudrais réclamer un remboursement",
                    "corrected_target": "je voudrais un remboursement",
                    "why_wrong": "Verbe superflu",
                    "repair_hint": "Enlevez réclamer.",
                    "severity": 1,
                    "task_error_type": "word_choice",
                },
            ],
            corrected_answer=learner_text,
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text=learner_text, mode="chat"
    )

    # The meta note goes, and so does the fragment the learner never wrote.
    assert correction["errata"] == []


def test_mission_correction_strips_markdown_from_learner_facing_prose(db_session):
    user = User(id=uuid4(), email="mission-markdown@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Gender",
                    "learner_text": "un photo",
                    "corrected_target": "une photo",
                    "why_wrong": "**photo est féminin : `une photo`**",
                    "repair_hint": "Use *une* before photo.",
                    "severity": 2,
                    "task_error_type": "gender_agreement",
                }
            ],
            corrected_answer="Je vous ai envoyé une photo hier.",
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text="Je vous ai envoyer un photo hier.", mode="chat"
    )

    erratum = correction["errata"][0]
    assert "*" not in erratum["why_wrong"]
    assert "`" not in erratum["why_wrong"]
    assert "«" in erratum["why_wrong"]
    assert "*" not in erratum["repair_hint"]


def test_mission_correction_prompt_follows_the_learners_own_language(db_session):
    user = User(
        id=uuid4(),
        email="mission-native@example.com",
        hashed_password="x",
        proficiency_level="A2",
        native_language="de",
    )
    mission = _mission_for_correction()
    llm = _StubMissionLLM(_correction_payload([], corrected_answer="Bonjour."))

    MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text="Bonjour.", mode="chat"
    )

    assert "German" in llm.system_prompts[0]
    assert "in English" not in llm.system_prompts[0]


def test_mission_task_compliance_note_is_not_filed_as_a_repair(db_session):
    """A "too little context" note is a remark about the task, not French the
    learner got wrong: filing it inflated "N réparations enregistrées" under a
    card that showed no repair."""
    user = User(id=uuid4(), email="mission-tasknote@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.commit()
    mission = _mission_for_correction()
    mission.user_id = user.id
    service = MissionCorrectionService(db_session, llm_service=None)

    correction = service.correct_submission(user=user, mission=mission, text="Oui merci.", mode="chat")
    assert any(item["task_error_type"] == "task_compliance" for item in correction["errata"])

    persisted = service.persist_errata(
        user=user, mission=mission, correction=correction, mode="chat", source_id="turn-task"
    )
    assert persisted == []


def test_mission_only_scores_the_vocabulary_the_page_prints(db_session):
    """`target_vocabulary_ids` also collects words linked to the mission's
    errata; those never reach the « À placer » ribbon, so penalising them
    graded the learner on a word the Courrier never named."""
    user = User(id=uuid4(), email="mission-hidden-vocab@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    shown = VocabularyWord(
        language="fr", word="le créneau", normalized_word="le creneau", frequency_rank=90,
        german_translation="das Zeitfenster", direction="fr_to_de", deck_name="French 5000", is_anki_card=True,
    )
    hidden = VocabularyWord(
        language="fr", word="le radiateur", normalized_word="le radiateur", frequency_rank=91,
        german_translation="der Heizkoerper", direction="fr_to_de", deck_name="French 5000", is_anki_card=True,
    )
    db_session.add_all([shown, hidden])
    db_session.commit()

    mission = _mission_for_correction()
    mission.user_id = user.id
    mission.target_vocabulary_ids = [shown.id, hidden.id]
    mission.prompt_payload = {
        "target_vocabulary": [{"word_id": shown.id, "word": "le créneau", "translation": "das Zeitfenster"}]
    }

    correction = MissionCorrectionService(db_session, llm_service=None).correct_submission(
        user=user, mission=mission, text="Bonjour, je vous confirme le rendez-vous de demain matin.", mode="chat"
    )

    scored = {item["external_id"] for item in correction["missing_targets"]}
    assert f"VOCAB_{shown.id}" in scored
    assert f"VOCAB_{hidden.id}" not in scored
    assert all(event["word_id"] != hidden.id for event in correction["vocabulary_events"])


def test_mission_flags_an_unused_target_word_once_per_mission(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    target_word = VocabularyWord(
        language="fr", word="constater", normalized_word="constater", frequency_rank=80,
        german_translation="feststellen", direction="fr_to_de", deck_name="French 5000", is_anki_card=True,
    )
    db_session.add(target_word)
    db_session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    mission_id = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "preferred_vocabulary_ids": [target_word.id],
            "use_news": False,
        },
        headers=headers,
    ).json()["mission"]["id"]

    def _missed(response):
        return [
            event for event in response.json()["correction"]["vocabulary_events"]
            if event["word_id"] == target_word.id and event["event_type"] == "missed_target"
        ]

    first = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Bonjour, le chauffage ne fonctionne plus depuis hier soir chez moi.", "mode": "chat"},
        headers=headers,
    )
    second = client.post(
        f"/api/v1/missions/{mission_id}/turns",
        json={"text": "Pourriez-vous envoyer quelqu'un demain matin pour la réparation ?", "mode": "chat"},
        headers=headers,
    )

    assert len(_missed(first)) == 1
    # A four-turn conversation used to charge the same unused word four times.
    assert _missed(second) == []


def test_mission_persistence_separates_repairs_from_vocabulary_credit(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(NewsService, "fetch_france_context", _fake_france_context)
    token = _token(client)
    target_word = VocabularyWord(
        language="fr", word="constater", normalized_word="constater", frequency_rank=80,
        german_translation="feststellen", direction="fr_to_de", deck_name="French 5000", is_anki_card=True,
    )
    db_session.add(target_word)
    db_session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    mission_id = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "preferred_vocabulary_ids": [target_word.id],
            "use_news": False,
        },
        headers=headers,
    ).json()["mission"]["id"]

    response = client.post(
        f"/api/v1/missions/{mission_id}/submit",
        json={"text": "Bonjour, je vous écris demain pour confirmer le rendez-vous avec votre équipe.", "mode": "writing"},
        headers=headers,
    )

    persistence = response.json()["correction"]["persistence"]
    # The unused target word is credited but is not a repair the card shows.
    assert persistence["saved_count"] >= 1
    assert persistence["repair_count"] == 0


def test_mission_debrief_keeps_objectives_met_in_an_earlier_turn(db_session):
    """Scoring only the LAST correction reported 0% task fit for a mission the
    learner had completed in turn one and then closed with "Oui."."""
    user = User(id=uuid4(), email="mission-debrief@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.flush()
    mission = _mission_for_correction()
    mission.user_id = user.id
    turns = [
        RealWorldMissionTurn(
            mission_id=mission.id, user_id=user.id, turn_index=1, role="user", mode="chat",
            text="Bonjour, la photo ne correspond pas à ma porte. Pouvez-vous relancer la livraison ?",
            correction_payload={
                "score_0_4": 4,
                "objective_progress": [
                    {"id": "real_world_task", "label": "…", "met": True, "note": "Clear."}
                ],
            },
        ),
        RealWorldMissionTurn(
            mission_id=mission.id, user_id=user.id, turn_index=3, role="user", mode="chat",
            text="Oui.",
            correction_payload={"score_0_4": 0.5, "objective_progress": []},
        ),
    ]

    debrief = missions_module.MissionDebriefService().build(
        mission=mission, attempts=[], turns=turns, errata_count=0, srs_result={"saved_count": 0},
    )

    assert debrief["readiness"]["task_fit"] == 100
    assert [item["met"] for item in debrief["objective_results"]] == [True]
    # The dossier speaks the publication's French.
    assert debrief["branch_outcome"]["next_best_move"].startswith(("Revoyez", "Ajoutez", "Refaites"))


def test_mission_objective_labels_are_french_and_never_count_by_index(db_session):
    user = User(id=uuid4(), email="mission-objectives@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.commit()
    _concept(db_session)
    concepts = db_session.query(GrammarConcept).filter(GrammarConcept.active.is_(True)).limit(3).all()

    objectives = MissionGenerator(db_session)._objectives(
        mission_type="message", concepts=concepts, errata=[], vocabulary=[], source_snapshot={}, stakes_level=1,
    )
    labels = [item["label"] for item in objectives]

    assert all("clear instance" not in label for label in labels)
    # Three objectives that each ask for one instance used to read "Use 1…",
    # "Use 2…", "Use 3 clear instance of …" — the enumeration index as a quota.
    assert all(item["target_count"] == 1 for item in objectives)
    assert labels[0].startswith("Écrire un message")
    assert all(label.startswith("Placer une fois : ") for label in labels[1:])


def test_mission_correction_drops_add_more_content_suggestions(db_session):
    """Live: "Oui," -> "Oui, bonsoir Madame Vidal." arrived typed as a grammar
    error. Nothing was wrong; the corrector wanted more said. The marker list
    cannot catch it (the prose came back in French), but the shape can."""
    user = User(id=uuid4(), email="mission-append@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Salutation",
                    "learner_text": "Oui,",
                    "corrected_target": "Oui, bonsoir Madame Vidal.",
                    "why_wrong": "Mot manquant: salutation et nom.",
                    "repair_hint": "Ajoutez une salutation.",
                    "severity": 1,
                    "task_error_type": "grammar",
                }
            ],
            corrected_answer="Oui, bonsoir Madame Vidal.",
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text="Oui, merci beaucoup.", mode="chat"
    )

    assert correction["errata"] == []
    # No repair survived, so nothing claims to be a correction.
    assert correction["corrected_answer"] == "Oui, merci beaucoup."


def test_mission_correction_refuses_a_spliced_fragment(db_session):
    """Trimming a sentence pair with two separate changes could splice two
    distant words into one nonsense card ("un porte" -> "une photo")."""
    user = User(id=uuid4(), email="mission-splice@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    learner_text = "Je vous ai envoyer un photo de mon porte hier soir avant le repas."
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Genre",
                    "learner_text": "un photo de mon porte hier soir",
                    "corrected_target": "une photo de ma porte hier soir",
                    "why_wrong": "Genre incorrect",
                    "repair_hint": "une photo, ma porte",
                    "severity": 2,
                    "task_error_type": "gender_agreement",
                }
            ],
            corrected_answer="Je vous ai envoyé une photo de ma porte hier soir avant le repas.",
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text=learner_text, mode="chat"
    )

    for erratum in correction["errata"]:
        # Whatever survives has to be readable back in the learner's own message.
        assert MissionCorrectionService._fragment_is_contiguous(erratum["learner_text"], learner_text)


def test_mission_correction_answer_stays_the_learners_when_no_repair_survives(db_session):
    user = User(id=uuid4(), email="mission-nocard@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    learner_text = "Bonjour, ma porte est verte et la photo montre une porte bleue."
    llm = _StubMissionLLM(
        _correction_payload(
            [],
            corrected_answer="Bonjour, ma porte est verte alors que la photo montre clairement une porte bleue.",
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text=learner_text, mode="chat"
    )

    assert correction["errata"] == []
    assert correction["corrected_answer"] == learner_text


def test_mission_correction_drops_write_more_notes_on_a_one_word_reply(db_session):
    """Live: "Oui." came back as erratum "Oui." -> "Oui, c’est" with
    corrected_answer "Oui, c’est correct mais pas assez d’information." — the
    corrector talking about the reply instead of repairing it."""
    user = User(id=uuid4(), email="mission-writemore@example.com", hashed_password="x", proficiency_level="A2")
    mission = _mission_for_correction()
    llm = _StubMissionLLM(
        _correction_payload(
            [
                {
                    "display_label": "Incomplet",
                    "learner_text": "Oui.",
                    "corrected_target": "Oui, c’est",
                    "why_wrong": "Manque de genre et nombre accordés; phrase incomplète",
                    "repair_hint": "Complétez la phrase.",
                    "severity": 2,
                    "task_error_type": "grammar",
                }
            ],
            corrected_answer="Oui, c’est correct mais pas assez d’information.",
        )
    )

    correction = MissionCorrectionService(db_session, llm_service=llm).correct_submission(
        user=user, mission=mission, text="Oui.", mode="chat"
    )

    assert correction["errata"] == []
    assert correction["corrected_answer"] == "Oui."
