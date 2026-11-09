"""#563 — «Noch 5 neue Wörter» promised five, served one, and the goal line credited 30.

Walk 6 Nov: after 20/20 cards the button said «Noch 5 neue Wörter»; the extra
deck held one card; the sheet after it said «Mit 30 Wörtern am Tag …». The
button's step, the deck's size and the goal line each counted on their own:
the step was always five, the grant raised the cap by five whatever the pool
could serve, and the goal line added the granted five to the learner's number.

Now the extra words are one number, ``vocabulary_pace.next_extra_step``: what
the next tap really serves. The offer's step (label), the grant (the cap, so the
deck's room), and the goal line's «Mit N Wörtern» all read it.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import vocabulary_pace
from tests.test_more_words_per_day import MORE, SESSION, _answer, _dose_of
from tests.test_wp154_drill_reload import (
    _deck,
    _forget_test_words,  # noqa: F401 - autouse fixture: the suite shares one database
    _ids,
    _login,
    _supply,
)


def _pace(client: TestClient, headers: dict) -> dict:
    response = client.get("/api/v1/vocabulary/new-words", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_one_extra_card_left_the_button_the_deck_and_the_goal_line_say_one(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 4, "w563a")  # the dose of 3, and one card more
    _dose_of(db_session, user, monkeypatch, 3)
    day = _ids(_deck(client, headers, SESSION))
    assert len(day) == 3
    _answer(client, headers, day)

    offer = _pace(client, headers)
    assert offer["step"] == 1, f"the button promises {offer['step']} new words, the pool holds 1"
    assert offer["can_add_more"] is True
    assert offer["more"]["words"] == 3 + 1, f"the goal line credits {offer['more']['words']} words a day"

    # Home's and Fertig's «Noch N neue Wörter» is the same number, not the step's name.
    from app.services.daily_session import build_session

    db_session.expire_all()
    done = build_session(
        db_session, user, journey=None, scene_done=True, scene_seconds=None, reviews_due=0,
        forge_href="/forge", forge_blocks_today=1,
    )
    assert done["done"] is True
    assert (done["more_words"], done["more_href"]) == (1, "/vocabulary/review?more=1")

    granted = client.post("/api/v1/vocabulary/new-words/more", headers=headers)
    assert granted.status_code == 200, granted.text
    assert granted.json()["extra_today"] == 1, "the grant raised the cap by more than the deck can serve"
    extra = _ids(_deck(client, headers, {**MORE, "new_limit": granted.json()["step"] or 1}))
    assert len(extra) == 1
    _answer(client, headers, extra)

    # The pool is empty: no button, no goal line promising more, no further grant.
    after = _pace(client, headers)
    assert after["can_add_more"] is False and after["step"] == 0
    assert client.post("/api/v1/vocabulary/new-words/more", headers=headers).status_code == 409
    assert vocabulary_pace.extra_new_words_today(db_session, user) == 1


def test_a_full_pool_still_offers_the_whole_step(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 30, "w563b")
    _dose_of(db_session, user, monkeypatch, 3)
    _answer(client, headers, _ids(_deck(client, headers, SESSION)))

    offer = _pace(client, headers)
    assert (offer["step"], offer["can_add_more"], offer["more"]["words"]) == (5, True, 8)
    assert client.post("/api/v1/vocabulary/new-words/more", headers=headers).json()["extra_today"] == 5
    assert len(_ids(_deck(client, headers, MORE))) == 5
