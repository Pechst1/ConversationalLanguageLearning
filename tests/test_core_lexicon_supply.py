"""Content program 2026-10-03 (E-1): the core list is the planned supply of new words.

A learner with no imported deck used to get no new words from the drill at all;
the core lexicon (A1 → C1) now seeds shared catalogue rows the drill introduces
in list order, from the learner's own band, once per lemma.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select

from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.core_lexicon import CORE_DECK, ensure_core_lexicon, sync_core_lexicon
from app.services.lexical_coverage import load_lexicon
from app.services.progress import ProgressService

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _drop_core_rows(db_session):
    """The test database outlives a test: leave no core rows for the next suite."""

    yield
    db_session.rollback()
    core_ids = select(VocabularyWord.id).where(VocabularyWord.deck_name == CORE_DECK)
    db_session.execute(delete(UserVocabularyProgress).where(UserVocabularyProgress.word_id.in_(core_ids)))
    db_session.execute(delete(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK))
    db_session.commit()


def _user(db, *, level: str = "A1.1") -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"core-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        target_language="fr",
        native_language="de",
        cefr_estimate=level,
    )
    db.add(user)
    db.commit()
    ensure_core_lexicon(db)  # deploy-time in production (scripts/sync_core_lexicon.py)
    db.commit()
    return user


def _new_words(db, user, n: int = 6) -> list[dict]:
    """The new words the drill offers from the core list.

    An imported deck comes first by design, and other suites leave deck rows in
    the shared test database, so only the core list's own offers are read here.
    """

    payload = ProgressService(db).get_vocabulary_recommendations(
        user=user, limit=n + 40, due_limit=0, fragile_limit=0, new_limit=n + 40,
        direction="fr_to_de", now=NOW,
    )
    return [
        item for item in payload["items"]
        if item["bucket"] == "new" and item.get("deck_name") == CORE_DECK
    ][:n]


def _core_count(db) -> int:
    return int(db.scalar(select(func.count(VocabularyWord.id)).where(VocabularyWord.deck_name == CORE_DECK)))


def test_the_core_list_seeds_once_without_numerals(db_session):
    lexicon = load_lexicon()
    expected = sum(1 for entry in lexicon.lemmas.values() if not entry.get("numeral"))

    ensure_core_lexicon(db_session)
    db_session.commit()
    assert _core_count(db_session) == expected
    assert sync_core_lexicon(db_session) == 0  # idempotent: nothing left to write

    row = db_session.scalar(select(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK,
                                                          VocabularyWord.normalized_word == "maison"))
    assert row is not None and row.part_of_speech == "noun" and row.gender == "f"
    assert row.difficulty_level == 1 and "A1" in row.topic_tags
    assert not db_session.scalar(select(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK,
                                                              VocabularyWord.normalized_word == "quarante-deux"))


def test_a_learner_without_a_deck_gets_core_words_in_list_order(db_session):
    user = _user(db_session, level="A1.1")

    words = _new_words(db_session, user)

    assert len(words) == 6
    lexicon = load_lexicon()
    assert all(lexicon.lemmas[item["word"]]["sub_band"] == "A1.1" for item in words)
    # Grammar words are taught by the grammar units, not as vocabulary cards.
    assert all(lexicon.lemmas[item["word"]].get("pos") != "function" for item in words)


def test_a_b2_learner_starts_at_their_own_band(db_session):
    user = _user(db_session, level="B2.1")

    words = _new_words(db_session, user)

    lexicon = load_lexicon()
    assert words and all(lexicon.band(item["word"]) in {"B2", "C1"} for item in words)


def test_a_lemma_the_learner_already_has_is_not_offered_again(db_session):
    user = _user(db_session, level="A1.1")
    first = _new_words(db_session, user, n=1)[0]
    imported = VocabularyWord(language="fr", word=first["word"], normalized_word=first["word"],
                              direction="fr_to_de", is_anki_card=True, deck_name="Mon deck")
    db_session.add(imported)
    db_session.flush()
    db_session.add(UserVocabularyProgress(user_id=user.id, word_id=imported.id))
    db_session.commit()

    again = {item["word"] for item in _new_words(db_session, user)}

    assert first["word"] not in again


def test_a_word_the_story_taught_comes_before_the_list(db_session):
    from app.db.models.session import LearningSession, WordInteraction
    from app.services.kept_words import SCENE_LEXICON_INTERACTION_TYPE

    user = _user(db_session, level="A1.1")
    ensure_core_lexicon(db_session)
    taught = db_session.scalar(select(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK,
                                                             VocabularyWord.normalized_word == "clé"))
    session = LearningSession(user_id=user.id, planned_duration_minutes=10)
    db_session.add(session)
    db_session.flush()
    db_session.add(WordInteraction(session_id=session.id, user_id=user.id, word_id=taught.id,
                                   interaction_type=SCENE_LEXICON_INTERACTION_TYPE,
                                   context_sentence="Voilà la clé.", user_response="clé", correction="Schlüssel"))
    db_session.commit()

    words = [item["word"] for item in _new_words(db_session, user, n=3)]

    assert words[0] == "clé"
