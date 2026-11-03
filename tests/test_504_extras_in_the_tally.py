"""#504 — the Done screen's Words tile counts every card answered today, extras included.

Walk, 3 November (a2-en, day 1): the learner finished the day's 20 words, asked
for «5 more new words», answered all five, and the Done screen still said «20
Words». The tally read the day deck's dealt size (`dealt_deck`), which leaves the
«more» cards out on purpose (they are not the day's intake), so the plan's step
count and the tally, two different things, were one number (#143).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import vocabulary_pace
from tests.test_396_one_word_count import (
    DAY,
    _answer,
    _cards,
    _session,
    _words_step,
)
from tests.test_wp154_drill_reload import (
    _deck,
    _forget_test_words,  # noqa: F401 - autouse fixture: the suite shares one database
    _login,
    _supply,
)

MORE = {"limit": 35, "due_limit": 30, "fragile_limit": 0, "new_limit": 5, "topic_limit": 0, "linked_limit": 0,
        "drill": "more"}


def _day_with_extras(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> tuple[dict, object, list[int], list[int]]:
    headers, user = _login(client, db_session)
    user.daily_pace = None
    user.new_words_per_day = 4
    db_session.commit()
    _supply(db_session, 40, prefix)
    monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *_a, **_k: (True, set()))
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *_a, **_k: 1.0)

    day = _cards(_deck(client, headers, DAY))
    assert len(day) == 4
    _answer(client, headers, day)

    assert client.post("/api/v1/vocabulary/new-words/more", headers=headers).status_code == 200
    extra = [item["word_id"] for item in _deck(client, headers, MORE)["new_words"]]
    assert len(extra) == 5
    return headers, user, day, extra


def test_504_the_tally_counts_the_extras_the_step_keeps_the_days_intake(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user, day, extra = _day_with_extras(client, db_session, monkeypatch, "w504")
    _answer(client, headers, extra)

    finished = _session(db_session, user)
    step = _words_step(finished)

    assert step["state"] == "done", step
    assert step["count"] == len(day), f"the step says {step['count']}, the day's intake is {len(day)}"
    assert finished["tally"]["words"] == len(day) + len(extra), (
        f"the Done screen says {finished['tally']['words']} Words after {len(day)} + {len(extra)} answered cards"
    )


def test_504_unanswered_extras_are_not_counted(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user, day, extra = _day_with_extras(client, db_session, monkeypatch, "w504b")
    _answer(client, headers, extra[:2])

    assert _session(db_session, user)["tally"]["words"] == len(day) + 2
