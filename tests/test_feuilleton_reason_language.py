"""WP-82 — the Feuilleton's «why» note follows the one-language rule.

A panel task's ``recommendation_reason`` is the app's own words: the learner's
language up to A2, French from B1, with all three versions served so the
client can re-apply the rule with the level it knows best.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.user import User
from app.services.graphic_novel import serialize_scene


def _scene(native_language: str, level: str) -> GraphicNovelScene:
    user = User(id=uuid.uuid4(), email="reader@example.com", native_language=native_language, cefr_estimate=level)
    scene = GraphicNovelScene(
        id=uuid.uuid4(),
        user_id=user.id,
        status="in_progress",
        script_payload={"final_prompt": {"id": "final", "prompt": "Répondez à Lila."}},
    )
    scene.user = user
    scene.panels = [
        GraphicNovelPanel(
            id=uuid.uuid4(),
            scene_id=scene.id,
            panel_index=1,
            overlay_payload={"tasks": [{"id": "t1", "prompt": "Complétez.", "target_vocabulary_ids": [3]}]},
        )
    ]
    return scene


@pytest.mark.parametrize(
    ("native", "level", "expected"),
    [
        ("en", "A1", "Chosen to reuse one of today’s words in the story."),
        ("de", "A2", "Ausgewählt, um ein Wort von heute in der Geschichte wiederzuverwenden."),
        ("de", "B1", "Choisie pour réemployer un mot du jour dans l’histoire."),
    ],
)
def test_panel_reason_is_in_the_chrome_language(native: str, level: str, expected: str) -> None:
    payload = serialize_scene(_scene(native, level))
    task = payload["panels"][0]["overlay_payload"]["tasks"][0]
    reason = task["recommendation_reason"]
    assert reason["text"] == expected
    assert set(reason["text_by_language"]) == {"fr", "en", "de"}
    # the task itself is content and is untouched
    assert task["prompt"] == "Complétez."
    final = payload["script_payload"]["final_prompt"]["recommendation_reason"]
    assert final["text"] == final["text_by_language"]["fr" if level == "B1" else native]


def test_a_scene_without_a_user_keeps_french() -> None:
    scene = _scene("en", "A1")
    scene.user = None
    reason = serialize_scene(scene)["panels"][0]["overlay_payload"]["tasks"][0]["recommendation_reason"]
    assert reason["text"].startswith("Choisie")
