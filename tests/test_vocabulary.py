"""Smoke tests for vocabulary endpoints using HTTPX."""
from __future__ import annotations

import pytest

from app.db.models.vocabulary import VocabularyWord


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
