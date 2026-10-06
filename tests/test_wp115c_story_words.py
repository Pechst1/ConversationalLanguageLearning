"""WP-115c — the story carries the words that don't stick: which words, and no spoilers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.db.models.progress import UserVocabularyProgress
from app.services import living_story as engine
from app.services.story_words import spoiled_story_words, story_due_words
from tests.test_daily_words import _make_due_word, _make_user


def _progress(db_session, user, word):
    db_session.flush()
    return db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()


def test_only_hard_due_words_are_the_storys_hardest_first(db_session):
    user = _make_user(db_session)
    easy = _make_due_word(db_session, user, "le pain", rank=10)
    lapsed = _make_due_word(db_session, user, "la serrure", rank=900)
    harder = _make_due_word(db_session, user, "le palier", rank=901)
    anki = _make_due_word(db_session, user, "la rampe", rank=902)
    for word, lapses, difficulty in ((easy, 0, 4.0), (lapsed, 2, 5.0), (harder, 4, 8.0), (anki, 6, 9.0)):
        row = _progress(db_session, user, word)
        row.lapses, row.difficulty = lapses, difficulty
    _progress(db_session, user, anki).scheduler = "anki"
    db_session.flush()
    words = story_due_words(db_session, user=user)
    assert [row["lemma"] for row in words] == ["le palier", "la serrure"], "most lapses first; never an easy or an Anki word"
    assert words[0]["gloss_native"] == "le palier-en"


def test_a_hard_word_that_is_not_due_waits(db_session):
    from datetime import UTC, datetime, timedelta

    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "la serrure", rank=900)
    row = _progress(db_session, user, word)
    row.lapses = 5
    row.due_at = datetime.now(UTC) + timedelta(days=3)
    db_session.flush()
    assert story_due_words(db_session, user=user) == []


@pytest.mark.parametrize(
    ("texts", "spoiled"),
    [
        (["Tu as vu la serrure ?"], ["la serrure"]),
        (["La SERRURE est cassée."], ["la serrure"]),
        (["Comment on dit, déjà… le truc où on met la clé ?"], []),
        (["Les serrures du quartier."], []),
    ],
)
def test_a_printed_story_word_is_a_spoiler(texts, spoiled):
    assert spoiled_story_words(texts, [{"lemma": "la serrure"}]) == spoiled


def test_the_director_is_asked_once_more_when_the_scene_prints_the_word():
    draft = SimpleNamespace(
        premise_fr="Une porte ne s'ouvre plus.",
        opening_line_fr="Tu peux m'aider avec la serrure ?",
        panels=[SimpleNamespace(narration_fr="", dialogue=[])],
    )
    with pytest.raises(engine.SoftRejection, match="story_word_printed") as refused:
        engine._check_story_words(draft, {"story_words": [{"lemma": "la serrure"}]})
    assert refused.value.proposal is draft, "the scene stays servable: the retry is served either way"
    draft.opening_line_fr = "Comment on dit, déjà… le truc où on met la clé ?"
    engine._check_story_words(draft, {"story_words": [{"lemma": "la serrure"}]})
