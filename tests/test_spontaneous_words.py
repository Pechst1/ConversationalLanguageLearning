import spacy
from uuid import uuid4

from app.core.conversation.generator import ConversationPlan, GeneratedTurn
from app.core.error_detection import ErrorDetectionResult
from app.core.error_detection.rules import DetectedError
from app.db.models import User, VocabularyWord
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.session import WordInteraction
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService
from app.services.session_service import SessionService


class StubLLMService:
    def generate_chat_completion(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResult(
            provider="stub",
            model="stub-model",
            content="Bonjour !",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0.0,
            raw_response={},
        )


class StubConversationGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate_turn_with_context(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        plan = ConversationPlan(queue_items=tuple(), review_targets=[], new_targets=[])
        return GeneratedTurn(
            text="Continuons à parler !",
            plan=plan,
            llm_result=StubLLMService().generate_chat_completion([]),
        )


class StubErrorDetector:
    def __init__(self, errors=None) -> None:
        self._errors = errors or []

    def analyze(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return ErrorDetectionResult(errors=list(self._errors), summary="stub")


def make_service(db_session, error_detector):
    progress_service = ProgressService(db_session)
    generator = StubConversationGenerator()
    service = SessionService(
        db_session,
        progress_service=progress_service,
        conversation_generator=generator,
        error_detector=error_detector,
        llm_service=StubLLMService(),
        nlp=spacy.blank("fr"),
    )
    return service


def create_user_and_word(db_session):
    user = User(
        email=f"spontaneous+{uuid4().hex}@example.com",
        hashed_password="not-used",
        native_language="en",
        target_language="fr",
    )
    db_session.add(user)
    db_session.flush()

    suffix = uuid4().hex[:6]
    word_text = f"parapluie{suffix}"
    vocab = VocabularyWord(
        language="fr",
        word=word_text,
        normalized_word=word_text,
        english_translation="umbrella",
        frequency_rank=500,
    )
    db_session.add(vocab)
    db_session.commit()
    return user, vocab


def test_unknown_word_detection_creates_progress(db_session):
    user, vocab = create_user_and_word(db_session)
    service = make_service(db_session, StubErrorDetector())
    session_result = service.create_session(user=user, planned_duration_minutes=15, generate_greeting=False)
    session = session_result.session

    content = f"J'aime mon {vocab.word} bleu."
    result = service.process_user_message(session=session, user=user, content=content)

    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == vocab.id)
        .one()
    )
    assert progress.reps >= 1

    review_log = (
        db_session.query(ReviewLog)
        .filter(ReviewLog.progress_id == progress.id)
        .order_by(ReviewLog.review_date.desc())
        .first()
    )
    assert review_log is not None
    assert review_log.rating == 3

    interaction = (
        db_session.query(WordInteraction)
        .filter(WordInteraction.session_id == session.id, WordInteraction.interaction_type == "spontaneous_use")
        .one()
    )
    assert interaction.word_id == vocab.id
    assert result.xp_awarded >= service.xp_config.base_message


def test_unknown_word_difficulty_assignment_with_errors(db_session):
    user, vocab = create_user_and_word(db_session)
    error = DetectedError(
        code="grammar",
        message="Erreur",
        span=f"mon {vocab.word}",
        suggestion=f"mon {vocab.word}",
        category="grammar",
        severity="high",
        confidence=0.8,
    )
    service = make_service(db_session, StubErrorDetector(errors=[error]))
    session = service.create_session(user=user, planned_duration_minutes=10, generate_greeting=False).session

    content = f"Mon {vocab.word} est cassé."
    service.process_user_message(session=session, user=user, content=content)

    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == vocab.id)
        .one()
    )
    review_log = (
        db_session.query(ReviewLog)
        .filter(ReviewLog.progress_id == progress.id)
        .order_by(ReviewLog.review_date.desc())
        .first()
    )
    assert review_log is not None
    assert review_log.rating == 0

    interaction = (
        db_session.query(WordInteraction)
        .filter(WordInteraction.session_id == session.id, WordInteraction.interaction_type == "spontaneous_use")
        .one()
    )
    assert interaction.word_id == vocab.id
