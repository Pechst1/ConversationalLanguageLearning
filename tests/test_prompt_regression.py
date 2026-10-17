"""E-7 / Loop v2: the story lanes' prompts are checked like code.

Each golden case in ``tests/prompt_regression/cases`` drives the real planner, author,
aids and reply-lane code with a replaying model client (no network, no spend):

* ``test_prompt_snapshot`` — the prompts the code builds today equal the committed
  snapshot; a change fails with a unified diff. Accept an intended change with
  ``PROMPT_SNAPSHOT_UPDATE=1 python -m pytest tests/test_prompt_regression.py`` or
  ``python scripts/prompt_regression.py --update``.
* ``test_replay`` — the recorded answers, fed through the deterministic guards the
  pipeline applies after the model answers, give the expected outcome, and every
  served page or reply keeps its level's limits and asks nothing already asked.

See ``tests/prompt_regression/harness.py`` for the fixture format.
"""

from __future__ import annotations

import functools
import os

import pytest

from tests.prompt_regression import harness

CASES = harness.load_cases()
UPDATE = os.environ.get(harness.UPDATE_ENV) == "1"


@functools.cache
def _result(case_id: str) -> harness.Result:
    return harness.run_case(next(case for case in CASES if case.id == case_id))


@pytest.mark.parametrize("case_id", [case.id for case in CASES])
def test_prompt_snapshot(case_id):
    result = _result(case_id)
    problem = harness.snapshot_diff(result)
    if problem and UPDATE:
        harness.write_snapshot(result)
        return
    if problem:
        pytest.fail(problem, pytrace=False)


@pytest.mark.parametrize("case_id", [case.id for case in CASES])
def test_replay(case_id):
    problems = harness.check(_result(case_id))
    assert not problems, "\n".join(problems)


def test_the_golden_set_covers_both_lanes_and_a_clean_day_per_band():
    clean = {(case.lane, case.level) for case in CASES if "clean" in case.id}
    assert {("page", "A1"), ("page", "A2"), ("page", "B1")} <= clean
    assert {case.lane for case in CASES} == {"page", "turn"}
    snapshots = {path.stem for path in harness.SNAPSHOTS.glob("*.txt")}
    assert snapshots == {case.id for case in CASES}, (
        "every case has a snapshot, and no snapshot is orphaned"
    )


def test_a_changed_prompt_line_fails_with_a_readable_diff(monkeypatch):
    """The mechanism itself: one changed line of the planner's prompt is caught,
    named, and shown as a diff line."""

    from app.services import story_split

    case = next(case for case in CASES if case.id == "page-a1-clean-plusieurs-semaines")
    monkeypatch.setattr(
        story_split,
        "PLANNER",
        story_split.PLANNER.replace("You decide what happens today.", "You decide what happens."),
    )
    problem = harness.snapshot_diff(harness.run_case(case))
    assert problem and "the prompt changed" in problem
    assert "-learner lives inside. You decide what happens today." in problem
    assert "+learner lives inside. You decide what happens." in problem
    assert harness.UPDATE_ENV in problem


def test_a_recorded_answer_knows_which_prompt_it_answered(monkeypatch):
    """``prompt_digest`` on every recorded answer: a prompt change marks exactly the
    answers it invalidates as stale — what ``--live`` would pay to refresh."""

    from app.services import story_split

    case = next(case for case in CASES if case.id == "page-a1-clean-plusieurs-semaines")
    before = set(harness.stale_answers(_result(case.id)))
    monkeypatch.setattr(story_split, "AIDS", story_split.AIDS + "\nOne more rule.")
    assert set(harness.stale_answers(harness.run_case(case))) - before == {"PageAids #1"}
