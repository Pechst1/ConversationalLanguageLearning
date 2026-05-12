"""Regression tests for Graphic Novel / Feuilleton mode."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.atelier import AtelierScheduler
from app.services.graphic_novel import GraphicNovelCorrectionService, GraphicNovelStoryGenerator


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
    db_session.add(erratum)
    db_session.commit()

    response = client.post(
        "/api/v1/graphic-novel/scenes",
        json={
            "cadence": "ad_hoc",
            "preferred_errata_ids": [str(erratum.id)],
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
    assert all("no readable text" in panel["image_prompt"].lower() for panel in scene["panels"])
    assert all("story premise" not in panel["image_prompt"].lower() for panel in scene["panels"])
    assert all("news/context inspiration" not in panel["image_prompt"].lower() for panel in scene["panels"])
    assert all("human continuity" in panel["image_prompt"].lower() for panel in scene["panels"])
    assert scene["panels"][0]["overlay_payload"]["bubbles"][0]["fr"].startswith("Encore une consigne")
    assert "The meeting" not in {panel["title"] for panel in scene["panels"]}


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
