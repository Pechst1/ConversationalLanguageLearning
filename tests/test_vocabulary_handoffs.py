"""Vocabulary handoff regressions across Atelier, Missions, and Feuilleton."""
from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.models.grammar import GrammarConcept
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier import AtelierScheduler
from app.services.graphic_novel import GraphicNovelStoryGenerator


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    password = "handoff-secure"
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
        .filter(GrammarConcept.external_id == "FR_A2_NEG_001", GrammarConcept.active.is_(True))
        .one()
    )


def _vocabulary_word(db_session, word: str = "enchainer") -> VocabularyWord:
    vocab = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word,
        frequency_rank=72,
        english_translation="to follow up",
        example_sentence=f"Je vais {word} avec une solution simple.",
        example_translation="I will follow up with a simple solution.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(vocab)
    db_session.commit()
    return vocab


def _patch_feuilleton_script(monkeypatch) -> None:
    def fake_build_script(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        target_vocabulary = kwargs.get("target_vocabulary") or []
        target_word = target_vocabulary[0] if target_vocabulary else {}
        panels: list[dict[str, Any]] = []
        for index in range(1, int(kwargs["panel_count"]) + 1):
            tasks: list[dict[str, Any]] = []
            if index == 2 and target_word:
                tasks.append(
                    {
                        "id": "handoff_target_vocabulary",
                        "task_type": "short_sentence",
                        "concept_id": kwargs["concepts"][0].id if kwargs.get("concepts") else None,
                        "label": "Vocabulary in context",
                        "instruction": f"Write one French sentence with {target_word['word']}.",
                        "prompt": f"Use {target_word['word']} in a new line that fits the scene.",
                        "expected_answer": "",
                        "accepted_answers": [],
                        "options": [],
                        "expected_features": [f"include {target_word['word']}"],
                        "placeholder": f"Phrase avec {target_word['word']}...",
                        "vocabulary_task": True,
                        "production_goal": "use_target_vocabulary_in_context",
                        "target_word_id": target_word["word_id"],
                        "target_word": target_word["word"],
                        "target_translation": target_word.get("translation"),
                        "example_sentence": target_word.get("example_sentence"),
                        "example_translation": target_word.get("example_translation"),
                    }
                )
            panels.append(
                {
                    "panel_index": index,
                    "title": f"Handoff panel {index}",
                    "beat": "A practical message becomes easier when the carried vocabulary remains visible.",
                    "image_prompt": "Draw one square editorial comic panel with no readable text.",
                    "overlay_payload": {
                        "caption": {"fr": "La scene garde le meme mot cible."},
                        "bubbles": [],
                        "tasks": tasks,
                    },
                }
            )
        return {
            "title": "Feuilleton handoff",
            "brief": "A compact test story for vocabulary handoffs.",
            "panel_count": kwargs["panel_count"],
            "story_quality": kwargs["story_quality"],
            "humor_style": kwargs["humor_style"],
            "experience_mode": kwargs["experience_mode"],
            "render_mode": kwargs["render_mode"],
            "image_quality": kwargs["image_quality"],
            "target_vocabulary": target_vocabulary,
            "selected_visual_premise": {"angle": "handoff", "mechanic": "the target word stays in context"},
            "visual_premise_candidates": [],
            "generation_debug": {"source": "test_stub"},
            "panels": panels,
        }

    monkeypatch.setattr(GraphicNovelStoryGenerator, "build_script", fake_build_script)


def test_vocabulary_handoff_round_trips_atelier_mission_and_feuilleton(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    _patch_feuilleton_script(monkeypatch)
    token = _token(client)
    concept = _concept(db_session)
    word = _vocabulary_word(db_session)

    atelier = client.post(
        "/api/v1/atelier/sessions",
        json={
            "preferred_concept_id": concept.id,
            "preferred_vocabulary_ids": [word.id],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert atelier.status_code == 201
    atelier_session = atelier.json()
    session_id = atelier_session["session_id"]
    assert atelier_session["concepts"][0]["id"] == concept.id
    assert atelier_session["target_vocabulary_ids"][0] == word.id
    assert atelier_session["target_vocabulary"][0]["word"] == word.word
    assert atelier_session["quote"]["target_vocabulary_ids"][0] == word.id

    fetched_session = client.get(
        f"/api/v1/atelier/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert fetched_session.status_code == 200
    assert fetched_session.json()["target_vocabulary_ids"][0] == word.id
    assert fetched_session.json()["target_vocabulary"][0]["example_sentence"] == word.example_sentence

    mission_create = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "atelier_session_id": session_id,
            "preferred_vocabulary_ids": [word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert mission_create.status_code == 200
    mission = mission_create.json()["mission"]
    mission_id = mission["id"]
    assert mission["atelier_session_id"] == session_id
    assert concept.id in mission["selected_concept_ids"]
    assert mission["target_vocabulary_ids"][0] == word.id
    assert mission["target_vocabulary"][0]["word"] == word.word
    assert mission["target_vocabulary"][0]["bucket"] == "preferred"
    assert mission["prompt_payload"]["target_vocabulary"][0]["word_id"] == word.id
    assert mission["prompt_payload"]["messenger"]["vocabulary_focus"][0]["word_id"] == word.id

    fetched_mission = client.get(
        f"/api/v1/missions/{mission_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert fetched_mission.status_code == 200
    assert fetched_mission.json()["mission"]["target_vocabulary_ids"][0] == word.id
    assert fetched_mission.json()["mission"]["target_vocabulary"][0]["word"] == word.word

    feuilleton_create = client.post(
        "/api/v1/graphic-novel/scenes",
        json={"cadence": "ad_hoc", "mission_id": mission_id, "use_news": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert feuilleton_create.status_code == 200
    scene = feuilleton_create.json()["scene"]
    assert scene["mission_id"] == mission_id
    assert scene["selected_concept_ids"][0] in mission["selected_concept_ids"]
    assert scene["target_vocabulary_ids"][0] == word.id
    assert scene["target_vocabulary"][0]["word"] == word.word
    assert scene["target_vocabulary"][0]["scheduler"] == "mission"
    assert scene["script_payload"]["target_vocabulary"][0]["word_id"] == word.id
    vocabulary_tasks = [
        task
        for panel in scene["panels"]
        for task in panel["overlay_payload"].get("tasks", [])
        if task.get("vocabulary_task")
    ]
    assert vocabulary_tasks[0]["target_word_id"] == word.id
    assert vocabulary_tasks[0]["production_goal"] == "use_target_vocabulary_in_context"

    fetched_scene = client.get(
        f"/api/v1/graphic-novel/scenes/{scene['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert fetched_scene.status_code == 200
    assert fetched_scene.json()["scene"]["target_vocabulary_ids"][0] == word.id
    assert fetched_scene.json()["scene"]["target_vocabulary"][0]["example_sentence"] == word.example_sentence


def test_feuilleton_explicit_vocabulary_query_overrides_mission_vocabulary(
    client: TestClient,
    db_session,
    monkeypatch,
) -> None:
    _patch_feuilleton_script(monkeypatch)
    token = _token(client)
    mission_word = _vocabulary_word(db_session, word="constater")
    explicit_word = _vocabulary_word(db_session, word="relancer")

    mission_create = client.post(
        "/api/v1/missions/",
        json={
            "mission_type": "message",
            "cadence": "ad_hoc",
            "preferred_vocabulary_ids": [mission_word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    mission_id = mission_create.json()["mission"]["id"]

    scene_create = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "mission_id": mission_id,
            "target_vocabulary_ids": [explicit_word.id],
            "use_news": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert scene_create.status_code == 200
    scene = scene_create.json()["scene"]
    assert scene["mission_id"] == mission_id
    assert scene["target_vocabulary_ids"][0] == explicit_word.id
    assert scene["target_vocabulary"][0]["word"] == explicit_word.word
    assert scene["target_vocabulary"][0]["scheduler"] == "explicit"
    assert mission_word.id not in scene["target_vocabulary_ids"][:1]
