"""#1098: «Aus deinen Fehlern» confirmed the learner's own slip as right.

Day-7 explore walk of 26 Nov 2026 (``a1-de-fresh``), days 4 and 6, the warm-up «Aus
deinen Fehlern · Was du selbst geschrieben hast, noch einmal richtig»:

* «c est · Schreib richtig, was du gesagt hast.», answered «c est» unchanged: «Richtig».
* «de Allemagne», answered «d Allemagne» (no apostrophe): «Richtig».
* «a 10», from the Courrier line «Je passe demain a 10 heure», built from two tiles
  «10» / «à» with nothing to think about; it came back on day 6 although it was right
  on day 4.

The only thing «c est» and «de Allemagne» test is the apostrophe, and the grader folded
it away: an apostrophe typed as a space is forgiven typography everywhere (#1088), also
where it is the very thing the repair is about. A repair now never accepts the slip it
repairs: a reading that leaves the learner's line as it was, or that lacks the
apostrophe the fix adds, is not right. A short slip is posed inside the learner's
sentence, typed, never as a bare fragment.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models.user import User
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import evaluate_recall
from app.services.journey_planner import build_recall_task
from app.services.repair_context import RepairContext
from tests.test_journey_planner import _brief


def _user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"own-error-1098-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
    )
    db.add(user)
    db.commit()
    return user


def _own_error(slip: str, fix: str, sentence: str | None, error_id: str = "err-1098"):
    return build_recall_task(
        target=TargetRef(kind=TargetKind.ERROR, id=error_id, label_fr=fix),
        scenario=_brief(),
        affordances=[],
        optional=False,
        learner_text=slip,
        repair=RepairContext(sentence=sentence) if sentence else None,
    )


def _outcome(db, task, typed: str) -> TaskOutcome:
    return evaluate_recall(
        db,
        user=_user(db),
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=typed),
        assistance=AssistanceLevel.NONE,
    ).outcome


#: The walk's items, each in the learner's line it came from.
C_EST = ("c est", "c'est", "Oui, c est loin de la gare.")
ALLEMAGNE = ("de Allemagne", "d'Allemagne", "Mon ami vient de Allemagne.")


@pytest.mark.parametrize(
    ("item", "typed"),
    [
        (C_EST, "c est"),
        (C_EST, "C est"),
        (C_EST, "Oui, c est loin de la gare."),
        (ALLEMAGNE, "d Allemagne"),
        (ALLEMAGNE, "de Allemagne"),
        (ALLEMAGNE, "Mon ami vient d Allemagne."),
    ],
)
def test_the_slip_retyped_or_without_its_apostrophe_is_not_right(db_session, item, typed) -> None:
    slip, fix, sentence = item
    task = _own_error(slip, fix, sentence)
    assert task is not None
    outcome = _outcome(db_session, task, typed)
    assert outcome is not TaskOutcome.MET, (
        f"«{typed}» was marked right for the slip «{slip}» (fix «{fix}»): the apostrophe is the whole item"
    )


@pytest.mark.parametrize(
    ("item", "typed"),
    [
        (C_EST, "c'est"),
        (C_EST, "c’est"),
        (C_EST, "Oui, c’est loin de la gare."),
        (ALLEMAGNE, "d'Allemagne"),
        (ALLEMAGNE, "d’Allemagne"),
        (ALLEMAGNE, "Mon ami vient d'Allemagne."),
    ],
)
def test_the_fix_with_its_apostrophe_straight_or_curly_is_right(db_session, item, typed) -> None:
    slip, fix, sentence = item
    task = _own_error(slip, fix, sentence)
    assert _outcome(db_session, task, typed) is TaskOutcome.MET, typed


def test_an_apostrophe_the_repair_is_not_about_stays_forgiven(db_session) -> None:
    # «Nous somes à l’hôtel» repairs «somes»; «l hotel» is typography it does not test (#562).
    task = _own_error("somes", "sommes", "Nous somes à l’hôtel avec Lila.")
    assert _outcome(db_session, task, "Nous sommes à l hotel avec Lila.") is TaskOutcome.MET


@pytest.mark.parametrize(
    ("slip", "fix", "sentence"),
    [("c est", "c'est", None), ("a 10", "à 10", None), ("de Odile", "d'Odile", None)],
)
def test_a_short_slip_is_never_posed_without_the_sentence_it_came_from(slip, fix, sentence) -> None:
    task = _own_error(slip, fix, sentence)
    assert task is None or (task.prompt_fr and len(task.prompt_fr.split()) > len(slip.split())), (
        f"the slip «{slip}» is posed as a bare fragment: {task.prompt_fr if task else None!r}"
    )


def test_a_short_slip_is_typed_inside_its_sentence_not_built_from_tiles() -> None:
    task = _own_error("a 10", "à 10", "Je passe demain a 10 heure.")
    assert task is not None
    assert task.task_type == "short_answer", f"«a 10» is built from the tiles {task.options}: nothing to think about"
    assert task.prompt_fr == "Je passe demain a 10 heure."
    assert task.slip_fr == "a 10"


def test_the_courrier_saves_the_sentence_a_slip_sat_in(db_session) -> None:
    """The walk's «a 10» came from a Courrier letter, saved without its sentence."""

    from app.db.models.error import UserError
    from app.services.missions import MissionCorrectionService

    user = _user(db_session)
    letter = "Bonjour Odile ! Je passe demain a 10 heure. A bientôt."
    mission = type("Mission", (), {"id": uuid.uuid4(), "mission_type": "letter"})()
    MissionCorrectionService(db_session).persist_errata(
        user=user,
        mission=mission,
        correction={
            "errata": [
                {
                    "learner_text": "a 10",
                    "corrected_target": "à 10",
                    "display_label": "Accent",
                    "why_wrong": "«à» devant une heure.",
                    "task_error_type": "grammar",
                }
            ]
        },
        mode="text",
        source_id=str(uuid.uuid4()),
        include_vocabulary=False,
        submission_text=letter,
    )
    saved = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert (saved.error_metadata or {}).get("context_fr") == "Je passe demain a 10 heure."


