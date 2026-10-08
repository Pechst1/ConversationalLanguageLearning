"""WP-D6 — the stored noun gender reaches every Lexique payload.

The Lexique draws a feminine noun as a circle and a masculine noun as a square,
so the list, the word sheet (biography), the due-context queue and the words of
the day must all carry ``gender`` and ``part_of_speech``. A word without a
stored gender must arrive as ``None`` — never a guess.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_token
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import UserDailyWordSlate, VocabularyWord

_CREATED_USERS: list[UUID] = []


@pytest.fixture(autouse=True)
def _cleanup(db_session):
    """Catalogue rows are shared across suites (coverage counts them), so this
    module removes every learner, slate, progress row and word it made."""

    _CREATED_USERS.clear()
    yield
    db_session.rollback()
    for user_id in _CREATED_USERS:
        word_ids = [
            row.word_id
            for row in db_session.query(UserVocabularyProgress.word_id).filter(UserVocabularyProgress.user_id == user_id)
        ]
        db_session.query(UserDailyWordSlate).filter(UserDailyWordSlate.user_id == user_id).delete()
        db_session.query(UserVocabularyProgress).filter(UserVocabularyProgress.user_id == user_id).delete()
        if word_ids:
            db_session.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).delete(synchronize_session=False)
    db_session.commit()


def _login(client: TestClient, db_session) -> tuple[dict[str, str], User]:
    email = f"{uuid4()}@example.com"
    password = "gender-shape-secure"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db_session.get(User, UUID(str(decode_token(token)["sub"])))
    _CREATED_USERS.append(user.id)
    return {"Authorization": f"Bearer {token}"}, user


def _due_word(db_session, user: User, word: str, *, pos: str | None, gender: str | None, rank: int) -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word,
        part_of_speech=pos,
        gender=gender,
        frequency_rank=rank,
        english_translation=f"{word}-en",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(row)
    db_session.flush()
    past = datetime.now(UTC) - timedelta(days=1)
    db_session.add(
        UserVocabularyProgress(
            user_id=user.id,
            word_id=row.id,
            scheduler="fsrs",
            state="reviewing",
            phase="review",
            due_at=past,
            due_date=past.date(),
            next_review_date=past,
            last_review_date=past - timedelta(days=4),
            stability=2.0,
            difficulty=7.0,
            scheduled_days=2,
            reps=5,
        )
    )
    return row


def test_gender_is_served_on_list_sheet_queue_and_slate(client: TestClient, db_session) -> None:
    headers, user = _login(client, db_session)
    addition = _due_word(db_session, user, "addition", pos="noun", gender="f", rank=9101)
    pain = _due_word(db_session, user, "pain", pos="noun", gender="m", rank=9102)
    # Not in the core lexicon: nothing to fill, no article (WP-84 fills the rest).
    unknown = _due_word(db_session, user, "brume", pos="noun", gender=None, rank=9103)
    # In the lexicon, no stored gender: WP-84 serves the lexicon's «le».
    hiver = _due_word(db_session, user, "hiver", pos=None, gender=None, rank=9105)
    db_session.commit()

    # The list endpoint is cached (Redis when present, across runs), so the
    # listed word is unique to this run.
    listed = _due_word(db_session, user, f"tablette{uuid4().hex[:10]}", pos="noun", gender="f", rank=9104)
    db_session.commit()
    listing = client.get("/api/v1/vocabulary/", params={"search": listed.word, "limit": 5}, headers=headers)
    assert listing.status_code == 200
    row = next(item for item in listing.json()["items"] if item["id"] == listed.id)
    assert row["gender"] == "f"
    assert row["part_of_speech"] == "noun"

    sheet = client.get(f"/api/v1/vocabulary/{pain.id}/biography", headers=headers)
    assert sheet.status_code == 200
    assert sheet.json()["word"]["gender"] == "m"

    context = client.get("/api/v1/vocabulary/due-context", params={"limit": 12}, headers=headers)
    assert context.status_code == 200
    queue = {
        item["word_id"]: item
        for bucket in ("due_words", "fragile_words", "new_words", "linked_words", "topic_compatible_words")
        for item in context.json()[bucket]
    }
    assert queue[addition.id]["gender"] == "f"
    assert queue[unknown.id]["gender"] is None
    assert (queue[hiver.id]["gender"], queue[hiver.id]["part_of_speech"]) == ("m", "noun")

    slate = client.get("/api/v1/vocabulary/words-of-the-day", headers=headers)
    assert slate.status_code == 200
    entries = {entry["word_id"]: entry for entry in slate.json()["words"]}
    assert entries[addition.id]["gender"] == "f"
    assert entries[addition.id]["part_of_speech"] == "noun"
    assert entries[unknown.id]["gender"] is None


def test_slate_reads_gender_live_after_a_backfill(client: TestClient, db_session) -> None:
    """The slate is frozen for the day; its grammar is not."""

    headers, user = _login(client, db_session)
    word = _due_word(db_session, user, "brume", pos="noun", gender=None, rank=9201)
    db_session.commit()

    first = client.get("/api/v1/vocabulary/words-of-the-day", headers=headers).json()
    assert next(e for e in first["words"] if e["word_id"] == word.id)["gender"] is None

    word.gender = "f"
    db_session.commit()

    second = client.get("/api/v1/vocabulary/words-of-the-day", headers=headers).json()
    assert next(e for e in second["words"] if e["word_id"] == word.id)["gender"] == "f"
