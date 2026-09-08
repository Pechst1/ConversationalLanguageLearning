"""WP-09 — the practical capability rubric (CONTRACTS §8).

Behavioural tests: every one drives the real
``app.services.journey_capabilities.build_capability_summary`` over evidence
written by the real WP-05 writer, so a rubric claim here is a claim about what
the learner's canonical records actually say.

The dangerous failure this file guards is the flattering one: reporting an
ability the learner never demonstrated. Reading, tapping, a one-word recall, a
copied suggestion, an unfinished objective and a historic row with unrecorded
help usage must all stay below "used it independently".
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.main import create_app
from app.services import journey_capabilities
from app.services.daily_journey_adapters import build_default_adapters
from app.services.journey_capabilities import (
    build_capability_summary,
    build_journey_capability_evidence,
)
from app.services.journey_contracts import (
    JOURNEY_CONTENT_VERSION,
    AssistanceLevel,
    CapabilityKey,
    CapabilityState,
    EvidenceKind,
    InputMode,
    ResponseEvaluation,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import (
    apply_learning_evidence,
    ensure_journey_learning_session,
)

FIXTURES = Path(__file__).parent / "fixtures" / "daily_journey_v1" / "public"
TEST_PASSWORD = "securepass123"


# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------

def _user(db_session: Session, **kwargs) -> User:
    fields = {
        "native_language": "en",
        "target_language": "fr",
        "proficiency_level": "A2",
    }
    fields.update(kwargs)
    user = User(
        id=uuid4(),
        email=f"capability-{uuid4().hex}@example.com",
        hashed_password="test",
        **fields,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _word(db_session: Session, word: str = "café") -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=f"{word}-{uuid4().hex[:6]}",
        normalized_word=f"{word}-{uuid4().hex[:6]}",
        english_translation=f"{word}-en",
        difficulty_level=1,
        frequency_rank=100,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _due_progress(db_session: Session, user: User, word: VocabularyWord) -> UserVocabularyProgress:
    now = datetime.now(UTC)
    progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=word.id,
        state="review",
        stability=3.0,
        difficulty=5.0,
        reps=2,
        due_at=now - timedelta(days=2),
        next_review_date=now - timedelta(days=2),
        due_date=(now - timedelta(days=2)).date(),
    )
    db_session.add(progress)
    db_session.flush()
    return progress


def _target(word: VocabularyWord) -> TargetRef:
    return TargetRef(
        kind=TargetKind.VOCABULARY,
        id=str(word.id),
        label_fr=word.word,
        label_native=word.english_translation,
    )


def _journey(
    db_session: Session,
    user: User,
    *,
    scenario_key: str = "order_at_cafe",
    local_date: date | None = None,
    timezone_name: str = "UTC",
    location_name: str | None = "Le Mistral",
    character_name: str | None = "Margaux",
    step_kinds: tuple[str, ...] = ("respond",),
) -> tuple[DailyJourney, list[DailyJourneyStep]]:
    journey = DailyJourney(
        user_id=user.id,
        local_date=local_date or date(2026, 9, 5),
        timezone=timezone_name,
        content_version=JOURNEY_CONTENT_VERSION,
        level_band="A1",
        status="completed",
        scenario_snapshot={
            "scenario_key": scenario_key,
            "title_fr": "Un café au Mistral",
            "location_name": location_name,
            "character_name": character_name,
        },
    )
    db_session.add(journey)
    db_session.flush()
    steps: list[DailyJourneyStep] = []
    for ordinal, kind in enumerate(step_kinds):
        step = DailyJourneyStep(
            journey_id=journey.id, ordinal=ordinal, kind=kind, status="completed"
        )
        db_session.add(step)
        steps.append(step)
    db_session.flush()
    return journey, steps


def _turn(
    db_session: Session,
    *,
    user: User,
    journey: DailyJourney,
    step: DailyJourneyStep,
    observations: list[TargetObservation],
    outcome: TaskOutcome = TaskOutcome.MET,
    assistance: AssistanceLevel = AssistanceLevel.NONE,
    modality: InputMode = InputMode.TEXT,
    when: datetime | None = None,
    timezone_name: str = "UTC",
):
    """Write one response turn through the real WP-05 evidence writer."""

    session = ensure_journey_learning_session(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key=str(journey.scenario_snapshot["scenario_key"]),
    )
    return apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey.id,
        step_id=step.id,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=outcome,
            assistance=assistance,
            observations=observations,
        ),
        modality=modality,
        timezone=timezone_name,
        now=when or datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
    )


def _observation(
    word: VocabularyWord,
    *,
    kind: EvidenceKind = EvidenceKind.PRODUCED_INDEPENDENT,
    assistance: AssistanceLevel = AssistanceLevel.NONE,
    modality: InputMode = InputMode.TEXT,
) -> TargetObservation:
    return TargetObservation(
        target=_target(word),
        evidence_kind=kind,
        assistance=assistance,
        modality=modality,
        learner_text="Un café, s'il vous plaît",
    )


def _independent_journey(
    db_session: Session,
    user: User,
    *,
    when: datetime,
    local_date: date,
    timezone_name: str = "UTC",
    modality: InputMode = InputMode.TEXT,
    scenario_key: str = "order_at_cafe",
) -> DailyJourney:
    """One complete, unassisted, objective-fulfilling response turn."""

    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (step,) = _journey(
        db_session,
        user,
        scenario_key=scenario_key,
        local_date=local_date,
        timezone_name=timezone_name,
    )
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[_observation(word, modality=modality)],
        modality=modality,
        when=when,
        timezone_name=timezone_name,
    )
    return journey


def _summary(db_session: Session, user: User, key: CapabilityKey, **kwargs):
    view = build_capability_summary(db_session, user=user, **kwargs)
    return next(item for item in view.capabilities if item.capability_key is key)


def _legacy_history(db_session: Session, user: User, *, scenario_key: str) -> None:
    """A pre-V2 completed moment: a success boolean with no recorded help."""

    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=10,
        topic="legacy atelier session",
        scenario=scenario_key,
        status="completed",
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        SessionLearningMoment(
            session_id=session.id,
            user_id=user.id,
            kind="vocab_check",
            source_type="atelier",
            source_id=str(uuid4()),
            status="completed",
            prompt_payload={"title": "un café"},
            result_payload={"correct": True},
            completed_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        )
    )
    db_session.flush()


# --------------------------------------------------------------------------
# 1. The empty and unknown floors
# --------------------------------------------------------------------------

def test_a_learner_with_no_evidence_has_tried_nothing(db_session: Session) -> None:
    user = _user(db_session)

    view = build_capability_summary(db_session, user=user)

    assert view.rubric_version == "capability-rubric-v1"
    assert [item.capability_key for item in view.capabilities] == [
        CapabilityKey.ORDER_AT_CAFE,
        CapabilityKey.ARRANGE_MEETING,
        CapabilityKey.EXPLAIN_DELAY,
    ]
    assert all(item.state is CapabilityState.NOT_TRIED for item in view.capabilities)
    assert all(item.modalities == [] for item in view.capabilities)
    assert all(item.evidence == [] for item in view.capabilities)
    assert all(item.latest_qualifying_on is None for item in view.capabilities)


def test_historic_success_with_unknown_help_never_becomes_independence(
    db_session: Session,
) -> None:
    user = _user(db_session)
    _legacy_history(db_session, user, scenario_key="order_at_cafe")

    view = build_capability_summary(db_session, user=user)
    cafe = next(
        item for item in view.capabilities
        if item.capability_key is CapabilityKey.ORDER_AT_CAFE
    )

    assert cafe.state is CapabilityState.UNKNOWN
    assert cafe.modalities == [], "unknown history proves no modality"
    assert cafe.latest_qualifying_on is None
    assert cafe.evidence == []
    assert [
        item.state for item in view.capabilities
        if item.capability_key is not CapabilityKey.ORDER_AT_CAFE
    ] == [CapabilityState.NOT_TRIED, CapabilityState.NOT_TRIED]


def test_recorded_support_outranks_unknown_history(db_session: Session) -> None:
    user = _user(db_session)
    _legacy_history(db_session, user, scenario_key="order_at_cafe")
    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (step,) = _journey(db_session, user)
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[
            _observation(
                word,
                kind=EvidenceKind.PRODUCED_SUPPORTED,
                assistance=AssistanceLevel.SUGGESTED_RESPONSE,
            )
        ],
        assistance=AssistanceLevel.SUGGESTED_RESPONSE,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.WITH_SUPPORT


# --------------------------------------------------------------------------
# 2. The ladder
# --------------------------------------------------------------------------

def test_supported_then_independent_then_used_again_later(db_session: Session) -> None:
    user = _user(db_session)

    supported_word = _word(db_session)
    _due_progress(db_session, user, supported_word)
    supported_journey, (supported_step,) = _journey(
        db_session, user, local_date=date(2026, 9, 1)
    )
    _turn(
        db_session,
        user=user,
        journey=supported_journey,
        step=supported_step,
        observations=[
            _observation(
                supported_word,
                kind=EvidenceKind.PRODUCED_SUPPORTED,
                assistance=AssistanceLevel.SUGGESTED_RESPONSE,
            )
        ],
        assistance=AssistanceLevel.SUGGESTED_RESPONSE,
        when=datetime(2026, 9, 1, 9, 0, tzinfo=UTC),
    )
    assert _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE).state is (
        CapabilityState.WITH_SUPPORT
    )

    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
    )
    once = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    assert once.state is CapabilityState.INDEPENDENT_ONCE
    assert once.latest_qualifying_on == date(2026, 9, 3)

    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    again = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    assert again.state is CapabilityState.USED_AGAIN_LATER
    assert again.latest_qualifying_on == date(2026, 9, 5)
    assert [item.state for item in again.evidence] == [
        CapabilityState.USED_AGAIN_LATER,
        CapabilityState.INDEPENDENT_ONCE,
        CapabilityState.WITH_SUPPORT,
    ], "the weaker history is preserved, newest first"

    # None of the other capabilities moved.
    assert _summary(db_session, user, CapabilityKey.EXPLAIN_DELAY).state is (
        CapabilityState.NOT_TRIED
    )


def test_a_capability_never_borrows_another_scenarios_evidence(db_session: Session) -> None:
    user = _user(db_session)
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
        scenario_key="arrange_meeting",
    )

    view = build_capability_summary(db_session, user=user)
    states = {item.capability_key: item.state for item in view.capabilities}

    assert states[CapabilityKey.ARRANGE_MEETING] is CapabilityState.INDEPENDENT_ONCE
    assert states[CapabilityKey.ORDER_AT_CAFE] is CapabilityState.NOT_TRIED
    assert states[CapabilityKey.EXPLAIN_DELAY] is CapabilityState.NOT_TRIED


# --------------------------------------------------------------------------
# 3. What can never qualify as independence
# --------------------------------------------------------------------------

def test_choice_selection_alone_can_never_qualify(db_session: Session) -> None:
    user = _user(db_session)
    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (step,) = _journey(db_session, user)
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[_observation(word, kind=EvidenceKind.RECOGNIZED)],
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.NOT_TRIED, "picking the right option is recognition"
    assert summary.evidence == []


def test_a_recall_answer_is_not_the_scenario_objective(db_session: Session) -> None:
    user = _user(db_session)
    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (recall_step,) = _journey(db_session, user, step_kinds=("recall",))
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=recall_step,
        observations=[_observation(word)],
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.NOT_TRIED, (
        "a perfect one-word recall does not mean the learner ordered a coffee"
    )


def test_an_unfulfilled_objective_never_reports_independence(db_session: Session) -> None:
    user = _user(db_session)
    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (step,) = _journey(db_session, user)
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[_observation(word)],
        outcome=TaskOutcome.PARTIALLY_MET,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.WITH_SUPPORT


def test_help_anywhere_in_the_turn_keeps_the_whole_turn_supported(
    db_session: Session,
) -> None:
    user = _user(db_session)
    revealed = _word(db_session, "terrasse")
    unaided = _word(db_session)
    _due_progress(db_session, user, revealed)
    _due_progress(db_session, user, unaided)
    journey, (step,) = _journey(db_session, user)
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[
            _observation(
                revealed,
                kind=EvidenceKind.PRODUCED_SUPPORTED,
                assistance=AssistanceLevel.SOLUTION,
            ),
            _observation(unaided),
        ],
        assistance=AssistanceLevel.SOLUTION,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.WITH_SUPPORT, (
        "a revealed solution helped the sentence, not just one word"
    )


def test_another_learners_evidence_never_appears(db_session: Session) -> None:
    owner = _user(db_session)
    stranger = _user(db_session)
    _independent_journey(
        db_session,
        owner,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
    )
    _legacy_history(db_session, owner, scenario_key="explain_delay")

    view = build_capability_summary(db_session, user=stranger)

    assert all(item.state is CapabilityState.NOT_TRIED for item in view.capabilities)
    assert all(item.evidence == [] for item in view.capabilities)
    assert _summary(db_session, owner, CapabilityKey.ORDER_AT_CAFE).state is (
        CapabilityState.INDEPENDENT_ONCE
    )


# --------------------------------------------------------------------------
# 4. The three repeat-use conditions
# --------------------------------------------------------------------------

def test_two_independent_uses_on_the_same_day_stay_independent_once(
    db_session: Session,
) -> None:
    """Yesterday's journey, finished this morning, plus today's journey.

    Two different journey IDs, but both observations land on the same
    learner-local date, so this is one day's work and not a later reuse.
    """

    user = _user(db_session)
    _independent_journey(
        db_session, user, when=datetime(2026, 9, 5, 8, 0, tzinfo=UTC), local_date=date(2026, 9, 4)
    )
    _independent_journey(
        db_session, user, when=datetime(2026, 9, 5, 21, 0, tzinfo=UTC), local_date=date(2026, 9, 5)
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.INDEPENDENT_ONCE
    assert summary.latest_qualifying_on == date(2026, 9, 5)


def test_two_independent_uses_in_the_same_journey_stay_independent_once(
    db_session: Session,
) -> None:
    user = _user(db_session)
    first_word = _word(db_session)
    second_word = _word(db_session, "addition")
    _due_progress(db_session, user, first_word)
    _due_progress(db_session, user, second_word)
    journey, (step,) = _journey(db_session, user, local_date=date(2026, 9, 4))
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[_observation(first_word)],
        when=datetime(2026, 9, 4, 8, 0, tzinfo=UTC),
    )
    # A journey that runs across midnight: a different learner-local date and
    # more than 24 hours later, but the *same* journey.
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[_observation(second_word)],
        when=datetime(2026, 9, 6, 9, 0, tzinfo=UTC),
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.INDEPENDENT_ONCE, (
        "one journey is one opportunity, however long it stayed open"
    )


def test_two_independent_uses_less_than_24_hours_apart_stay_independent_once(
    db_session: Session,
) -> None:
    user = _user(db_session)
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 4, 22, 0, tzinfo=UTC),
        local_date=date(2026, 9, 4),
    )
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 7, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.INDEPENDENT_ONCE, (
        "different journeys and different dates, but only nine hours apart"
    )


def test_repeat_use_needs_all_three_conditions_together(db_session: Session) -> None:
    user = _user(db_session)
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 4, 8, 0, tzinfo=UTC),
        local_date=date(2026, 9, 4),
    )
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.USED_AGAIN_LATER
    assert summary.latest_qualifying_on == date(2026, 9, 5)


def test_the_learner_local_date_decides_the_boundary(db_session: Session) -> None:
    """Two UTC instants 26 hours apart that are the *same* Auckland date."""

    user = _user(db_session)
    # 2026-09-04 12:00 UTC is 2026-09-05 00:00 in Auckland (UTC+12).
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 4, 12, 30, tzinfo=UTC),
        local_date=date(2026, 9, 5),
        timezone_name="Pacific/Auckland",
    )
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 14, 30, tzinfo=UTC),
        local_date=date(2026, 9, 6),
        timezone_name="Pacific/Auckland",
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.USED_AGAIN_LATER
    assert summary.latest_qualifying_on == date(2026, 9, 6), (
        "the qualifying date is the learner's own, not UTC's"
    )


def test_replayed_evidence_is_still_one_opportunity(db_session: Session) -> None:
    user = _user(db_session)
    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (step,) = _journey(db_session, user)
    for _ in range(3):
        _turn(
            db_session,
            user=user,
            journey=journey,
            step=step,
            observations=[_observation(word)],
        )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.INDEPENDENT_ONCE, (
        "an HTTP retry must not manufacture a second independent use"
    )
    assert len(summary.evidence) == 1


# --------------------------------------------------------------------------
# 5. Modality, context, and what the summary exposes
# --------------------------------------------------------------------------

def test_a_written_success_never_claims_pronunciation(db_session: Session) -> None:
    user = _user(db_session)
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
        modality=InputMode.TEXT,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.modalities == [InputMode.TEXT]
    assert [item.modality for item in summary.evidence] == [InputMode.TEXT]


def test_a_spoken_success_reports_voice(db_session: Session) -> None:
    user = _user(db_session)
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
        modality=InputMode.VOICE,
    )
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
        modality=InputMode.TEXT,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.USED_AGAIN_LATER
    assert summary.modalities == [InputMode.TEXT, InputMode.VOICE]
    assert {item.modality for item in summary.evidence} == {
        InputMode.TEXT,
        InputMode.VOICE,
    }


def test_evidence_carries_the_task_the_date_and_the_source_context(
    db_session: Session,
) -> None:
    user = _user(db_session)
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)
    (evidence,) = summary.evidence

    assert summary.title_native == "Order at a café"
    assert evidence.capability_key is CapabilityKey.ORDER_AT_CAFE
    assert evidence.state is CapabilityState.INDEPENDENT_ONCE
    assert evidence.observed_on == date(2026, 9, 3)
    assert evidence.context_native == "Ordered at Le Mistral with Margaux."


def test_context_never_invents_a_place_the_journey_did_not_record(
    db_session: Session,
) -> None:
    user = _user(db_session)
    word = _word(db_session)
    _due_progress(db_session, user, word)
    journey, (step,) = _journey(db_session, user, location_name=None, character_name=None)
    _turn(db_session, user=user, journey=journey, step=step, observations=[_observation(word)])

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.evidence[0].context_native == "Ordered at a café."


def test_controls_follow_the_learners_language(db_session: Session) -> None:
    user = _user(db_session, native_language="de")
    _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
    )

    german = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE, control_language="de")
    french = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE, control_language="fr")
    fallback = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE, control_language="sv")

    assert german.title_native == "Im Café bestellen"
    assert german.evidence[0].context_native == "Im Le Mistral bei Margaux bestellt."
    assert french.title_native == "Commander au café"
    assert fallback.title_native == "Order at a café"


# --------------------------------------------------------------------------
# 6. The labels change nothing else
# --------------------------------------------------------------------------

def test_capability_labels_change_neither_cefr_nor_the_srs_schedule(
    db_session: Session,
) -> None:
    user = _user(db_session, cefr_estimate="A1")
    word = _word(db_session)
    progress = _due_progress(db_session, user, word)
    journey, (step,) = _journey(db_session, user)
    _turn(db_session, user=user, journey=journey, step=step, observations=[_observation(word)])
    db_session.flush()

    def schedule() -> tuple:
        # SQLite drops tzinfo on refresh; compare wall-clock values.
        due_at = progress.due_at
        return (
            user.cefr_estimate,
            user.proficiency_level,
            due_at.replace(tzinfo=None) if due_at is not None else None,
            progress.reps,
            progress.lapses,
            progress.state,
        )

    before = schedule()
    moments_before = (
        db_session.query(SessionLearningMoment)
        .filter(SessionLearningMoment.user_id == user.id)
        .count()
    )

    for _ in range(3):
        build_capability_summary(db_session, user=user)
    db_session.flush()
    db_session.refresh(progress)
    db_session.refresh(user)

    assert schedule() == before
    assert (
        db_session.query(SessionLearningMoment)
        .filter(SessionLearningMoment.user_id == user.id)
        .count()
        == moments_before
    ), "reading the summary writes no evidence"


def test_the_real_module_replaces_the_stub_adapter() -> None:
    adapters = build_default_adapters()

    assert adapters.capabilities is journey_capabilities
    assert not getattr(adapters.capabilities, "is_stub", False)


# --------------------------------------------------------------------------
# 7. Frozen-fixture parity for the live endpoint
# --------------------------------------------------------------------------

def test_the_endpoint_matches_the_frozen_unknown_legacy_fixture(
    db_session: Session,
) -> None:
    """The real HTTP route, with WP-09 wired in, against the frozen payload."""

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        email = f"capability-fixture-{uuid4().hex}@example.com"
        client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": TEST_PASSWORD,
                "target_language": "fr",
                "native_language": "en",
            },
        )
        token = client.post(
            "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
        ).json()["access_token"]
        user = db_session.query(User).filter(User.email == email).one()
        _legacy_history(db_session, user, scenario_key="order_at_cafe")
        db_session.flush()

        response = client.get(
            "/api/v1/daily-journeys/capabilities/progress",
            headers={"Authorization": f"Bearer {token}"},
        )

    expected = json.loads(
        (FIXTURES / "unknown_legacy_assistance.json").read_text(encoding="utf-8")
    )["response"]
    assert response.status_code == 200, response.text
    assert response.json() == expected


# --------------------------------------------------------------------------
# 8. One rubric: the per-journey view WP-02's recap reads
# --------------------------------------------------------------------------

def test_a_turn_that_touched_no_target_is_still_an_opportunity(
    db_session: Session,
) -> None:
    """WP-09's gap 1: a met objective with no tracked target read `not_tried`.

    A brand-new learner has nothing due, so the response task carries no
    target and the turn produces no per-target observation. The learner still
    ordered the coffee.
    """

    user = _user(db_session)
    journey, (step,) = _journey(db_session, user)
    _turn(db_session, user=user, journey=journey, step=step, observations=[])

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.INDEPENDENT_ONCE
    assert summary.modalities == [InputMode.TEXT]
    assert summary.latest_qualifying_on == date(2026, 9, 5)
    assert [item.context_native for item in summary.evidence] == [
        "Ordered at Le Mistral with Margaux."
    ]


def test_an_unmet_objective_with_no_target_claims_nothing(db_session: Session) -> None:
    user = _user(db_session)
    journey, (step,) = _journey(db_session, user)
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[],
        outcome=TaskOutcome.NOT_YET,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.NOT_TRIED
    assert summary.evidence == []
    assert build_journey_capability_evidence(
        db_session, user=user, journey_id=journey.id
    ) == []


def test_a_supported_turn_with_no_target_is_with_support(db_session: Session) -> None:
    user = _user(db_session)
    journey, (step,) = _journey(db_session, user)
    _turn(
        db_session,
        user=user,
        journey=journey,
        step=step,
        observations=[],
        assistance=AssistanceLevel.SUGGESTED_RESPONSE,
    )

    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert summary.state is CapabilityState.WITH_SUPPORT, (
        "a copied suggestion is never independent production"
    )


def test_the_per_journey_view_never_disagrees_with_the_summary(
    db_session: Session,
) -> None:
    """The one guarantee WP-02's recap depends on."""

    user = _user(db_session)
    journey = _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )

    evidence = build_journey_capability_evidence(
        db_session, user=user, journey_id=journey.id
    )
    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    assert len(evidence) == 1
    assert evidence[0].state is summary.state is CapabilityState.INDEPENDENT_ONCE
    assert evidence[0] in summary.evidence