@pytest.mark.parametrize(
    ("slip", "fix", "sentence", "typed"),
    [
        ("a 10", "à 10", "Je passe demain a 10 heure.", "à 10"),
        ("de Odile", "d'Odile", "C'est le livre de Odile.", "d'Odile"),
    ],
)
def test_an_own_error_answered_right_is_not_served_again_two_days_later(db_session, slip, fix, sentence, typed) -> None:
    from app.db.models.error import UserError
    from app.services.journey_errata import errata_targets_for_user
    from app.services.journey_learning import (
        apply_learning_evidence,
        ensure_journey_learning_session,
    )

    user = _user(db_session)
    now = datetime.now(UTC)
    error = UserError(
        id=uuid.uuid4(),
        user_id=user.id,
        error_category="grammar",
        display_label="Accent",
        original_text=slip,
        correction=fix,
        occurrences=1,
        state="new",
        next_review_date=now - timedelta(hours=1),
        error_metadata={"context_fr": sentence},
    )
    db_session.add(error)
    db_session.commit()
    targets = errata_targets_for_user(db_session, user, now=now)
    target = next(t for t in targets if t.error_id == str(error.id))
    task = build_recall_task(
        target=target.as_candidate().target,
        scenario=_brief(),
        affordances=[],
        optional=False,
        learner_text=slip,
        repair=RepairContext(sentence=sentence),
    )
    assert task is not None
    if task.task_type == "tiles":
        by_text = {tile["text_fr"]: tile["id"] for tile in task.options}
        answer = AttemptAnswer(mode=InputMode.TEXT, text=None, tile_ids=[by_text[word] for word in fix.split()])
    else:
        answer = AttemptAnswer(mode=InputMode.TEXT, text=typed)
    evaluation = evaluate_recall(db_session, user=user, task=task, answer=answer, assistance=AssistanceLevel.NONE)
    assert evaluation.outcome is TaskOutcome.MET
    journey_id = uuid.uuid4()
    session = ensure_journey_learning_session(db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe")
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=uuid.uuid4(),
        session=session,
        evaluation=evaluation,
        modality=InputMode.TEXT,
    )
    db_session.flush()
    two_days_later = now + timedelta(days=2, hours=1)
    again = [t.error_id for t in errata_targets_for_user(db_session, user, now=two_days_later, due_by=two_days_later)]
    assert str(error.id) not in again, (
        f"«{slip}» was answered right and is served again two days later "
        f"(next review {db_session.get(UserError, error.id).next_review_date})"
    )


def _due_slip(db, user, slip: str, fix: str, *, context: str | None, overdue_days: int, now: datetime):
    from app.db.models.error import UserError

    row = UserError(
        id=uuid.uuid4(),
        user_id=user.id,
        error_category="grammar",
        display_label="Grammaire",
        original_text=slip,
        correction=fix,
        occurrences=1,
        state="new",
        next_review_date=now - timedelta(days=overdue_days, hours=1),
        error_metadata={"context_fr": context} if context else {},
    )
    db.add(row)
    return row


