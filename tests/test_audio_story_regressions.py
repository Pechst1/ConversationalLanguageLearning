"""Regression tests for audio-session isolation and story choices."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import Text, select

from app.api.v1.endpoints import audio, stories
from app.api.v1.endpoints.audio_session import (
    AudioSessionEndRequest,
    AudioSessionMessageRequest,
    end_audio_session,
    respond_to_audio,
)
from app.core.error_detection.rules import DetectedError
from app.db.models.pilot_event import PilotEvent
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.schemas.story import StoryInputRequest
from app.services import llm_service as llm_service_module
from app.services.audio_session_service import (
    AudioSessionNotFoundError,
    AudioSessionService,
)
from app.services.llm_service import OpenAIProvider


class StubLLMService:
    def __init__(self) -> None:
        self.messages: list[dict] | None = None

    def generate_chat_completion(self, *, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.messages = messages
        return SimpleNamespace(content="Très bien, continuons.")


class StubErrorDetector:
    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        pass

    def analyze(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return SimpleNamespace(errors=[])


def _user(db_session, email: str) -> User:  # type: ignore[no-untyped-def]
    user = User(
        email=email,
        hashed_password="not-used",
        target_language="fr",
        proficiency_level="A2",
        total_xp=0,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_audio_response_is_scoped_to_the_authenticated_owner(db_session):
    owner = _user(db_session, "audio-owner@example.com")
    attacker = _user(db_session, "audio-attacker@example.com")
    session = LearningSession(
        user_id=owner.id,
        planned_duration_minutes=5,
        status="in_progress",
    )
    db_session.add(session)
    db_session.commit()

    service = AudioSessionService(db_session, StubLLMService())
    with pytest.raises(AudioSessionNotFoundError):
        asyncio.run(
            service.process_user_response(
                session_id=session.id,
                user_id=attacker.id,
                user_text="Bonjour",
                conversation_history=[],
            )
        )


def test_audio_system_prompt_column_is_unbounded_text():
    assert isinstance(ConversationMessage.__table__.c.generation_prompt.type, Text)


def test_audio_session_rejects_malformed_ids_before_processing():
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            respond_to_audio(
                request=AudioSessionMessageRequest(
                    session_id="not-a-uuid",
                    user_text="Bonjour",
                ),
                db=SimpleNamespace(),
                llm_service=SimpleNamespace(),
                current_user=SimpleNamespace(id=uuid.uuid4()),
            )
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Invalid session_id format"


def test_audio_response_uses_stored_prompt_and_persists_progress(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.core.error_detection.detector.ErrorDetector",
        StubErrorDetector,
    )
    user = _user(db_session, "audio-progress@example.com")
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=5,
        status="in_progress",
        xp_earned=0,
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ConversationMessage(
            session_id=session.id,
            sender="ai",
            content="Bonjour !",
            sequence_number=1,
            generation_prompt="trusted server prompt",
        )
    )
    db_session.commit()

    llm = StubLLMService()
    result = asyncio.run(
        AudioSessionService(db_session, llm).process_user_response(
            session_id=session.id,
            user_id=user.id,
            user_text="Je vais bien.",
            conversation_history=[
                {"role": "system", "content": "untrusted client prompt"},
                {"role": "assistant", "content": "Comment ça va ?"},
            ],
        )
    )

    db_session.refresh(session)
    db_session.refresh(user)
    messages = (
        db_session.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session.id)
        .order_by(ConversationMessage.sequence_number)
        .all()
    )

    assert llm.messages is not None
    assert llm.messages[0] == {
        "role": "system",
        "content": "trusted server prompt",
    }
    assert [message["role"] for message in llm.messages].count("system") == 1
    assert result["xp_awarded"] == 10
    assert session.xp_earned == 10
    assert session.correct_responses == 1
    assert user.total_xp == 10
    assert [(message.sender, message.sequence_number) for message in messages] == [
        ("ai", 1),
        ("user", 2),
        ("ai", 3),
    ]


def test_audio_errors_keep_full_xp_and_mint_courage_then_recovery(
    db_session,
    monkeypatch,
):
    class ErrorDetectorWithMistake:
        def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def analyze(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                errors=[
                    DetectedError(
                        code="verb_conjugation",
                        message="Conjuguez le verbe.",
                        span="je aller",
                        suggestion="je vais",
                        category="grammar",
                        severity="medium",
                        confidence=0.95,
                    )
                ]
            )

    monkeypatch.setattr(
        "app.core.error_detection.detector.ErrorDetector",
        ErrorDetectorWithMistake,
    )
    monkeypatch.setattr(
        "app.services.audio_session_service.ErrorMemoryService.record_detected_error",
        lambda *args, **kwargs: {"action": "created"},
    )
    user = _user(db_session, "audio-courage@example.com")
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=5,
        status="in_progress",
        xp_earned=0,
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ConversationMessage(
            session_id=session.id,
            sender="ai",
            content="Bonjour !",
            sequence_number=1,
            generation_prompt="trusted server prompt",
        )
    )
    db_session.commit()
    service = AudioSessionService(db_session, StubLLMService())

    courageous = asyncio.run(
        service.process_user_response(
            session_id=session.id,
            user_id=user.id,
            user_text="Je aller au marché.",
            conversation_history=[],
        )
    )

    assert courageous["xp_awarded"] == 10
    assert courageous["minted_collectibles"][0]["metadata"]["effort"] == "courage"

    monkeypatch.setattr(
        "app.core.error_detection.detector.ErrorDetector",
        StubErrorDetector,
    )
    recovered = asyncio.run(
        service.process_user_response(
            session_id=session.id,
            user_id=user.id,
            user_text="Je vais au marché.",
            conversation_history=[],
        )
    )

    db_session.refresh(user)
    assert recovered["xp_awarded"] == 10
    assert recovered["minted_collectibles"][0]["metadata"]["effort"] == "recovery"
    assert user.total_xp == 20


def test_audio_end_returns_persisted_summary(db_session):
    user = _user(db_session, "audio-summary@example.com")
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=5,
        status="in_progress",
        started_at=datetime.now(UTC) - timedelta(seconds=65),
        xp_earned=17,
        incorrect_responses=2,
    )
    db_session.add(session)
    db_session.flush()
    db_session.add_all(
        [
            ConversationMessage(
                session_id=session.id,
                sender="user",
                content="Je retrouve enfin Romy.",
                words_used=["enfin", "retrouver"],
                sequence_number=1,
            ),
            ConversationMessage(
                session_id=session.id,
                sender="ai",
                content="Elle vous attend.",
                sequence_number=2,
            ),
        ]
    )
    db_session.commit()

    response = asyncio.run(
        end_audio_session(
            request=AudioSessionEndRequest(session_id=str(session.id)),
            db=db_session,
            current_user=user,
        )
    )

    db_session.refresh(session)
    assert response.total_xp == 17
    assert response.errors_practiced == 2
    assert response.duration_seconds >= 65
    assert response.turns == 1
    assert response.produced_words == 4
    assert response.due_words_reused == ["enfin", "retrouver"]
    assert session.status == "completed"
    assert session.completed_at is not None
    assert session.actual_duration_minutes >= 1


def test_audio_end_is_idempotent_and_files_the_studio_once(db_session):
    """Classing the same call twice must replay the recap, not re-file it."""
    user = _user(db_session, "audio-idempotent@example.com")
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=5,
        status="in_progress",
        started_at=datetime.now(UTC) - timedelta(seconds=30),
        xp_earned=20,
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        ConversationMessage(
            session_id=session.id,
            sender="user",
            content="Bonjour Romy, ça va bien.",
            sequence_number=1,
        )
    )
    db_session.commit()

    request = AudioSessionEndRequest(session_id=str(session.id))
    first = asyncio.run(end_audio_session(request=request, db=db_session, current_user=user))
    second = asyncio.run(end_audio_session(request=request, db=db_session, current_user=user))

    completed = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.entity_id == str(session.id),
            PilotEvent.event_type == "plan_completed",
        )
    ).all()

    # One séance, one plan_completed: La Une counts the studio done exactly once.
    assert len(completed) == 1
    # The filed duration is frozen at completion instead of growing per request.
    assert second.duration_seconds == first.duration_seconds
    assert second.turns == first.turns == 1
    # Nothing new is written into the serial memory on the replay.
    assert second.cast_memory is None


def test_audio_turn_ignores_transcription_artifacts_and_duplicate_repairs():
    """Whisper owns the commas; the learner is only charged for spoken mistakes."""
    keep = AudioSessionService._is_spoken_mistake

    assert keep("grammar", "verb_tenses", "high") is True
    assert keep("grammar", "gender_agreement", "medium") is True
    assert keep("punctuation", "punctuation", "low") is False
    assert keep("style", "capitalization", "medium") is False
    assert keep("style", "other", "low") is False

    # The detector answers with alternatives and German glosses; only the repair
    # reaches the recap, and a "repair" that restates the learner is dropped.
    primary = AudioSessionService._primary_suggestion
    assert primary("allée (wenn Sprecherin weiblich) oder allé") == "allée"
    assert primary("un exemplaire du journal / un journal") == "un exemplaire du journal"
    assert primary("je suis allé(s)") == "je suis allé(s)"

    real = AudioSessionService._is_real_correction
    # Punctuation-only and case-only "repairs" are inaudible, so they are not repairs.
    assert real("Bonjour,", "Bonjour") is False
    assert real("mon ami", "mon ami") is False
    # Accents and elisions stay meaningful.
    assert real("je allais", "j’allais") is True
    assert real("marche", "marché") is True
    assert real("allée", primary("allée (wenn Sprecherin weiblich) oder allé")) is False


def test_audio_upload_limit_is_enforced_before_transcription():
    class OversizedUpload:
        content_type = "audio/webm"

        async def read(self, size: int) -> bytes:
            return b"x" * size

    class FailIfCalled:
        def transcribe_audio(self, content):  # type: ignore[no-untyped-def]
            raise AssertionError("oversized audio must not reach the provider")

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            audio.transcribe_audio(
                file=OversizedUpload(),
                llm_service=FailIfCalled(),
                current_user=SimpleNamespace(id=uuid.uuid4()),
            )
        )

    assert error.value.status_code == 413
    assert error.value.detail == "Audio file exceeds the 25 MB limit"


def test_audio_endpoint_preserves_iphone_recording_metadata():
    class IPhoneUpload:
        content_type = "audio/mp4;codecs=mp4a.40.2"
        filename = "recording.mp4"

        async def read(self, size: int) -> bytes:
            assert size == audio.MAX_AUDIO_UPLOAD_BYTES + 1
            return b"iphone-audio"

    class RecordingTranscriber:
        def __init__(self) -> None:
            self.call = None

        def transcribe_audio(self, content, **kwargs):  # type: ignore[no-untyped-def]
            self.call = (content, kwargs)
            return "bonjour"

    transcriber = RecordingTranscriber()
    response = asyncio.run(
        audio.transcribe_audio(
            file=IPhoneUpload(),
            llm_service=transcriber,
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )
    )

    assert response == {"text": "bonjour"}
    assert transcriber.call == (
        b"iphone-audio",
        {
            "filename": "recording.mp4",
            "content_type": "audio/mp4;codecs=mp4a.40.2",
        },
    )


def test_openai_transcription_uses_safe_mp4_multipart_metadata(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"text": "bonjour"}

    class FakeClient:
        def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):  # type: ignore[no-untyped-def]
            return None

        def post(self, path, **kwargs):  # type: ignore[no-untyped-def]
            captured["post"] = (path, kwargs)
            return FakeResponse()

    monkeypatch.setattr(llm_service_module.httpx, "Client", FakeClient)
    provider = OpenAIProvider(api_key="test-key", model="gpt-5-mini")

    result = provider.transcribe_audio(
        b"iphone-audio",
        filename="../../recording.webm",
        content_type="audio/mp4; codecs=mp4a.40.2",
    )

    assert result == "bonjour"
    path, request = captured["post"]
    assert path == "/audio/transcriptions"
    assert request["files"] == {"file": ("audio.mp4", b"iphone-audio", "audio/mp4")}


def test_tts_endpoint_does_not_expose_provider_errors():
    class FailingTTS:
        def text_to_speech(self, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("secret provider credential")

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            audio.text_to_speech(
                request=audio.TTSRequest(text="Bonjour"),
                llm_service=FailingTTS(),
                current_user=SimpleNamespace(id=uuid.uuid4()),
            )
        )

    assert error.value.status_code == 500
    assert error.value.detail == "Text-to-speech generation failed"
    assert "credential" not in error.value.detail


def test_story_choice_awards_xp_without_running_error_detection(monkeypatch):
    npc = SimpleNamespace(id="guide", name="Le guide")
    scene = SimpleNamespace(
        id="scene-1",
        location=None,
        transition_rules=[],
        player_interaction={
            "options": [
                {
                    "id": "choice-1",
                    "effects": [],
                    "response": {"narration": "Vous prenez le passage de gauche."},
                }
            ]
        },
    )
    context = SimpleNamespace(
        scene=scene,
        chapter=SimpleNamespace(id="chapter-1", title="Le passage"),
        narration="Deux passages s'ouvrent devant vous.",
        objectives=[],
        npcs=[SimpleNamespace(npc=npc)],
    )

    class StubStoryService:
        def __init__(self, db) -> None:  # type: ignore[no-untyped-def]
            pass

        def get_current_scene(self, user, story_id):  # type: ignore[no-untyped-def]
            return context

        def get_story_progress(self, user, story_id):  # type: ignore[no-untyped-def]
            return SimpleNamespace(story_flags={})

        def set_story_flag(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        def advance_scene(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return None

    class StubNPCService:
        def __init__(self, db) -> None:  # type: ignore[no-untyped-def]
            pass

        def get_npc(self, npc_id):  # type: ignore[no-untyped-def]
            return npc

        def get_or_create_relationship(self, user, npc_id):  # type: ignore[no-untyped-def]
            return SimpleNamespace(level=1)

        def add_memory(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

    class StubDB:
        def commit(self) -> None:
            pass

    class StubUser:
        id = uuid.uuid4()
        proficiency_level = "A2"
        total_xp = 0

        def mark_activity(self) -> None:
            pass

    monkeypatch.setattr(stories, "StoryService", StubStoryService)
    monkeypatch.setattr(stories, "NPCService", StubNPCService)
    monkeypatch.setattr(
        "app.services.llm_service.LLMService",
        lambda: SimpleNamespace(),
    )

    response = asyncio.run(
        stories.process_story_input(
            story_id="story-1",
            request=StoryInputRequest(content="", choice_id="choice-1"),
            db=StubDB(),
            current_user=StubUser(),
        )
    )

    assert response.xp_earned == 6
    assert response.errors_detected == []
    assert response.npc_response is not None
    assert response.npc_response.content == "Vous prenez le passage de gauche."


def test_story_errors_never_reduce_conversation_xp():
    clean = stories._calculate_story_xp(
        content="Je réponds avec une phrase assez longue pour prendre un vrai risque.",
        error_count=0,
        has_story_progress=False,
    )
    adventurous = stories._calculate_story_xp(
        content="Je réponds avec une phrase assez longue pour prendre un vrai risque.",
        error_count=4,
        has_story_progress=False,
    )

    assert adventurous["total"] == 15
    assert clean["total"] > adventurous["total"]
    assert all(item["amount"] >= 0 for item in adventurous["breakdown"])
    assert all(item["reason"] != "Fehler" for item in adventurous["breakdown"])
