"""2026-10-03: the vocabulary check credits a sub-band a learner already knows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import band_check
from app.services.core_lexicon import CORE_DECK, ensure_core_lexicon
from app.services.kept_words import SCENE_LEXICON_INTERACTION_TYPE
from app.services.level_coverage import band_words, known_lemmas, read_lemmas

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _drop_core_rows(db_session):
    yield
    db_session.rollback()
    core_ids = select(VocabularyWord.id).where(VocabularyWord.deck_name == CORE_DECK)
    db_session.execute(delete(WordInteraction).where(WordInteraction.word_id.in_(core_ids)))
    db_session.execute(delete(UserVocabularyProgress).where(UserVocabularyProgress.word_id.in_(core_ids)))
    db_session.execute(delete(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK))
    db_session.commit()


def _user(db, level: str) -> User:
    user = User(id=uuid.uuid4(), email=f"bc-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                target_language="fr", native_language="de", cefr_estimate=level)
    db.add(user)
    db.commit()
    return user


def _answers(user, sub_band, *, wrong: int = 0) -> dict[str, int | None]:
    items = band_check._items(user, sub_band, now=NOW)
    answers = {item["id"]: item["answer"] for item in items}
    for item in items[:wrong]:
        answers[item["id"]] = None
    return answers


def test_only_sub_bands_below_the_learners_own_are_offered(db_session):
    user = _user(db_session, "B1.1")
    bands = [row["sub_band"] for row in band_check.checkable(db_session, user)]
    assert bands == ["A1.1", "A1.2", "A2.1", "A2.2"]
    assert band_check.checkable(db_session, _user(db_session, "A1.1")) == []


def test_items_are_meaning_choices_without_the_key_and_stable_for_the_attempt(db_session):
    user = _user(db_session, "A2.1")
    first = band_check.sample(user, "A1.1", now=NOW)
    assert len(first) == band_check.ITEMS
    assert all(len(item["options"]) == 4 and "answer" not in item for item in first)
    assert first == band_check.sample(user, "A1.1", now=NOW)
    # WP-127: keyed by the attempt, not the day — midnight changes nothing.
    assert first == band_check.sample(user, "A1.1", now=NOW.replace(day=NOW.day + 1))
    assert first != band_check.sample(user, "A1.1", attempt=1)


def test_a_pass_credits_the_band_except_the_missed_words(db_session):
    user = _user(db_session, "A2.1")
    ensure_core_lexicon(db_session)
    answers = _answers(user, "A1.1", wrong=2)  # 22 / 24 ≥ 90 %
    result = band_check.submit(db_session, user, "A1.1", answers, now=NOW)
    db_session.commit()
    assert result["passed"] and result["correct"] == 22 and result["credited_words"] > 200
    known = known_lemmas(db_session, user, now=NOW)
    assert len(known & band_words("A1.1")) >= 0.8 * len(band_words("A1.1"))
    assert not set(result["missed"]) & known
    assert "A1.1" in band_check.credited_sub_bands(db_session, user)
    # WP-127: the sampled, right words are sampled recognition; the rest inferred.
    assert result["credited_sampled"] == 22
    assert result["credited_inferred"] == result["credited_words"] - 22
    assert band_check.credit_kinds(db_session, user)["A1.1"] == "sampled"


def test_a_fail_credits_nothing(db_session):
    user = _user(db_session, "A2.1")
    result = band_check.submit(db_session, user, "A1.1", _answers(user, "A1.1", wrong=4), now=NOW)
    assert not result["passed"] and result["credited_words"] == 0


def test_a_word_met_in_three_sentences_on_three_days_is_known_from_reading(db_session):
    user = _user(db_session, "A1.1")
    ensure_core_lexicon(db_session)
    word = db_session.scalar(select(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK,
                                                           VocabularyWord.normalized_word == "clé"))
    session = LearningSession(user_id=user.id, planned_duration_minutes=10)
    db_session.add(session)
    db_session.flush()
    for day, sentence in enumerate(["Voilà la clé.", "Où est la clé ?", "La clé est sur la table."], start=1):
        db_session.add(WordInteraction(session_id=session.id, user_id=user.id, word_id=word.id,
                                       interaction_type=SCENE_LEXICON_INTERACTION_TYPE, context_sentence=sentence,
                                       created_at=datetime(2026, 10, day, tzinfo=UTC)))
        db_session.flush()
        assert ("clé" in read_lemmas(db_session, user)) is (day == 3)


def test_the_band_check_routes_are_not_captured_by_the_word_route(client):
    """GET /vocabulary/band-check answered 422 when /{word_id} was declared first."""

    response = client.get("/api/v1/vocabulary/band-check")
    assert response.status_code in {200, 401, 403}
