"""Owner request, 1 November — the day deck opens on today's scene words.

In the day's word deck (``review.tsx?day=1``) a word that appeared in today's
scene comes first, and its card quotes the scene line it appeared in, with the
line's translation when the scene carried one. The order is decided once, on
the server (``deck_order``), so every client shows the same deck.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
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
from app.services.deck_order import deck_order
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


@pytest.fixture(scope="module", autouse=True)
def _leave_the_catalogue_as_found(db_engine):
    """A day deck may sync the core list into the shared database; it leaves with the module."""

    from sqlalchemy.orm import sessionmaker

    from app.services.core_lexicon import CORE_DECK

    db = sessionmaker(bind=db_engine)()
    had_core = db.query(VocabularyWord.id).filter(VocabularyWord.deck_name == CORE_DECK).first() is not None
    db.close()
    yield
    if had_core:
        return
    db = sessionmaker(bind=db_engine)()
    core = db.query(VocabularyWord.id).filter(VocabularyWord.deck_name == CORE_DECK).subquery()
    progress = db.query(UserVocabularyProgress.id).filter(UserVocabularyProgress.word_id.in_(core)).subquery()
    db.query(ReviewLog).filter(ReviewLog.progress_id.in_(progress)).delete(synchronize_session=False)
    db.query(UserVocabularyProgress).filter(UserVocabularyProgress.word_id.in_(core)).delete(synchronize_session=False)
    db.query(VocabularyWord).filter(VocabularyWord.deck_name == CORE_DECK).delete(synchronize_session=False)
    db.commit()
    db.close()


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


def _word(db: Session, text: str, *, gender: str | None = None) -> VocabularyWord:
    word = VocabularyWord(
        word=text,
        normalized_word=text,
        language="fr",
        english_translation=f"{text} (en)",
        german_translation=f"{text} (de)",
        example_sentence=f"Exemple du catalogue avec {text}.",
        example_translation=f"Katalogbeispiel mit {text}.",
        part_of_speech="noun",
        gender=gender,
        is_anki_card=True,
        frequency_rank=1,
    )
    db.add(word)
    db.flush()
    _CREATED.append(int(word.id))
    return word


def _due(db: Session, user: User, word: VocabularyWord) -> None:
    now = datetime.now(UTC)
    db.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=word.id,
            reps=3,
            state="review",
            scheduler="fsrs",
            stability=2.0,
            due_at=now - timedelta(days=1),
            next_review_date=now - timedelta(days=1),
            created_at=now - timedelta(days=12),
        )
    )
    db.flush()


def _login(client: TestClient, db: Session) -> tuple[dict, User]:
    email = f"scene-first-{uuid.uuid4().hex[:8]}@example.com"
    password = "scene-first-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "de"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db.get(User, UUID(str(decode_token(token)["sub"])))
    user.daily_goal_minutes = 10
    user.new_words_per_day = None
    user.daily_pace = None
    user.timezone = "Europe/Paris"
    user.default_vocab_direction = None  # the test's cards carry no direction
    db.flush()
    return {"Authorization": f"Bearer {token}"}, user


def _todays_scene(db: Session, user: User, *, reserved: list[int]) -> DailyJourney:
    """Today's journey, over: two reserved words, a lexicon and translated lines."""

    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=local_today(user),
        timezone="Europe/Paris",
        status="completed",
        budget_seconds=600,
        plan_selection={vocabulary_pace.JOURNEY_NEW_WORDS_KEY: list(reserved)},
        created_at=datetime.now(UTC),
    )
    db.add(journey)
    db.flush()
    draft = {
        "premise_fr": "Une nuit au vieux moulin.",
        "panels": [
            {
                "narration_fr": "Le vent souffle.",
                "dialogue": [
                    {"text_fr": "Passe-moi la lanterne, vite !", "text_native": "Gib mir die Laterne, schnell!"},
                    {"text_fr": "On monte au grenier. Il fait noir.", "text_native": None},
                    {"text_fr": "L'horloge sonne minuit.", "text_native": "Die Uhr schlägt Mitternacht."},
                ],
            }
        ],
        "lexicon": [
            {"lemma": "lanterne", "surface_fr": "lanterne", "line_ref": "panel:0:line:0"},
            {"lemma": "horloge", "surface_fr": "horloge", "line_ref": "panel:0:line:2"},
        ],
    }
    db.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=0,
            kind="scene",
            status="completed",
            private_task={"scenario_brief": {"story_context": {"draft": draft}}},
        )
    )
    db.flush()
    return journey


