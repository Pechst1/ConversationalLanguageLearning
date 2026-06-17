from __future__ import annotations

import uuid

from app.db.models.error import UserError
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.vocabulary_credit import VocabularyCreditService


def _user_and_word(db_session) -> tuple[User, VocabularyWord]:
    user = User(
        email=f"vocab-credit-{uuid.uuid4().hex}@example.com",
        hashed_password="hashed",
        target_language="fr",
        native_language="de",
    )
    word = VocabularyWord(
        language="fr",
        word="abaisser",
        normalized_word="abaisser",
        german_translation="herabsetzen, senken",
        example_sentence="Il faut abaisser le prix avant vendredi.",
        example_translation="Der Preis muss vor Freitag gesenkt werden.",
        deck_name="Französisch 5000::1. FR → DE",
    )
    db_session.add_all([user, word])
    db_session.commit()
    return user, word


def test_seen_context_applies_tiny_credit_without_review_log(db_session) -> None:
    user, word = _user_and_word(db_session)
    result = VocabularyCreditService(db_session).apply(
        user=user,
        word=word,
        event_type="seen_context",
        source_type="graphic_novel",
        context=word.example_sentence,
    )

    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id)
        .one()
    )

    assert result.credit_kind == "seen_context"
    assert progress.times_seen == 1
    assert progress.proficiency_score == 1
    assert db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).count() == 0


def test_recognition_applies_medium_review_credit(db_session) -> None:
    user, word = _user_and_word(db_session)
    result = VocabularyCreditService(db_session).apply(
        user=user,
        word=word,
        event_type="recognized",
        source_type="session",
        learner_text="senken",
    )

    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id)
        .one()
    )

    assert result.credit_kind == "recognized"
    assert progress.reps == 1
    assert progress.times_seen == 1
    assert db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).one().rating == 2


def test_incorrect_production_creates_vocab_linked_erratum(db_session) -> None:
    user, word = _user_and_word(db_session)
    result = VocabularyCreditService(db_session).apply(
        user=user,
        word=word,
        event_type="produced_incorrect",
        source_type="mission",
        learner_text="Je baisse le prix.",
        corrected_text="Je dois abaisser le prix.",
        explanation="This mission targeted abaisser for the formal register.",
        repair_hint="Use abaisser in this formal message.",
    )

    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == word.id)
        .one()
    )
    erratum = db_session.query(UserError).filter(UserError.user_id == user.id).one()

    assert result.credit_kind == "produced_incorrect"
    assert result.erratum_id == str(erratum.id)
    assert progress.times_used_incorrectly == 1
    assert progress.state == "relearning"
    assert erratum.review_mode == "vocabulary"
    assert erratum.linked_word_id == word.id
    assert erratum.source_type == "mission"
    assert erratum.task_error_type == "vocabulary_incorrect_use"


def test_repeated_incorrect_production_reuses_vocab_memory(db_session) -> None:
    user, word = _user_and_word(db_session)
    service = VocabularyCreditService(db_session)

    first = service.apply(
        user=user,
        word=word,
        event_type="produced_incorrect",
        source_type="session",
        learner_text="abaisser",
        corrected_text="abaisser le prix",
    )
    second = service.apply(
        user=user,
        word=word,
        event_type="produced_incorrect",
        source_type="session",
        learner_text="abaisser",
        corrected_text="abaisser le prix",
    )

    errata = db_session.query(UserError).filter(UserError.user_id == user.id).all()

    assert len(errata) == 1
    assert first.erratum_id == second.erratum_id
    assert second.erratum_action == "repeated"
    assert errata[0].occurrences == 2
