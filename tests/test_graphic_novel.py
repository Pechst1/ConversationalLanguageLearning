"""Regression tests for Graphic Novel / Feuilleton mode."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.progress import UserVocabularyProgress
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import AtelierScheduler
from app.services.graphic_novel import GraphicNovelCorrectionService, GraphicNovelGenerationError, GraphicNovelScheduler, GraphicNovelStoryGenerator


def _patch_story(monkeypatch):
    monkeypatch.setattr("app.services.graphic_novel._safe_llm", lambda: object())

    def fake_llm_skeleton(self, **kwargs):
        return _valid_visual_skeleton(panel_count=kwargs["panel_count"]), {
            "provider": "test",
            "model": kwargs["story_model"],
            "skeleton_prompt_tokens": 100,
            "skeleton_completion_tokens": 150,
            "skeleton_generation_usd": 0.0005,
            "skeleton_system_prompt": "skeleton system",
            "skeleton_user_payload": {
                "panel_count": kwargs["panel_count"],
                "target_vocabulary": kwargs.get("target_vocabulary", []),
            },
        }

    def fake_llm_surface(self, **kwargs):
        script = _valid_visual_surface(panel_count=kwargs["panel_count"])
        target_vocabulary = kwargs.get("target_vocabulary", [])
        if target_vocabulary:
            word = target_vocabulary[0]
            for panel in script["panels"]:
                for task in panel["overlay_payload"].get("tasks", []):
                    if task.get("task_type") == "short_sentence":
                        task.update(
                            {
                                "id": "panel_vocabulary_generated",
                                "label": "Vocabulary in context",
                                "instruction": f"Write one natural French sentence that continues the scene and uses {word['word']}.",
                                "prompt": (
                                    f"Context anchor: {word.get('example_sentence') or word['word']} "
                                    f"Now add one new French line for this panel that uses {word['word']} naturally."
                                ),
                                "prompt_translation": f"Use {word['word']} in a new French line that fits the comic moment.",
                                "expected_features": [
                                    f"include the target vocabulary word: {word['word']}",
                                    "continue the panel with a fresh contextual sentence",
                                ],
                                "vocabulary_task": True,
                                "production_goal": "use_target_vocabulary_in_context",
                                "target_word_id": word["word_id"],
                                "target_word": word["word"],
                                "target_translation": word.get("translation"),
                                "example_sentence": word.get("example_sentence"),
                                "example_translation": word.get("example_translation"),
                            }
                        )
                        break
                if any(task.get("vocabulary_task") for task in panel["overlay_payload"].get("tasks", [])):
                    break
        return script, {
            "provider": "test",
            "model": kwargs["story_model"],
            "surface_prompt_tokens": 100,
            "surface_completion_tokens": 200,
            "surface_generation_usd": 0.0005,
            "surface_system_prompt": "surface system",
            "surface_user_payload": {
                "panel_count": kwargs["panel_count"],
                "target_vocabulary": kwargs.get("target_vocabulary", []),
            },
        }

    monkeypatch.setattr(GraphicNovelStoryGenerator, "_llm_skeleton", fake_llm_skeleton)
    monkeypatch.setattr(GraphicNovelStoryGenerator, "_llm_surface", fake_llm_surface)


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    password = "feuilleton-secure"
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


def _serial_world() -> dict:
    return {
        "logline": "A newcomer finds a life in French.",
        "setting": {
            "recurring_locations": [
                {"id": "le_mistral", "name": "Le Mistral", "description": "A warm corner cafe."},
                {"id": "user_apartment", "name": "Your apartment", "description": "A cold sixth-floor studio."},
                {"id": "marin_lila_flat", "name": "Marin & Lila's flat", "description": "An art-covered two-room flat near Republique."},
                {"id": "newsroom", "name": "Romy's newsroom", "description": "Screens everywhere and no quiet corners."},
                {"id": "ngo_office", "name": "Marin's NGO office", "description": "Protest posters and dying plants."},
                {"id": "marche_canal", "name": "The Canal market", "description": "Cheese stalls, haggling, Sunday crowds."},
                {"id": "buttes_chaumont", "name": "Parc des Buttes-Chaumont", "description": "A hilly park made for real conversations."},
                {"id": "metro_platform", "name": "Metro platform", "description": "Last trains and missed connections."},
                {"id": "gus_loft", "name": "Gus's chateau", "description": "A theatrical bachelor loft."},
                {"id": "brocante", "name": "A flea market", "description": "Antiques, junk, and exactly the wrong gift."},
                {"id": "office_admin", "name": "An admin office", "description": "The bureaucratic vous battleground."},
            ]
        },
        "cast": [
            {"id": "marin_leveque", "name": "Marin Lévêque", "role": "friend", "dynamic_with_user": "warm anchor"},
            {"id": "lila_bonnet", "name": "Lila Bonnet", "role": "friend", "dynamic_with_user": "teasing ringleader"},
            {"id": "romy_tremblay", "name": "Romy Tremblay", "role": "journalist", "dynamic_with_user": "central tension"},
        ],
        "visual_design": {
            "characters": {
                "marin_leveque": {"build": "very tall", "accent_colour": "sea green"},
                "lila_bonnet": {"hair": "paint-flecked", "accent_colour": "marigold"},
                "romy_tremblay": {"wardrobe": "leather jacket", "accent_colour": "cold blue"},
            }
        },
    }


def test_create_feuilleton_prioritizes_due_errata(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
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
        word="prévenir",
        normalized_word="prevenir",
        frequency_rank=95,
        german_translation="warnen",
        example_sentence="Je dois prévenir Marc avant la réunion.",
        example_translation="I have to warn Marc before the meeting.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    target_word = VocabularyWord(
        language="fr",
        word="remarquer",
        normalized_word="remarquer",
        frequency_rank=88,
        german_translation="bemerken",
        example_sentence="Elle remarque le détail trop tard.",
        example_translation="She notices the detail too late.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add_all([erratum, vocab_word, target_word])
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
            last_review_date=datetime.now(timezone.utc) - timedelta(days=4),
            stability=2.1,
            difficulty=7.2,
            interval_days=2,
            scheduled_days=2,
            reps=4,
            proficiency_score=41,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "preferred_errata_ids": [str(erratum.id)],
            "target_vocabulary_ids": [target_word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    scene = response.json()["scene"]
    assert str(erratum.id) in scene["target_errata_ids"]
    assert concept.id in scene["selected_concept_ids"]
    assert scene["script_payload"]["panel_count"] == 6
    assert scene["script_payload"]["experience_mode"] == "study"
    assert scene["script_payload"]["render_mode"] == "panels"
    assert scene["script_payload"]["image_quality"] == "medium"
    assert "page_image" not in scene["script_payload"]
    assert scene["target_vocabulary_ids"][0] == target_word.id
    assert scene["target_vocabulary"][0]["word"] == "remarquer"
    assert scene["target_vocabulary"][0]["example_sentence"] == "Elle remarque le détail trop tard."
    assert scene["target_vocabulary"][0]["example_translation"] == "She notices the detail too late."
    assert vocab_word.id in scene["target_vocabulary_ids"]
    assert any(item["word"] == "prévenir" for item in scene["target_vocabulary"])
    assert any(item["translation"] == "warnen" for item in scene["script_payload"]["target_vocabulary"])
    assert any(
        item["word_id"] == vocab_word.id
        for item in scene["script_payload"]["generation_debug"]["surface_user_payload"]["target_vocabulary"]
    )
    assert len(scene["panels"]) == 6
    assert scene["script_payload"]["selected_visual_premise"]["absurd_image"]
    assert len(scene["script_payload"]["visual_premise_candidates"]) == 3
    assert scene["script_payload"]["story_model"]
    assert scene["script_payload"]["estimated_cost"]["image_generation_usd"] > 0
    tasks = [
        task
        for panel in scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    assert [task["task_type"] for task in tasks[:3]] == ["cloze", "choice", "short_sentence"]
    assert len(tasks) == 5
    vocabulary_tasks = [task for task in tasks if task.get("vocabulary_task")]
    assert len(vocabulary_tasks) == 1
    assert vocabulary_tasks[0]["task_type"] == "short_sentence"
    assert vocabulary_tasks[0]["production_goal"] == "use_target_vocabulary_in_context"
    assert vocabulary_tasks[0]["target_word_id"] == target_word.id
    assert vocabulary_tasks[0]["target_word"] == "remarquer"
    assert vocabulary_tasks[0]["example_sentence"] == "Elle remarque le détail trop tard."
    assert vocabulary_tasks[0]["example_translation"] == "She notices the detail too late."
    assert "Elle remarque le détail trop tard." in vocabulary_tasks[0]["prompt"]
    assert all("no readable text" in panel["image_prompt"].lower() for panel in scene["panels"])
    assert all("story premise" not in panel["image_prompt"].lower() for panel in scene["panels"])
    assert all("news/context inspiration" not in panel["image_prompt"].lower() for panel in scene["panels"])
    assert all("human continuity" in panel["image_prompt"].lower() for panel in scene["panels"])
    assert scene["panels"][0]["overlay_payload"]["bubbles"][0]["fr"].startswith("Encore une consigne")
    assert "The meeting" not in {panel["title"] for panel in scene["panels"]}


def test_create_feuilleton_defaults_to_mission_target_vocabulary(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)
    concept = _concept(db_session)
    user = _user_from_token(db_session, token)
    mission_word = VocabularyWord(
        language="fr",
        word="oser",
        normalized_word="oser",
        frequency_rank=110,
        german_translation="wagen",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(mission_word)
    db_session.flush()
    mission = RealWorldMission(
        user_id=user.id,
        status="available",
        cadence="ad_hoc",
        mission_type="message",
        title="Mission vocab seed",
        brief="Use a target word.",
        selected_concept_ids=[concept.id],
        target_errata_ids=[],
        target_vocabulary_ids=[mission_word.id],
        source_snapshot={},
        objectives=[],
        prompt_payload={},
    )
    db_session.add(mission)
    db_session.commit()

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "mission_id": str(mission.id), "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    scene = response.json()["scene"]
    assert scene["mission_id"] == str(mission.id)
    assert scene["target_vocabulary_ids"][0] == mission_word.id
    assert scene["target_vocabulary"][0]["word"] == "oser"


def test_non_serial_feuilleton_generation_does_not_enter_serial_plan(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)

    def fail_serial_plan(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("non-serial generation must not call the serial episode planner")

    monkeypatch.setattr(GraphicNovelStoryGenerator, "_serial_episode_plan", fail_serial_plan)
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id], "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    scene = response.json()["scene"]
    assert scene["serial_thread_id"] is None
    assert scene["script_payload"]["generation_debug"]["status"] in {"passed", "accepted_with_notes"}
    tasks = [
        task
        for panel in scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    assert [task["task_type"] for task in tasks[:3]] == ["cloze", "choice", "short_sentence"]
    assert tasks[1]["options"] == ["S'il pleut, prends ton manteau.", "S'il pleut, prendras ton manteau."]


def test_feuilleton_vocabulary_task_miss_creates_credit_erratum(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)
    user = _user_from_token(db_session, token)
    target_word = VocabularyWord(
        language="fr",
        word="remarquer",
        normalized_word="remarquer",
        frequency_rank=88,
        german_translation="bemerken",
        example_sentence="Elle remarque le détail trop tard.",
        example_translation="She notices the detail too late.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(target_word)
    db_session.commit()

    create = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "target_vocabulary_ids": [target_word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    scene = create.json()["scene"]
    vocabulary_task = next(
        task
        for panel in scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
        if task.get("vocabulary_task")
    )

    miss = client.post(
        f"/api/v1/graphic-novel/scenes/{scene['id']}/attempts",
        json={
            "task_id": vocabulary_task["id"],
            "answer_payload": {"answer": "Je regarde le dossier avec attention."},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert miss.status_code == 200
    correction = miss.json()["correction"]
    assert correction["verdict"] == "partial"
    assert any(
        event["word_id"] == target_word.id and event["event_type"] == "missed_target"
        for event in correction["vocabulary_events"]
    )
    assert correction["errata"][0]["linked_word_id"] == target_word.id
    assert any(item["linked_word_id"] == target_word.id for item in miss.json()["errata"])
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == target_word.id)
        .one()
    )
    assert progress.state == "relearning"
    assert progress.phase == "relearn"

    all_tasks = [
        task
        for panel in scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    for task in all_tasks:
        if task["id"] == vocabulary_task["id"]:
            continue
        answer = task.get("expected_answer") or "Je remarque le tampon dans la scène."
        response = client.post(
            f"/api/v1/graphic-novel/scenes/{scene['id']}/attempts",
            json={"task_id": task["id"], "answer_payload": {"answer": answer}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
    final_prompt = scene["script_payload"]["final_prompt"]
    response = client.post(
        f"/api/v1/graphic-novel/scenes/{scene['id']}/attempts",
        json={
            "task_id": final_prompt["id"],
            "answer_payload": {"answer": "Je remarque enfin pourquoi le tampon ralentit la scène."},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    complete = client.post(
        f"/api/v1/graphic-novel/scenes/{scene['id']}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert complete.status_code == 200
    assert complete.json()["recap"]["vocabulary_credit"]["missed_target"] >= 1


def test_feuilleton_completion_requires_required_tasks(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)
    concept = _concept(db_session)
    create = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create.status_code == 200
    scene = create.json()["scene"]

    complete = client.post(
        f"/api/v1/graphic-novel/scenes/{scene['id']}/complete",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert complete.status_code == 409
    detail = complete.json()["detail"]
    assert detail["code"] == "feuilleton_tasks_incomplete"
    assert scene["script_payload"]["final_prompt"]["id"] in detail["missing_task_ids"]


def test_closed_task_correction_is_deterministic_and_persists_errata(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)
    concept = _concept(db_session)
    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    scene = response.json()["scene"]
    task = scene["panels"][1]["overlay_payload"]["tasks"][0]

    wrong = client.post(
        f"/api/v1/graphic-novel/scenes/{scene['id']}/attempts",
        json={"task_id": task["id"], "answer_payload": {"answer": "réponds"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wrong.status_code == 200
    payload = wrong.json()
    assert payload["correction"]["verdict"] == "needs_revision"
    assert payload["correction"]["errata"][0]["learner_text"] == "réponds"
    assert payload["errata"], "A real grammar miss should become durable error memory"

    correct = client.post(
        f"/api/v1/graphic-novel/scenes/{scene['id']}/attempts",
        json={"task_id": task["id"], "answer_payload": {"answer": "repondrai"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert correct.status_code == 200
    assert correct.json()["correction"]["verdict"] == "correct"


def test_closed_task_fallback_feedback_uses_concept_metadata_for_non_tense_items(db_session):
    concept = GrammarConcept(
        external_id=f"FR_B1_REL_{uuid4().hex[:8]}",
        language="fr",
        name="Relative pronouns: qui, que, dont",
        level="B1",
        category="Pronouns",
        subskill="relative clauses",
        core_rule="Use qui, que, ou, or dont according to the role inside the relative clause.",
        main_traps="using que where dont is needed after a de-complement",
        exercise_tags=["relative_pronoun", "dont", "de_complement"],
        active=True,
    )
    db_session.add(concept)
    db_session.commit()
    task = {
        "id": "relative_choice",
        "task_type": "choice",
        "concept_id": concept.id,
        "label": "Use it in context",
        "instruction": "Choose the French line that fits.",
        "prompt": "Le dossier ____ je parle reste sur la table.",
        "expected_answer": "dont",
        "accepted_answers": ["dont"],
        "options": ["que", "dont", "qui"],
        "expected_features": [],
        "feedback_context": "The blank connects the second clause to the first.",
    }

    correction = GraphicNovelCorrectionService(db_session)._correct_closed(
        task=task,
        panel=None,
        answer_payload={"answer": "que"},
    )

    assert correction["verdict"] == "needs_revision"
    assert correction["errata"][0]["task_error_type"] == "relative_pronoun"
    assert "relative" in correction["why"].lower()
    assert "role" in correction["repair"].lower()
    assert "imparfait" not in correction["why"].lower()
    assert "passé composé" not in correction["why"].lower()


def test_feuilleton_supports_variable_panel_lengths(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)
    concept = _concept(db_session)

    quick = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id], "panel_count": 4},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert quick.status_code == 200
    quick_scene = quick.json()["scene"]
    quick_tasks = [
        task
        for panel in quick_scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    assert len(quick_scene["panels"]) == 4
    assert quick_scene["script_payload"]["task_count"] == 3
    assert len(quick_tasks) == 3

    long = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "preferred_concept_ids": [concept.id],
            "panel_count": 8,
            "story_quality": "premium",
            "humor_style": "absurd",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert long.status_code == 200
    long_scene = long.json()["scene"]
    long_tasks = [
        task
        for panel in long_scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    assert len(long_scene["panels"]) == 8
    assert long_scene["script_payload"]["task_count"] == 7
    assert len(long_tasks) == 7
    assert long_scene["script_payload"]["story_quality"] == "premium"
    assert long_scene["script_payload"]["humor_style"] == "absurd"


def test_feuilleton_reward_mode_is_disabled(client: TestClient, db_session):
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "preferred_concept_ids": [concept.id],
            "experience_mode": "reward",
            "render_mode": "page",
            "image_quality": "low",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Reward Feuilleton mode is currently disabled."


def test_feuilleton_panel_mode_uses_per_panel_image_payloads(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "preferred_concept_ids": [concept.id],
            "experience_mode": "study",
            "render_mode": "panels",
            "image_quality": "medium",
            "public_figure_mode": "named_context",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    scene = response.json()["scene"]
    script = scene["script_payload"]
    assert script["render_mode"] == "panels"
    assert script["image_quality"] == "medium"
    assert "page_image" not in script
    assert scene["image_quality"] == "medium"
    assert all(panel["image_payload"].get("render_mode") != "page" for panel in scene["panels"])
    assert all("human continuity" in panel["image_prompt"].lower() for panel in scene["panels"])


def test_feuilleton_generation_failure_is_honest(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr("app.services.graphic_novel._safe_llm", lambda: None)
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "feuilleton_generation_failed"
    assert "story_llm_unavailable" in detail["errors"]


def test_feuilleton_demo_script_can_power_mobile_qa_without_llm(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr("app.services.graphic_novel._safe_llm", lambda: None)
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_DEMO_SCRIPT_ENABLED", True)
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id], "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    scene = response.json()["scene"]
    assert len(scene["panels"]) == 6
    assert scene["script_payload"]["generation_debug"]["demo_script_used"] is True
    assert scene["script_payload"]["visual_only_demo"] is True
    assert scene["script_payload"]["final_prompt"]["id"] == ""
    assert not any(
        panel["overlay_payload"].get("tasks", [])
        for panel in scene["panels"]
    )


def test_feuilleton_rejects_unknown_explicit_target_vocabulary(client: TestClient, db_session, monkeypatch):
    _patch_story(monkeypatch)
    token = _token(client)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "target_vocabulary_ids": [999999], "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "unknown_target_vocabulary"


def test_serial_feuilleton_script_matches_episode_one_state_and_visual_contract(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    user = User(
        id=uuid4(),
        email=f"serial-feuilleton-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    source_snapshot = {
        "mode": "serial_news_seed",
        "title": "Paris tests a repair hotline",
        "source": "Atelier serial QA",
        "items": [
            {
                "title": "Paris tests a repair hotline",
                "summary": "A city service becomes cafe argument fuel.",
                "source": "Atelier serial QA",
            }
        ],
    }
    serial_context = {
        "thread_id": str(uuid4()),
        "episode_index": 0,
        "world_bible": _serial_world(),
        "state": {"heating_fixed": True, "marchand_trust": "improving"},
        "news_seed": {"title": "Paris tests a repair hotline"},
        "previous_locations": ["user_apartment"],
    }

    warm_script = generator.build_script(
        user=user,
        concepts=[],
        errata=[],
        source_snapshot=source_snapshot,
        panel_count=6,
        story_quality="standard",
        humor_style="satirical",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        target_vocabulary=[{"word_id": 1, "word": "reparer", "translation": "to repair"}],
        serial_context=serial_context,
    )
    cold_script = generator.build_script(
        user=user,
        concepts=[],
        errata=[],
        source_snapshot=source_snapshot,
        panel_count=6,
        story_quality="standard",
        humor_style="satirical",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        target_vocabulary=[{"word_id": 1, "word": "reparer", "translation": "to repair"}],
        serial_context={**serial_context, "state": {"heating_fixed": False, "marchand_trust": "strained"}},
    )

    assert warm_script["generation_debug"]["prompt_variant"] == "serial"
    assert warm_script["location_id"] == "le_mistral"
    assert warm_script["location_id"] not in warm_script["serial_context"]["previous_locations"]
    assert warm_script["hook"]["next_beat_kind"] == "mission"
    assert warm_script["hook"]["unresolved_question"]
    assert "Romy" in " ".join(panel["beat"] for panel in warm_script["panels"])
    assert warm_script["panels"][-1]["beat"] != cold_script["panels"][-1]["beat"]
    assert "réparation" in warm_script["panels"][0]["beat"].lower()
    assert warm_script["panels"][0]["overlay_payload"]["caption"]["fr"].startswith("Première nuit à Paris")
    assert "peut-être" in warm_script["panels"][1]["overlay_payload"]["caption"]["fr"]
    prompt_text = " ".join(panel["image_prompt"] for panel in warm_script["panels"])
    assert "sea green" in prompt_text
    assert "cold blue" in prompt_text
    assert "Atelier serial QA" in warm_script["source_usage"]["attribution"]
    choice_task = warm_script["panels"][1]["overlay_payload"]["tasks"][0]
    assert choice_task["id"] == "panel_2_choice"
    assert choice_task["options"][0]["fr"].startswith("Bonsoir")
    assert choice_task["options"][1]["fr"].startswith("Salut")
    assert set(choice_task["branch_target"]) == {"A", "B"}


def test_serial_location_rotation_uses_full_location_library(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    world = _serial_world()
    previous_locations = ["user_apartment"]
    chosen: list[str] = []

    for episode_index in range(1, 8):
        location = generator._serial_location(
            world=world,
            previous_locations=previous_locations,
            episode_index=episode_index,
        )
        location_id = str(location["id"])
        assert location_id != previous_locations[-1]
        chosen.append(location_id)
        previous_locations.append(location_id)

    assert chosen[0] == "le_mistral"
    assert len(set(chosen)) >= 6
    assert chosen.count("le_mistral") == 1
    assert chosen[:2] != ["le_mistral", "user_apartment"]


def test_serial_visual_design_contract_feeds_cast_and_location_descriptors(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    world = _serial_world()
    world["visual_design"]["characters"]["romy_tremblay"] = {
        "canonical_descriptor": "locked Romy model sheet descriptor; leather jacket; cold-blue accent",
        "accent_colour": "#1d3a8a",
        "ui_token": "--char-romy",
        "reference_images": ["assets/serial/characters/romy_tremblay/model-sheet.png"],
        "style_ref": "assets/serial/characters/romy_tremblay/model-sheet.png",
        "expressions": {"warm": "softened", "guarded": "reporter stare"},
    }
    world["visual_design"]["locations"] = {
        "le_mistral": {
            "canonical_descriptor": "locked Le Mistral plate descriptor; zinc counter; rain on glass",
            "reference_images": ["assets/serial/locations/le_mistral-counter.png"],
        }
    }

    romy = next(item for item in generator._serial_cast(world) if item["id"] == "romy_tremblay")
    assert "locked Romy model sheet descriptor" in romy["visual_description"]
    assert "#1d3a8a" in romy["visual_description"]
    assert "--char-romy" in romy["visual_description"]
    assert "reference images: assets/serial/characters/romy_tremblay/model-sheet.png" in romy["visual_description"]
    assert "style reference: assets/serial/characters/romy_tremblay/model-sheet.png" in romy["visual_description"]
    assert "expressions: warm, guarded" in romy["visual_description"]

    user = User(
        id=uuid4(),
        email=f"serial-visual-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()

    script = generator.build_script(
        user=user,
        concepts=[],
        errata=[],
        source_snapshot={"mode": "serial_news_seed", "title": "Paris tests a repair hotline", "source": "QA"},
        panel_count=6,
        story_quality="standard",
        humor_style="satirical",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        target_vocabulary=[],
        serial_context={
                "thread_id": str(uuid4()),
                "episode_index": 0,
                "world_bible": world,
                "state": {},
                "news_seed": {"title": "Paris tests a repair hotline"},
            "previous_locations": ["user_apartment"],
        },
    )

    assert script["location_id"] == "le_mistral"
    assert script["selected_visual_premise"]["domain"] == (
        "locked Le Mistral plate descriptor; zinc counter; rain on glass; "
        "reference images: assets/serial/locations/le_mistral-counter.png"
    )


def test_serial_image_prompts_include_f6_craft_guardrails(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    user = User(
        id=uuid4(),
        email=f"serial-image-guardrails-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()

    script = generator.build_script(
        user=user,
        concepts=[],
        errata=[],
        source_snapshot={"mode": "serial_news_seed", "title": "Paris tests a repair hotline", "source": "QA"},
        panel_count=6,
        story_quality="standard",
        humor_style="satirical",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        target_vocabulary=[],
        serial_context={
            "thread_id": str(uuid4()),
            "episode_index": 1,
            "world_bible": _serial_world(),
            "state": {"heating_fixed": True},
            "news_seed": {"title": "Paris tests a repair hotline"},
            "previous_locations": ["user_apartment"],
        },
    )

    prompts = [panel["image_prompt"] for panel in script["panels"]]
    assert all("Shot variety:" in prompt for prompt in prompts)
    assert all("Foreground prop guardrail:" in prompt for prompt in prompts)
    assert all("no visible screen contents" in prompt.lower() for prompt in prompts)
    assert not any("showing on the screen" in prompt.lower() for prompt in prompts)
    assert not any("displaying on the screen" in prompt.lower() for prompt in prompts)
    assert len({panel["serial_shot_hint"] for panel in script["panels"]}) >= 4


def test_serial_feuilleton_uses_llm_episode_plan_when_available(db_session, monkeypatch):
    generator = GraphicNovelStoryGenerator(db_session)
    user = User(
        id=uuid4(),
        email=f"serial-llm-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="B1",
    )
    db_session.add(user)
    db_session.commit()

    plan = {
        "episode_title": "Feuilleton: Le marché du dimanche",
        "episode_brief": "Romy drags everyone to the Canal market to chase a story.",
        "twist": "The newcomer accidentally becomes Romy's on-camera source.",
        "panels": [
            {
                "title": "Le réveil",
                "beat": "Lila bangs on the door: the group is already late for the market.",
                "panel_action": "A sleepy newcomer is hauled out into a bright Sunday morning.",
                "caption_fr": "Dimanche. Lila ne connaît pas le mot grasse matinée.",
                "caption_en": "Sunday. Lila does not know the words sleeping in.",
                "tasks": [
                    {
                        "id": "panel_1_market_cloze",
                        "task_type": "cloze",
                        "label": "Market wake-up",
                        "instruction": "Complete Lila's line from this morning.",
                        "prompt": "On est en retard pour le _____.",
                        "prompt_translation": "We are late for the market.",
                        "expected_answer": "marché",
                        "accepted_answers": ["marché", "le marché"],
                        "options": [],
                        "expected_features": [],
                        "placeholder": "marché",
                        "scene_function": "Names the actual Sunday pressure instead of replaying the pilot radiator.",
                        "feedback_context": "Marché is the story location and the useful noun in the beat.",
                    }
                ],
                "bubbles": [
                    {
                        "speaker_id": "lila_bonnet",
                        "speaker": "Lila",
                        "fr": "Debout. Romy va nous tuer.",
                        "en": "Up. Romy is going to kill us.",
                        "x": 11,
                        "y": 10,
                        "tone": "brisk",
                    }
                ],
            },
            {
                "title": "Le stand de fromage",
                "beat": "At the cheese stall you must choose how to ask the vendor.",
                "panel_action": "The newcomer hesitates in front of a towering wall of cheese.",
                "caption_fr": "Le fromager attend. Tu choisis tes mots.",
                "caption_en": "The cheesemonger waits. You choose your words.",
                "tasks": [
                    {
                        "id": "panel_2_vendor_choice",
                        "task_type": "choice",
                        "label": "Ask the vendor",
                        "instruction": "Choose the line that fits the stall.",
                        "prompt": "Tu demandes une dégustation :",
                        "prompt_translation": "You ask for a tasting:",
                        "expected_answer": "B",
                        "accepted_answers": ["B"],
                        "options": [
                            {
                                "value": "A",
                                "label": "A",
                                "fr": "Excusez-moi, je pourrais goûter ce fromage ?",
                                "en": "Excuse me, could I taste this cheese?",
                                "next_panel_beat": "You ask formally; the vendor decides you are a tourist.",
                            },
                            {
                                "value": "B",
                                "label": "B",
                                "fr": "On peut goûter celui-là, s'il vous plaît ?",
                                "en": "Could we taste that one, please?",
                                "next_panel_beat": "You ask warmly; the vendor slips you an extra slice.",
                            },
                        ],
                        "expected_features": [],
                        "placeholder": "",
                        "scene_function": "Makes the learner choose register at the market stall.",
                        "feedback_context": "Both lines are useful; B joins the group more naturally.",
                    }
                ],
                "bubbles": [],
            },
            {
                "title": "Marin philosophe",
                "beat": "Marin explains, near tears, why this cheese reminds him of Brittany.",
                "panel_action": "Marin holds a wheel of cheese like a sacred relic.",
                "caption_fr": "Marin pleure presque. C'est juste du fromage.",
                "caption_en": "Marin is nearly crying. It is just cheese.",
                "tasks": [],
                "bubbles": [
                    {
                        "speaker_id": "marin_leveque",
                        "speaker": "Marin",
                        "fr": "Il a une mémoire, ce fromage.",
                        "en": "This cheese has a memory.",
                        "x": 50,
                        "y": 12,
                        "tone": "sincere",
                    }
                ],
            },
            {
                "title": "Romy en direct",
                "beat": "Romy films a segment about market prices and pushes a microphone at you.",
                "panel_action": "A phone-camera light swings toward the startled newcomer.",
                "caption_fr": "Romy appelle ça du journalisme. Toi, une embuscade.",
                "caption_en": "Romy calls it journalism. You call it an ambush.",
                "tasks": [
                    {
                        "id": "panel_4_market_reaction",
                        "task_type": "short_sentence",
                        "label": "On-camera reaction",
                        "instruction": "Answer Romy with one sentence that uses the target word.",
                        "prompt": "Réponds à Romy sur le marché.",
                        "prompt_translation": "Answer Romy about the market.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": ["use le marché", "one consequence"],
                        "placeholder": "Le marché...",
                        "scene_function": "Connects the news texture to the market plot.",
                        "feedback_context": "Use the target vocabulary as part of Romy's ambush.",
                    }
                ],
                "bubbles": [
                    {
                        "speaker_id": "romy_tremblay",
                        "speaker": "Romy",
                        "fr": "Une phrase. Naturelle.",
                        "en": "One sentence. Natural.",
                        "x": 42,
                        "y": 9,
                        "tone": "dry",
                    }
                ],
            },
            {
                "title": "Le café d'après",
                "beat": "The group debriefs over coffee; you somehow passed.",
                "panel_action": "Five friends crowd a tiny outdoor table covered in market loot.",
                "caption_fr": "Tu as survécu au direct. Presque dignement.",
                "caption_en": "You survived the live shot. Almost with dignity.",
                "tasks": [],
                "bubbles": [],
            },
            {
                "title": "La question de Romy",
                "beat": "Romy replays the clip and asks if you'd ever go on camera for real.",
                "panel_action": "Romy turns her phone toward you, eyebrow raised, waiting.",
                "caption_fr": "Elle sourit. La vraie question arrive.",
                "caption_en": "She smiles. The real question is coming.",
                "tasks": [
                    {
                        "id": "panel_6_camera_line",
                        "task_type": "short_sentence",
                        "label": "Answer Romy",
                        "instruction": "Give Romy one concrete answer.",
                        "prompt": "Réponds à sa proposition.",
                        "prompt_translation": "Answer her proposal.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": ["future or condition", "specific next step"],
                        "placeholder": "Je pourrais...",
                        "scene_function": "Turns the cliffhanger into the next social problem.",
                        "feedback_context": "The line should invite the next episode, not recap this one.",
                    }
                ],
                "bubbles": [
                    {
                        "speaker_id": "romy_tremblay",
                        "speaker": "Romy",
                        "fr": "Alors ? Tu recommences lundi ?",
                        "en": "So? Are you doing it again Monday?",
                        "x": 14,
                        "y": 11,
                        "tone": "challenge",
                    }
                ],
            },
        ],
        "opening_cloze": {
            "prompt": "On est en retard pour le _____.",
            "prompt_translation": "We are late for the market.",
            "answer": "marché",
        },
        "choice": {
            "option_a_next_beat": "You ask formally; the vendor decides you are a tourist.",
            "option_b_next_beat": "You ask warmly; the vendor slips you an extra slice.",
        },
        "hook": {
            "text": "Romy te tend son téléphone : « La prochaine fois, tu parles devant la caméra. »",
            "unresolved_question": "Will you say yes to Romy — on camera and otherwise?",
            "teaser": "Il faut une réponse avant lundi.",
        },
    }
    monkeypatch.setattr(
        GraphicNovelStoryGenerator,
        "_serial_episode_plan",
        lambda self, **kwargs: plan,
    )

    serial_context = {
        "thread_id": str(uuid4()),
        "episode_index": 4,
        "world_bible": _serial_world(),
        "state": {"heating_fixed": True, "user.knows_tu_switch": "learning"},
        "news_seed": {"title": "Market prices in the news"},
        "previous_locations": ["le_mistral", "user_apartment"],
        "hook_from_previous": {"text": "Romy proposed an early start.", "next_beat_kind": "feuilleton"},
    }

    script = generator.build_script(
        user=user,
        concepts=[],
        errata=[],
        source_snapshot={"mode": "serial_news_seed", "title": "Market prices in the news", "source": "QA"},
        panel_count=6,
        story_quality="standard",
        humor_style="satirical",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        target_vocabulary=[{"word_id": 7, "word": "le marché", "translation": "the market"}],
        serial_context=serial_context,
    )

    # The episode is the LLM plan, not the hardcoded pilot.
    assert script["generation_debug"]["status"] == "serial_llm_script"
    assert script["generation_debug"]["fallback_used"] is False
    assert script["generation_debug"]["serial_plan_source"] == "llm"
    assert script["title"] == "Feuilleton: Le marché du dimanche"
    panel_beats = " ".join(panel["beat"] for panel in script["panels"])
    assert "cheese stall" in panel_beats
    assert "première nuit" not in panel_beats.lower() and "radiator" not in panel_beats.lower()
    # The cliffhanger is the plan's hook and still seeds the next mission.
    assert script["hook"]["unresolved_question"] == "Will you say yes to Romy — on camera and otherwise?"
    assert script["hook"]["next_beat_kind"] == "mission"
    # Plan content flows into tasks, bubbles, and visible choice option text.
    task_labels = [
        task["label"]
        for panel in script["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    assert {"Radiator phrase", "How do you enter?", "Introduce yourself", "News reaction", "Keep the thread alive"}.isdisjoint(task_labels)
    cloze_task = script["panels"][0]["overlay_payload"]["tasks"][0]
    assert cloze_task["expected_answer"] == "marché"
    choice_task = script["panels"][1]["overlay_payload"]["tasks"][0]
    assert choice_task["options"][0]["fr"].startswith("Excusez-moi")
    assert choice_task["options"][1]["fr"].startswith("On peut goûter")
    assert "extra slice" in choice_task["branch_target"]["B"]["next_panel_beat"]
    assert script["panels"][0]["overlay_payload"]["bubbles"][0]["fr"] == "Debout. Romy va nous tuer."
    assert script["panels"][0]["overlay_payload"]["bubbles"][0]["accent_color"] == "marigold"


def test_serial_episode_one_can_still_fallback_but_episode_two_needs_story_true_plan(db_session, monkeypatch):
    generator = GraphicNovelStoryGenerator(db_session)
    user = User(
        id=uuid4(),
        email=f"serial-fallback-boundary-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    monkeypatch.setattr(GraphicNovelStoryGenerator, "_serial_episode_plan", lambda self, **kwargs: None)

    serial_context = {
        "thread_id": str(uuid4()),
        "episode_index": 1,
        "world_bible": _serial_world(),
        "state": {"heating_fixed": True},
        "news_seed": {"title": "Paris tests a repair hotline"},
        "previous_locations": ["user_apartment"],
    }
    fallback_script = generator.build_script(
        user=user,
        concepts=[],
        errata=[],
        source_snapshot={"mode": "serial_news_seed", "title": "Paris tests a repair hotline", "source": "QA"},
        panel_count=6,
        story_quality="standard",
        humor_style="satirical",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        target_vocabulary=[{"word_id": 1, "word": "réparer", "translation": "to repair"}],
        serial_context=serial_context,
    )

    assert fallback_script["generation_debug"]["serial_plan_source"] == "template"
    assert fallback_script["generation_debug"]["fallback_used"] is True
    with pytest.raises(GraphicNovelGenerationError) as exc:
        generator.build_script(
            user=user,
            concepts=[],
            errata=[],
            source_snapshot={"mode": "serial_news_seed", "title": "Paris tests a repair hotline", "source": "QA"},
            panel_count=6,
            story_quality="standard",
            humor_style="satirical",
            experience_mode="study",
            render_mode="panels",
            image_quality="medium",
            public_figure_mode="named_context",
            target_vocabulary=[{"word_id": 1, "word": "réparer", "translation": "to repair"}],
            serial_context={**serial_context, "episode_index": 2},
        )
    assert "serial_story_llm_unavailable" in exc.value.errors


def test_serial_plan_rejects_first_meeting_task_after_group_is_known(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    plan = {
        "panels": [
            {
                "tasks": [
                    {
                        "id": "panel_1_known_group_intro",
                        "task_type": "short_sentence",
                        "label": "Say who you are",
                        "instruction": "Write one sentence to present yourself to the group again.",
                        "prompt": "Présente-toi au groupe.",
                        "prompt_translation": "Introduce yourself to the group.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": ["present tense", "self-introduction"],
                        "placeholder": "Je suis...",
                        "scene_function": "This would wrongly replay the pilot meeting after the group knows the learner.",
                        "feedback_context": "The learner has already met the group, so this task should be rejected.",
                    }
                ],
                "bubbles": [
                    {
                        "speaker_id": "lila_bonnet",
                        "speaker": "Lila",
                        "fr": "Tu connais déjà la table.",
                        "en": "You already know the table.",
                        "x": 12,
                        "y": 9,
                        "tone": "dry",
                    }
                ],
            }
        ]
    }

    errors = generator._serial_plan_quality_errors(
        episode_plan=plan,
        panel_count=1,
        branch_target={},
        target_vocabulary=[],
        state={"user": {"has_met_group": True}},
    )

    assert "serial_plan_reintroduces_known_group" in errors


def test_serial_episode_plan_receives_state_flags_and_register_map(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    captured: dict[str, Any] = {}

    class FakeLLM:
        def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["system_prompt"] = kwargs["system_prompt"]
            captured["payload"] = json.loads(kwargs["messages"][0]["content"])
            return type("Result", (), {
                "content": json.dumps({
                    "episode_title": "Feuilleton: test",
                    "episode_brief": "A payload contract test.",
                    "twist": "The state matters.",
                    "panels": [
                        {
                            "title": "Test",
                            "beat": "Lila addresses the learner as someone already known.",
                            "panel_action": "A small register beat at the table.",
                            "caption_fr": "Lila te reconnaît tout de suite.",
                            "caption_en": "Lila recognizes you right away.",
                            "tasks": [],
                            "bubbles": [],
                        }
                    ],
                    "opening_cloze": {"prompt": "", "prompt_translation": "", "answer": ""},
                    "choice": {"option_a_next_beat": "", "option_b_next_beat": ""},
                    "hook": {"text": "La suite appelle.", "unresolved_question": "Pourquoi ?", "teaser": "Demain."},
                })
            })()

    generator.llm = FakeLLM()
    user = User(
        id=uuid4(),
        email=f"serial-payload-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A2",
    )

    plan = generator._serial_episode_plan(
        user=user,
        world=_serial_world(),
        state={
            "user": {"has_met_group": True, "default_register": "vous"},
            "relationships": {"lila_bonnet": {"register": "tu", "closeness": 4}},
        },
        hook_from_previous={},
        location={"id": "le_mistral", "name": "Le Mistral", "description": "A warm cafe."},
        cast=[],
        news_title="Paris tests a repair hotline",
        targets=[],
        target_vocabulary=[],
        episode_brief={},
        panel_count=1,
        story_quality="standard",
        humor_style="satirical",
        story_model="test-model",
        episode_index=4,
    )

    assert plan
    assert captured["payload"]["serial_state_flags"]["user_has_met_group"] is True
    assert captured["payload"]["register_state"]["default"] == "vous"
    assert captured["payload"]["register_state"]["relationships"]["lila_bonnet"]["register"] == "tu"
    assert "do not force tu unless the relationship register is tu" in captured["system_prompt"]


def test_serial_feuilleton_choice_branch_persists_state_and_next_panel(db_session):
    user = User(
        id=uuid4(),
        email=f"serial-branch-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.flush()
    thread = SerialThread(user_id=user.id, world_bible=_serial_world(), state={}, news_seed={})
    db_session.add(thread)
    db_session.flush()
    next_beat = "Lila grins at the warm tu and decides you may be useful entertainment."
    task = {
        "id": "panel_2_choice",
        "task_type": "choice",
        "concept_id": None,
        "label": "How do you enter?",
        "instruction": "Choose the line that sets your first impression.",
        "prompt": "Tu entres et tu dis :",
        "prompt_translation": "You go in and say:",
        "expected_answer": "B",
        "accepted_answers": ["B"],
        "options": ["A", "B"],
        "expected_features": [],
        "placeholder": "",
        "scene_function": "Turns the entrance into a bounded branch about tu/vous and confidence.",
        "feedback_context": "Both options are plausible; the choice changes how the next panel treats you.",
        "branch_target": {
            "B": {
                "state_delta": {
                    "set": {"user.first_impression": "game", "user.knows_tu_switch": "learning"},
                    "reason": "The learner entered warmly with tu.",
                    "source": {"type": "feuilleton_choice", "task_id": "panel_2_choice"},
                },
                "next_panel_beat": next_beat,
            }
        },
    }
    scene = GraphicNovelScene(
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status="available",
        cadence="serial",
        title="Serial branch test",
        brief="A deterministic branch test.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={
            "panels": [
                {"panel_index": 1, "beat": "The doorway choice waits."},
                {"panel_index": 2, "beat": "Original booth beat."},
            ],
            "final_prompt": {"id": ""},
        },
        recap_payload={},
        cache_key=f"serial-branch-{uuid4().hex}",
        prompt_version="test",
        image_model="test",
        image_quality="medium",
    )
    db_session.add(scene)
    db_session.flush()
    panel = GraphicNovelPanel(
        scene_id=scene.id,
        panel_index=1,
        title="Door",
        beat="The doorway choice waits.",
        image_prompt="test",
        image_payload={},
        overlay_payload={
            "caption": {"panel_index": 1, "fr": "Tu entres.", "en": "You enter."},
            "bubbles": [],
            "tasks": [task],
        },
        generation_metadata={},
    )
    following_panel = GraphicNovelPanel(
        scene_id=scene.id,
        panel_index=2,
        title="Booth",
        beat="Original booth beat.",
        image_prompt="test",
        image_payload={},
        overlay_payload={
            "caption": {"panel_index": 2, "fr": "La table attend.", "en": "The table waits."},
            "bubbles": [],
            "tasks": [],
        },
        generation_metadata={},
    )
    db_session.add_all([panel, following_panel])
    db_session.commit()
    db_session.refresh(scene)

    attempt, _ = GraphicNovelCorrectionService(db_session, llm_service=None).submit_attempt(
        user=user,
        scene=scene,
        task_id="panel_2_choice",
        answer_payload={"answer": "B"},
    )

    db_session.refresh(thread)
    db_session.refresh(following_panel)
    db_session.refresh(scene)
    assert attempt.correction_payload["branch_outcome"]["selected"] == "B"
    assert thread.state["user.first_impression"] == "game"
    assert thread.state["user.knows_tu_switch"] == "learning"
    assert following_panel.beat == next_beat
    assert following_panel.generation_metadata["branch_applied"]["next_panel_beat"] == next_beat
    assert scene.script_payload["panels"][1]["beat"] == next_beat


def test_scene_creation_queues_images_when_image_generation_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(GraphicNovelScheduler, "_enqueue_scene_image_generation", lambda self, scene_id: None)
    image_mock = AsyncMock(return_value={"url": "/assets/generated/should-not-be-called.png"})
    monkeypatch.setattr("app.services.graphic_novel.GraphicNovelImageService.generate_panel_image", image_mock)

    class FakeGenerator:
        def build_script(self, **kwargs):
            script = _valid_visual_script(panel_count=kwargs["panel_count"])
            script["render_mode"] = kwargs["render_mode"]
            return script

    user = User(
        id=uuid4(),
        email=f"async-images-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="B1",
    )
    db_session.add(user)
    db_session.commit()

    scene = asyncio.run(
        GraphicNovelScheduler(db_session, generator=FakeGenerator()).create(
            user=user,
            cadence="ad_hoc",
            panel_count=4,
            force_new=True,
            sync=None,
        )
    )

    assert scene.status == "generating"
    assert image_mock.await_count == 0
    assert scene.panels
    assert all(panel.image_url is None for panel in scene.panels)
    assert all(panel.generation_metadata["image_status"] == "queued" for panel in scene.panels)


def test_local_image_storage_persists_panel_url(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "local")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_URL_PREFIX", "/media/test-graphic-novel")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED", False)

    class FakeGenerator:
        def build_script(self, **kwargs):
            script = _valid_visual_script(panel_count=kwargs["panel_count"])
            script["render_mode"] = kwargs["render_mode"]
            return script

    user = User(
        id=uuid4(),
        email=f"local-image-storage-{uuid4()}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="en",
        proficiency_level="B1",
    )
    db_session.add(user)
    db_session.commit()

    scene = asyncio.run(
        GraphicNovelScheduler(db_session, generator=FakeGenerator()).create(
            user=user,
            cadence="ad_hoc",
            panel_count=4,
            force_new=True,
            sync=True,
        )
    )

    panel = sorted(scene.panels, key=lambda item: item.panel_index)[0]
    assert panel.image_url
    assert panel.image_url.startswith("/media/test-graphic-novel/scenes/")
    assert not panel.image_url.startswith("data:")
    assert panel.image_payload["url"] == panel.image_url
    assert panel.image_payload["storage"]["backend"] == "local"
    stored_path = tmp_path / panel.image_payload["storage"]["key"]
    assert stored_path.exists()
    assert stored_path.read_text(encoding="utf-8").lstrip().startswith("<svg")


def test_feuilleton_validation_notes_do_not_block_scene(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr("app.services.graphic_novel._safe_llm", lambda: object())

    def fake_llm_skeleton(self, **kwargs):
        return _valid_visual_skeleton(panel_count=kwargs["panel_count"]), {
            "provider": "test",
            "model": kwargs["story_model"],
            "skeleton_prompt_tokens": 100,
            "skeleton_completion_tokens": 150,
            "skeleton_generation_usd": 0.0005,
            "skeleton_system_prompt": "skeleton system",
            "skeleton_user_payload": {"panel_count": kwargs["panel_count"]},
        }

    def fake_llm_surface(self, **kwargs):
        script = _valid_visual_surface(panel_count=kwargs["panel_count"])
        script["panels"][2]["beat"] = (
            "The practical problem gets slightly more theatrical while the target grammar stays necessary."
        )
        return script, {
            "provider": "test",
            "model": kwargs["story_model"],
            "surface_prompt_tokens": 100,
            "surface_completion_tokens": 200,
            "surface_generation_usd": 0.0005,
            "surface_system_prompt": "surface system",
            "surface_user_payload": {"panel_count": kwargs["panel_count"]},
        }

    monkeypatch.setattr(GraphicNovelStoryGenerator, "_llm_skeleton", fake_llm_skeleton)
    monkeypatch.setattr(GraphicNovelStoryGenerator, "_llm_surface", fake_llm_surface)
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    debug = response.json()["scene"]["script_payload"]["generation_debug"]
    assert debug["status"] == "accepted_with_notes"
    assert "panel_beat_is_pedagogy_or_template" in debug["validation_errors"]


def test_feuilleton_premium_story_timeout_falls_back_to_standard(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr("app.services.graphic_novel._safe_llm", lambda: object())

    def fake_llm_skeleton(self, **kwargs):
        if kwargs["story_model"] == settings.OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL:
            return None
        return _valid_visual_skeleton(panel_count=kwargs["panel_count"]), {
            "provider": "test",
            "model": kwargs["story_model"],
            "skeleton_prompt_tokens": 100,
            "skeleton_completion_tokens": 150,
            "skeleton_generation_usd": 0.0005,
            "skeleton_system_prompt": "skeleton system",
            "skeleton_user_payload": {"panel_count": kwargs["panel_count"]},
        }

    def fake_llm_surface(self, **kwargs):
        return _valid_visual_surface(panel_count=kwargs["panel_count"]), {
            "provider": "test",
            "model": kwargs["story_model"],
            "surface_prompt_tokens": 100,
            "surface_completion_tokens": 200,
            "surface_generation_usd": 0.0005,
            "surface_system_prompt": "surface system",
            "surface_user_payload": {"panel_count": kwargs["panel_count"]},
        }

    monkeypatch.setattr(GraphicNovelStoryGenerator, "_llm_skeleton", fake_llm_skeleton)
    monkeypatch.setattr(GraphicNovelStoryGenerator, "_llm_surface", fake_llm_surface)
    token = _token(client)
    concept = _concept(db_session)

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "preferred_concept_ids": [concept.id], "story_quality": "premium"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    script = response.json()["scene"]["script_payload"]
    assert script["story_model"] == settings.OPENAI_GRAPHIC_NOVEL_SCRIPT_MODEL
    assert script["generation_debug"]["requested_model"] == settings.OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL
    assert script["generation_debug"]["fallback_model_used"] is True


def test_feuilleton_validator_rejects_worksheet_in_comic_costume(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    script = _valid_visual_script(panel_count=4)

    assert generator._validate_script(
        script=script,
        panel_count=4,
        experience_mode="study",
        public_figure_mode="named_context",
    ) == []

    repeated_beat = _valid_visual_script(panel_count=4)
    repeated_beat["panels"][2]["beat"] = "The practical problem gets slightly more theatrical while the target grammar stays necessary."
    assert "panel_beat_is_pedagogy_or_template" in generator._validate_script(
        script=repeated_beat,
        panel_count=4,
        experience_mode="study",
        public_figure_mode="named_context",
    )

    weak_premise = _valid_visual_script(panel_count=4)
    weak_premise["selected_visual_premise"]["mechanic"] = "A cafe scene."
    assert "weak_selected_visual_premise_mechanic" in generator._validate_script(
        script=weak_premise,
        panel_count=4,
        experience_mode="study",
        public_figure_mode="named_context",
    )

    copied_task = _valid_visual_script(panel_count=4)
    copied_task["panels"][1]["overlay_payload"]["caption"]["fr"] = "Si elle appelle, je répondrai tout de suite."
    assert "closed_task_copied_from_caption" in generator._validate_script(
        script=copied_task,
        panel_count=4,
        experience_mode="study",
        public_figure_mode="named_context",
    )


def test_feuilleton_normalization_does_not_backfill_missing_ai_task_text(db_session):
    generator = GraphicNovelStoryGenerator(db_session)
    script = _valid_visual_surface(panel_count=4)
    script["panels"][1]["overlay_payload"]["tasks"][0].pop("instruction")
    script["final_prompt"].pop("prompt_translation")

    normalized = generator._normalize_script(
        script=script,
        source_snapshot={"mode": "test", "source": "Atelier test", "title": "Test source"},
        concepts=[],
        targets=[],
        target_vocabulary=[],
        panel_count=4,
        story_quality="standard",
        humor_style="dry visual satire",
        story_model="test-model",
        experience_mode="study",
        render_mode="panels",
        image_quality="medium",
        public_figure_mode="named_context",
        story_cost=0.0,
    )

    tasks = [
        task
        for panel in normalized["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
    ]
    errors = generator._validate_script(
        script=normalized,
        panel_count=4,
        experience_mode="study",
        public_figure_mode="named_context",
    )

    assert "panel_cloze_future_result" not in {task["id"] for task in tasks}
    assert normalized["final_prompt"]["id"] == ""
    assert "overlay_task_count_mismatch_expected_3" in errors
    assert "final_prompt_missing_required_content" in errors


def _valid_visual_skeleton(panel_count: int = 4) -> dict:
    beats = [
        {
            "panel_index": index,
            "beat": [
                "The umbrella is placed at a tiny official table while everyone waits.",
                "A waiter offers the umbrella a coffee before serving the people.",
                "A reporter measures whether the umbrella blocks the exit politely enough.",
                "The cafe queue accepts the umbrella as the only authority left.",
                "The umbrella starts receiving messages meant for the public office.",
                "Outside, the people have left and the umbrella is still holding office.",
                "A passer-by asks the umbrella for an appointment in the rain.",
                "The empty cafe displays the umbrella's resignation letter without words.",
            ][index - 1],
            "panel_action": [
                "One black umbrella sits alone at a small press table.",
                "A waiter slides a coffee toward the umbrella as if it were a minister.",
                "A reporter checks the doorway blocked by the umbrella's handle.",
                "The cafe queue points to the umbrella before making any decision.",
                "A phone lights up beside the umbrella while people wait for its answer.",
                "The final panel turns outside: people have gone, the umbrella remains in charge.",
                "The umbrella now receives public appointments from strangers in the rain.",
                "The room is empty except for the umbrella and one absurd official envelope.",
            ][index - 1],
            "turn_type": "callback with changed meaning" if index == panel_count else "visual escalation",
            "action_change": "Keep one umbrella as the only repeated prop; change the composition and action.",
        }
        for index in range(1, panel_count + 1)
    ]
    premise = {
        "angle": "Umbrella press office",
        "mechanic": "A familiar announcement gives an ordinary object more authority than the people repeating it.",
        "headline_mechanic": "An official announcement makes a familiar situation behave as if it were urgent again.",
        "anchor_object": "one black umbrella",
        "domain": "a Paris cafe, then the street outside it",
        "why_it_matches_source": "The source mechanic becomes visible because an ordinary object gets more authority than people repeating an announcement.",
        "beat_sequence": beats,
        "score_0_10": 8,
    }
    return {
        "title": "Feuilleton: Le parapluie officiel",
        "brief": "A visual gag about an announcement that gives an umbrella too much authority.",
        "headline_mechanic": premise["headline_mechanic"],
        "visual_premise_candidates": [
            premise,
            {**premise, "angle": "Stamp witness", "anchor_object": "one red stamp"},
            {**premise, "angle": "Poster handshake", "anchor_object": "one campaign poster"},
        ],
        "selected_visual_premise": premise,
        "human_characters": [
            {"name": "Elise", "role": "reporter", "visual_description": "beige coat, notepad, dry expression", "comic_function": "notices the absurd authority"},
            {"name": "Marc", "role": "waiter", "visual_description": "black apron, towel, suspicious politeness", "comic_function": "treats the prop like an official guest"},
        ],
        "prop_bible": [
            {"name": "one black umbrella", "visual_description": "plain black umbrella, never a person", "comic_function": "recurring visual authority"},
        ],
        "twist": "The umbrella becomes the last official presence after everyone else solves the problem.",
        "payoff": "The authority remains, but the people have already left.",
        "source_usage": {"mode": "test", "how_used": "source mechanic became a visual authority joke", "attribution": "Atelier test"},
    }


def _valid_visual_surface(panel_count: int = 4) -> dict:
    prompt = (
        "Draw one square editorial visual-gag comic panel with Penguin Crime paperback-cover mood and photomechanical halftone texture. "
        "Scene visual preamble: an official announcement makes a familiar situation urgent again. "
        "Human continuity: Elise, a reporter with a beige coat; Marc, a waiter with a black apron. "
        "Panel action: one umbrella sits at a press table like the only competent public official. "
        "Penguin Crime paperback-cover mood with photomechanical halftone texture. "
        "Use real public figures only as named topic context outside the image. "
        "Do not draw readable text, captions, speech bubbles, UI, blanks, signs, labels, or answer choices."
    )
    skeleton = _valid_visual_skeleton(panel_count)
    premise = skeleton["selected_visual_premise"]
    panels = []
    task_positions = set(range(2, panel_count + 1))
    task_bank = [
        {
            "id": "panel_cloze_future_result",
            "task_type": "cloze",
            "concept_id": None,
            "label": "Future result",
            "instruction": "Complete the next line after the phone rings.",
            "prompt": "Si elle appelle, je ____ tout de suite.",
            "prompt_translation": "If she calls, I ____ right away.",
            "expected_answer": "répondrai",
            "accepted_answers": ["répondrai", "repondrai"],
            "options": ["réponds", "répondrai", "répondrais"],
            "expected_features": [],
            "placeholder": "Your answer",
            "scene_function": "The next line gives the cafe a concrete consequence after the phone interrupts the argument.",
            "feedback_context": "The si-clause stays present and the result clause carries the future.",
        },
        {
            "id": "panel_choice_imperative_result",
            "task_type": "choice",
            "concept_id": None,
            "label": "Imperative result",
            "instruction": "Choose the instruction that moves everyone outside.",
            "prompt": "The rain starts during the errand.",
            "prompt_translation": "The rain starts during the errand.",
            "expected_answer": "S'il pleut, prends ton manteau.",
            "accepted_answers": ["S'il pleut, prends ton manteau."],
            "options": ["S'il pleut, prends ton manteau.", "S'il pleut, prendras ton manteau."],
            "expected_features": [],
            "placeholder": "Your answer",
            "scene_function": "The line gives a direct instruction so the scene can leave the cafe.",
            "feedback_context": "A direct instruction after si uses the imperative.",
        },
        {
            "id": "panel_short_sentence_condition",
            "task_type": "short_sentence",
            "concept_id": None,
            "label": "Use it in context",
            "instruction": "Add one dry sentence that makes the umbrella's authority worse.",
            "prompt": "Continue the visual gag.",
            "prompt_translation": "Continue the visual gag.",
            "expected_answer": "",
            "accepted_answers": [],
            "options": [],
            "expected_features": ["si", "future_or_imperative_result"],
            "placeholder": "Si..., je...",
            "scene_function": "You add a new condition that pushes the visual gag one beat further.",
            "feedback_context": "The sentence should add a fresh consequence rather than repeat the caption.",
        },
        {
            "id": "panel_cloze_extra",
            "task_type": "cloze",
            "concept_id": None,
            "label": "Another result",
            "instruction": "Complete the next beat.",
            "prompt": "Si le parapluie décide, nous ____.",
            "prompt_translation": "If the umbrella decides, we ____.",
            "expected_answer": "partirons",
            "accepted_answers": ["partirons"],
            "options": ["partons", "partirons"],
            "expected_features": [],
            "placeholder": "Your answer",
            "scene_function": "The line lets the crowd accept the umbrella's ridiculous authority.",
            "feedback_context": "Use future simple for the consequence.",
        },
    ]
    while len(task_bank) < panel_count - 1:
        index = len(task_bank) + 1
        task_bank.append(
            {
                "id": f"panel_extra_{index}",
                "task_type": "choice",
                "concept_id": None,
                "label": "Article in the next beat",
                "instruction": "Choose the French line that could appear next.",
                "prompt": "The umbrella signs the cafe list.",
                "prompt_translation": "The umbrella signs the cafe list.",
                "expected_answer": "L'affiche attend dehors.",
                "accepted_answers": ["L'affiche attend dehors."],
                "options": ["L'affiche attend dehors.", "Les affiches attendent dehors.", "Une affiche attend dehors."],
                "expected_features": [],
                "placeholder": "Your answer",
                "scene_function": "The line adds a new visual beat without copying the caption.",
                "feedback_context": "Choose a valid French article-noun pairing for the singular object.",
            }
        )
    for index in range(1, panel_count + 1):
        beat = premise["beat_sequence"][index - 1]
        caption = {
            "panel_index": index,
            "fr": f"Le parapluie gagnait en autorité, scène {index}.",
            "en": f"The umbrella was gaining authority, scene {index}.",
        }
        bubbles = [
            {
                "speaker": "Camille",
                "fr": f"Encore une consigne pour le parapluie {index}.",
                "en": f"Another instruction for umbrella {index}.",
                "x": 12,
                "y": 12,
                "tone": "deadpan",
            }
        ] if index % 2 == 1 else []
        tasks = [task_bank.pop(0)] if index in task_positions and task_bank else []
        panels.append(
            {
                "panel_index": index,
                "title": f"Authority {index}",
                "beat": beat["beat"],
                "panel_action": beat["panel_action"],
                "image_prompt_note": beat["action_change"],
                "overlay_payload": {"caption": caption, "bubbles": bubbles, "tasks": tasks},
            }
        )
    return {
        "title": "Feuilleton: Le parapluie officiel",
        "brief": "A visual gag about an announcement that gives an umbrella too much authority.",
        "captions": [panel["overlay_payload"]["caption"] for panel in panels],
        "comic_tone": "dry visual satire",
        "dialogue_register": "native-like captions",
        "support_register": "B1 English support",
        "glosses": [
            {"term": "gagner en autorité", "meaning": "to gain authority", "reason": "deadpan caption phrase"},
            {"term": "parapluie", "meaning": "umbrella", "reason": "decisive prop"},
        ],
        "panels": panels,
        "final_prompt": {
            "id": "final_line",
            "task_type": "short_sentence",
            "instruction": "Write one natural French sentence that adds one more consequence to the umbrella gag.",
            "prompt_body": "Add one final French line after everyone has left the cafe.",
            "prompt_translation": "Add one final French line after everyone has left the cafe.",
            "placeholder": "Si...",
            "expected_features": ["si", "future_or_imperative_result"],
            "min_words": 6,
            "max_words": 30,
        },
        "quality_notes": ["visual premise test fixture", "tasks extend the caption"],
        "comedy_validation": {
            "has_setup": True,
            "has_escalation": True,
            "has_reversal": True,
            "has_payoff": True,
            "dialogue_not_flattened": True,
            "grammar_not_driving_every_panel": True,
        },
    }


def _valid_visual_script(panel_count: int = 4) -> dict:
    skeleton = _valid_visual_skeleton(panel_count)
    surface = _valid_visual_surface(panel_count)
    prompt = (
        "Draw one square editorial visual-gag comic panel with Penguin Crime paperback-cover mood and photomechanical halftone texture. "
        "Scene visual preamble: an official announcement makes a familiar situation urgent again. "
        "Human continuity: Elise, a reporter with a beige coat; Marc, a waiter with a black apron. "
        "Panel action: one umbrella holds office after everyone else leaves. "
        "Use real public figures only as named topic context outside the image. "
        "Do not draw readable text, captions, speech bubbles, UI, blanks, signs, labels, or answer choices."
    )
    panels = []
    for panel in surface["panels"]:
        panels.append(
            {
                **panel,
                "visual_gag": panel["panel_action"],
                "prop_focus": skeleton["selected_visual_premise"]["anchor_object"],
                "image_prompt": prompt,
            }
        )
    return {
        **surface,
        **skeleton,
        "story_bible": {
            "premise": skeleton["selected_visual_premise"]["mechanic"],
            "setting": skeleton["selected_visual_premise"]["domain"],
            "conflict": skeleton["headline_mechanic"],
            "news_mechanic": skeleton["headline_mechanic"],
            "twist": skeleton["twist"],
            "payoff": skeleton["payoff"],
            "grammar_integration": "Exercises add the next useful line after dialogue creates a need.",
        },
        "character_bible": skeleton["human_characters"],
        "prop_bible": skeleton["prop_bible"],
        "panels": panels,
        "story_quality_score": 8,
        "comedy_validation": {
            "has_setup": True,
            "has_escalation": True,
            "has_reversal": True,
            "has_payoff": True,
            "dialogue_not_flattened": True,
            "grammar_not_driving_every_panel": True,
        },
    }
