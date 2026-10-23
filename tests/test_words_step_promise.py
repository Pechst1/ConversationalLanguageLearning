"""#279 — the words step promises exactly the cards the review opens with.

Found in the 22 October live walk: Home said «10 words · 4 min», the review
(``/vocabulary/review?day=1``) opened at 0/21. The step's count was
``new_left or reviews`` (one of the two) while its minutes already added both,
and the review deck was sized by its own caps. The step now reads the same
:func:`app.services.daily_session.words_queue` the minutes come from, with the
caps the due-context endpoint applies, and these tests hold the two ends
together: the promised count is the deck's length.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyDrillBatch, VocabularyWord
from app.services import daily_session, vocabulary_pace
from app.services.daily_session import SessionInputs, session_view

#: ``pages/vocabulary/review.tsx``'s ``dayQueueParams``: the day's deck.
DAY_QUEUE = {
    "limit": 100, "due_limit": 100, "fragile_limit": 0, "new_limit": 50, "topic_limit": 0, "linked_limit": 0,
    "drill": "session",
}

_CREATED: list[int] = []


@pytest.fixture(autouse=True)
def _forget_test_words(db_session: Session):
    yield
    db_session.rollback()
    if not _CREATED:
        return
    progress_ids = [
        row.id for row in db_session.query(UserVocabularyProgress).filter(UserVocabularyProgress.word_id.in_(_CREATED))
    ]
    if progress_ids:
        db_session.query(ReviewLog).filter(ReviewLog.progress_id.in_(progress_ids)).delete(synchronize_session=False)
        db_session.query(UserVocabularyProgress).filter(UserVocabularyProgress.id.in_(progress_ids)).delete(
            synchronize_session=False
        )
    db_session.query(VocabularyDrillBatch).delete(synchronize_session=False)
    db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(_CREATED)).delete(synchronize_session=False)
    db_session.commit()
    _CREATED.clear()


def _words(db: Session, count: int, tag: str) -> list[int]:
    ids = []
    for index in range(count):
        word = VocabularyWord(
            word=f"{tag}{index:03d}",
            normalized_word=f"{tag}{index:03d}",
            language="fr",
            english_translation=f"{tag}{index:03d} (en)",
            is_anki_card=True,
            frequency_rank=index + 1,
        )
        db.add(word)
        db.flush()
        _CREATED.append(int(word.id))
        ids.append(int(word.id))
    db.commit()
    return ids


def _learner(client: TestClient, db: Session, *, quota: int = 10) -> tuple[dict, User]:
    email = f"promise-{uuid.uuid4().hex[:8]}@example.com"
    password = "promise-secure-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db.get(User, UUID(str(decode_token(token)["sub"])))
    user.daily_pace = None
    user.new_words_per_day = quota
    user.timezone = "Europe/Paris"
    db.commit()
    return {"Authorization": f"Bearer {token}"}, user


def _seed(db: Session, user: User, *, due: int, introduced_today: int) -> None:
    """``due`` words met on earlier days and waiting; ``introduced_today`` met this morning."""

    now = datetime.now(UTC)
    for word_id in _words(db, due, "promd"):
        db.add(
            UserVocabularyProgress(
                user_id=user.id, word_id=word_id, state="review", phase="review", reps=3,
                due_at=now - timedelta(hours=3), last_review_date=now - timedelta(days=4),
                created_at=now - timedelta(days=9),
            )
        )
    for word_id in _words(db, introduced_today, "promi"):
        db.add(
            UserVocabularyProgress(
                user_id=user.id, word_id=word_id, state="learning", phase="learn", reps=1,
                due_at=now + timedelta(days=1), last_review_date=now, created_at=now,
            )
        )
    _words(db, 40, "promn")
    db.commit()


def _promise(db: Session, user: User) -> dict:
    """Home's words step, built the way ``DailyJourneyService`` builds it."""

    from app.services.progress import ProgressService

    session = daily_session.build_session(
        db, user, journey=None, scene_done=True, scene_seconds=None,
        reviews_due=ProgressService(db).count_due_reviews(user.id),
        forge_href="/atelier?mode=forge", forge_blocks_today=0,
    )
    return next(step for step in session["steps"] if step["kind"] == "words")


def _deck_length(client: TestClient, headers: dict) -> int:
    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_QUEUE)
    assert response.status_code == 200, response.text
    deck = response.json()
    names = ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")
    return len({item["word_id"] for name in names for item in deck[name]})


def test_a_day_with_due_cards_promises_the_decks_length(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _learner(client, db_session, quota=10)
    _seed(db_session, user, due=8, introduced_today=3)
    # The scene is done: the journey's words are introduced, none left reserved.
    monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *a, **k: (True, set()))

    step = _promise(db_session, user)
    deck = _deck_length(client, headers)

    # 10 words a day, 3 met in the scene: 7 new and the 8 reviews due.
    assert deck == 15
    assert step["count"] == deck, f"Home promises {step['count']} cards, the review opens with {deck}"
    assert (step["new_left"], step["reviews"]) == (7, 8)


