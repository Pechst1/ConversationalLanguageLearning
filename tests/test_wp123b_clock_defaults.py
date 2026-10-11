"""WP-123b — evidence timestamps follow the application's clock.

The level forecast and the CEFR signals read *when* a card, a unit, an attempt,
an erratum or a reading interaction was created. Those columns used to take only
the database's ``now()``, which ``app.core.test_clock`` cannot move: in the life
walk every card was "created" on the real day 0, so from day 15 on the measured
intake of the last 14 days was zero and the forecast sat at its two-year cap.

Pins:
1. with the test clock 20 days ahead, every evidence column writes the shifted day;
2. an explicit value still wins over the default;
3. the measured forecast counts a card created "today" under the shifted clock;
4. production reads are unchanged: without the test clock the default is the
   real ``now`` (UTC), and the ``server_default`` stays for raw SQL.
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core import test_clock
from app.db.models._clock import app_now
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord

OFFSET_DAYS = 20


@pytest.fixture
def clock_ahead():
    """The app's clock ``OFFSET_DAYS`` ahead (as the life walk moves it), restored after."""

    test_clock.install()
    test_clock.set_offset_days(OFFSET_DAYS)
    yield
    test_clock.set_offset_days(0)
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith("app."):
            continue
        for attr, stand_in, real in (
            ("datetime", test_clock.ShiftedDatetime, test_clock._REAL_DATETIME),
            ("date", test_clock.ShiftedDate, test_clock._REAL_DATE),
            ("_date", test_clock.ShiftedDate, test_clock._REAL_DATE),
        ):
            if getattr(module, attr, None) is stand_in:
                setattr(module, attr, real)


def _user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp123b-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
        cefr_estimate="A1.1",
        cefr_estimate_payload={},
    )
    db.add(user)
    db.commit()
    return user


def _word(db) -> VocabularyWord:
    text = f"mot{uuid.uuid4().hex[:6]}"
    word = VocabularyWord(word=text, normalized_word=text, language="fr", german_translation="Wort")
    db.add(word)
    db.commit()
    return word


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _shifted_day() -> datetime:
    return datetime.now(UTC) + timedelta(days=OFFSET_DAYS)


def test_every_evidence_timestamp_follows_the_shifted_clock(db_session, clock_ahead):
    user = _user(db_session)
    word = _word(db_session)
    concept = db_session.query(GrammarConcept).first()
    if concept is None:
        concept = GrammarConcept(external_id=f"WP123B_{uuid.uuid4().hex[:6]}", name="Test", level="A1")
        db_session.add(concept)
        db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed")
    learning = LearningSession(user_id=user.id, planned_duration_minutes=10)
    db_session.add_all([session, learning])
    db_session.flush()
    rows = [
        UserVocabularyProgress(user_id=user.id, word_id=word.id),
        UserGrammarProgress(user_id=user.id, concept_id=concept.id),
        UserError(user_id=user.id, error_category="grammar"),
        WordInteraction(session_id=learning.id, user_id=user.id, word_id=word.id, interaction_type="scene_lexicon"),
        AtelierAttempt(
            atelier_session_id=session.id, user_id=user.id, round="recognize", mode="fill",
            exercise_id="wp123b", verdict="correct", score_0_4=3.0,
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    expected = _shifted_day().date()
    for row in rows:
        db_session.refresh(row)
        assert _aware(row.created_at).date() == expected, (type(row).__name__, row.created_at)
    progress = rows[0]
    assert _aware(progress.updated_at).date() == expected
    assert _aware(progress.first_seen_date).date() == expected
    # onupdate follows the app clock as well.
    progress.times_seen = 3
    db_session.commit()
    db_session.refresh(progress)
    assert _aware(progress.updated_at).date() == expected


def test_an_explicit_timestamp_still_wins(db_session, clock_ahead):
    user = _user(db_session)
    word = _word(db_session)
    then = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
    row = UserVocabularyProgress(user_id=user.id, word_id=word.id, created_at=then)
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert _aware(row.created_at) == then


def test_the_measured_intake_counts_a_card_created_on_the_shifted_day(db_session, clock_ahead):
    from app.services.level_forecast import measured_intake

    user = _user(db_session)
    for _ in range(7):
        db_session.add(UserVocabularyProgress(user_id=user.id, word_id=_word(db_session).id))
    db_session.commit()
    measured = measured_intake(db_session, user, now=_shifted_day())
    # Seven cards in the 14-day window: half a word a day. With the database's
    # clock they were 20 days old and the window was empty (0 words a day).
    assert measured.words_per_day == pytest.approx(7 / 14)


def test_without_the_test_clock_the_default_is_the_real_utc_now():
    before = datetime.now(UTC)
    value = app_now()
    assert value.tzinfo is not None
    assert before - timedelta(seconds=1) <= value <= datetime.now(UTC) + timedelta(seconds=1)
    # The schema default is unchanged (no migration): raw SQL inserts keep now().
    for column in (UserVocabularyProgress.__table__.c.created_at, UserError.__table__.c.created_at):
        assert column.server_default is not None
        assert column.default is not None and column.default.arg.__name__ == "app_now"