def _all_cards(deck: dict) -> dict[int, dict]:
    cards: dict[int, dict] = {}
    for name in ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words"):
        for card in deck[name]:
            cards.setdefault(card["word_id"], card)
    return cards


def test_the_day_deck_opens_on_todays_scene_words_with_their_lines(client: TestClient, db_session: Session) -> None:
    headers, user = _login(client, db_session)
    reviews = [_word(db_session, f"scnrev{index}{uuid.uuid4().hex[:4]}") for index in range(3)]
    for word in reviews:
        _due(db_session, user, word)
    # A review the scene's lexicon featured (a studied word met again in the story).
    horloge = _word(db_session, "horloge", gender="f")
    _due(db_session, user, horloge)
    # The scene's own new words, reserved by today's journey and left unmet.
    lanterne = _word(db_session, "lanterne", gender="f")
    grenier = _word(db_session, "grenier", gender="m")
    _todays_scene(db_session, user, reserved=[lanterne.id, grenier.id])
    db_session.commit()

    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_DECK)
    assert response.status_code == 200, response.text
    deck = response.json()
    order = deck["deck_order"]
    scene = {horloge.id, lanterne.id, grenier.id}
    assert set(order[: len(scene)]) == scene, order
    # Inside the scene group the payload's own order holds: the review first, then the new words as dealt.
    assert order[: len(scene)] == [horloge.id, lanterne.id, grenier.id]
    # Then the reviews, before anything new.
    review_ids = {word.id for word in reviews}
    assert set(order[len(scene): len(scene) + len(review_ids)]) == review_ids

    cards = _all_cards(deck)
    assert all(cards[word_id]["scene_word"] for word_id in scene)
    assert not any(cards[word.id]["scene_word"] for word in reviews)
    assert cards[lanterne.id]["example_sentence"] == "Passe-moi la lanterne, vite !"
    assert cards[lanterne.id]["example_translation"] == "Gib mir die Laterne, schnell!"
    assert cards[horloge.id]["example_sentence"] == "L'horloge sonne minuit."
    assert cards[horloge.id]["example_translation"] == "Die Uhr schlägt Mitternacht."
    # A line the scene did not translate is quoted without a translation (never the catalogue's).
    assert cards[grenier.id]["example_sentence"] == "On monte au grenier."
    assert cards[grenier.id]["example_translation"] is None
    # A word that was not in the scene keeps the catalogue's example.
    assert cards[reviews[0].id]["example_sentence"].startswith("Exemple du catalogue")


def test_the_deck_order_keeps_the_existing_tiers_after_the_scene_words() -> None:
    def card(word_id: int, bucket: str, **extra: object) -> dict:
        return {"word_id": word_id, "bucket": bucket, **extra}

    payload = {
        "due_words": [card(1, "due"), card(2, "due", ladder="scene"), card(3, "due", ladder="rescue")],
        "fragile_words": [card(4, "fragile")],
        "linked_words": [],
        "topic_compatible_words": [],
        "new_words": [card(5, "new"), card(6, "new"), card(7, "new", scene_word=True), card(1, "new")],
    }
    # Scene word, rescue, own line, reviews, slate, the rest; each id once.
    assert deck_order(payload, slate_ids=[6]) == [7, 3, 2, 1, 4, 6, 5]
    assert deck_order(payload) == [7, 3, 2, 1, 4, 5, 6]
