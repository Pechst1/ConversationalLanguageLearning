"""WP-115a — one honest memory: earned grades, what a review was, the learner's caps."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.services.vocab_fsrs import earned_rating
from app.services.vocabulary_credit import VocabularyCreditService
from tests.test_daily_words import _make_due_word


def _login(client: TestClient, db_session) -> tuple[dict, User]:
    email = f"{uuid4()}@example.com"
    password = "wp115a-secure-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, db_session.get(User, UUID(str(decode_token(token)["sub"])))


@pytest.mark.parametrize(
    ("review_format", "correct", "rating", "earned"),
    [
        ("typed", True, 3, 2),
        ("typed", False, 3, 0),
        ("cloze", True, 0, 2),
        ("audio", True, 1, 2),
        ("choice", True, 3, 1),
        ("flashcard", None, 3, 3),
        (None, None, 1, 1),
    ],
)
def test_an_answered_card_earns_its_grade(review_format, correct, rating, earned):
    assert earned_rating(review_format, correct, rating) == earned


def _log_of(db_session, user: User, word_id: int) -> ReviewLog:
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word_id).one()
    return db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).order_by(ReviewLog.created_at.desc()).first()


def test_the_drill_grades_a_typed_answer_and_logs_what_the_review_was(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=80)
    db_session.commit()
    response = client.post(
        "/api/v1/anki/review",
        headers=headers,
        json={"word_id": word.id, "rating": 3, "format": "typed", "correct": True, "direction": "native_to_fr"},
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    log = _log_of(db_session, user, word.id)
    assert log.rating == 2, "a typed answer earns Good, whatever button was pressed"
    assert (log.source, log.format, log.direction) == ("drill", "typed", "native_to_fr")


def test_a_self_rated_flashcard_keeps_the_learners_rating(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "le zinc", rank=81)
    db_session.commit()
    assert client.post("/api/v1/anki/review", headers=headers, json={"word_id": word.id, "rating": 1}).status_code == 200
    db_session.expire_all()
    log = _log_of(db_session, user, word.id)
    assert (log.rating, log.format, log.source) == (1, "flashcard", "drill")


def test_the_days_credit_logs_its_source_and_format(db_session):
    from tests.test_vocabulary_credit import _user_and_word

    user, word = _user_and_word(db_session)
    VocabularyCreditService(db_session).apply(
        user=user, word=word, event_type="produced_correct", source_type="atelier",
        source_payload={"task_type": "short_answer"},
    )
    log = _log_of(db_session, user, word.id)
    assert (log.rating, log.source, log.format) == (2, "atelier", "short_answer")


def test_the_learner_sets_anki_like_caps(client: TestClient, db_session):
    headers, _user = _login(client, db_session)
    before = client.get("/api/v1/users/me/settings", headers=headers).json()
    assert before["max_reviews_per_day"] == 200
    patched = client.patch(
        "/api/v1/users/me/settings", headers=headers, json={"new_words_per_day": 80, "max_reviews_per_day": 500}
    )
    assert patched.status_code == 200, patched.text
    assert (patched.json()["new_words_per_day"], patched.json()["max_reviews_per_day"]) == (80, 500)
    assert client.patch("/api/v1/users/me/settings", headers=headers, json={"new_words_per_day": 101}).status_code == 422


def test_the_drill_stops_at_the_learners_review_cap(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    first = _make_due_word(db_session, user, "la porte", rank=82)
    second = _make_due_word(db_session, user, "la valise", rank=83)
    db_session.commit()
    client.patch("/api/v1/users/me/settings", headers=headers, json={"max_reviews_per_day": 1})
    before = client.get("/api/v1/vocabulary/due-context?due_limit=10", headers=headers)
    assert before.status_code == 200, before.text
    assert len(before.json()["due_words"]) == 1, "one review left: one due word offered"
    client.post("/api/v1/anki/review", headers=headers, json={"word_id": first.id, "rating": 2})
    after = client.get("/api/v1/vocabulary/due-context?due_limit=10", headers=headers).json()
    assert after["due_words"] == [], f"the cap is spent; {second.word} waits for tomorrow"


def test_a_kept_word_remembers_where_it_was_met(db_session):
    from app.services.kept_words import keep_word
    from tests.test_vocabulary_credit import _user_and_word

    user, word = _user_and_word(db_session)
    sentence = f"Tu as une {word.word} et une lettre."
    kept = keep_word(
        db_session, user=user, term=word.word, sentence=sentence,
        met={"speaker_id": "margaux_barman", "panel_id": "p-3", "line_key": "p-3:l0"},
    )
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=kept.word_id).one()
    assert progress.context["sentence_fr"] == sentence
    assert (progress.context["speaker_id"], progress.context["panel_id"], progress.context["line_key"]) == (
        "margaux_barman", "p-3", "p-3:l0",
    )
