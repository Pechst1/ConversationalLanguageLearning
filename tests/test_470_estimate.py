"""#470 — Home prints one number for the day's words.

Walk, 2 November (a1-de-fresh, day 2): the day card said «+ Wörter ≈ 9 s» while
the plan row under it said «21 Wörter — 20 neu · 1 zum Wiederholen · 7 Min.».
The card priced the cards already due (`word_drill_seconds(due)`), the plan row
priced the day deck (new + due, `words_seconds`). The day's word workload was
counted twice, in two ways (the mechanism of #143).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import daily_session
from tests.test_journey_end_to_end import (
    assembled_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
    seed_due_vocabulary,
)
from tests.test_wp154_drill_reload import (  # noqa: F401 - autouse + supply
    _forget_test_words,
    _supply,
)


def test_470_same_deck(
    assembled_client: TestClient, db_session: Session, journey_enabled: None  # noqa: F811
) -> None:
    email = "t470-words@example.com"
    headers = register(assembled_client, email)
    _supply(db_session, 40, "w470")  # new words to deal
    seed_due_vocabulary(db_session, learner_id(db_session, email), (("la clé", "the key"),))

    today = assembled_client.get("/api/v1/daily-journeys/today", headers=headers).json()
    step = next(step for step in today["session"]["steps"] if step["kind"] == "words")
    assert step["new_left"] > 0, step
    deck_seconds = daily_session.words_seconds(step["new_left"], step["reviews"])

    words = [item for item in today["time_estimate"]["extensions"] if item["kind"] == "words"]
    assert words, "the day card names the words"
    # Before: 9 s (the one due card) next to «21 Wörter … 7 Min.».
    assert words[0]["seconds"] == deck_seconds, (
        f"day card says {words[0]['seconds']} s, the plan row's deck ({step['new_left']} new + "
        f"{step['reviews']} due) is {deck_seconds} s"
    )
    assert daily_session.minutes(words[0]["seconds"]) == step["minutes"]
