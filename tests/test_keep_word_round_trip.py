# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""WP-138 — «Garder» then «Réviser»: a word kept from the scene comes back in it.

The 2026-10-06 browser walk: an English learner on day 1 tapped «appartement» in
Marin's line, read «flat», pressed Keep and got «This word could not be kept»
(``POST /vocabulary/keep`` → 422). The cause was the shared catalogue row: the
first learner whose day recorded the scene lexicon created «appartement» with
*their* gloss only — a French-speaking learner's English fallback written into the
French column — so every later learner was shown «flat» by the lookup (a fallback
gloss) and refused by the keep (no gloss in their language).

These tests hold the round trip: the scene word is keepable for every learner the
scene glossed it for, the lookup and the keep read the same row, a word that
genuinely cannot be kept says why (permanently) in a structured refusal, and a kept
word comes back in the drill on its own line, blanked — the scene rung.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import kept_words
from app.services.kept_words import record_scene_lexicon
from app.services.recall_ladder import blank_word
from tests.test_journey_end_to_end import (
    TEST_PASSWORD,
    assembled_client,  # noqa: F401 - fixture
    learner_id,
)

#: The suite shares one database and other suites leave «appartement» rows behind,
#: so each test reads the walk's word under a name of its own (``WORD``), with the
#: authored glosses the real word has (asserted against the real lists below).
WORD = "appartement"
LINE = "Vous allez vendre l'appartement d'Odile ? À Solvel ?"
#: The season's authored entry for the word (app/data/season/s1), as the season
#: runtime hands it to the day: ``gloss_native`` is the learner's language, or
#: English when the season has none in it (a French-speaking learner).
SEASON_GLOSS = {"en": "flat, apartment", "de": "die Wohnung"}


_AUTHORED_INDEX = kept_words._authored_gloss_index


@pytest.fixture(autouse=True)
def _leave_the_catalogue_as_found(db_session: Session):
    """These tests commit catalogue rows; later suites (an empty queue, a printed
    slate) read the shared catalogue, so every row made here leaves with the test."""

    from sqlalchemy import func

    from app.db.base import Base

    before = db_session.query(func.max(VocabularyWord.id)).scalar() or 0
    yield
    db_session.rollback()
    made = [row.id for row in db_session.query(VocabularyWord.id).filter(VocabularyWord.id > before)]
    if not made:
        return
    word_table = VocabularyWord.__table__
    for table in reversed(Base.metadata.sorted_tables):
        for fk in table.foreign_keys:
            if fk.column.table is word_table and table.name in db_session.bind.dialect.get_table_names(
                db_session.connection()
            ):
                db_session.execute(table.delete().where(fk.parent.in_(made)))
    db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(made)).delete(synchronize_session=False)
    db_session.commit()


@pytest.fixture(autouse=True)
def _own_word(monkeypatch: pytest.MonkeyPatch) -> None:
    global WORD, LINE
    WORD = f"appartement{uuid.uuid4().hex[:6]}"
    LINE = f"Vous allez vendre l'{WORD} d'Odile ? À Solvel ?"
    real = _AUTHORED_INDEX()
    monkeypatch.setattr(kept_words, "_authored_gloss_index", lambda: {**real, WORD: dict(SEASON_GLOSS)})


def test_the_authored_lists_gloss_the_walks_word_in_english_and_german() -> None:
    assert _AUTHORED_INDEX()["appartement"] == SEASON_GLOSS


def _entry(native: str) -> dict:
    return {
        "surface_fr": WORD,
        "lemma": WORD,
        "gloss_native": SEASON_GLOSS.get(native) or SEASON_GLOSS["en"],
        "part_of_speech": "noun",
        "gender": "m",
        "line_ref": "premise",
    }


def _learner(client: TestClient, db: Session, native: str, cefr: str = "A1.1") -> tuple[dict, User]:
    email = f"wp138-{native}-{uuid.uuid4().hex[:8]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "target_language": "fr",
            "native_language": native,
            "cefr_estimate": cefr,
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    user = db.get(User, learner_id(db, email))
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, user


