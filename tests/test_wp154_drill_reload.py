"""WP-154 — the drill's dealt batch survives a reload.

Found 7 October: with more room than one session (Intensif's 18), a learner who
answered three of eight new words and reloaded was dealt three *other* words into
the freed slots, because the deck was three reads over current state. The drill
(``drill=session`` / ``drill=more``) now keeps the batch it dealt for the
learner's app day and serves what is left of it.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyDrillBatch, VocabularyWord
from app.services import drill_batch
from app.services.streak import local_today

SESSION = {
    "limit": 50, "due_limit": 30, "fragile_limit": 12, "new_limit": 8, "topic_limit": 8, "linked_limit": 8,
    "drill": "session",
}

_CREATED: list[int] = []


def _more(n: int) -> dict:
    """review.tsx's «Encore N mots» continuation."""

    return {
        "limit": n + 30, "due_limit": 30, "fragile_limit": 0, "new_limit": n, "topic_limit": 0, "linked_limit": 0,
        "drill": "more",
    }


@pytest.fixture(autouse=True)
def _forget_test_words(db_session: Session):
    """The suite shares one database: this module's rank-1 Anki cards would
    otherwise be every later learner's first new words."""

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
    db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(_CREATED)).delete(synchronize_session=False)
    db_session.commit()
    _CREATED.clear()


def _supply(db: Session, count: int, tag: str) -> list[int]:
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


def _login(client: TestClient, db: Session, *, minutes: int = 30) -> tuple[dict, User]:
    email = f"wp154-{uuid.uuid4().hex[:8]}@example.com"
    password = "wp154-secure-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db.get(User, UUID(str(decode_token(token)["sub"])))
    user.daily_goal_minutes = minutes  # Intensif: 30 a day, 18 of them the drill's before the journey
    user.new_words_per_day = None
    user.timezone = "Europe/Paris"
    db.commit()
    return {"Authorization": f"Bearer {token}"}, user


def _deck(client: TestClient, headers: dict, params: dict) -> dict:
    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _ids(deck: dict, name: str = "new_words") -> list[int]:
    return [item["word_id"] for item in deck[name]]


def _answer(client: TestClient, headers: dict, word_ids: list[int]) -> None:
    for word_id in word_ids:
        reviewed = client.post(
            "/api/v1/anki/review", headers=headers, json={"word_id": word_id, "rating": 2, "format": "flashcard"}
        )
        assert reviewed.status_code == 200, reviewed.text


def test_the_stateless_deck_refills_the_freed_slots(client: TestClient, db_session: Session) -> None:
    """The defect, as surfaces without ``drill`` still see it: the deck is current state."""

    headers, _user = _login(client, db_session)
    _supply(db_session, 40, "wp154s")
    params = {key: value for key, value in SESSION.items() if key != "drill"}
    first = _deck(client, headers, params)
    assert len(first["new_words"]) == 8
    _answer(client, headers, _ids(first)[:3])
    again = _deck(client, headers, params)
    assert len(again["new_words"]) == 8 and set(_ids(again)) - set(_ids(first))


def test_a_reload_serves_the_rest_of_the_batch_in_order(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 40, "wp154r")
    first = _deck(client, headers, SESSION)
    dealt = _ids(first)
    assert len(dealt) == 8 and first["new_words_left_today"] == 10

    _answer(client, headers, dealt[:3])
    reload = _deck(client, headers, SESSION)
    assert _ids(reload) == dealt[3:], "a reload shows the rest of the batch, never new words"
    # The day's allowance is unchanged by a reload: 18 − 3 answered − 5 still dealt.
    assert reload["new_words_left_today"] == 10
    # A second reload is the same deck again.
    assert _ids(_deck(client, headers, SESSION)) == dealt[3:]

    batch = drill_batch.load_batch(db_session, user, local_today(user))
    db_session.refresh(batch)
    assert batch.cursor == 3 and [item["word_id"] for item in batch.items if item["list"] == "new_words"] == dealt

    # Once the batch is answered, the next request deals the next one.
    _answer(client, headers, dealt[3:])
    nxt = _deck(client, headers, SESSION)
    assert len(nxt["new_words"]) == 8 and not set(_ids(nxt)) & set(dealt)
    assert nxt["new_words_left_today"] == 2


