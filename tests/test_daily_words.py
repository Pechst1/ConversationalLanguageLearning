"""Les Mots du jour — daily word slate selection, stamping, and surface wiring."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import UserDailyWordSlate, VocabularyWord
from app.services.daily_words import SLATE_SIZE, DailyWordSlateService
from app.services.missions import MissionGenerator


def _make_user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        native_language="en",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_due_word(db_session, user: User, word: str, *, rank: int) -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word,
        frequency_rank=rank,
        german_translation=f"{word}-de",
        english_translation=f"{word}-en",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
        example_sentence=f"Voici {word} dans une phrase.",
    )
    db_session.add(row)
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=row.id,
            scheduler="fsrs",
            state="reviewing",
            phase="review",
            due_at=datetime.now(UTC) - timedelta(days=1),
            due_date=(datetime.now(UTC) - timedelta(days=1)).date(),
            next_review_date=datetime.now(UTC) - timedelta(days=1),
            last_review_date=datetime.now(UTC) - timedelta(days=5),
            stability=2.0,
            difficulty=7.0,
            scheduled_days=2,
            reps=5,
        )
    )
    return row


def _make_scene(db_session, user: User, *, word_ids: list[int], episode_index: int | None = 2) -> GraphicNovelScene:
    scene = GraphicNovelScene(
        user_id=user.id,
        status="available",
        title="Le radiateur froid",
        brief="Une scène de test.",
        episode_index=episode_index,
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=word_ids,
        source_snapshot={},
        script_payload={},
        recap_payload={},
        cache_key=uuid4().hex,
        prompt_version="test",
        image_model="test",
        image_quality="low",
    )
    db_session.add(scene)
    db_session.flush()
    return scene


def test_slate_is_stable_for_the_day_and_capped(db_session) -> None:
    user = _make_user(db_session)
    for index in range(6):
        _make_due_word(db_session, user, f"mot{index}", rank=10 + index)
    db_session.commit()

    service = DailyWordSlateService(db_session)
    first = service.get_or_create(user=user)
    second = service.get_or_create(user=user)

    assert first["words"], "slate should pick due words"
    assert len(first["words"]) <= SLATE_SIZE
    assert [entry["word_id"] for entry in first["words"]] == [entry["word_id"] for entry in second["words"]]
    assert db_session.query(UserDailyWordSlate).filter(UserDailyWordSlate.user_id == user.id).count() == 1
    for entry in first["words"]:
        assert entry["stamps"] == {}
        assert entry["triple"] is False


def test_first_call_race_keeps_winner_without_rolling_back_outer_work(
    db_session,
    monkeypatch,
) -> None:
    user = _make_user(db_session)
    winner_payload = {
        "date": datetime.now(UTC).date().isoformat(),
        "words": [],
        "triples": 0,
        "version": "mots-du-jour-v1",
    }
    db_session.add(
        UserDailyWordSlate(
            user_id=user.id,
            slate_date=datetime.now(UTC).date(),
            payload=winner_payload,
        )
    )
    db_session.commit()

    # Simulate another request winning between our initial lookup and insert.
    service = DailyWordSlateService(db_session)
    real_row = service._row
    lookups = 0

    def raced_row(**kwargs):
        nonlocal lookups
        lookups += 1
        if lookups == 1:
            return None
        return real_row(**kwargs)

    monkeypatch.setattr(service, "_row", raced_row)
    user.full_name = "Must survive the slate race"

    assert service.get_or_create(user=user) == winner_payload
    db_session.commit()
    db_session.expire(user)
    assert user.full_name == "Must survive the slate race"


def test_slate_prefers_words_in_todays_scene_and_carries_anchor(db_session) -> None:
    user = _make_user(db_session)
    words = [_make_due_word(db_session, user, f"scene{index}", rank=20 + index) for index in range(6)]
    in_scene = words[-1]
    _make_scene(db_session, user, word_ids=[in_scene.id])
    db_session.commit()

    payload = DailyWordSlateService(db_session).get_or_create(user=user)

    first_entry = payload["words"][0]
    assert first_entry["word_id"] == in_scene.id
    assert "épisode 3" in (first_entry["anchor"] or "")


def test_record_encounter_stamps_and_detects_triple(db_session) -> None:
    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "tamponner", rank=30)
    db_session.commit()

    service = DailyWordSlateService(db_session)
    payload = service.get_or_create(user=user)
    assert any(entry["word_id"] == word.id for entry in payload["words"])

    assert service.record_encounter(user=user, word_id=word.id, kind="lu") is not None
    assert service.record_encounter(user=user, word_id=word.id, kind="lu") is None, "stamps are idempotent"
    assert service.record_encounter(user=user, word_id=word.id, kind="retrouve") is not None
    updated = service.record_encounter(user=user, word_id=word.id, kind="place")
    assert updated is not None and updated["triple"] is True

    refreshed = service.get_or_create(user=user)
    entry = next(item for item in refreshed["words"] if item["word_id"] == word.id)
    assert entry["triple"] is True
    assert refreshed["triples"] == 1

    assert service.record_encounter(user=user, word_id=999_999, kind="lu") is None
    assert service.record_encounter(user=user, word_id=word.id, kind="bogus") is None


def test_scene_completion_stamps_lu(db_session) -> None:
    from app.services.graphic_novel import GraphicNovelScheduler

    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "feuilletonner", rank=40)
    db_session.commit()

    service = DailyWordSlateService(db_session)
    service.get_or_create(user=user)
    scene = _make_scene(db_session, user, word_ids=[word.id])
    db_session.commit()

    GraphicNovelScheduler(db_session).complete(user=user, scene=scene)

    payload = service.get_or_create(user=user)
    entry = next(item for item in payload["words"] if item["word_id"] == word.id)
    assert entry["stamps"].get("lu")


def test_mission_vocabulary_selection_includes_slate_words(db_session) -> None:
    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "convoquer", rank=50)
    db_session.commit()

    slate = DailyWordSlateService(db_session).get_or_create(user=user)
    assert any(entry["word_id"] == word.id for entry in slate["words"])

    selected = MissionGenerator(db_session)._select_vocabulary(user=user, limit=3)
    selected_ids = {item["word_id"] for item in selected}
    assert word.id in selected_ids
    buckets = {item["word_id"]: item["bucket"] for item in selected}
    assert buckets[word.id] == "mot_du_jour"


def test_seeded_missions_keep_their_identity_without_slate_words(db_session) -> None:
    user = _make_user(db_session)
    slate_word = _make_due_word(db_session, user, "distraire", rank=55)
    explicit = VocabularyWord(
        language="fr",
        word="chauffage",
        normalized_word="chauffage",
        frequency_rank=70,
        german_translation="Heizung",
        direction="fr_to_de",
        is_anki_card=True,
    )
    db_session.add(explicit)
    db_session.commit()

    DailyWordSlateService(db_session).get_or_create(user=user)

    selected = MissionGenerator(db_session)._select_vocabulary(
        user=user, limit=1, preferred_vocabulary_ids=[explicit.id]
    )
    assert [item["word_id"] for item in selected] == [explicit.id]
    assert all(item["bucket"] != "mot_du_jour" for item in selected)
    assert slate_word.id not in {item["word_id"] for item in selected}


def test_words_of_the_day_endpoint_and_review_records_retrouve(client: TestClient, db_session) -> None:
    email = f"{uuid4()}@example.com"
    password = "mots-du-jour-secure"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.get(User, UUID(str(decode_token(token)["sub"])))
    word = _make_due_word(db_session, user, "retrouver", rank=60)
    db_session.commit()

    first = client.get("/api/v1/vocabulary/words-of-the-day", headers=headers)
    assert first.status_code == 200
    payload = first.json()
    assert any(entry["word_id"] == word.id for entry in payload["words"])

    review = client.post(
        "/api/v1/anki/review",
        headers=headers,
        json={"word_id": word.id, "rating": 3},
    )
    assert review.status_code == 200

    second = client.get("/api/v1/vocabulary/words-of-the-day", headers=headers).json()
    entry = next(item for item in second["words"] if item["word_id"] == word.id)
    assert entry["stamps"].get("retrouve")
