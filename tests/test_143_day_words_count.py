"""#143 — Home's «Weiter: N Wörter» is the deck the learner then sees.

Walk, 18 October (a1-de, day 1): «Weiter: 20 Wörter» opened «0/19», and Home
afterwards said «20 Wörter — erledigt». Home took the quota less today's
introductions; the drill also leaves out the new words today's journey reserved
and has not introduced yet (WP-L6), so the deck held one word fewer. Live,
19 October: the Lexique opened first dealt its eight, the day deck then served
that batch and grew by a continuation at its end. The word step now reads the
deck's own state (``daily_session.day_deck``), and the day deck opens the
Lexique's batch on the whole dose.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import daily_session, vocabulary_pace
from tests.test_wp154_drill_reload import (
    SESSION,
    _answer,
    _deck,
    _forget_test_words,  # noqa: F401 - autouse fixture: the suite shares one database
    _ids,
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


def _home_words(db: Session, user) -> dict:
    """The word step as Home and the hand-offs print it (``TodayEnvelope.session``)."""

    db.expire_all()
    session = daily_session.build_session(
        db,
        user,
        journey=None,
        scene_done=True,
        scene_seconds=480,
        reviews_due=0,
        forge_href="/atelier?mode=forge&from=day",
        forge_blocks_today=0,
    )
    return next(step for step in session["steps"] if step["kind"] == "words")


@pytest.fixture
def normal_pace(monkeypatch: pytest.MonkeyPatch):
    def setup(db: Session, user, reserved: set[int]) -> None:
        user.daily_pace = "normal"  # 20 new words a day
        user.new_words_per_day = 20
        db.commit()
        # Today's journey is planned and keeps `reserved` to introduce itself.
        monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *_a, **_k: (True, set(reserved)))
        monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *_a, **_k: 1.0)

    return setup


def test_143_the_word_step_promises_the_cards_the_day_deck_deals(
    client: TestClient, db_session: Session, normal_pace
) -> None:
    headers, user = _login(client, db_session)
    supply = _supply(db_session, 40, "w143a")
    normal_pace(db_session, user, {supply[0]})

    promised = _home_words(db_session, user)
    deck = _deck(client, headers, DAY)
    cards = _cards(deck)
    assert supply[0] not in cards, "the journey's reserved word is the journey's to introduce"
    # Before: «Weiter: 20 Wörter» over a deck of 19.
    assert promised["count"] == len(cards) == 19
    assert deck["new_words_left_today"] == 0, "the deck holds the whole dose"

    # Halfway through, Home names what the deck still holds.
    _answer(client, headers, cards[:7])
    assert _home_words(db_session, user)["count"] == len(_cards(_deck(client, headers, DAY))) == 12

    # Done: the step says what the day did, as the end screen does, not the pace's 20.
    _answer(client, headers, cards[7:])
    assert _cards(_deck(client, headers, DAY)) == []
    done = _home_words(db_session, user)
    assert done["state"] == "done"
    assert done["count"] == 19


def test_143_the_day_deck_opens_the_lexiques_batch_on_the_whole_dose(
    client: TestClient, db_session: Session, normal_pace
) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 40, "w143b")
    normal_pace(db_session, user, set())

    # The Lexique tab first: one session of eight new words, dealt and kept.
    lexique = _ids(_deck(client, headers, SESSION))
    assert len(lexique) == 8
    _answer(client, headers, lexique[:3])
    promised = _home_words(db_session, user)
    assert promised["count"] == 17, "20 for the day, 3 of them already met"

    # Before: the day deck served the Lexique's five, «0/5», then grew at its end.
    day = _deck(client, headers, DAY)
    cards = _cards(day)
    assert len(cards) == promised["count"] == 17
    assert cards[:5] == lexique[3:], "the Lexique's cards keep their places"
    assert day["new_words_left_today"] == 0
    # A reload is the same deck, and Home still promises it.
    assert _cards(_deck(client, headers, DAY)) == cards
    assert _home_words(db_session, user)["count"] == 17

    # The Lexique's own reload never tops up its session (WP-154).
    assert _ids(_deck(client, headers, SESSION))[:5] == lexique[3:]