def test_a_new_app_day_deals_a_new_batch(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 40, "wp154d")
    dealt = _ids(_deck(client, headers, SESSION))
    _answer(client, headers, dealt[:3])
    # The batch was dealt on the learner's previous app day.
    batch = drill_batch.load_batch(db_session, user, local_today(user))
    batch.day = local_today(user) - timedelta(days=1)
    db_session.commit()

    today = _deck(client, headers, SESSION)
    # A fresh deal: the five still unanswered lead the list, three more follow.
    assert len(today["new_words"]) == 8 and _ids(today)[:5] == dealt[3:]
    rows = db_session.query(VocabularyDrillBatch).filter(VocabularyDrillBatch.user_id == user.id).all()
    assert [row.day for row in rows] == [local_today(user)], "one row per learner: yesterday's is spent"


def test_the_top_up_appends_and_never_repeats_a_word(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 40, "wp154t")
    first = _deck(client, headers, SESSION)
    dealt = _ids(first)
    _answer(client, headers, dealt)
    left = first["new_words_left_today"]
    assert left == 10

    more = _deck(client, headers, _more(min(8, left)))
    added = _ids(more)
    assert len(added) == 8 and not set(added) & set(dealt)
    assert more["new_words_left_today"] == 2

    batch = drill_batch.load_batch(db_session, user, local_today(user))
    db_session.refresh(batch)
    stored = [item["word_id"] for item in batch.items if item["list"] == "new_words"]
    assert stored == dealt + added, "the continuation is appended to the day's batch"

    # A reload mid-continuation serves the rest of it.
    _answer(client, headers, added[:2])
    assert _ids(_deck(client, headers, SESSION)) == added[2:]
    _answer(client, headers, added[2:])
    last = _deck(client, headers, _more(2))
    assert len(last["new_words"]) == 2 and not set(_ids(last)) & set(dealt + added)
    assert last["new_words_left_today"] == 0
    introduced = dealt + added + _ids(last)
    assert len(introduced) == len(set(introduced)) == 18


def test_two_tabs_share_the_batch(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 40, "wp154w")
    tab_a = _deck(client, headers, SESSION)
    tab_b = _deck(client, headers, SESSION)
    assert _ids(tab_a) == _ids(tab_b)
    _answer(client, headers, _ids(tab_a)[:4])
    assert _ids(_deck(client, headers, SESSION)) == _ids(tab_a)[4:]
    assert db_session.query(VocabularyDrillBatch).filter(VocabularyDrillBatch.user_id == user.id).count() == 1


def test_another_learners_batch_is_never_served(client: TestClient, db_session: Session) -> None:
    headers_a, user_a = _login(client, db_session)
    headers_b, user_b = _login(client, db_session)
    _supply(db_session, 40, "wp154o")
    dealt_a = _ids(_deck(client, headers_a, SESSION))
    assert drill_batch.load_batch(db_session, user_b, local_today(user_b)) is None
    _answer(client, headers_a, dealt_a[:3])

    deck_b = _deck(client, headers_b, SESSION)
    # B is dealt their own deck: all eight, not what is left of A's.
    assert len(deck_b["new_words"]) == 8 and _ids(deck_b)[:3] == dealt_a[:3]
    _answer(client, headers_b, _ids(deck_b)[:1])
    assert _ids(_deck(client, headers_b, SESSION)) == _ids(deck_b)[1:]
    assert _ids(_deck(client, headers_a, SESSION)) == dealt_a[3:]
    rows = db_session.query(VocabularyDrillBatch).filter(
        VocabularyDrillBatch.user_id.in_([user_a.id, user_b.id])
    ).all()
    assert sorted(str(row.user_id) for row in rows) == sorted([str(user_a.id), str(user_b.id)])


def test_a_word_the_journey_reserves_later_leaves_the_batch(db_session: Session) -> None:
    from tests.test_journey_events import make_user

    user = make_user(db_session, f"wp154-{uuid.uuid4().hex[:8]}@example.com")
    items = [
        {"word_id": 11, "list": "new_words", "bucket": "new", "at": "2026-10-08T08:00:00+00:00"},
        {"word_id": 12, "list": "new_words", "bucket": "new", "at": "2026-10-08T08:00:00+00:00"},
    ]
    assert drill_batch.remaining_items(db_session, user, items, reserved_new={12}) == items[:1]


def test_the_review_only_encore_keeps_no_batch(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 10, "wp154e")
    deck = _deck(client, headers, {"limit": 15, "due_limit": 15, "fragile_limit": 15, "new_limit": 0,
                                   "topic_limit": 0, "linked_limit": 0})
    assert deck["new_words"] == []
    assert drill_batch.load_batch(db_session, user, local_today(user)) is None
