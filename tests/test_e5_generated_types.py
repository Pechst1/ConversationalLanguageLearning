"""E-5: OpenAPI exposes actual public fields and sparse wire shapes stay intact."""

from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.endpoints.story_engine import public_scene
from app.main import create_app
from app.schemas.daily_journey import LineAudioResult, RecallOption
from app.schemas.story_projection import EpisodeAudioManifestRead, StoryEpisodeRead
from app.services.episode_audio import EpisodeAudioResult


def test_openapi_documents_the_real_public_models():
    schema = create_app().openapi()
    models = schema["components"]["schemas"]
    for name, field in (
        ("RecallPrompt", "task_type"), ("RecallOption", "text_fr"),
        ("RuleCardPayload", "rule"), ("LineAudioResult", "clip_id"),
        ("JourneyErrorDetail", "code"), ("VocabularyWordRead", "translation"),
    ):
        assert field in models[name]["properties"]
    assert "steps" in models["JourneySnapshot"]["required"]
    assert "audio_url" not in models["RecallPrompt"]["required"]
    assert "side" not in models["RecallOption"]["required"]
    for suffix, method, model in (
        ("/episodes", "get", "StoryEpisodePageRead"),
        ("/episodes/{scene_id}", "get", "StoryEpisodeRead"),
        ("/episodes/{scene_id}/position", "put", "StoryPositionRead"),
        ("/episodes/{scene_id}/audio", "get", "EpisodeAudioManifestRead"),
        ("/episodes/{scene_id}/audio", "post", "EpisodeAudioManifestRead"),
    ):
        response = schema["paths"]["/api/v1/story-engine" + suffix][method]["responses"]["200"]
        assert response["content"]["application/json"]["schema"] == {"$ref": f"#/components/schemas/{model}"}
    assert create_app().openapi() == schema


def test_schema_metadata_preserves_sparse_serialization():
    assert LineAudioResult(status="disabled").model_dump() == {"status": "disabled"}
    assert RecallOption(id="a", text_fr="Bonjour").model_dump() == {"id": "a", "text_fr": "Bonjour"}


def test_reader_dto_accepts_the_actual_protected_projection():
    panel = SimpleNamespace(
        id=uuid4(), panel_index=0, image_url=None, generation_metadata={},
        overlay_payload={"narration_fr": "Le café ouvre.", "dialogue": [{
            "character_id": "romy", "text_fr": "Tu viens ?",
            "grammar_marks": [{"unit_id": 12, "start": 0, "end": 2}],
        }]},
    )
    scene = SimpleNamespace(
        id=uuid4(), serial_thread_id=uuid4(), title="Au café", status="completed", panels=[panel],
        source_snapshot={"chapter": {"id": "c1", "title_fr": "Le café", "shape": "bottle",
                                     "letter_beat": None, "finale": False, "interlude": False}},
        recap_payload={"resolution_fr": "À demain !"},
        script_payload={"grammar_focus": {"unit_id": 12, "title_fr": "Tu", "woven": True}},
    )
    wire = public_scene(scene, {"romy": "Romy"})
    dto = StoryEpisodeRead.model_validate(wire)
    assert dto.panels[0].dialogue[0].character_name == "Romy"
    assert dto.grammar_focus.unit_id == "12"
    assert dto.journey_id is None


def test_audio_dto_accepts_ready_and_disabled_actual_manifests():
    clip = {"id": "c", "line_key": "l", "ordinal": 0, "character_id": "romy",
            "voice": "coral", "content_type": "audio/mpeg", "char_count": 10, "text_fr": "Tu viens ?"}
    for status, clips in (("ready", [clip]), ("disabled", [])):
        wire = EpisodeAudioResult(status=status, clips=clips).as_payload()
        assert EpisodeAudioManifestRead.model_validate(wire).model_dump() == wire
