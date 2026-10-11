"""WP-L1 — grammar plumbing between the daily journey and grammar memory.

One test per item: the journey's grammar target is labelled in French with the
learner's own-language title, a correction in a reply books its concept, a
journey credit grows from the concept's history, and a mastered concept comes
back when its long interval is up.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import (
    GrammarConcept,
    GrammarConceptLocalization,
    UserGrammarProgress,
)
from app.db.models.user import User
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    Correction,
    EvidenceKind,
    InputMode,
    ResponseEvaluation,
    ResponseTask,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_conversation import _observations_for
from app.services.journey_learning import (
    JOURNEY_SOURCE_TYPE,
    _target_ref_for_item,
    apply_learning_evidence,
    ensure_journey_learning_session,
)
from app.services.unified_srs import ItemType, UnifiedSRSService


def _user(db_session, *, native_language: str = "de") -> User:
    user = User(
        id=uuid4(),
        email=f"wp-l1-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language=native_language,
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _articles_concept(db_session) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A1_ART_{uuid4().hex[:8]}",
        language="fr",
        name="Definite articles: le, la, l', les",
        level="A1",
        category="Articles",
        subskill="definite_articles",
        # Ahead of every other active concept in the shared test database, so
        # the inference's first match is this one.
        difficulty_order=-1_000_000,
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    db_session.add_all(
        [
            GrammarConceptLocalization(
                concept_id=concept.id, locale="fr",
                title="Les articles définis : le, la, l', les",
            ),
            GrammarConceptLocalization(
                concept_id=concept.id, locale="de",
                title="Bestimmte Artikel: le, la, l', les",
            ),
        ]
    )
    db_session.flush()
    return concept


def _progress(db_session, user, concept, **fields) -> UserGrammarProgress:
    progress = UserGrammarProgress(user_id=user.id, concept_id=concept.id, **fields)
    db_session.add(progress)
    db_session.flush()
    return progress


def _grammar_item(db_session, user, concept):
    pool = UnifiedSRSService(db_session).get_journey_candidate_pool(user.id)
    return next(
        (
            item
            for item in pool
            if item.item_type is ItemType.GRAMMAR and item.original_id == concept.id
        ),
        None,
    )


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


# --------------------------------------------------------------------------
# (a) labels
# --------------------------------------------------------------------------

def test_a_due_grammar_target_is_labelled_in_french_and_in_the_learner_language(db_session):
    concept = _articles_concept(db_session)
    past = datetime.now(UTC) - timedelta(days=1)

    german = _user(db_session, native_language="de")
    _progress(db_session, german, concept, score=5.0, reps=1, state="in_arbeit", next_review=past)
    target = _target_ref_for_item(_grammar_item(db_session, german, concept))
    assert target.kind is TargetKind.GRAMMAR
    assert target.label_fr == "Les articles définis : le, la, l', les"
    assert target.label_native == "Bestimmte Artikel: le, la, l', les"

    english = _user(db_session, native_language="en")
    _progress(db_session, english, concept, score=5.0, reps=1, state="in_arbeit", next_review=past)
    target = _target_ref_for_item(_grammar_item(db_session, english, concept))
    assert target.label_fr == "Les articles définis : le, la, l', les"
    assert target.label_native == "Definite articles: le, la, l', les"


def test_a_reply_that_quotes_a_grammar_title_is_not_evidence_of_the_concept():
    target = TargetRef(
        kind=TargetKind.GRAMMAR, id="7", label_fr="Les articles définis",
        label_native="Bestimmte Artikel",
    )
    task = ResponseTask(
        objective_native="Order a coffee.",
        character_id="margaux_barman",
        character_name="Margaux",
        opening_line_fr="Bonjour !",
        targets=[target],
        required_intents=["order_drink"],
        allowed_outcomes=["served_at_terrace"],
        rubric_native="The learner orders a drink.",
    )
    text = "Les articles définis, un café s'il vous plaît."
    observations = _observations_for(
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        text=text,
        assistance=AssistanceLevel.NONE,
        correction=None,
    )
    assert observations == []


# --------------------------------------------------------------------------
# (b) a reply's grammar mistake books its concept; a repair credits it
# --------------------------------------------------------------------------

def test_a_journey_correction_names_its_concept_and_makes_it_due_tomorrow(db_session):
    user = _user(db_session)
    concept = _articles_concept(db_session)
    now = datetime.now(UTC)
    _progress(
        db_session, user, concept, score=8.5, reps=3, state="gefestigt",
        last_review=now - timedelta(days=10), next_review=now + timedelta(days=20),
    )
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[],
            # «je vais au le café»: the note says nothing a keyword could find,
            # the determiner-only change is what names the family.
            correction=Correction(
                span_fr="au le café", corrected_fr="au café", note_native="Au = à + le."
            ),
        ),
        modality=InputMode.TEXT,
    )

    erratum = (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.source_type == JOURNEY_SOURCE_TYPE)
        .one()
    )
    assert erratum.concept_id == concept.id
    progress = (
        db_session.query(UserGrammarProgress)
        .filter_by(user_id=user.id, concept_id=concept.id)
        .one()
    )
    assert _naive(progress.next_review) <= _naive(datetime.now(UTC) + timedelta(days=1, minutes=1))

    # Repairing that erratum in a later journey step credits the concept too,
    # the way the unified queue's repair does.
    reps_before = progress.reps
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=uuid4(),
        step_id=uuid4(),
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=TargetRef(kind=TargetKind.ERROR, id=str(erratum.id), label_fr="au café"),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je vais au café.",
                )
            ],
        ),
        modality=InputMode.TEXT,
    )
    db_session.refresh(progress)
    assert progress.reps == reps_before + 1
    assert progress.score == 8.5


# --------------------------------------------------------------------------
# (c) journey credit uses the concept's history
# --------------------------------------------------------------------------

def test_journey_credit_grows_from_the_concepts_history(db_session):
    user = _user(db_session)
    concept = _articles_concept(db_session)
    now = datetime.now(UTC)
    _progress(
        db_session, user, concept, score=8.5, reps=3, state="gefestigt",
        last_review=now - timedelta(days=14), next_review=now,
    )
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=TargetRef(
                        kind=TargetKind.GRAMMAR, id=str(concept.id), label_fr="Les articles"
                    ),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je prends le train.",
                )
            ],
        ),
        modality=InputMode.TEXT,
        now=now,
    )
    progress = (
        db_session.query(UserGrammarProgress)
        .filter_by(user_id=user.id, concept_id=concept.id)
        .one()
    )
    # The first-review seed for this score is 14 days; a fourth success on a
    # 14-day interval must reach further than that.
    assert progress.reps == 4
    assert (_naive(progress.next_review) - _naive(now)).days > 14


# --------------------------------------------------------------------------
# (d) mastered concepts come back at their long interval
# --------------------------------------------------------------------------

def test_a_mastered_concept_past_its_interval_is_in_the_due_pool(db_session):
    user = _user(db_session)
    due = _articles_concept(db_session)
    later = _articles_concept(db_session)
    now = datetime.now(UTC)
    _progress(
        db_session, user, due, score=9.5, reps=6, state="gemeistert",
        last_review=now - timedelta(days=90), next_review=now - timedelta(days=1),
    )
    _progress(
        db_session, user, later, score=9.5, reps=6, state="gemeistert",
        last_review=now - timedelta(days=10), next_review=now + timedelta(days=80),
    )
    service = UnifiedSRSService(db_session)

    assert _grammar_item(db_session, user, due) is not None
    assert _grammar_item(db_session, user, later) is None
    queue_ids = {
        item.original_id
        for item in service.get_daily_practice_queue(user_id=user.id).queue
        if item.item_type is ItemType.GRAMMAR
    }
    assert due.id in queue_ids
    assert later.id not in queue_ids


def test_a_grammar_title_never_becomes_a_recall_question():
    """«Which French phrase means "Definite articles"?» is a fake question (WP-L1)."""

    from app.services.journey_contracts import TargetKind, TargetRef
    from app.services.journey_planner import build_recall_task, build_word_bank_task
    from tests.test_journey_planner import _brief

    target = TargetRef(
        kind=TargetKind.GRAMMAR,
        id="17",
        label_fr="Les articles définis : le, la, l', les",
        label_native="Definite articles: le, la, l', les",
        concept_title=True,
    )
    affordances = ["un café noir", "une table dehors", "s'il vous plaît"]
    assert (
        build_recall_task(target=target, scenario=_brief(), affordances=affordances, optional=False)
        is None
    )
    assert (
        build_word_bank_task(
            target=target, affordances=affordances, optional=False, control_language="en"
        )
        is None
    )
