"""Owner request 2026-10-17: «Corrige cette phrase» without retyping the sentence,
and a missed drill asked once more at the end of its set.

* A repair is right when the learner writes only the corrected part («vertes» for
  «des chaises vert»), the part with some of its context, or the whole sentence —
  one rule (``answer_acceptance.judge_repair``) for the daily drill and La Forge.
* A wrong part is corrected as a part («verts → vertes»), and saved as the whole
  sentence it stands for.
* A missed drill comes back once after the last drill of its run; missing it again
  books nothing a second time.
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

import app.services.daily_journey as journey_module
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.user import User
from app.schemas.daily_journey import (
    JourneyAdvanceRequest,
    JourneyAttemptRequest,
    JourneyCreateRequest,
)
from app.services.answer_acceptance import judge_repair
from app.services.daily_journey import RETRY_OF_KEY, DailyJourneyService
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import evaluate_recall

SOURCE = "des chaises vert"
RIGHT = ["des chaises vertes"]


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    ["vertes", "chaises vertes", "des chaises vertes", "Des chaises vertes.", "  VERTES "],
)
def test_the_corrected_part_or_the_whole_sentence_is_right(answer: str) -> None:
    assert judge_repair(answer, SOURCE, RIGHT).correct


@pytest.mark.parametrize("answer", ["vert", "verts", "rouge", "chaises", "des", "vertes vertes"])
def test_a_part_that_does_not_hold_the_whole_correction_is_wrong(answer: str) -> None:
    assert not judge_repair(answer, SOURCE, RIGHT).correct


def test_a_wrong_part_is_measured_against_the_part_it_stands_for() -> None:
    verdict = judge_repair("verts", SOURCE, RIGHT)

    assert verdict.read_as == "des chaises verts"
    assert verdict.expected_part == "vertes"
    assert verdict.note == "form"


def test_a_change_in_the_middle_of_the_sentence_is_answered_by_its_part() -> None:
    source, right = "Hier, il a allé au cinéma.", ["Hier, il est allé au cinéma."]

    assert judge_repair("est", source, right).correct
    assert judge_repair("il est allé", source, right).correct
    assert not judge_repair("a", source, right).correct
    assert not judge_repair("allé", source, right).correct


def test_a_part_is_judged_by_the_same_contract_as_a_sentence() -> None:
    # An accent that is grammar stays strict; elision is French, not typography.
    assert not judge_repair("a", "Il va a Paris.", ["Il va à Paris."]).correct
    assert judge_repair("à", "Il va a Paris.", ["Il va à Paris."]).correct
    assert judge_repair("l'eau", "Je bois le eau.", ["Je bois l'eau."]).correct
    assert judge_repair("l’eau", "Je bois le eau.", ["Je bois l'eau."]).correct


# ---------------------------------------------------------------------------
# The daily drill
# ---------------------------------------------------------------------------


def _user(db: Session, email: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="x",
        native_language="fr",
        target_language="fr",
        proficiency_level="beginner",
    )
    db.add(user)
    db.commit()
    return user


def _repair_task() -> RecallTask:
    return RecallTask(
        task_type="transform",
        instruction_native="Corrige cette phrase.",
        prompt_fr=SOURCE,
        options=[],
        target=TargetRef(kind=TargetKind.GRAMMAR, id="adj-accord", label_fr="L'accord de l'adjectif"),
        optional=False,
        accepted_answers=list(RIGHT),
        hint_native="L'adjectif s'accorde avec le nom.",
        solution_fr=RIGHT[0],
        source_fr=SOURCE,
    )


def _grade(db: Session, user: User, text: str):
    return evaluate_recall(
        db,
        user=user,
        task=_repair_task(),
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        assistance=AssistanceLevel.NONE,
    )


def test_the_screenshot_answer_is_right(db_session: Session) -> None:
    user = _user(db_session, "repair-part-right@example.com")

    evaluation = _grade(db_session, user, "vertes")

    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.correction is None


def test_a_wrong_part_is_corrected_as_a_part_and_saved_as_a_sentence(db_session: Session) -> None:
    user = _user(db_session, "repair-part-wrong@example.com")

    evaluation = _grade(db_session, user, "verts")

    assert evaluation.outcome is TaskOutcome.NOT_YET
    correction = evaluation.correction
    assert correction is not None
    assert (correction.span_fr, correction.corrected_fr) == ("verts", "vertes")
    assert (correction.saved_span_fr, correction.saved_corrected_fr) == ("des chaises verts", RIGHT[0])


def test_a_wrong_whole_sentence_is_still_corrected_whole(db_session: Session) -> None:
    user = _user(db_session, "repair-part-whole@example.com")

    correction = _grade(db_session, user, "des chaises verts").correction

    assert correction is not None
    assert correction.corrected_fr == RIGHT[0]
    assert correction.saved_span_fr is None


# ---------------------------------------------------------------------------
# La Forge
# ---------------------------------------------------------------------------


def test_a_forge_repair_takes_the_corrected_part(db_session: Session) -> None:
    from app.services.atelier import AtelierCorrectionService

    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = "fr"
    prompt = {"items": [{"id": "r1", "source": SOURCE, "source_fr": SOURCE, "expected_answer": RIGHT[0]}]}

    right = service._correct_transform_rule_based(None, prompt, {"answers": {"r1": "vertes"}})
    wrong = service._correct_transform_rule_based(None, prompt, {"answers": {"r1": "verts"}})

    assert right["verdict"] == "correct"
    assert wrong["verdict"] == "incorrect"
    assert wrong["errata"][0]["learner_text"] == "des chaises verts"


# ---------------------------------------------------------------------------
# The retry at the end of the set
# ---------------------------------------------------------------------------


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)


def _wrong_input(db: Session, step_id: str) -> dict[str, Any]:
    step = db.get(DailyJourneyStep, uuid.UUID(step_id))
    task = dict(step.private_task or {})["recall_task"]
    if task.get("correct_option_id"):
        other = next(o["id"] for o in task["options"] if o["id"] != task["correct_option_id"])
        return {"mode": "choice", "option_id": other}
    if task.get("correct_tile_order"):
        return {"mode": "tiles", "tile_ids": list(reversed(task["correct_tile_order"]))}
    return {"mode": "text", "text": "zzz"}


def _right_input(db: Session, step_id: str) -> dict[str, Any]:
    step = db.get(DailyJourneyStep, uuid.UUID(step_id))
    task = dict(step.private_task or {})["recall_task"]
    if task.get("correct_option_id"):
        return {"mode": "choice", "option_id": task["correct_option_id"]}
    if task.get("correct_tile_order"):
        return {"mode": "tiles", "tile_ids": list(task["correct_tile_order"])}
    return {"mode": "text", "text": (task.get("accepted_answers") or [""])[0]}


def _answer(service, user, state, step_id: str, payload: dict[str, Any]):
    result = service.submit_attempt(
        user,
        uuid.UUID(state.id),
        uuid.UUID(step_id),
        JourneyAttemptRequest.model_validate(
            {"mutation_id": uuid.uuid4().hex, "expected_revision": state.revision, "input": payload}
        ),
    )
    state = service.advance(
        user,
        uuid.UUID(state.id),
        JourneyAdvanceRequest(
            mutation_id=uuid.uuid4().hex, expected_revision=result.journey.revision, current_step_id=step_id
        ),
    )
    return result, state


def _advance(service, user, state):
    return service.advance(
        user,
        uuid.UUID(state.id),
        JourneyAdvanceRequest(
            mutation_id=uuid.uuid4().hex, expected_revision=state.revision, current_step_id=state.current_step_id
        ),
    )


def _start(db: Session, email: str):
    from app.services.daily_journey_adapters import build_default_adapters
    from tests.test_journey_end_to_end import CAFE_WORDS, seed_due_vocabulary

    user = _user(db, email)
    user.native_language = "en"
    db.commit()
    seed_due_vocabulary(db, user.id, CAFE_WORDS)
    service = DailyJourneyService(db, build_default_adapters())
    state, _ = service.create_journey(
        user,
        JourneyCreateRequest(
            mutation_id=uuid.uuid4().hex,
            timezone="Europe/Paris",
            budget_seconds=600,
            preferred_input_mode=InputMode.TEXT,
        ),
    )
    return service, user, state


def _walk_to_run(service, user, state):
    """Advance to the first recall that has another pending recall right after it."""

    while state.current_step_id is not None:
        steps = state.steps
        index = next(i for i, s in enumerate(steps) if s.id == state.current_step_id)
        step = steps[index]
        if step.kind == "recall" and index + 1 < len(steps) and steps[index + 1].kind == "recall":
            return state
        if step.kind == "recall":
            _, state = _answer(service, user, state, step.id, _right_input(service.db, step.id))
        elif step.kind == "respond":
            for _ in range(4):
                result = service.submit_attempt(
                    user,
                    uuid.UUID(state.id),
                    uuid.UUID(step.id),
                    JourneyAttemptRequest.model_validate(
                        {
                            "mutation_id": uuid.uuid4().hex,
                            "expected_revision": state.revision,
                            "input": {"mode": "text", "text": "Je voudrais un café en terrasse, s'il vous plaît."},
                        }
                    ),
                )
                state = result.journey
                if result.next_turn is None:
                    break
            state = _advance(service, user, state)
        else:
            state = _advance(service, user, state)
    pytest.skip("no run of two drills in the default day")


def _run_end(steps, index: int) -> int:
    end = index
    while end + 1 < len(steps) and steps[end + 1].kind == "recall":
        end += 1
    return end


def test_a_missed_drill_comes_back_once_at_the_end_of_its_set(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "retry-once@example.com")
    state = _walk_to_run(service, user, state)
    before = [(s.id, s.kind) for s in state.steps]
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    missed = state.steps[index]
    end = _run_end(state.steps, index)

    result, state = _answer(service, user, state, missed.id, _wrong_input(db_session, missed.id))

    assert result.task_outcome is TaskOutcome.NOT_YET
    # The learner goes on: the next step is the next drill, not the same one.
    assert state.current_step_id == before[index + 1][0]
    assert len(state.steps) == len(before) + 1
    retry = state.steps[end + 1]
    assert retry.kind == "recall"
    assert retry.prompt.retry is True
    assert retry.prompt.target == missed.prompt.target
    # Everything after the set kept its order, one place down.
    assert [s.id for s in state.steps[end + 2 :]] == [sid for sid, _ in before[end + 1 :]]
    assert [s.ordinal for s in state.steps] == sorted({s.ordinal for s in state.steps})
    row = db_session.get(DailyJourneyStep, uuid.UUID(retry.id))
    assert row.private_task[RETRY_OF_KEY] == missed.id

    # Reach the retry; missing it again queues nothing more.
    while state.current_step_id != retry.id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    count = len(state.steps)
    again, state = _answer(service, user, state, retry.id, _wrong_input(db_session, retry.id))
    assert again.task_outcome is TaskOutcome.NOT_YET
    assert again.correction is not None or missed.prompt.task_type != "transform"
    assert len(state.steps) == count
    stored = db_session.get(DailyJourneyStep, uuid.UUID(retry.id)).private_task["result"]
    assert stored["observations"] == []

    journey = db_session.get(DailyJourney, uuid.UUID(state.id))
    assert journey is not None


def test_a_retry_answered_right_counts_as_supported(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "retry-right@example.com")
    state = _walk_to_run(service, user, state)
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    missed = state.steps[index]
    end = _run_end(state.steps, index)

    _, state = _answer(service, user, state, missed.id, _wrong_input(db_session, missed.id))
    retry_id = state.steps[end + 1].id
    while state.current_step_id != retry_id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    result, state = _answer(service, user, state, retry_id, _right_input(db_session, retry_id))

    assert result.task_outcome is TaskOutcome.MET
    stored = db_session.get(DailyJourneyStep, uuid.UUID(retry_id)).private_task["result"]
    assert stored["assistance_level"] == str(AssistanceLevel.SOLUTION)
    assert all(o["evidence_kind"] != "produced_independent" for o in stored["observations"])
    # The public record of help stays the learner's own.
    assert next(s for s in state.steps if s.id == retry_id).assistance_used == []


def test_missing_the_last_drill_of_a_set_queues_no_retry(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "retry-last@example.com")
    state = _walk_to_run(service, user, state)
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    end = _run_end(state.steps, index)
    while state.current_step_id != state.steps[end].id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    count = len(state.steps)

    _, state = _answer(service, user, state, state.steps[end].id, _wrong_input(db_session, state.steps[end].id))

    assert len(state.steps) == count


def test_a_day_with_a_retry_still_finishes(db_session: Session, enabled: None) -> None:
    from tests.test_daily_journey_state import drive_to_finish

    service, user, state = _start(db_session, "retry-finish@example.com")
    state = _walk_to_run(service, user, state)
    _, state = _answer(service, user, state, state.current_step_id, _wrong_input(db_session, state.current_step_id))

    final = drive_to_finish(service, user, state, finish_kind="complete")

    assert final.status == "completed"
    assert final.recap is not None


def test_a_part_refused_for_a_grammar_accent_is_corrected_as_a_part(db_session: Session) -> None:
    user = _user(db_session, "repair-part-accent@example.com")
    task = RecallTask(
        task_type="transform",
        instruction_native="Corrige cette phrase.",
        prompt_fr="Il va a Paris.",
        options=[],
        target=TargetRef(kind=TargetKind.GRAMMAR, id="a-accent", label_fr="à"),
        optional=False,
        accepted_answers=["Il va à Paris."],
        solution_fr="Il va à Paris.",
        source_fr="Il va a Paris.",
    )

    evaluation = evaluate_recall(
        db_session, user=user, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="a"),
        assistance=AssistanceLevel.NONE,
    )

    assert evaluation.outcome is TaskOutcome.NOT_YET
    assert (evaluation.correction.span_fr, evaluation.correction.corrected_fr) == ("a", "à")
    assert evaluation.correction.saved_corrected_fr == "Il va à Paris."
