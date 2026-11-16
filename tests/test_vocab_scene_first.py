"""Owner request, 2 November — the word deck asks the scheduler's words first.

«Der Wörterstapel soll primär die Wörter abfragen, die als nächstes durch den
Scheduler vorgeschlagen werden … gleichzeitig sollen auch Wörter aus den Szenen
genommen werden … aber lieber die Wörter, die nach dem Scheduler kommen.»

PR #465 (1 Nov) had put today's scene words first. Now (``app/services/deck_order.py``):
every due review first in the scheduler's order; today's scene words take at
most a third of the new-word slots (at least one), out of the new-word budget,
never on top of it; the rest are the scheduler's next new words. A scene word's
card still quotes the scene line it appeared in (#472: never the episode title).
The order is decided once, on the server (``deck_order``).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from fractions import Fraction
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
from app.services.deck_order import SCENE_SHARE_OF_NEW_WORDS, deck_order, mix_new_words, scene_slots
from app.services.scene_deck import quotable_texts, scene_lines
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


def _due(db: Session, user: User, word: VocabularyWord, *, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
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


def _todays_scene(
    db: Session, user: User, *, reserved: list[int], status: str = "completed", now: datetime | None = None
) -> DailyJourney:
    """Today's journey, over: two reserved words, a lexicon and translated lines."""

    now = now or datetime.now(UTC)
    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=local_today(user, now),
        timezone="Europe/Paris",
        status=status,
        budget_seconds=600,
        plan_selection={vocabulary_pace.JOURNEY_NEW_WORDS_KEY: list(reserved)},
        created_at=now,
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


def test_due_reviews_come_first_and_scene_words_take_at_most_a_third_of_the_new_slots(
    client: TestClient, db_session: Session
) -> None:
    """A day with D due reviews and S scene words: every due review before any new
    word, and the scene words take at most floor(new_slots / 3) of the new slots."""

    headers, user = _login(client, db_session)
    user.new_words_per_day = 9  # nine new-word slots in the day deck
    db_session.flush()
    reviews = [_word(db_session, f"scnrev{index}{uuid.uuid4().hex[:4]}") for index in range(3)]
    for word in reviews:
        _due(db_session, user, word)
    # A review the scene's lexicon featured: a review still, quoting the scene.
    horloge = _word(db_session, "horloge", gender="f")
    _due(db_session, user, horloge)
    # Six scene words, reserved by today's journey and left unmet: twice the share.
    lanterne = _word(db_session, "lanterne", gender="f")
    grenier = _word(db_session, "grenier", gender="m")
    minuit = _word(db_session, "minuit", gender="m")
    others = [_word(db_session, f"scnres{index}{uuid.uuid4().hex[:4]}") for index in range(3)]
    reserved = [lanterne.id, grenier.id, minuit.id, *(word.id for word in others)]
    _todays_scene(db_session, user, reserved=reserved)
    # The scheduler's own next new words.
    for index in range(12):
        _word(db_session, f"scnnew{index:02d}{uuid.uuid4().hex[:4]}")
    db_session.commit()

    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_DECK)
    assert response.status_code == 200, response.text
    deck = response.json()
    order = deck["deck_order"]
    cards = _all_cards(deck)
    assert set(order) == set(cards), "the order names every card of the deck, once"
    assert len(order) == len(set(order))

    due = [word.id for word in (*reviews, horloge)]
    # Every due review first, before any new word.
    assert set(order[: len(due)]) == set(due), order
    new_slots = order[len(due):]
    assert len(new_slots) == 9, "the scene's share comes out of the nine new-word slots, never on top"
    scene_cards = [word_id for word_id in new_slots if cards[word_id]["scene_word"]]
    assert 1 <= len(scene_cards) <= len(new_slots) // 3, (scene_cards, new_slots)
    assert set(scene_cards) <= set(reserved)
    # The rest are the scheduler's next new words, none of the scene's left over.
    assert not set(new_slots) - set(scene_cards) & set(reserved)
    # Spread, not bunched: the scheduler's word opens the new words.
    assert not cards[new_slots[0]]["scene_word"]

    # Each scene card quotes the scene line holding its word.
    assert cards[lanterne.id]["example_sentence"] == "Passe-moi la lanterne, vite !"
    assert cards[lanterne.id]["example_translation"] == "Gib mir die Laterne, schnell!"
    assert cards[grenier.id]["example_sentence"] == "On monte au grenier."
    assert cards[grenier.id]["example_translation"] is None
    assert cards[minuit.id]["example_sentence"] == "L'horloge sonne minuit."
    # The featured review stays a review and quotes its line too.
    assert not cards[horloge.id]["scene_word"]
    assert cards[horloge.id]["example_sentence"] == "L'horloge sonne minuit."
    assert cards[horloge.id]["example_translation"] == "Die Uhr schlägt Mitternacht."
    # A word that was not in the scene keeps the catalogue's example.
    assert cards[reviews[0].id]["example_sentence"].startswith("Exemple du catalogue")
    # A reload is the same deck.
    again = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_DECK).json()
    assert again["deck_order"] == order