def test_the_per_journey_view_reports_only_that_journey(db_session: Session) -> None:
    user = _user(db_session)
    first = _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 3, 9, 0, tzinfo=UTC),
        local_date=date(2026, 9, 3),
    )
    second = _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )

    latest = build_journey_capability_evidence(
        db_session, user=user, journey_id=second.id
    )
    earliest = build_journey_capability_evidence(
        db_session, user=user, journey_id=first.id
    )
    summary = _summary(db_session, user, CapabilityKey.ORDER_AT_CAFE)

    # The second journey is the one that closed the repeat pair.
    assert summary.state is CapabilityState.USED_AGAIN_LATER
    assert [item.state for item in latest] == [CapabilityState.USED_AGAIN_LATER]
    assert [item.state for item in earliest] == [CapabilityState.INDEPENDENT_ONCE]
    assert [item.observed_on for item in latest] == [date(2026, 9, 5)]


def test_another_learners_journey_is_never_reported(db_session: Session) -> None:
    owner = _user(db_session)
    stranger = _user(db_session)
    journey = _independent_journey(
        db_session,
        owner,
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )

    assert build_journey_capability_evidence(
        db_session, user=stranger, journey_id=journey.id
    ) == []


def test_the_per_journey_view_writes_nothing(db_session: Session) -> None:
    user = _user(db_session)
    journey = _independent_journey(
        db_session,
        user,
        when=datetime(2026, 9, 5, 10, 0, tzinfo=UTC),
        local_date=date(2026, 9, 5),
    )
    before = (
        db_session.query(SessionLearningMoment)
        .filter(SessionLearningMoment.user_id == user.id)
        .count()
    )

    build_journey_capability_evidence(db_session, user=user, journey_id=journey.id)

    assert (
        db_session.query(SessionLearningMoment)
        .filter(SessionLearningMoment.user_id == user.id)
        .count()
        == before
    )
