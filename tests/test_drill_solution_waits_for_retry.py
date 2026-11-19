"""P5 (owner, 2026-11-13; review finding 3): no solution before the retry in the scene's drill.

«The user should not see what is right when he then gets another chance to fix it; only
afterwards the solution.» La Forge keeps that rule (``solution_gate``); the daily drill
(«Rappel», «Avant la scène») now does too:

* a miss whose item is asked again («Encore une fois») is served without the corrected
  line and without the right card; it says where and why;
* the retry, answered, shows the solution;
* a choice between two shows it at once; round 3: the last drill of its set comes back
  once after it (it used to show the solution at once);
* the retry is answered «with a hint», not «with the solution shown», when the solution
  was in fact kept back; the lapse is booked once, as before.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

import app.services.daily_journey as journey_module
from app.db.models.daily_journey import DailyJourneyStep
from app.services.journey_contracts import AssistanceLevel, TaskOutcome
from tests.test_repair_part_and_retry import _answer, _right_input, _run_end, _start, _walk_to_run

RIGHT = "C'est qui, vous ?"
OPTIONS = [
    {"id": "o1", "text_fr": RIGHT},
    {"id": "o2", "text_fr": "Vous allez vendre l'appartement d'Odile ?"},
    {"id": "o3", "text_fr": "Il pleut."},
]


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)


def _as_choice(db: Session, step_id: str, options: list[dict[str, str]]) -> None:
    """The 12 Nov walk's item: «In welchem Satz steckt die Regel von heute?», key «C'est qui, vous ?»."""

    step = db.get(DailyJourneyStep, uuid.UUID(step_id))
    private = dict(step.private_task or {})
    task = dict(private["recall_task"])
    task.update(
        {
            "task_type": "choice",
            "instruction_native": "In welchem Satz steckt die Regel von heute?",
            "prompt_fr": None,
            "correct_option_id": "o1",
            "correct_tile_order": [],
            "accepted_answers": [],
            "solution_fr": RIGHT,
            "hint_native": None,
            "why_native": None,
            "options": options,
        }
    )
    private["recall_task"] = task
    step.private_task = private
    db.commit()


def _payload_text(result) -> str:
    return result.model_dump_json()


def _retry_of(state, end: int):
    retry = state.steps[end + 1]
    assert retry.prompt.retry is True
    return retry


def test_a_missed_three_way_pick_with_a_retry_keeps_the_solution_back(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "p5-withheld@example.com")
    state = _walk_to_run(service, user, state)
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    end = _run_end(state.steps, index)
    missed_id = state.current_step_id
    _as_choice(db_session, missed_id, OPTIONS)

    result, state = _answer(service, user, state, missed_id, {"mode": "choice", "option_id": "o3"})

    assert result.task_outcome is TaskOutcome.NOT_YET
    retry = _retry_of(state, end)
    # Where and why, never what: no corrected line, no right card, no edit.
    correction = result.correction
    assert correction is not None
    assert correction.corrected_fr == ""
    assert getattr(correction, "solution", None) is not None and correction.solution.state == "withheld"
    assert correction.span_fr == "Il pleut."
    assert correction.note_native
    assert result.check is not None and result.check.edits == [] and result.check.corrected is None
    assert "qui, vous" not in _payload_text(result), "the right card is named in the payload"

    # The retry is answered: now the solution is on the payload.
    while state.current_step_id != retry.id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    again, state = _answer(service, user, state, retry.id, {"mode": "choice", "option_id": "o2"})

    assert again.task_outcome is TaskOutcome.NOT_YET
    assert again.correction is not None
    assert getattr(again.correction, "solution", None) is None
    assert again.correction.corrected_fr == RIGHT


def test_a_retry_after_a_withheld_miss_is_answered_with_a_hint(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "p5-retry-hint@example.com")
    state = _walk_to_run(service, user, state)
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    end = _run_end(state.steps, index)
    missed_id = state.current_step_id
    _as_choice(db_session, missed_id, OPTIONS)

    _, state = _answer(service, user, state, missed_id, {"mode": "choice", "option_id": "o3"})
    retry_id = _retry_of(state, end).id
    assert db_session.get(DailyJourneyStep, uuid.UUID(retry_id)).private_task.get("solution_withheld") is True
    while state.current_step_id != retry_id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    result, state = _answer(service, user, state, retry_id, {"mode": "choice", "option_id": "o1"})

    assert result.task_outcome is TaskOutcome.MET
    stored = db_session.get(DailyJourneyStep, uuid.UUID(retry_id)).private_task["result"]
    # Assisted all the same (the reason was read), but not «with the solution shown».
    assert stored["assistance_level"] == str(AssistanceLevel.HINT)
    assert all(o["evidence_kind"] != "produced_independent" for o in stored["observations"])
    # The lapse stays booked once, on the first miss.
    first = db_session.get(DailyJourneyStep, uuid.UUID(missed_id)).private_task["result"]
    assert [o["evidence_kind"] for o in first["observations"]] == ["not_yet"]


def test_the_last_drill_of_its_set_comes_back_once_with_its_solution_kept(db_session: Session, enabled: None) -> None:
    """Round 3 (walk 2, A1 day 2): «Je fatigué suis», the last drill of the day's run,
    showed «Je suis fatigué» at once and never came back. It is now asked once more
    right after its run, its solution kept until then."""

    service, user, state = _start(db_session, "p5-no-retry@example.com")
    state = _walk_to_run(service, user, state)
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    end = _run_end(state.steps, index)
    while state.current_step_id != state.steps[end].id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    last_id = state.steps[end].id
    _as_choice(db_session, last_id, OPTIONS)
    count = len(state.steps)

    result, state = _answer(service, user, state, last_id, {"mode": "choice", "option_id": "o3"})

    assert len(state.steps) == count + 1, "the last drill of its set comes back once"
    retry = _retry_of(state, end)
    assert result.correction is not None
    assert result.correction.solution is not None and result.correction.solution.state == "withheld"
    assert result.correction.corrected_fr == ""
    assert "qui, vous" not in _payload_text(result)
    # The retry is the one chance: its miss shows the solution, and queues nothing more.
    again, state = _answer(service, user, state, retry.id, {"mode": "choice", "option_id": "o2"})
    assert len(state.steps) == count + 1
    assert again.correction is not None and getattr(again.correction, "solution", None) is None
    assert again.correction.corrected_fr == RIGHT


def test_the_last_two_way_drill_of_its_set_shows_the_solution_at_once(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "p5-no-retry-two@example.com")
    state = _walk_to_run(service, user, state)
    index = next(i for i, s in enumerate(state.steps) if s.id == state.current_step_id)
    end = _run_end(state.steps, index)
    while state.current_step_id != state.steps[end].id:
        current = state.current_step_id
        _, state = _answer(service, user, state, current, _right_input(db_session, current))
    last_id = state.steps[end].id
    _as_choice(db_session, last_id, OPTIONS[:2])
    count = len(state.steps)

    result, state = _answer(service, user, state, last_id, {"mode": "choice", "option_id": "o2"})

    assert len(state.steps) == count, "a two-way miss names the other card: no retry after its run"
    assert result.correction is not None
    assert getattr(result.correction, "solution", None) is None
    assert result.correction.corrected_fr == RIGHT


def test_a_two_way_pick_shows_the_solution_at_once(db_session: Session, enabled: None) -> None:
    service, user, state = _start(db_session, "p5-two-way@example.com")
    state = _walk_to_run(service, user, state)
    missed_id = state.current_step_id
    _as_choice(db_session, missed_id, OPTIONS[:2])

    result, state = _answer(service, user, state, missed_id, {"mode": "choice", "option_id": "o2"})

    assert result.task_outcome is TaskOutcome.NOT_YET
    assert result.correction is not None
    assert getattr(result.correction, "solution", None) is None
    assert result.correction.corrected_fr == RIGHT


def test_a_solution_the_learner_asked_for_is_not_withheld(db_session: Session, enabled: None) -> None:
    from app.schemas.daily_journey import JourneyHelpRequest

    service, user, state = _start(db_session, "p5-asked@example.com")
    state = _walk_to_run(service, user, state)
    missed_id = state.current_step_id
    _as_choice(db_session, missed_id, OPTIONS)

    help_result = service.use_help(
        user,
        uuid.UUID(state.id),
        uuid.UUID(missed_id),
        JourneyHelpRequest(mutation_id=uuid.uuid4().hex, expected_revision=state.revision, help_kind="solution"),
    )
    assert help_result.content_fr == RIGHT, "«Montrer la réponse» still shows the answer"
    state = help_result.journey
    result, state = _answer(service, user, state, missed_id, {"mode": "choice", "option_id": "o3"})

    assert result.correction is not None
    assert getattr(result.correction, "solution", None) is None
    assert result.correction.corrected_fr == RIGHT


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_the_withheld_note_never_names_the_answer(language: str) -> None:
    from app.services.journey_contracts import Correction, RecallTask, TargetKind, TargetRef
    from app.services.journey_learning import pick_miss_note, withheld_recall_note

    task = RecallTask(
        task_type="choice",
        instruction_native="?",
        prompt_fr=None,
        options=list(OPTIONS),
        target=TargetRef(kind=TargetKind.GRAMMAR, id="cest-qui", label_fr="c'est qui"),
        optional=False,
        correct_option_id="o1",
        solution_fr=RIGHT,
    )
    note = pick_miss_note(task, language)
    assert note and "qui" in note
    correction = Correction(span_fr="Il pleut.", corrected_fr=RIGHT, note_native=note, kind="pick")

    withheld = withheld_recall_note(task, correction, language=language)

    assert withheld
    assert "qui" not in withheld.lower()


def test_a_withheld_build_says_which_part_is_off() -> None:
    from app.services.journey_contracts import Correction, RecallTask, TargetKind, TargetRef
    from app.services.journey_learning import tile_order_note, withheld_recall_note

    task = RecallTask(
        task_type="tiles",
        instruction_native="Build the sentence.",
        prompt_fr=None,
        options=[
            {"id": "t1", "text_fr": "Je"},
            {"id": "t2", "text_fr": "suis"},
            {"id": "t3", "text_fr": "à"},
            {"id": "t4", "text_fr": "Paris"},
        ],
        target=TargetRef(kind=TargetKind.GRAMMAR, id="etre", label_fr="être"),
        optional=False,
        correct_tile_order=["t1", "t2", "t3", "t4"],
        solution_fr="Je suis à Paris",
    )
    note = tile_order_note(task, ["t1", "t3", "t2", "t4"], "en")
    correction = Correction(span_fr="Je à suis Paris", corrected_fr="Je suis à Paris", note_native=note)

    assert withheld_recall_note(task, correction, language="en") == note == "From “à” on, the order is off."
