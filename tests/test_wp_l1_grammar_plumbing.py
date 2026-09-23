"""WP-L1 · Grammar plumbing — the half owned by grammar.py / atelier.py.

One test per item:
- a mastered concept comes back when its long interval runs out;
- the cold-start picker never serves a studied concept as "new";
- an in-context mention leaves the SM-2 interval readback intact;
- a disabled or unreachable critic no longer sends every set to the fallback.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.config import settings
from app.db.models.atelier import AtelierGenerationEvent
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.schemas.user import UserCreate, UserSettingsUpdate, UserUpdate
from app.services.atelier import (
    ATELIER_GENERATION_MAX_ATTEMPTS,
    AtelierExerciseGenerator,
    AtelierScheduler,
)
from app.services.grammar import GrammarService, previous_interval_days
from app.services.grammar_catalog import FRENCH_CORE_CATALOG_VERSION
from app.services.llm_service import LLMProviderError, LLMResult
from tests.test_atelier import _clear_exercise_sets, _concept, _raw_llm_payload


def _user(db_session, *, cefr: str = "A1.1") -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        cefr_estimate=cefr,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _progress(db_session, user: User, concept: GrammarConcept, **fields) -> UserGrammarProgress:
    row = UserGrammarProgress(user_id=user.id, concept_id=concept.id, **fields)
    db_session.add(row)
    db_session.commit()
    return row


def _catalog(db_session, level: str, *, core_only: bool = False) -> list[GrammarConcept]:
    AtelierScheduler(db_session).ensure_catalog()
    query = db_session.query(GrammarConcept)
    if core_only:
        # Other tests leave active ad-hoc concepts behind; the Relevé counts
        # only the core catalogue.
        query = query.filter(GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_VERSION)
    return (
        query.filter(
            GrammarConcept.active.is_(True),
            GrammarConcept.external_id.isnot(None),
            GrammarConcept.external_id != "",
            GrammarConcept.level == level,
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Mastered concepts stay in the due query
# ---------------------------------------------------------------------------


def test_a_mastered_concept_is_due_again_when_its_interval_runs_out(db_session) -> None:
    user = _user(db_session)
    concept = _catalog(db_session, "A1", core_only=True)[0]
    now = datetime.now(UTC)
    _progress(
        db_session,
        user,
        concept,
        score=9.5,
        reps=6,
        state="gemeistert",
        last_review=now - timedelta(days=61),
        next_review=now - timedelta(days=1),
    )

    due = GrammarService(db_session).get_due_concepts(user=user, limit=5)

    assert due[0][0].id == concept.id
    assert GrammarService(db_session).get_summary(user=user)["due_today"] >= 1


def test_a_mastered_concept_not_yet_due_stays_away(db_session) -> None:
    user = _user(db_session)
    concept = _catalog(db_session, "A1")[0]
    now = datetime.now(UTC)
    _progress(
        db_session,
        user,
        concept,
        score=9.5,
        reps=6,
        state="gemeistert",
        last_review=now - timedelta(days=1),
        next_review=now + timedelta(days=60),
    )

    due = GrammarService(db_session).get_due_concepts(user=user, limit=50)

    assert concept.id not in {c.id for c, _ in due}


# ---------------------------------------------------------------------------
# The cold-start picker never re-serves a studied concept as "new"
# ---------------------------------------------------------------------------


def _studied_not_due(db_session, user: User, concept: GrammarConcept) -> None:
    now = datetime.now(UTC)
    _progress(
        db_session,
        user,
        concept,
        score=8.0,
        reps=2,
        state="gefestigt",
        last_review=now - timedelta(days=2),
        next_review=now + timedelta(days=6),
    )


def test_select_today_never_labels_a_studied_concept_new(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.atelier.placement_band", lambda db, user: None)
    monkeypatch.setattr(AtelierScheduler, "concept_limit", lambda self, user: 3)
    user = _user(db_session)
    a1 = sorted(_catalog(db_session, "A1"), key=lambda c: (not c.is_foundation, c.difficulty_order, c.id))
    # The two concepts the old picker would open on are already studied.
    for concept in a1[:2]:
        _studied_not_due(db_session, user, concept)

    selected = AtelierScheduler(db_session).select_today(user)

    studied = {concept.id for concept in a1[:2]}
    new_ids = {selection.concept.id for selection in selected if selection.role == "new"}
    assert new_ids, "an unstudied A1 concept should still be introduced"
    assert not (new_ids & studied)
    for selection in selected:
        if selection.role == "new":
            assert selection.progress is None


def test_an_exhausted_band_serves_fewer_and_never_walks_up(db_session, monkeypatch) -> None:
    monkeypatch.setattr("app.services.atelier.placement_band", lambda db, user: None)
    monkeypatch.setattr(AtelierScheduler, "concept_limit", lambda self, user: 3)
    user = _user(db_session, cefr="A1.2")
    for concept in _catalog(db_session, "A1"):
        _studied_not_due(db_session, user, concept)

    selected = AtelierScheduler(db_session).select_today(user)

    assert not [selection for selection in selected if selection.role == "new"]


# ---------------------------------------------------------------------------
# An in-context mention leaves the interval readback intact
# ---------------------------------------------------------------------------


def test_practiced_in_context_keeps_the_previous_interval(db_session) -> None:
    """Property: for a concept with history, the (last_review, next_review)
    pair — and so `previous_interval_days`, which SM-2 reads — is identical
    before and after a mention; only the score moves (+0.5)."""

    user = _user(db_session)
    concept = _catalog(db_session, "A1")[0]
    now = datetime.now(UTC)
    last = now - timedelta(days=10)
    nxt = now + timedelta(days=10)
    _progress(
        db_session,
        user,
        concept,
        score=7.0,
        reps=3,
        state="gefestigt",
        last_review=last,
        next_review=nxt,
    )

    GrammarService(db_session).mark_concepts_practiced_in_context(user=user, concept_ids=[concept.id])

    row = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    assert row.score == 7.5
    assert row.reps == 3
    # The column may come back naive; compare the instants.
    assert row.last_review.replace(tzinfo=None) == last.replace(tzinfo=None)
    assert row.next_review.replace(tzinfo=None) == nxt.replace(tzinfo=None)
    assert previous_interval_days(row) == 20


def test_practiced_in_context_first_time_writes_a_consistent_pair(db_session) -> None:
    user = _user(db_session)
    concept = _catalog(db_session, "A1")[1]

    GrammarService(db_session).mark_concepts_practiced_in_context(user=user, concept_ids=[concept.id])

    row = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    assert row.reps == 1
    # WP-L3: a first meeting is the weakest evidence (recognise, with help): a
    # one-day stability, and a (last_review, next_review) pair that says so.
    assert row.stability == 1.0
    assert previous_interval_days(row) == 1


# ---------------------------------------------------------------------------
# A disabled or unreachable critic does not reject every set
# ---------------------------------------------------------------------------


def _result(content: dict) -> LLMResult:
    return LLMResult(
        provider="openai",
        model="gpt-4o-mini",
        content=json.dumps(content),
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
        cost=0.0,
        raw_response={},
    )


class _GenerationOnlyLLM:
    """Generates the fixture payload; the critique call either raises or
    returns a fixed verdict list."""

    def __init__(self, payload: dict, *, critique: dict | Exception | None = None) -> None:
        self.payload = payload
        self.critique = critique
        self.generation_calls = 0
        self.critique_calls = 0

    def generate_chat_completion(self, messages, **kwargs):
        name = (((kwargs.get("response_format") or {}).get("json_schema") or {}).get("name") or "")
        if name == "atelier_exercise_critique":
            self.critique_calls += 1
            if isinstance(self.critique, Exception):
                raise self.critique
            return _result(self.critique or {"verdicts": []})
        self.generation_calls += 1
        return _result(self.payload)


def _events(db_session, concept: GrammarConcept, event_type: str) -> list[AtelierGenerationEvent]:
    return (
        db_session.query(AtelierGenerationEvent)
        .filter(AtelierGenerationEvent.concept_id == concept.id, AtelierGenerationEvent.event_type == event_type)
        .all()
    )


def test_a_disabled_critic_accepts_a_valid_set_as_validator_only(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_EXERCISE_CRITIQUE_ENABLED", False)
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    db_session.query(AtelierGenerationEvent).filter(AtelierGenerationEvent.concept_id == concept.id).delete()
    db_session.commit()
    fake = _GenerationOnlyLLM(json.loads(json.dumps(_raw_llm_payload(concept))))

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert fake.generation_calls == 1
    assert fake.critique_calls == 0
    events = _events(db_session, concept, "validator_only")
    assert len(events) == 1 and events[0].passed is True


def test_an_unreachable_critic_accepts_a_valid_set_as_validator_only(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_EXERCISE_CRITIQUE_ENABLED", True)
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    db_session.query(AtelierGenerationEvent).filter(AtelierGenerationEvent.concept_id == concept.id).delete()
    db_session.commit()
    fake = _GenerationOnlyLLM(
        json.loads(json.dumps(_raw_llm_payload(concept))),
        critique=LLMProviderError("critic timed out"),
    )

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert fake.critique_calls == 1
    assert len(_events(db_session, concept, "validator_only")) == 1


def test_a_critic_that_ran_but_skipped_items_still_blocks(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_EXERCISE_CRITIQUE_ENABLED", True)
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    fake = _GenerationOnlyLLM(json.loads(json.dumps(_raw_llm_payload(concept))), critique={"verdicts": []})

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake).get_or_create(concept)

    assert exercise_set.source == "fallback"
    assert fake.critique_calls == ATELIER_GENERATION_MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# Settings: new words per day is kept (WP-L6) and bounded
# ---------------------------------------------------------------------------


def test_new_words_per_day_is_bounded_on_every_input() -> None:
    import pytest
    from pydantic import ValidationError

    for schema in (UserSettingsUpdate, UserUpdate):
        assert schema(new_words_per_day=50).new_words_per_day == 50
        for bad in (0, 51):
            with pytest.raises(ValidationError):
                schema(new_words_per_day=bad)
    with pytest.raises(ValidationError):
        UserCreate(email="a@example.com", password="long-enough-pw", new_words_per_day=80)
