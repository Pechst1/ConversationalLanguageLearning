"""P7 (pilot, 17 Nov 2026; review finding 4) — a word deck made of the story and the learner.

The walk's logs (a1-/b1-part1…3): of about twenty daily words one to five came
from the scene, the rest a frequency list; «valise», kept with «Behalten» and
promised «es kommt morgen wieder», was in no deck on days 2 to 5; the gentle
restart after four days away dealt 100 cards (80 reviews); «frais» in «les frais
de changement du vol» was glossed «fresh; cool».

Guards: a kept word opens the next deck; all of the scene's words are dealt
inside the dose; after two or more missed days the deck holds 20 reviews, the
oldest due, and Home's minutes follow; «Normal» plans 15; a scene word shows the
sense its line gives it.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import vocabulary_pace
from app.services.streak import local_today

DAY_DECK = {
    "limit": 100,
    "due_limit": 100,
    "fragile_limit": 0,
    "new_limit": 50,
    "topic_limit": 0,
    "linked_limit": 0,
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
    db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(_CREATED)).delete(synchronize_session=False)
    db_session.commit()
    _CREATED.clear()


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *_a, **_k: 1.0)


def _word(db: Session, text: str) -> VocabularyWord:
    word = VocabularyWord(
        word=text,
        normalized_word=text,
        language="fr",
        english_translation=f"{text} (en)",
        german_translation=f"{text} (de)",
        example_sentence=f"Exemple du catalogue avec {text}.",
        part_of_speech="noun",
        is_anki_card=True,
        frequency_rank=1,
    )
    db.add(word)
    db.flush()
    _CREATED.append(int(word.id))
    return word


def _due(db: Session, user: User, word: VocabularyWord, *, now: datetime, days_ago: float = 1.0) -> None:
    at = now - timedelta(days=days_ago)
    db.add(
        UserVocabularyProgress(
            user_id=user.id, word_id=word.id, reps=3, state="review", scheduler="fsrs", stability=2.0,
            due_at=at, next_review_date=at, last_review_date=at - timedelta(days=3),
            created_at=now - timedelta(days=30),
        )
    )
    db.flush()


def _met_today(db: Session, user: User, word: VocabularyWord, *, now: datetime) -> None:
    start, _end = vocabulary_pace._local_window(user, now)
    db.add(
        UserVocabularyProgress(
            user_id=user.id, word_id=word.id, reps=1, state="learning", scheduler="fsrs", stability=0.5,
            due_at=now + timedelta(hours=6), next_review_date=now + timedelta(hours=6),
            last_review_date=now, created_at=max(now - timedelta(minutes=20), start),
        )
    )
    db.flush()


def _login(client: TestClient, db: Session, *, pace: str | None = "normal") -> tuple[dict, User]:
    email = f"p7-deck-{uuid.uuid4().hex[:8]}@example.com"
    password = "p7-deck-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "de"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db.get(User, UUID(str(decode_token(token)["sub"])))
    user.daily_goal_minutes = 10
    user.daily_pace = pace
    # A learner stored at Normal's old twenty: the pace speaks for the words.
    user.new_words_per_day = 20
    user.timezone = "Europe/Paris"
    user.default_vocab_direction = None
    db.flush()
    return {"Authorization": f"Bearer {token}"}, user


def _all_cards(deck: dict) -> dict[int, dict]:
    cards: dict[int, dict] = {}
    for name in ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words"):
        for card in deck[name]:
            cards.setdefault(card["word_id"], card)
    return cards


def test_normal_plans_fifteen_new_words(client: TestClient, db_session: Session) -> None:
    """Owner decision 1: «Normal» deals 15 a day, a learner stored at the old 20 too;
    a custom number (no pace) is untouched."""

    from app.services import day_words
    from app.services.daily_session import PACES

    assert PACES["normal"].words == 15
    _headers, user = _login(client, db_session)
    assert day_words.make_plan(db_session, user, now=datetime.now(UTC))["quota"] == 15
    user.daily_pace = None  # a custom number of their own
    db_session.flush()
    assert day_words.make_plan(db_session, user, now=datetime.now(UTC))["quota"] == 20


def test_a_word_kept_on_day_one_opens_day_twos_deck(client: TestClient, db_session: Session) -> None:
    """«valise» kept with «Behalten» yesterday is the first card of today's deck,
    with thirty other reviews due and a review cap that cuts the list."""

    from app.services.kept_words import keep_word

    headers, user = _login(client, db_session)
    user.max_reviews_per_day = 20  # the day's review list is cut
    now = datetime.now(UTC)
    for index in range(30):
        _due(db_session, user, _word(db_session, f"pseptrev{index:02d}{uuid.uuid4().hex[:4]}"), now=now, days_ago=2 + index / 10)
    _word(db_session, "valise")
    yesterday = now - timedelta(days=1)
    kept = keep_word(
        db_session, user=user, term="valise", sentence="Ma valise est restée à Lyon.", now=yesterday
    )
    row = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=kept.word_id).one()
    row.created_at = yesterday
    db_session.commit()

    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_DECK)
    assert response.status_code == 200, response.text
    deck = response.json()
    assert deck["deck_order"][0] == kept.word_id, deck["deck_order"][:5]
    assert _all_cards(deck)[kept.word_id]["kept_word"] is True


def test_every_scene_word_is_dealt_inside_the_dose(client: TestClient, db_session: Session) -> None:
    """Six scene words and a dose of 15: all six dealt, fifteen new words in all."""

    headers, user = _login(client, db_session, pace=None)
    user.new_words_per_day = 15  # the dose alone, whatever the pace table says
    now = datetime.now(UTC)
    scene = [_word(db_session, f"pscene{index}{uuid.uuid4().hex[:4]}") for index in range(6)]
    for word in scene:
        _met_today(db_session, user, word, now=now)
    journey = DailyJourney(
        id=uuid.uuid4(), user_id=user.id, local_date=local_today(user, now), timezone="Europe/Paris",
        status="completed", budget_seconds=600,
        plan_selection={vocabulary_pace.JOURNEY_NEW_WORDS_KEY: [word.id for word in scene]}, created_at=now,
    )
    db_session.add(journey)
    for index in range(20):
        _word(db_session, f"pnew{index:02d}{uuid.uuid4().hex[:4]}")
    db_session.commit()

    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_DECK)
    assert response.status_code == 200, response.text
    deck = response.json()
    cards = _all_cards(deck)
    scene_ids = {word.id for word in scene}
    assert scene_ids <= set(cards), "every scene word is a card of the deck"
    fresh = [word_id for word_id, card in cards.items() if word_id not in scene_ids and card["bucket"] == "new"]
    assert len(scene_ids) + len(fresh) == 15, (len(fresh), sorted(cards))
    order = deck["deck_order"]
    # The scene's words before the scheduler's.
    assert set(order[:6]) == scene_ids, order


def test_a_return_after_four_days_holds_twenty_reviews_and_its_minutes(
    client: TestClient, db_session: Session
) -> None:
    """Four missed days, eighty due: twenty reviews, the oldest due; Home's count and
    minutes say twenty; the next day still caps while the backlog is twenty or more."""

    from app.services import daily_session, day_words

    _headers, user = _login(client, db_session)
    now = datetime.now(UTC)
    today = local_today(user, now)
    user.grammar_last_review_date = today - timedelta(days=5)  # four whole days missed
    words = [_word(db_session, f"pret{index:02d}{uuid.uuid4().hex[:4]}") for index in range(80)]
    for index, word in enumerate(words):
        _due(db_session, user, word, now=now, days_ago=1 + index / 4)
    db_session.commit()

    day_words.ensure_plan(db_session, user, now=now)
    new, reviews = daily_session.day_deck(db_session, user, reviews_due=80, now=now)
    assert reviews == 20, (new, reviews)
    seconds = daily_session.day_words_seconds(db_session, user, reviews_due=80, now=now)
    assert seconds == daily_session.words_seconds(new, 20)
    from app.services import drill_batch

    plan = day_words.read_plan(drill_batch.load_batch(db_session, user, today))
    oldest = {word.id for word in words[-20:]}
    assert set(plan["reviews"]) == oldest, "the oldest due first"

    # The next day, back to a daily rhythm: still capped while the backlog stands.
    user.grammar_last_review_date = today
    db_session.flush()
    tomorrow = day_words.make_plan(db_session, user, now=now + timedelta(days=1))
    assert len(tomorrow["reviews"]) == 20 and tomorrow["review_cap"] is True


def test_a_scene_word_shows_the_sense_its_line_gives_it() -> None:
    from app.services.scene_deck import mark_scene_words, scene_lines

    draft = {
        "panels": [
            {
                "narration_fr": "",
                "dialogue": [
                    {
                        "text_fr": "Les frais de changement du vol sont élevés.",
                        "text_native": "Die Umbuchungsgebühren sind hoch.",
                    }
                ],
            }
        ],
        "lexicon": [
            {"lemma": "frais", "surface_fr": "frais", "gloss_native": "Gebühren", "line_ref": "panel:0:line:0"}
        ],
    }
    lines = scene_lines(
        draft=draft, journey_id=None, words={7: SimpleNamespace(word="frais")}, progress={}, candidates={7}
    )
    payload = {"new_words": [{"word_id": 7, "translation": "frisch; kühl", "translation_language": "de"}]}
    card = mark_scene_words(payload, scene_ids={7}, lines=lines, gloss_language="de")["new_words"][0]
    assert card["translation"] == "Gebühren"
    assert card["example_sentence"] == "Les frais de changement du vol sont élevés."
    # No lexicon gloss: the dictionary's stays.
    draft["lexicon"][0]["gloss_native"] = ""
    lines = scene_lines(
        draft=draft, journey_id=None, words={7: SimpleNamespace(word="frais")}, progress={}, candidates={7}
    )
    payload = {"new_words": [{"word_id": 7, "translation": "frisch; kühl", "translation_language": "de"}]}
    assert mark_scene_words(payload, scene_ids={7}, lines=lines, gloss_language="de")["new_words"][0][
        "translation"
    ] == "frisch; kühl"


def test_the_deck_order_is_kept_then_reviews_then_every_scene_word_then_the_scheduler() -> None:
    from app.services.deck_order import deck_order

    def card(word_id: int, bucket: str, **extra: object) -> dict:
        return {"word_id": word_id, "bucket": bucket, **extra}

    payload = {
        "due_words": [card(1, "due"), card(2, "due"), card(3, "due", kept_word=True)],
        "fragile_words": [],
        "linked_words": [],
        "topic_compatible_words": [],
        "new_words": [card(4, "new"), card(5, "new", scene_word=True), card(6, "new", scene_word=True), card(7, "new")],
    }
    assert deck_order(payload) == [3, 1, 2, 5, 6, 4, 7]
    assert deck_order(payload, slate_ids=[7]) == [3, 1, 2, 5, 6, 7, 4]