def test_the_promise_keeps_the_learners_review_cap(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _learner(client, db_session, quota=10)
    user.max_reviews_per_day = 5
    db_session.commit()
    _seed(db_session, user, due=8, introduced_today=3)
    monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *a, **k: (True, set()))

    step = _promise(db_session, user)
    deck = _deck_length(client, headers)

    assert deck == 5 + 7, "the cap is the deck's: 5 reviews and the 7 new words"
    assert step["count"] == deck
    assert step["reviews"] == 5


def test_the_count_and_the_minutes_are_one_queue() -> None:
    """The step's number and its minutes come from the same two figures."""

    inputs = SessionInputs(
        pace="normal", scene_done=True, scene_seconds=480, quota=10, introduced=0, reviews_due=8,
        words_marked_done=False, forge_seconds=300, forge_blocks_today=0, forge_href="/x", exercises_today=0,
    )
    step = next(s for s in session_view(inputs)["steps"] if s["kind"] == "words")
    assert step["count"] == 18, "10 new words and 8 reviews are 18 cards, not 10"
    from app.services.daily_session import words_queue

    queue = words_queue(step["new_left"], step["reviews"])
    assert step["count"] == queue.count
    assert step["minutes"] == daily_session.minutes(queue.seconds)


def _deck_parts(client: TestClient, headers: dict) -> tuple[int, int]:
    """``(new, reviews)`` the day's review deals."""

    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_QUEUE)
    assert response.status_code == 200, response.text
    deck = response.json()
    return len(deck["new_words"]), len(deck["due_words"])


def test_a_large_backlog_still_promises_what_the_review_deals(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Back after a week away: 130 reviews due. The deck holds 100 cards, the new
    words first; the promise is that deck, not «10 new · 100 to review» over a
    review that deals 100 reviews and no new word (#279, reviewer's note)."""

    headers, user = _learner(client, db_session, quota=10)
    _seed(db_session, user, due=130, introduced_today=0)
    monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *a, **k: (True, set()))

    step = _promise(db_session, user)
    new_dealt, reviews_dealt = _deck_parts(client, headers)

    assert step["count"] == new_dealt + reviews_dealt, (
        f"Home promises {step['count']} cards ({step['new_left']} new, {step['reviews']} to review), "
        f"the review deals {new_dealt} new and {reviews_dealt} to review"
    )
    assert step["new_left"] + step["reviews"] == step["count"]
    assert (step["new_left"], step["reviews"]) == (new_dealt, reviews_dealt)


def test_a_day_whose_journey_is_not_planned_yet_promises_what_the_review_deals(
    client: TestClient, db_session: Session
) -> None:
    """Before the journey is planned the drill leaves the rhythm's share of new
    words free for it. Home reads that same room, so it does not promise the
    whole quota while the review deals less (#279, reviewer's note)."""

    headers, user = _learner(client, db_session, quota=10)
    _seed(db_session, user, due=8, introduced_today=0)

    step = _promise(db_session, user)
    new_dealt, reviews_dealt = _deck_parts(client, headers)

    assert step["count"] == new_dealt + reviews_dealt, (
        f"Home promises {step['count']} cards, the review deals {new_dealt} new and {reviews_dealt} to review"
    )
    assert (step["new_left"], step["reviews"]) == (new_dealt, reviews_dealt)


def test_the_review_asks_for_the_deck_size_the_promise_is_capped_at() -> None:
    """``review.tsx`` sends ``limit`` for the day's deck; the promise caps its
    cards at :data:`daily_session.DAY_DECK_LIMIT`. One number, two files."""

    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "web-frontend/pages/vocabulary/review.tsx").read_text()
    block = re.search(r"const dayQueueParams = \{(.*?)\} as const", source, re.S)
    assert block, "dayQueueParams moved: update this test"
    sent = re.search(r"\blimit:\s*(\d+)", block.group(1))
    assert sent and int(sent.group(1)) == daily_session.DAY_DECK_LIMIT


def test_the_review_room_leaves_the_new_words_their_place() -> None:
    from app.services.daily_session import DAY_DECK_LIMIT, review_room, words_queue

    assert review_room(10) == DAY_DECK_LIMIT - 10
    assert review_room(10, reviews_left=3) == 3
    assert review_room(10, deck_limit=12) == 2
    queue = words_queue(10, 130)
    assert (queue.new, queue.reviews, queue.count) == (10, DAY_DECK_LIMIT - 10, DAY_DECK_LIMIT)