def _met_today(db: Session, user: User, word: VocabularyWord, *, now: datetime | None = None) -> None:
    """The scene introduced ``word`` today (its progress row is today's).

    Twenty minutes ago, but never before the learner's midnight: at 00:05 in Berlin
    twenty minutes ago is yesterday, and the word was not met today (9 Nov CI)."""

    now = now or datetime.now(UTC)
    start, _end = vocabulary_pace._local_window(user, now)
    db.add(
        UserVocabularyProgress(
            user_id=user.id, word_id=word.id, reps=1, state="learning", scheduler="fsrs", stability=0.5,
            due_at=now + timedelta(hours=6), next_review_date=now + timedelta(hours=6),
            created_at=max(now - timedelta(minutes=20), start),
        )
    )
    db.flush()


@pytest.mark.parametrize("scene_status", ["completed", "active"])
def test_the_scene_share_never_takes_the_day_past_its_intake(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, scene_status: str, learner_clock: datetime
) -> None:
    """Codex on PR #487: quota 9, six words the scene introduced (``completed``) or has
    still to introduce (``active``). Leaving five of them out of the deck frees no
    intake: the scheduler's replacements stop at the day's nine, and Home's count
    is the deck's."""

    from app.services import daily_session, day_words, drill_batch, vocabulary_pace
    from app.services.deck_order import scene_slots as share_of
    from app.services.streak import local_today
    from app.services.vocabulary_pace import introduced_today

    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *_a, **_k: 1.0)
    headers, user = _login(client, db_session)
    user.new_words_per_day = 9
    db_session.flush()
    reviews = [_word(db_session, f"scnirev{index}{uuid.uuid4().hex[:4]}") for index in range(2)]
    now = learner_clock
    for word in reviews:
        _due(db_session, user, word, now=now)
    scene_words = [_word(db_session, f"scnin{index}{uuid.uuid4().hex[:4]}") for index in range(6)]
    if scene_status == "completed":
        for word in scene_words:
            _met_today(db_session, user, word, now=now)
    _todays_scene(db_session, user, reserved=[word.id for word in scene_words], status=scene_status, now=now)
    for index in range(12):
        _word(db_session, f"scninew{index:02d}{uuid.uuid4().hex[:4]}")
    db_session.commit()

    db_session.expire_all()
    # Home's first read of the day picks the day's plan (``build_session``), then counts it.
    day_words.ensure_plan(db_session, user)
    home_new, home_reviews = daily_session.day_deck(db_session, user, reviews_due=len(reviews))
    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_DECK)
    assert response.status_code == 200, response.text
    deck = response.json()
    cards = _all_cards(deck)
    order = deck["deck_order"]
    db_session.expire_all()
    batch = drill_batch.load_batch(db_session, user, local_today(user))
    size = day_words.dealt_size(batch)
    pending = int(size or 0) - len(cards)

    # Home's count is the deck: the cards dealt and the scene's still to come.
    assert home_new + home_reviews == size, (home_new, home_reviews, size, len(cards))
    assert sum(daily_session.day_deck(db_session, user, reviews_due=len(reviews))) == size

    # The day introduces at most its nine: today's introductions, the deck's new
    # cards, and the scene's reservations still to come.
    scene_ids = {word.id for word in scene_words}
    deck_new = {word_id for word_id, card in cards.items() if word_id not in scene_ids and card["bucket"] == "new"}
    still_to_come = scene_ids - introduced_today(db_session, user) if scene_status == "active" else set()
    introductions = introduced_today(db_session, user) | deck_new | still_to_come
    assert len(introductions) <= 9, (len(introductions), len(deck_new), len(still_to_come))

    # The rule holds: reviews first, the scene's share at most a third of the new slots.
    review_ids = {word.id for word in reviews}
    assert set(order[: len(review_ids)]) == review_ids, order
    scene_slots_held = sum(1 for word_id in cards if word_id in scene_ids) + pending
    new_slots = len(cards) - len(review_ids) + pending
    assert 1 <= scene_slots_held <= share_of(new_slots, scene_slots_held) <= max(1, new_slots // 3)
    assert len(deck_new) == 3, "the scheduler fills what the intake leaves, no more"


def test_the_deck_order_puts_reviews_first_and_mixes_a_third_of_scene_words_into_the_new() -> None:
    def card(word_id: int, bucket: str, **extra: object) -> dict:
        return {"word_id": word_id, "bucket": bucket, **extra}

    payload = {
        "due_words": [card(1, "due"), card(2, "due", ladder="scene"), card(3, "due", ladder="rescue")],
        "fragile_words": [card(4, "fragile")],
        "linked_words": [],
        "topic_compatible_words": [],
        "new_words": [
            card(5, "new"),
            card(6, "new"),
            card(7, "new", scene_word=True),
            card(8, "new"),
            card(9, "new", scene_word=True),
            card(10, "new"),
            card(1, "new"),
        ],
    }
    # Reviews in the scheduler's order; then the new words, a scene word every third card.
    assert deck_order(payload) == [1, 2, 3, 4, 5, 6, 7, 8, 10, 9]
    # Today's slate words lead the scheduler's new words.
    assert deck_order(payload, slate_ids=[8]) == [1, 2, 3, 4, 8, 5, 7, 6, 10, 9]


@pytest.mark.parametrize(
    ("new_slots", "scene", "expected"),
    [(0, 3, 0), (5, 0, 0), (1, 4, 1), (2, 4, 1), (3, 4, 1), (9, 6, 3), (10, 6, 3), (12, 2, 2), (50, 40, 16)],
)
def test_scene_slots_is_a_third_rounded_down_but_at_least_one(new_slots: int, scene: int, expected: int) -> None:
    assert scene_slots(new_slots, scene) == expected
    assert SCENE_SHARE_OF_NEW_WORDS == Fraction(1, 3)


def test_mix_new_words_never_lets_the_scene_run_ahead_of_its_share() -> None:
    for scheduler_count in range(0, 12):
        for scene_count in range(0, 12):
            scheduler = [f"s{index}" for index in range(scheduler_count)]
            scene = [f"c{index}" for index in range(scene_count)]
            mixed = mix_new_words(scheduler, scene)
            assert sorted(mixed) == sorted(scheduler + scene)
            share = scene_slots(scheduler_count + scene_count, scene_count)
            head = mixed[: len(mixed) - (scene_count - share)]
            assert sum(item.startswith("c") for item in head) == share
            assert [item for item in mixed if item.startswith("s")] == scheduler, "the scheduler's order holds"
            if scheduler_count >= 2 * share:
                for end in range(1, len(head) + 1):
                    assert sum(item.startswith("c") for item in head[:end]) <= max(1, end // 3) or end < 3


def test_472_a_scene_line_is_never_the_episode_title() -> None:
    """An authored day B (no caption) is published with its title in premise_fr and
    opening_line_fr: «la lettre» quoted the title «La lettre» (walk, 2 Nov)."""

    draft = {
        "title_fr": "La lettre",
        "premise_fr": "La lettre",
        "opening_line_fr": "La lettre",
        "chapter": {"title_fr": "La lettre"},
        "panels": [
            {"narration_fr": "", "dialogue": [{"text_fr": "Un chocolat ?", "text_native": "Eine Schokolade?"}]},
            {
                "narration_fr": "",
                "dialogue": [
                    {
                        "text_fr": "Leur prix est dans votre lettre. Avant le 8 janvier.",
                        "text_native": "Ihr Preis steht in Ihrem Brief. Vor dem 8. Januar.",
                    }
                ],
            },
        ],
        "lexicon": [{"lemma": "lettre", "surface_fr": "lettre", "line_ref": "premise"}],
    }
    words = {1: SimpleNamespace(word="la lettre"), 2: SimpleNamespace(word="le prix")}
    lines = scene_lines(draft=draft, journey_id="j", words=words, progress={}, candidates={2})
    assert lines[1]["sentence_fr"] == "Leur prix est dans votre lettre. Avant le 8 janvier."
    assert lines[1]["translation"] == "Ihr Preis steht in Ihrem Brief. Vor dem 8. Januar."
    assert lines[2]["sentence_fr"].startswith("Leur prix")
    assert "La lettre" not in quotable_texts(draft).values()
    # A word printed only in the title has no scene line at all (the catalogue's example stays).
    only_title = {**draft, "lexicon": [{"lemma": "lettre", "surface_fr": "lettre", "line_ref": "premise"}], "panels": []}
    assert scene_lines(draft=only_title, journey_id="j", words=words, progress={}, candidates={1}) == {}


def test_472_season_one_day_two_quotes_a_line_of_the_scene_for_lettre() -> None:
    """The walk's own page: Season 1, t1 day B, an A1 learner."""

    from datetime import date

    from app.services.season import runtime
    from app.services.season.clock import Position
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    page = resolve_day(season, "t1", "b", flags={}, band="A1.1", language="de")
    index, segment = next((i, seg) for i, seg in enumerate(season.segments) if seg.id == "t1")
    today = SimpleNamespace(
        language="de", season=season, pos=Position(season.id, segment, index, 2, 59),
        local_date=date(2026, 11, 2), band="A1.1", flags={}, state={},
    )
    draft = runtime.authored_draft(today, page, page.get("turns") or [])
    assert draft["premise_fr"] == draft["title_fr"] == "La lettre", "the page this guard is about"
    words = {1: SimpleNamespace(word="la lettre")}
    line = scene_lines(draft=draft, journey_id="j", words=words, progress={}, candidates={1})[1]["sentence_fr"]
    spoken = [line_["text_fr"] for panel in draft["panels"] for line_ in panel["dialogue"]]
    assert line != "La lettre"
    assert any(line in text or text in line for text in spoken), line
    assert "lettre" in line