def _day_one_scene(db: Session, user: User) -> None:
    """What the day-1 journey does with the scene's lexicon (journey_learning)."""

    record_scene_lexicon(
        db, user=user, entries=[_entry(user.native_language)], sentences={WORD: LINE}, level="A1"
    )
    db.commit()


def _keep(client: TestClient, headers: dict, term: str | None = None, sentence: str | None = None):
    term, sentence = term or WORD, sentence or LINE
    return client.post(
        "/api/v1/vocabulary/keep",
        headers=headers,
        json={
            "term": term,
            "sentence": sentence,
            "surface": term,
            "speaker_id": "marin",
            "panel_id": "p3",
            "line_key": "p3:l0",
        },
    )


def test_a_scene_word_is_keepable_by_every_learner_the_scene_glossed_it_for(
    assembled_client: TestClient, db_session: Session
) -> None:
    # The walk's order: a French-speaking learner's day 1 reached the scene first.
    fr_headers, fr_user = _learner(assembled_client, db_session, "fr")
    _day_one_scene(db_session, fr_user)
    en_headers, en_user = _learner(assembled_client, db_session, "en")
    _day_one_scene(db_session, en_user)
    de_headers, de_user = _learner(assembled_client, db_session, "de")
    _day_one_scene(db_session, de_user)

    # The shared row never holds another language's text in a gloss column.
    rows = db_session.query(VocabularyWord).filter(VocabularyWord.normalized_word == WORD).all()
    assert rows and all(row.french_translation in (None, "") for row in rows)

    for headers, gloss in ((en_headers, "flat, apartment"), (de_headers, "die Wohnung")):
        looked_up = assembled_client.get(f"/api/v1/vocabulary/lookup?word={WORD}", headers=headers)
        assert looked_up.status_code == 200, looked_up.text
        assert looked_up.json()["translation"] == gloss
        kept = _keep(assembled_client, headers)
        assert kept.status_code == 200, kept.text
        assert kept.json()["gloss"] == gloss
        assert kept.json()["example_fr"] == LINE


def test_a_learner_whose_own_language_is_french_keeps_the_labelled_fallback(
    assembled_client: TestClient, db_session: Session
) -> None:
    """Owner call 2026-10-07: French has no French translation; the French-speaking
    learner keeps the meaning the sheet showed (English first), labelled as such."""

    headers, user = _learner(assembled_client, db_session, "fr")
    _day_one_scene(db_session, user)
    looked_up = assembled_client.get(f"/api/v1/vocabulary/lookup?word={WORD}", headers=headers).json()
    kept = _keep(assembled_client, headers)
    assert kept.status_code == 200, kept.text
    assert kept.json()["gloss"] == looked_up["translation"] == "flat, apartment"
    assert kept.json()["example_fr"] == LINE


def test_lookup_and_keep_read_the_same_row(assembled_client: TestClient, db_session: Session) -> None:
    """Two catalogue rows for one word (a scene row with one learner's gloss, the
    core row with all of them): the sheet's meaning and the kept meaning agree."""

    db_session.add(
        VocabularyWord(
            language="fr", word=WORD, normalized_word=WORD,
            german_translation="die Wohnung", topic_tags=["scene_lexicon"], difficulty_level=1,
        )
    )
    db_session.add(
        VocabularyWord(
            language="fr", word=WORD, normalized_word=WORD,
            english_translation="flat, apartment", german_translation="die Wohnung",
            frequency_rank=297, difficulty_level=1,
        )
    )
    db_session.commit()
    headers, _ = _learner(assembled_client, db_session, "en")
    looked_up = assembled_client.get(f"/api/v1/vocabulary/lookup?word={WORD}", headers=headers).json()
    assert looked_up["translation"] == "flat, apartment"
    assert looked_up["translation_language"] == "en"
    kept = _keep(assembled_client, headers)
    assert kept.status_code == 200, kept.text
    assert kept.json()["word_id"] == looked_up["id"]


