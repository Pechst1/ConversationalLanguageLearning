"""WP-115d — the week's letter asks for the learner's due words (by meaning), and a
word used unprompted in a reply is noticed."""

from __future__ import annotations

import asyncio

from app.db.models.progress import UserVocabularyProgress
from app.services.missions import MissionScheduler
from app.services.story_words import letter_due_words
from tests.test_daily_words import _make_due_word, _make_user


def _hard(db_session, user, word, lapses=3):
    db_session.flush()
    row = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    row.lapses = lapses


def test_the_letter_takes_the_hardest_due_words_first(db_session):
    user = _make_user(db_session)
    easy = _make_due_word(db_session, user, "le pain", rank=10)
    hard = _make_due_word(db_session, user, "la serrure", rank=900)
    _hard(db_session, user, easy, lapses=0)
    _hard(db_session, user, hard, lapses=4)
    db_session.flush()
    ids = letter_due_words(db_session, user=user)
    assert ids[0] == hard.id and easy.id in ids, "hardest first, then the other due words"


def test_the_weeks_letter_asks_for_due_words_by_meaning(db_session, monkeypatch):
    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "la serrure", rank=900)
    _hard(db_session, user, word)
    db_session.commit()
    scheduler = MissionScheduler(db_session)
    monkeypatch.setattr(scheduler, "_standalone_count", lambda **_kw: 1)  # not the first letter
    letter = asyncio.run(scheduler.ensure_weekly(user))
    payload = letter.prompt_payload or {}
    assert word.id in [item.get("word_id") for item in payload.get("target_vocabulary") or []]
    assert payload.get("recall_ribbon") is True, "the ribbon shows the meaning; the reply recalls the word"


def test_a_reviewed_word_used_unprompted_is_noticed_and_credited(db_session):
    from types import SimpleNamespace

    from app.db.models.pilot_event import PilotEvent
    from app.db.models.progress import ReviewLog
    from app.services import living_story as engine
    from app.services.story_words import transfer_words

    user = _make_user(db_session)
    word = _make_due_word(db_session, user, "la serrure", rank=900)
    target = _make_due_word(db_session, user, "le palier", rank=901)
    db_session.flush()
    text = "J'ai changé la serrure hier, et le palier est propre."
    targets = {target.id}
    assert [row["lemma"] for row in transfer_words(db_session, user=user, text=text, exclude_ids=targets)] == ["la serrure"]
    assert transfer_words(db_session, user=user, text="Bonjour !") == []
    task = SimpleNamespace(targets=[SimpleNamespace(kind="vocabulary", id=str(target.id))])
    answer = SimpleNamespace(text=text)
    assert engine._noticed_word(db_session, user, task, answer) == "la serrure", "the reply may notice it"
    assert engine.credit_transfer(db_session, user=user, task=task, answer=answer) == [word.id]
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    log = db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).one()
    assert (log.rating, log.format) == (2, "transfer"), "recalled unprompted: a production review"
    assert db_session.query(PilotEvent).filter_by(user_id=user.id, event_type="vocab_transfer").count() == 1


def test_the_retention_report_counts_transfer(db_session):
    from types import SimpleNamespace

    from app.services import living_story as engine
    from app.services.vocab_metrics import retention_report

    user = _make_user(db_session)
    _make_due_word(db_session, user, "la serrure", rank=900)
    db_session.flush()
    engine.credit_transfer(db_session, user=user, task=SimpleNamespace(targets=[]), answer=SimpleNamespace(text="La serrure est cassée."))
    report = retention_report(db_session, days=7, user_ids=[user.id])
    assert report["transfer"] == {"events": 1, "learners": 1, "words": 1}