def _own_error_recalls(plan) -> list[dict]:
    from app.services.journey_contracts import StepKind

    return [
        dict(step.public_prompt or {})
        for step in plan.steps
        if step.kind is StepKind.RECALL and step.target is not None and step.target.kind is TargetKind.ERROR
    ]


def test_a_slip_that_cannot_be_posed_takes_no_errata_slot(db_session) -> None:
    """Verify of #1115: three context-less short slips kept every errata slot, were never
    posed (so never reviewed, so always most overdue), and «c est», which has its
    sentence, never reached the day: «Aus deinen Fehlern» went empty for good."""

    from app.services.journey_errata import errata_candidates_for_user
    from app.services.journey_planner import plan_journey

    user = _user(db_session)
    now = datetime.now(UTC)
    _due_slip(db_session, user, "une homme", "un homme", context=None, overdue_days=9, now=now)
    _due_slip(db_session, user, "le maison", "la maison", context=None, overdue_days=8, now=now)
    _due_slip(db_session, user, "envoyerai", "enverrai", context=None, overdue_days=7, now=now)
    long_slip = _due_slip(
        db_session, user, "je suis allé au la gare", "je suis allé à la gare", context=None, overdue_days=1, now=now
    )
    c_est = _due_slip(db_session, user, "c est", "c'est", context="Oui, c est loin de la gare.", overdue_days=1, now=now)
    db_session.commit()

    candidates = errata_candidates_for_user(db_session, user, now=now)
    offered = [candidate.metadata.get("erratum_learner") for candidate in candidates]
    assert str(c_est.id) in {candidate.target.id for candidate in candidates}, (
        f"«c est», which has its sentence, takes no errata slot; the slots went to {offered}"
    )
    posed = [(prompt.get("prompt_fr"), prompt.get("slip_fr")) for prompt in _own_error_recalls(
        plan_journey(scenario=_brief(), candidates=candidates)
    )]
    assert posed, f"«Aus deinen Fehlern» is empty: no own-error recall was posed from {offered}"
    assert all(prompt and len(prompt.split()) >= 3 for prompt, _slip in posed), f"a bare fragment was posed: {posed}"

    # The long slip and «c est» tie on the day's one own-error recall; without the
    # long slip, «c est» is posed inside its sentence, its slip marked.
    db_session.delete(long_slip)
    db_session.commit()
    plan = plan_journey(scenario=_brief(), candidates=errata_candidates_for_user(db_session, user, now=now))
    posed = [(prompt.get("prompt_fr"), prompt.get("slip_fr")) for prompt in _own_error_recalls(plan)]
    assert posed == [("Oui, c est loin de la gare.", "c est")], (
        f"«c est» with its sentence was not posed; the day's own-error recalls: {posed}"
    )


def test_a_slip_from_the_journal_is_saved_with_its_sentence_and_posed_inside_it(db_session) -> None:
    """The journal saved «une homme» bare (``learner_text: span``): never posable as a repair."""

    from types import SimpleNamespace

    from app.db.models.error import UserError
    from app.services.journal import JournalService
    from app.services.journey_errata import errata_candidates_for_user
    from app.services.journey_planner import plan_journey

    user = _user(db_session)
    entry = SimpleNamespace(
        id=uuid.uuid4(),
        journey_id=None,
        entry_text="Aujourd'hui je suis au marché. Je vois une homme avec un chien. Il est sympa.",
    )
    JournalService(db_session)._record_errata(
        user,
        entry,
        {"errata": [{"span_fr": "une homme", "corrected_fr": "un homme", "label": "Genre", "note_native": "homme ist maskulin."}]},
    )
    db_session.flush()
    saved = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert (saved.error_metadata or {}).get("context_fr") == "Je vois une homme avec un chien.", (
        f"the journal saved «une homme» without its sentence: {saved.error_metadata!r}"
    )

    now = datetime.now(UTC)
    saved.next_review_date = now - timedelta(days=1)
    db_session.commit()
    plan = plan_journey(scenario=_brief(), candidates=errata_candidates_for_user(db_session, user, now=now))
    posed = [(prompt.get("prompt_fr"), prompt.get("slip_fr")) for prompt in _own_error_recalls(plan)]
    assert posed == [("Je vois une homme avec un chien.", "une homme")], posed
