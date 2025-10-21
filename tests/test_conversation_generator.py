"""Tests for the conversation generator module."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.conversation.generator import (
    ConversationGenerator,
    ConversationHistoryMessage,
    iter_target_vocabulary,
)
from app.db.models import User, VocabularyWord
from app.db.models.progress import UserVocabularyProgress
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService


class DummyLLMService:
    """Record invocations and return a canned response."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"messages": list(messages), "kwargs": kwargs})
        return LLMResult(
            provider="stub",
            model="stub-model",
            content="Réponse tutor",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            cost=0.0,
            raw_response={},
        )


@pytest.fixture()
def seeded_user(db_session):
    user = User(
        email=f"conversation+{uuid4().hex}@example.com",
        hashed_password="not-used",
        native_language="en",
        target_language="fr",
        proficiency_level="B1",
    )
    db_session.add(user)
    db_session.flush()

    words: list[VocabularyWord] = []
    for index in range(6):
        word = VocabularyWord(
            language="fr",
            word=f"mot{index}",
            normalized_word=f"mot{index}",
            english_translation=f"word{index}",
            frequency_rank=index + 1,
        )
        db_session.add(word)
        words.append(word)
    db_session.flush()

    for index in range(3):
        progress = UserVocabularyProgress(
            user_id=user.id,
            word_id=words[index].id,
            due_date=date.today() - timedelta(days=1),
            state="learning",
        )
        db_session.add(progress)

    db_session.commit()
    return user, words


def test_generator_prioritizes_due_words(db_session, seeded_user):
    user, words = seeded_user
    llm = DummyLLMService()
    generator = ConversationGenerator(
        progress_service=ProgressService(db_session),
        llm_service=llm,
        target_limit=6,
        review_ratio=0.6,
    )

    history = [ConversationHistoryMessage(role="user", content="Bonjour, je veux pratiquer.")]
    turn = generator.generate_turn(
        user=user,
        learner_level="B1",
        style="casual",
        history=history,
    )

    review_surfaces = {target.surface for target in turn.plan.review_targets}
    new_surfaces = {target.surface for target in turn.plan.new_targets}

    assert review_surfaces == {words[i].word for i in range(3)}
    assert len(new_surfaces) == 3
    assert llm.calls, "LLM should have been invoked"
    call = llm.calls[0]
    assert str(call["kwargs"]["system_prompt"]).startswith("You are")
    first_message = call["messages"][0]
    assert first_message["role"] == "system"
    assert "Review targets" in first_message["content"]

    vocab_words = list(iter_target_vocabulary(turn.plan))
    assert {word.word for word in vocab_words} >= review_surfaces


def test_history_is_trimmed(db_session, seeded_user):
    user, _ = seeded_user
    llm = DummyLLMService()
    generator = ConversationGenerator(
        progress_service=ProgressService(db_session),
        llm_service=llm,
        target_limit=4,
        max_history_messages=4,
    )

    history = [
        ConversationHistoryMessage(role="user", content=f"tour {index}")
        if index % 2 == 0
        else ConversationHistoryMessage(role="assistant", content=f"réponse {index}")
        for index in range(8)
    ]

    generator.generate_turn(
        user=user,
        learner_level="B1",
        style="travel",
        history=history,
    )

    trimmed_messages = llm.calls[0]["messages"][-4:]
    assert [message["content"] for message in trimmed_messages] == [
        "tour 4",
        "réponse 5",
        "tour 6",
        "réponse 7",
    ]


def test_generator_handles_empty_targets(db_session):
    user = User(
        email="no-targets@example.com",
        hashed_password="not-used",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()

    llm = DummyLLMService()
    generator = ConversationGenerator(
        progress_service=ProgressService(db_session),
        llm_service=llm,
        target_limit=0,
    )

    turn = generator.generate_turn(user=user, learner_level="A2", style="business")

    assert turn.plan.target_words == []
    assert "No explicit targets" in llm.calls[0]["messages"][0]["content"]
