"""#396 — the day's word count is one number from Home to the Done screen.

Live walk 31 October (day 19): Home said «5 words», the step button «Next: 8
words», the review opened at 0/8, Home afterwards «10 words — done» and the Done
screen «11 Words». The step button and the review already agreed (both read the
deck, #143/#279); the two numbers after the deck was finished did not: the
finished step and the end screen's tally counted *every word touched today*
(``max(introduced today, distinct words reviewed today)``), the scene's own
words and La Forge's reviews included, while the deck the learner went through
held eight cards. A finished step now says the size of the deck that was dealt,
the number the button and the review header showed.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.services import daily_session, vocabulary_pace
from app.services.progress import ProgressService
from app.utils.cache import cache_backend
from tests.test_wp154_drill_reload import (
    _deck,
    _forget_test_words,  # noqa: F401 - autouse fixture: the suite shares one database
    _login,
    _supply,
)

#: ``pages/vocabulary/review.tsx``'s ``dayQueueParams`` (``WORDS_HREF``).
DAY = {
    "limit": 100, "due_limit": 100, "fragile_limit": 0, "new_limit": 50, "topic_limit": 0, "linked_limit": 0,
    "drill": "session",
}


def _cards(deck: dict) -> list[int]:
    return [
        item["word_id"]
        for name in ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")
        for item in deck[name]
    ]


def _answer(client: TestClient, headers: dict, word_ids: list[int]) -> None:
    """Answer each card «good»: the word is not due again in minutes."""

    for word_id in word_ids:
        reviewed = client.post(
            "/api/v1/anki/review", headers=headers, json={"word_id": word_id, "rating": 3, "format": "flashcard"}
        )
        assert reviewed.status_code == 200, reviewed.text


def _session(db: Session, user) -> dict:
    """Home's day as ``TodayEnvelope.session`` carries it, scene done."""

    db.expire_all()
    # The due count is cached for a minute; this test is about the day's number,
    # not the cache (``test_396_an_answered_card_is_no_longer_counted_as_due``).
    cache_backend.clear()
    return daily_session.build_session(
        db,
        user,
        journey=None,
        scene_done=True,
        scene_seconds=480,
        reviews_due=ProgressService(db).count_due_reviews(user.id),
        forge_href="/atelier?mode=forge&from=day",
        forge_blocks_today=0,
    )


def _words_step(session: dict) -> dict:
    return next(step for step in session["steps"] if step["kind"] == "words")


def test_396_the_finished_step_and_the_end_screen_say_the_decks_size(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    user.daily_pace = None
    user.new_words_per_day = 10
    db_session.commit()
    supply = _supply(db_session, 40, "w396")
    # Words met on earlier days and due today: the deck's reviews.
    now = datetime.now(UTC)
    for word_id in _supply(db_session, 4, "w396due"):
        db_session.add(
            UserVocabularyProgress(
                user_id=user.id, word_id=word_id, state="review", phase="review", reps=3,
                due_at=now - timedelta(hours=3), last_review_date=now - timedelta(days=4),
                created_at=now - timedelta(days=9),
            )
        )
    db_session.commit()
    # The scene is done: it met three new words and answered them (the journey's
    # own credit), and its reservation is spent.
    monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *_a, **_k: (True, set()))
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *_a, **_k: 1.0)
    _answer(client, headers, supply[:3])

    # What Home and the step button promise, and what the review opens with.
    promised = _words_step(_session(db_session, user))
    deck = _deck(client, headers, DAY)
    cards = _cards(deck)
    assert promised["count"] == len(cards), f"the button says {promised['count']}, the review opens at 0/{len(cards)}"
    assert len(cards) > 4, "new words and the due reviews are in the deck"

    # The learner goes through the deck, and La Forge reviews a word of the scene on top.
    _answer(client, headers, cards)
    _answer(client, headers, supply[:2])

    finished = _session(db_session, user)
    step = _words_step(finished)

    assert step["state"] == "done", step
    assert step["count"] == len(cards), (
        f"Home says «{step['count']} words — done» after a deck of {len(cards)} cards"
    )
    assert finished["tally"]["words"] == len(cards), (
        f"the Done screen says {finished['tally']['words']} Words after a deck of {len(cards)} cards"
    )


def test_396_an_answered_card_is_no_longer_counted_as_due(client: TestClient, db_session: Session) -> None:
    """Home's «to review» is the due count, cached for a minute. The review page's
    own write path did not drop it, so Home went on counting cards the learner had
    just answered: the day's number then differed from the deck's."""

    headers, user = _login(client, db_session)
    now = datetime.now(UTC)
    due = _supply(db_session, 3, "w396stale")
    for word_id in due:
        db_session.add(
            UserVocabularyProgress(
                user_id=user.id, word_id=word_id, state="review", phase="review", reps=3,
                due_at=now - timedelta(hours=3), last_review_date=now - timedelta(days=4),
                created_at=now - timedelta(days=9),
            )
        )
    db_session.commit()
    cache_backend.clear()
    assert ProgressService(db_session).count_due_reviews(user.id) == 3

    _answer(client, headers, due)

    counted = ProgressService(db_session).count_due_reviews(user.id)
    assert counted == 0, f"Home still counts {counted} reviews after the learner answered all three"
