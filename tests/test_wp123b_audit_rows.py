"""WP-123b — the experience-review row audit, on a disposable database.

``scripts/audit_experience_review_rows.py`` is meant to be pointed (read only) at
production by the owner. Here it runs against a throwaway SQLite file holding one
row of every kind it must find and one of every kind it must leave alone:

1. the dry run finds exactly the provenance-proven rows and writes nothing — not
   even when asked to (the connection is read only);
2. ``--apply`` changes exactly those rows (reschedules the old credits, removes
   the bogus errata), backs each up first, and leaves every other row identical;
3. a second ``--apply`` finds nothing and changes nothing (idempotent).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.error import UserError
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from scripts import audit_experience_review_rows as audit_rows

TABLES = (
    User, VocabularyWord, UserVocabularyProgress, ReviewLog, UserError,
    RealWorldMission, RealWorldMissionTurn, RealWorldMissionAttempt, DailyJourney, DailyJourneyStep,
)
CREDITED = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


def _word(db: Session, text_: str) -> VocabularyWord:
    word = VocabularyWord(word=text_, normalized_word=text_, language="fr", german_translation=text_.upper())
    db.add(word)
    db.flush()
    return word


def _card(db: Session, user: User, word: VocabularyWord, **values) -> UserVocabularyProgress:
    defaults = {"stability": 30.0, "difficulty": 4.0, "reps": 2, "lapses": 0, "state": "review", "phase": "review",
                    "scheduler": "fsrs", "last_review_date": CREDITED, "due_at": CREDITED + timedelta(days=15),
                    "next_review_date": CREDITED + timedelta(days=15), "due_date": (CREDITED + timedelta(days=15)).date(),
                    "scheduled_days": 15, "interval_days": 15, "provenance": "band_check_inferred", "provenance_ref": "B1.2"}
    card = UserVocabularyProgress(user_id=user.id, word_id=word.id, **{**defaults, **values})
    db.add(card)
    db.flush()
    return card


def _erratum(db: Session, user: User, **values) -> UserError:
    defaults = {"error_category": "vocabulary", "occurrences": 1, "state": "open", "source_type": "mission",
                    "task_error_type": "vocabulary_missing_target", "error_metadata": {}}
    row = UserError(user_id=user.id, **{**defaults, **values})
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def fixture_db(tmp_path: Path):
    """A throwaway SQLite file with one row of every kind the audit must tell apart."""

    url = f"sqlite:///{tmp_path / 'audit.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[model.__table__ for model in TABLES])
    expected: dict[str, set[str]] = {name: set() for name in audit_rows.CATEGORIES}
    with Session(engine) as db:
        b2 = User(id=uuid.uuid4(), email="b2@example.com", hashed_password="x", native_language="en",
                  target_language="fr", proficiency_level="B2", cefr_estimate="B2.1")
        other = User(id=uuid.uuid4(), email="a1@example.com", hashed_password="x", native_language="de",
                     target_language="fr", proficiency_level="A1", cefr_estimate="A1.1")
        db.add_all([b2, other])
        db.flush()
        words = [_word(db, f"mot{i}") for i in range(12)]

        # 1 · band-check credits: one old, untouched → reschedule.
        flood = _card(db, b2, words[0])
        expected["band_check_flood"].add(str(flood.id))
        reviewed = _card(db, b2, words[1])  # old, but reviewed since: an independent review
        db.add(ReviewLog(progress_id=reviewed.id, rating=2, review_date=CREDITED + timedelta(days=12), source="drill"))
        _card(db, b2, words[2], stability=120.0, provenance_ref="B1.1")  # the current schedule
        _card(db, b2, words[3], provenance=None, provenance_ref=None)  # an imported / ordinary card
        _card(db, b2, words[4], lapses=1)  # lapsed since

        # 2 · letter-omission errata.
        bogus = _erratum(db, b2, linked_word_id=words[5].id, display_label="Use target word: mot5")
        expected["letter_omission_errata"].add(str(bogus.id))
        _erratum(db, b2, occurrences=3)  # merged: ambiguous
        _erratum(db, b2, source_type="graphic_novel")  # a story task, not a letter
        _erratum(db, b2, state="mastered")  # already out of the queue
        _erratum(db, b2, task_error_type="vocabulary_incorrect_use")  # a genuine wrong use

        # 3 · omission lapses (report only).
        mission = RealWorldMission(user_id=b2.id, title="Lettre", brief="Écrire")
        db.add(mission)
        db.flush()
        db.add(RealWorldMissionTurn(
            mission_id=mission.id, user_id=b2.id, turn_index=0, role="user", text="Bonjour",
            correction_payload={"vocabulary_events": [{"word_id": words[6].id, "event_type": "missed_target"},
                                                      {"word_id": words[7].id, "event_type": "missed_target"}]},
        ))
        db.add(RealWorldMissionAttempt(
            mission_id=mission.id, user_id=b2.id,
            correction_payload={"vocabulary_events": [{"word_id": words[7].id, "event_type": "produced_incorrect"}]},
        ))
        lapsed = _card(db, b2, words[6], provenance=None, stability=2.0, reps=3, lapses=1)
        lapse = ReviewLog(progress_id=lapsed.id, rating=0, review_date=CREDITED, source="mission")
        wrong = _card(db, b2, words[7], provenance=None, stability=2.0, reps=3, lapses=1)
        db.add_all([lapse, ReviewLog(progress_id=wrong.id, rating=0, review_date=CREDITED, source="mission")])
        db.flush()
        expected["letter_omission_lapses"].add(str(lapse.id))

        # 4 · practice-miss vocabulary errata.
        tap = _erratum(db, other, source_type="daily_journey", task_error_type="vocabulary_incorrect_use",
                       error_metadata={"source_payload": {"task_type": "choice"}})
        expected["practice_miss_vocab_errata"].add(str(tap.id))
        _erratum(db, other, source_type="daily_journey", task_error_type="vocabulary_incorrect_use",
                 error_metadata={"source_payload": {"task_type": "reply"}})
        _erratum(db, other, source_type="daily_journey", task_error_type="vocabulary_incorrect_use",
                 error_metadata={})

        # 5 · give-up correction errata.
        journey = DailyJourney(user_id=other.id, local_date=date(2026, 10, 2))
        db.add(journey)
        db.flush()
        recall = DailyJourneyStep(journey_id=journey.id, ordinal=1, kind="recall")
        reply = DailyJourneyStep(journey_id=journey.id, ordinal=2, kind="respond")
        db.add_all([recall, reply])
        db.flush()

        def correction(step: DailyJourneyStep, learner: str) -> UserError:
            key = f"journey:{journey.id}:{step.id}:correction:abc:not_yet"
            return _erratum(db, other, source_type="daily_journey", task_error_type="journey_correction",
                            error_category="grammar", original_text=learner, correction="appartement",
                            error_metadata={"source_payload": {"source_key": key}})

        give_up = correction(recall, "euh je ne sais pas")
        expected["give_up_correction_errata"].add(str(give_up.id))
        correction(reply, "Ich weiß nicht")  # a reply: the current policy keeps it
        correction(recall, "le appartement")  # an attempt at the answer: legitimate
        # Unrelated rows the audit has no business with.
        _erratum(db, other, source_type="atelier", task_error_type="grammar_target", error_category="grammar")
        _card(db, other, words[8], provenance=None, stability=5.0, reps=4)
        db.commit()
    yield url, expected
    engine.dispose()


def _snapshot(url: str) -> dict[str, dict[str, dict]]:
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            out = {}
            for model in TABLES:
                table = Table(model.__tablename__, MetaData(), autoload_with=conn, resolve_fks=False)
                out[model.__tablename__] = {
                    str(row["id"]): dict(row) for row in conn.execute(select(table)).mappings()
                }
            return out
    finally:
        engine.dispose()


def _norm(row_id: str) -> str:
    return row_id.replace("-", "")


def _ids(reports, category: str) -> set[str]:
    return {f.row_id for r in reports if r.category == category for f in r.affected}


def test_the_dry_run_finds_exactly_the_proven_rows_and_writes_nothing(fixture_db):
    url, expected = fixture_db
    before = _snapshot(url)
    reports, done = audit_rows.run(url)
    assert done == {}
    for category in audit_rows.CATEGORIES:
        assert {_norm(i) for i in _ids(reports, category)} == {_norm(i) for i in expected[category]}, category
    by_name = {r.category: r for r in reports}
    assert by_name["band_check_flood"].left_alone == {
        "reviewed since the credit (an independent review)": 1,
        "current schedule (stability is not the old credit's 30)": 1,
        "changed since the credit (reps/lapses)": 1,
    }
    assert sum(by_name["letter_omission_errata"].left_alone.values()) == 3
    assert by_name["letter_omission_lapses"].left_alone == {"the word was also used wrongly (a real lapse is possible)": 1}
    assert by_name["give_up_correction_errata"].left_alone == {
        "a give-up in a reply (the current policy keeps it)": 1,
        "an attempt at the answer (legitimate)": 1,
    }
    # The rescheduled credit lands in the current window and never earlier than before.
    finding = by_name["band_check_flood"].affected[0]
    assert finding.detail["distance"] == 1  # B1.2 is one sub-band below B2.1
    assert 20 <= finding.detail["days_after"] <= 90
    assert finding.detail["due_after"] >= finding.detail["due_before"]
    assert _snapshot(url) == before


def test_the_dry_run_connection_refuses_writes(fixture_db):
    url, _expected = fixture_db
    engine = create_engine(url)
    try:
        with engine.connect() as conn, conn.begin():
            audit_rows._read_only(conn)
            with pytest.raises(OperationalError):
                conn.execute(text("DELETE FROM user_errors"))
    finally:
        engine.dispose()


def test_apply_changes_only_the_proven_rows_backs_them_up_and_is_idempotent(fixture_db, tmp_path):
    url, expected = fixture_db
    before = _snapshot(url)
    backup = tmp_path / "backup.jsonl"
    reports, done = audit_rows.run(url, apply=True, backup=backup)
    assert done == {"band_check_flood": 1, "letter_omission_errata": 1,
                    "practice_miss_vocab_errata": 1, "give_up_correction_errata": 1}
    saved = [json.loads(line) for line in backup.read_text().splitlines()]
    assert sorted(entry["category"] for entry in saved) == sorted(done)
    assert all(entry["row"] for entry in saved)

    after = _snapshot(url)
    touched = {f.row_id for r in reports for f in r.affected if f.action != "report"}
    for table, rows in before.items():
        for row_id, row in rows.items():
            if row_id in touched:
                continue
            assert after[table].get(row_id) == row, (table, row_id)  # every other row identical
    removed = {f.row_id for r in reports for f in r.affected if f.action == "delete"}
    assert removed and not removed & set(after["user_errors"])
    flood = next(f for f in reports[0].affected)
    card = after["user_vocabulary_progress"][flood.row_id]
    assert card["stability"] == 60.0  # credit_schedule(1)
    assert str(card["due_at"]) >= str(before["user_vocabulary_progress"][flood.row_id]["due_at"])
    # The omission lapse is reported, never changed.
    lapse_id = next(iter(_ids(reports, "letter_omission_lapses")))
    assert after["review_logs"][lapse_id] == before["review_logs"][lapse_id]

    again, done_again = audit_rows.run(url, apply=True, backup=tmp_path / "again.jsonl")
    assert done_again == {}
    assert all(not r.affected for r in again if r.category != "letter_omission_lapses")
    assert _snapshot(url) == after


def test_a_database_without_the_new_columns_is_answered_not_applicable(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, cefr_estimate TEXT, proficiency_level TEXT)"))
        conn.execute(text("CREATE TABLE user_vocabulary_progress (id TEXT PRIMARY KEY, user_id TEXT, word_id INTEGER)"))
        conn.execute(text("CREATE TABLE review_logs (id TEXT PRIMARY KEY, progress_id TEXT, rating INTEGER)"))
    engine.dispose()
    reports, _ = audit_rows.run(url)
    by_name = {r.category: r for r in reports}
    assert by_name["band_check_flood"].applicable is False
    assert "never deployed" in by_name["band_check_flood"].reason
    assert by_name["letter_omission_errata"].applicable is False


def test_apply_without_a_backup_file_refuses(fixture_db):
    url, _expected = fixture_db
    with pytest.raises(SystemExit):
        audit_rows.run(url, apply=True, backup=None)