def test_a_word_that_cannot_be_kept_says_why_and_that_it_is_permanent(
    assembled_client: TestClient, db_session: Session
) -> None:
    headers, _ = _learner(assembled_client, db_session, "en")
    db_session.add(
        VocabularyWord(
            language="fr", word="gouttière", normalized_word="gouttière",
            german_translation="Dachrinne", difficulty_level=1,
        )
    )
    db_session.commit()
    refused = _keep(assembled_client, headers, term="gouttière", sentence="La gouttière déborde.")
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail["code"] == "no_gloss_in_learner_language"
    assert detail["retryable"] is False
    # The learner's own language, and the French chrome line for the French reader.
    assert detail["message_native"] and detail["message_native"] != detail["message"]
    assert detail["language"] == "en"

    missing = _keep(assembled_client, headers, term="introuvablemot", sentence="Un introuvablemot.")
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "not_in_lexicon"
    assert missing.json()["detail"]["retryable"] is False


def test_a_kept_word_comes_back_in_the_drill_on_its_own_line(
    assembled_client: TestClient, db_session: Session
) -> None:
    """Keep → the drill: the card is on the scene rung, its cue is the original line
    with the word blanked, spoken by the character who said it."""

    for native in ("en", "de"):
        headers, user = _learner(assembled_client, db_session, native)
        _day_one_scene(db_session, user)
        kept = _keep(assembled_client, headers)
        assert kept.status_code == 200, kept.text
        word_id = kept.json()["word_id"]

        progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word_id).one()
        assert progress.context["sentence_fr"] == LINE
        assert progress.context["speaker_id"] == "marin"

        context = assembled_client.get(
            "/api/v1/vocabulary/due-context",
            headers=headers,
            params={"limit": 50, "due_limit": 30, "fragile_limit": 12, "new_limit": 6},
        )
        assert context.status_code == 200, context.text
        body = context.json()
        items = [
            item
            for bucket in ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words")
            for item in body.get(bucket) or []
        ]
        card = next((item for item in items if item["word_id"] == word_id), None)
        assert card is not None, f"the kept word is not in the drill: {[i['word'] for i in items]}"
        assert card["ladder"] == "scene"
        assert card["scene_cue"]["sentence_fr"] == blank_word(LINE, WORD)
        assert "_____" in card["scene_cue"]["sentence_fr"]
        assert card["scene_cue"]["speaker_id"] == "marin"
        assert card["translation"] == SEASON_GLOSS[native]


def test_a_b1_learner_keeps_a_word_and_drills_it_in_its_scene(
    assembled_client: TestClient, db_session: Session
) -> None:
    """The walk's B1 learner (French chrome, English speaker) had an empty drill:
    the keep was refused. A core-lexicon word is keepable at any level."""

    db_session.add(
        VocabularyWord(
            language="fr", word=WORD, normalized_word=WORD,
            english_translation="flat, apartment", german_translation="die Wohnung",
            frequency_rank=297, difficulty_level=1,
        )
    )
    db_session.commit()
    headers, user = _learner(assembled_client, db_session, "en", cefr="B1.1")
    line = f"… Vous allez vraiment vendre l'{WORD} d'Odile ? À ces gens-là ?"
    kept = _keep(assembled_client, headers, sentence=line)
    assert kept.status_code == 200, kept.text
    body = assembled_client.get("/api/v1/vocabulary/due-context", headers=headers, params={"limit": 50}).json()
    items = [item for bucket in body.values() if isinstance(bucket, list) for item in bucket if isinstance(item, dict)]
    card = next(item for item in items if item.get("word_id") == kept.json()["word_id"])
    assert card["ladder"] == "scene"
    assert card["scene_cue"]["sentence_fr"] == blank_word(line, WORD)
