"""Smoke tests for vocabulary endpoints using HTTPX."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.config import settings
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord


async def _register_and_login(async_client, email: str, password: str = "verysecure") -> str:
    await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return response.json()["access_token"]


@pytest.fixture()
def sample_vocabulary(db_session):
    db_session.query(VocabularyWord).delete()
    db_session.commit()
    words = [
        VocabularyWord(
            language="es",
            word="hola",
            normalized_word="hola",
            part_of_speech="interjection",
            frequency_rank=1,
            english_translation="hello",
            difficulty_level=1,
            topic_tags=["greetings"],
        ),
        VocabularyWord(
            language="es",
            word="gracias",
            normalized_word="gracias",
            part_of_speech="noun",
            frequency_rank=2,
            english_translation="thank you",
            difficulty_level=1,
            topic_tags=["politeness"],
        ),
    ]
    db_session.add_all(words)
    db_session.commit()
    try:
        yield words
    finally:
        db_session.query(VocabularyWord).delete()
        db_session.commit()


@pytest.mark.asyncio
async def test_list_vocabulary(async_client, sample_vocabulary):
    response = await async_client.get("/api/v1/vocabulary/", params={"limit": 10})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["word"] == "hola"


@pytest.mark.asyncio
async def test_get_vocabulary_word(async_client, sample_vocabulary):
    word_id = sample_vocabulary[0].id
    response = await async_client.get(f"/api/v1/vocabulary/{word_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["word"] == "hola"
    assert payload["topic_tags"] == ["greetings"]


@pytest.mark.asyncio
async def test_filter_vocabulary_by_language(async_client, sample_vocabulary):
    response = await async_client.get("/api/v1/vocabulary/", params={"language": "es"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2

    other_language_response = await async_client.get(
        "/api/v1/vocabulary/", params={"language": "fr"}
    )
    assert other_language_response.status_code == 200
    assert other_language_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_vocabulary_matches_word_and_translation(async_client, sample_vocabulary, db_session):
    accent_word = VocabularyWord(
        language="fr",
        word="été",
        normalized_word="ete",
        part_of_speech="noun",
        frequency_rank=3,
        english_translation="summer",
        german_translation="Sommer",
        difficulty_level=1,
    )
    db_session.add(accent_word)
    db_session.commit()

    word_response = await async_client.get(
        "/api/v1/vocabulary/",
        params={"language": "fr", "search": "ete", "limit": 10},
    )
    translation_response = await async_client.get(
        "/api/v1/vocabulary/",
        params={"language": "es", "search": "thank", "limit": 10},
    )

    assert word_response.status_code == 200
    word_payload = word_response.json()
    assert word_payload["total"] == 1
    assert word_payload["items"][0]["word"] == "été"

    assert translation_response.status_code == 200
    translation_payload = translation_response.json()
    assert translation_payload["total"] == 1
    assert translation_payload["items"][0]["word"] == "gracias"


@pytest.mark.asyncio
async def test_vocabulary_due_context_returns_bucketed_words(async_client, db_session):
    email = "vocab-context@example.com"
    token = await _register_and_login(async_client, email)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == email).one()
    due_word = VocabularyWord(
        language="fr",
        word="arriver",
        normalized_word="arriver",
        frequency_rank=70,
        german_translation="ankommen",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    new_word = VocabularyWord(
        language="fr",
        word="maison",
        normalized_word="maison",
        frequency_rank=30,
        german_translation="Haus",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    linked_word = VocabularyWord(
        language="fr",
        word="dossier",
        normalized_word="dossier",
        frequency_rank=400,
        german_translation="Akte",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    topic_word = VocabularyWord(
        language="fr",
        word="train",
        normalized_word="train",
        frequency_rank=500,
        german_translation="Zug",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
        topic_tags=["travel"],
    )
    db_session.add_all([due_word, new_word, linked_word, topic_word])
    db_session.flush()
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=due_word.id,
            scheduler="anki",
            state="reviewing",
            phase="review",
            due_at=datetime.now(timezone.utc) - timedelta(days=1),
            due_date=date.today() - timedelta(days=1),
            reps=5,
            proficiency_score=70,
        )
    )
    db_session.commit()

    try:
        response = await async_client.get(
            "/api/v1/vocabulary/due-context",
            headers=headers,
            params={
                "limit": 4,
                "due_limit": 1,
                "fragile_limit": 0,
                "new_limit": 1,
                "topic_limit": 1,
                "linked_limit": 1,
                "direction": "fr_to_de",
                "topic_tags": "travel",
                "linked_word_ids": str(linked_word.id),
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"]["due"] == 1
        assert payload["summary"]["new"] == 1
        assert payload["summary"]["topic_compatible"] == 1
        assert payload["summary"]["linked"] == 1
        assert payload["due_words"][0]["word"] == "arriver"
        assert payload["new_words"][0]["word"] == "maison"
        assert payload["topic_compatible_words"][0]["word"] == "train"
        assert payload["linked_words"][0]["word"] == "dossier"
    finally:
        db_session.query(UserVocabularyProgress).filter(
            UserVocabularyProgress.user_id == user.id
        ).delete()
        db_session.query(VocabularyWord).filter(
            VocabularyWord.id.in_([due_word.id, new_word.id, linked_word.id, topic_word.id])
        ).delete(synchronize_session=False)
        db_session.commit()


@pytest.mark.asyncio
async def test_vocabulary_due_context_uses_demo_user_without_auth(
    async_client, db_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", True)
    word = VocabularyWord(
        language="fr",
        word="abaisser",
        normalized_word="abaisser",
        frequency_rank=10,
        german_translation="senken",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(word)
    db_session.commit()

    try:
        response = await async_client.get(
            "/api/v1/vocabulary/due-context",
            params={"limit": 1, "due_limit": 0, "fragile_limit": 0, "new_limit": 1},
        )

        assert response.status_code == 200
        assert response.json()["new_words"][0]["word"] == "abaisser"
    finally:
        db_session.query(VocabularyWord).filter(VocabularyWord.id == word.id).delete()
        db_session.query(User).filter(User.email == "atelier-demo@local.test").delete()
        db_session.commit()


@pytest.mark.asyncio
async def test_vocabulary_due_context_rejects_invalid_direction(async_client):
    response = await async_client.get(
        "/api/v1/vocabulary/due-context",
        params={"direction": "fr_to_en"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_vocabulary_due_context_route_is_not_captured_by_word_id(
    async_client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "AUTO_CREATE_USERS_ON_LOGIN", True)
    try:
        response = await async_client.get("/api/v1/vocabulary/due-context")

        assert response.status_code != 422
    finally:
        db_session.query(User).filter(User.email == "atelier-demo@local.test").delete()
        db_session.commit()


@pytest.mark.asyncio
async def test_vocabulary_biography_returns_origin_progress_and_context(async_client, db_session):
    email = "vocab-biography@example.com"
    token = await _register_and_login(async_client, email)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == email).one()
    now = datetime.now(timezone.utc)
    word = VocabularyWord(
        language="fr",
        word="prévoir",
        normalized_word="prevoir",
        part_of_speech="verb",
        frequency_rank=314,
        german_translation="vorsehen",
        deck_name="French 5000",
        direction="fr_to_de",
        is_anki_card=True,
        example_sentence="Je dois prévoir assez de temps.",
        example_translation="I need to plan enough time.",
        topic_tags=["planning"],
    )
    db_session.add(word)
    db_session.flush()
    progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=word.id,
        scheduler="anki",
        state="reviewing",
        phase="review",
        due_at=now - timedelta(hours=2),
        due_date=date.today(),
        next_review_date=now - timedelta(hours=2),
        last_review_date=now - timedelta(days=3),
        reps=4,
        lapses=1,
        times_seen=3,
        times_used_correctly=1,
        proficiency_score=62,
    )
    erratum = UserError(
        user_id=user.id,
        error_category="vocabulary",
        display_label="Use target word: prévoir",
        linked_word_id=word.id,
        original_text="Je dois planifier.",
        correction="Je dois prévoir.",
        why_wrong="The mission asked for prévoir.",
        repair_hint="Use prévoir for planning ahead.",
        source_type="mission",
        review_mode="vocabulary",
        task_error_type="vocabulary_missing_target",
    )
    mission = RealWorldMission(
        user_id=user.id,
        title="Plan the weekend",
        brief="Write a short plan using prévoir.",
        target_vocabulary_ids=[word.id],
        selected_concept_ids=[],
        target_errata_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={"target_vocabulary": [{"word_id": word.id, "word": word.word}]},
        recap_payload={},
    )
    db_session.add_all([progress, erratum, mission])
    db_session.commit()

    try:
        response = await async_client.get(f"/api/v1/vocabulary/{word.id}/biography", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["word"]["word"] == "prévoir"
        assert payload["origin"]["label"] == "French 5000"
        assert payload["progress"]["fragility_label"] == "Due now"
        assert payload["progress"]["times_seen"] == 3
        assert payload["examples"][0]["sentence"] == "Je dois prévoir assez de temps."
        assert payload["linked_errata_count"] == 1
        event_types = {event["event_type"] for event in payload["timeline"]}
        assert {"origin", "schedule", "erratum", "mission"}.issubset(event_types)
        assert payload["context_event_count"] >= 2
    finally:
        db_session.query(UserError).filter(UserError.user_id == user.id).delete()
        db_session.query(RealWorldMission).filter(RealWorldMission.user_id == user.id).delete()
        db_session.query(UserVocabularyProgress).filter(
            UserVocabularyProgress.user_id == user.id
        ).delete()
        db_session.query(VocabularyWord).filter(VocabularyWord.id == word.id).delete()
        db_session.commit()


@pytest.mark.asyncio
async def test_vocabulary_biography_includes_atelier_and_feuilleton_thread(async_client, db_session):
    email = "vocab-biography-thread@example.com"
    token = await _register_and_login(async_client, email)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == email).one()
    word = VocabularyWord(
        language="fr",
        word="relancer",
        normalized_word="relancer",
        frequency_rank=512,
        german_translation="erneut anstoßen",
        deck_name="French 5000",
        direction="fr_to_de",
        is_anki_card=True,
        example_sentence="Je vais relancer la discussion demain.",
        example_translation="I will restart the discussion tomorrow.",
    )
    db_session.add(word)
    db_session.flush()
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[],
        quote_payload={
            "title": "Follow-up workshop",
            "brief": "Use the target word to restart a conversation.",
            "target_vocabulary_ids": [word.id],
        },
    )
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=None,
        round="sentence",
        mode="short_sentence",
        exercise_id="vocab-thread",
        prompt_payload={"context_anchor": {"word_id": word.id, "word": word.word}},
        answer_payload={"text": "Je vais relancer le dossier."},
        correction_payload={"vocabulary_credit": {"events": [{"word_id": word.id}]}},
        verdict="accepted",
        score_0_4=4,
    )
    scene = GraphicNovelScene(
        user_id=user.id,
        status="completed",
        cadence="ad_hoc",
        title="Le bureau reprend",
        brief="The story brings the word back in context.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[word.id],
        source_snapshot={},
        script_payload={"target_vocabulary": [{"word_id": word.id, "word": word.word}]},
        recap_payload={"vocabulary_credit": {"seen_context": 1}},
        cache_key=f"thread-{word.id}",
        prompt_version="test",
        image_model="none",
        image_quality="low",
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([attempt, scene])
    db_session.commit()

    try:
        response = await async_client.get(f"/api/v1/vocabulary/{word.id}/biography", headers=headers)

        assert response.status_code == 200
        payload = response.json()
        event_types = {event["event_type"] for event in payload["timeline"]}
        assert {"atelier", "atelier_attempt", "graphic_novel"}.issubset(event_types)
        assert any(event["label"] == "Atelier context anchor" for event in payload["timeline"])
        assert any(event["label"] == "Feuilleton thread: Le bureau reprend" for event in payload["timeline"])
        assert payload["context_event_count"] >= 3
    finally:
        db_session.query(GraphicNovelScene).filter(GraphicNovelScene.user_id == user.id).delete()
        db_session.query(AtelierAttempt).filter(AtelierAttempt.user_id == user.id).delete()
        db_session.query(AtelierSession).filter(AtelierSession.user_id == user.id).delete()
        db_session.query(VocabularyWord).filter(VocabularyWord.id == word.id).delete()
        db_session.commit()
