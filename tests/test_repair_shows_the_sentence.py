"""#278: a repair drill shows the sentence the learner wrote and names its rule.

Walk 22 Oct (day 10, A1.1): the card was the bare word «Sommer», with «Write this
correctly in French. Write what you said, correctly.» A learner who does not
remember the slip cannot tell what is asked. The saved erratum held only the
wrong fragment («sommer»), never the sentence it sat in nor the rule it broke,
so the planner had nothing else to print.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    StepKind,
    TargetKind,
    TargetRef,
)
from app.services.journey_errata import errata_targets_for_user
from app.services.journey_learning import (
    apply_learning_evidence,
    ensure_journey_learning_session,
    evaluate_recall,
)
from app.services.journey_planner import plan_journey
from tests.test_journey_planner import _brief

GAP = "Nous ____ contents ici."
SLIP = "Sommer"
SENTENCE = "Nous Sommer contents ici."
RULE = "Le verbe être au présent"


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"repair-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _concept(db_session) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A1_{uuid4().hex[:8]}",
        language="fr",
        name=RULE,
        level="A1",
        category="Verbes",
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    return concept


def _missed_sentence(db_session, user, concept) -> UserError:
    """The learner types «Sommer» into the gap of «Nous ____ contents ici.», the way the product records it."""

    task = RecallTask(
        task_type="short_answer",
        instruction_native="Fill the gap.",
        prompt_fr=GAP,
        options=[],
        target=TargetRef(kind=TargetKind.GRAMMAR, id=str(concept.id), label_fr=concept.name),
        optional=False,
        accepted_answers=["sommes"],
        solution_fr="sommes",
        hint_native="Nous goes with sommes.",
        source_fr=GAP,
    )
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    evaluation = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=SLIP),
        assistance=AssistanceLevel.NONE,
    )
    assert evaluation.correction is not None
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=evaluation,
        modality=InputMode.TEXT,
    )
    db_session.flush()
    return db_session.query(UserError).filter(UserError.user_id == user.id).one()


def test_a_repair_built_from_a_stored_slip_shows_the_sentence_and_names_the_rule(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session)
    error = _missed_sentence(db_session, user, concept)
    # The stored slip is a fragment, which is why the card used to be one word.
    assert error.original_text == SLIP

    error.next_review_date = datetime.now(UTC) - timedelta(days=1)  # due, as on a later day
    db_session.flush()
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    assert targets
    plan = plan_journey(scenario=_brief(), candidates=[], errata_targets=targets)
    repairs = [
        step
        for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
    ]
    assert repairs, "the stored slip was not planned as a repair"
    shown = json.dumps(repairs[0].public_prompt, ensure_ascii=False)

    assert SENTENCE in shown, f"the repair does not show the sentence the learner wrote: {shown}"
    assert RULE in shown, f"the repair does not name the rule the slip broke: {shown}"
    # The wrong part is named, so the card can mark it inside the sentence.
    assert repairs[0].public_prompt.get("slip_fr") == SLIP, shown
    # The answer is the corrected part (the corrected sentence is accepted too), and the sentence is the headline.
    task = repairs[0].private_task
    assert task.prompt_fr == SENTENCE and task.accepted_answers[0] == "sommes"


def test_a_missed_repair_and_its_solution_say_the_rule(db_session) -> None:
    user = _user(db_session)
    concept = _concept(db_session)
    error = _missed_sentence(db_session, user, concept)
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db_session.flush()
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    plan = plan_journey(scenario=_brief(), candidates=[], errata_targets=targets)
    task = next(
        step.private_task
        for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
    )
    assert RULE in (task.rule_native or ""), "the repair carries no rule to show with its answer"
    missed = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="sommer"),
        assistance=AssistanceLevel.NONE,
    )
    assert missed.correction is not None
    assert RULE in missed.correction.note_native, missed.correction.note_native


def test_a_slip_found_alone_in_a_gap_is_put_back_in_its_sentence() -> None:
    from app.services.repair_context import context_sentence, corrected_sentence

    assert context_sentence(slip="Sommer", answer="Sommer", prompt="Nous ____ contents ici.") == SENTENCE
    # The learner's own longer answer is the sentence; the item's prompt is not needed.
    assert context_sentence(slip="sommer", answer="Nous sommer là.", prompt=None) == "Nous sommer là."
    # A slip that stands alone, with nothing around it, has no sentence: nothing is made up.
    assert context_sentence(slip="sommer", answer="sommer", prompt=None) is None
    assert corrected_sentence(SENTENCE, "Sommer", "sommes") == "Nous sommes contents ici."


def test_a_forge_slip_is_saved_with_the_sentence_of_its_item(db_session) -> None:
    """The Forge and the Séance save errata too: the same bare fragment, the same fix."""

    from app.db.models.atelier import AtelierAttempt, AtelierSession
    from app.services.error_memory import ErrorMemoryService

    user = _user(db_session)
    concept = _concept(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="recognize",
        mode="fill",
        exercise_id="fill-1",
        prompt_payload={"items": [{"id": "fill-1", "prompt": GAP, "choices": ["sommes", "êtes", "sont"]}]},
        answer_payload={},
        correction_payload={
            "errata": [
                {
                    "item_id": "fill-1",
                    "learner_text": SLIP,
                    "corrected_target": "sommes",
                    "display_label": "Être au présent",
                    "why_wrong": "Nous goes with sommes.",
                    "task_error_type": "grammar_target",
                }
            ]
        },
        verdict="needs_work",
        score_0_4=0.0,
    )
    db_session.add(attempt)
    db_session.flush()
    ErrorMemoryService(db_session).record_atelier_attempt(user=user, attempt=attempt)
    saved = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert saved.original_text == SLIP
    assert (saved.error_metadata or {}).get("context_fr") == SENTENCE


def test_a_repair_that_shows_a_sentence_accepts_the_corrected_sentence_and_the_word(db_session) -> None:
    """Reviewer note, PR #291: the card prints «Nous Sommer contents ici.» under
    «Write this correctly», so the corrected sentence must be marked right as well
    as the one marked word."""

    from app.services.journey_contracts import TaskOutcome

    user = _user(db_session)
    concept = _concept(db_session)
    error = _missed_sentence(db_session, user, concept)
    error.next_review_date = datetime.now(UTC) - timedelta(days=1)
    db_session.flush()
    targets = errata_targets_for_user(db_session, user, now=datetime.now(UTC))
    plan = plan_journey(scenario=_brief(), candidates=[], errata_targets=targets)
    task = next(
        step.private_task
        for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
    )
    assert task.prompt_fr == SENTENCE
    for typed in ("sommes", "Nous sommes contents ici.", "nous sommes contents ici"):
        verdict = evaluate_recall(
            db_session,
            user=user,
            task=task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text=typed),
            assistance=AssistanceLevel.NONE,
        )
        assert verdict.outcome is TaskOutcome.MET, (
            f"«{typed}» is a correct answer to the card but was marked {verdict.outcome}"
        )
