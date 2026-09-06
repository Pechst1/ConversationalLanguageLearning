"""WP-04 — the five-minute planner.

These tests are pure: the planner takes no ``Session``, so nothing here needs a
database. That is itself part of the contract — a planner that cannot write
cannot quietly mark ninety-eight unselected words reviewed.
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
import pathlib
from dataclasses import asdict, replace

import pytest

from app.services import journey_planner as planner
from app.services.journey_contracts import (
    DEFAULT_BUDGET_SECONDS,
    JOURNEY_CONTENT_VERSION,
    MAX_PLANNED_STEPS,
    MAX_RECALL_STEPS,
    MAX_RESPOND_TURNS,
    CapabilityKey,
    InputMode,
    LearningCandidate,
    PlannedJourney,
    ResponseTask,
    ScenarioBrief,
    StepKind,
    StepStatus,
    TargetKind,
    TargetRef,
)
from app.services.journey_planner import PacingProfile, PlanUnavailable, plan_journey

PLANNER_SOURCE = pathlib.Path(planner.__file__).read_text(encoding="utf-8")

#: Answer-key material that must never reach a renderer payload.
ANSWER_KEY_MARKERS = (
    "accepted_answers",
    "correct_option_id",
    "correct_tile_order",
    "solution_fr",
    "rubric_native",
    "allowed_outcomes",
    "required_intents",
    "optional_intents",
    "suggested_response_fr",
)


# --------------------------------------------------------------------------
# Builders. The scenario key/band/version are real, so the planner's scene-fit
# lookup hits WP-03's actual authored café affordances.
# --------------------------------------------------------------------------


def _response_task(**overrides) -> ResponseTask:
    base = {
        "objective_native": "Say what you would like to drink and where you want to sit.",
        "character_id": "margaux_barman",
        "character_name": "Margaux",
        "opening_line_fr": "Alors, qu'est-ce que je vous sers ?",
        "max_turns": MAX_RESPOND_TURNS,
        "repair_allowed": True,
        "targets": [],
        "required_intents": ["name_a_hot_drink", "state_where_you_will_drink_it"],
        "optional_intents": ["greet_margaux"],
        "allowed_outcomes": ["served_at_counter", "served_at_terrace", "takeaway"],
        "rubric_native": "Met: the learner names a hot drink AND says where they will have it.",
        "suggested_response_fr": "Je voudrais un café, s'il vous plaît.",
        "hint_native": "Start with « Je voudrais… » and add where you will drink it.",
        "translation_native": "I would like a coffee, please.",
        "estimated_seconds": 120,
    }
    base.update(overrides)
    return ResponseTask(**base)


def _brief(**overrides) -> ScenarioBrief:
    base = {
        "scenario_key": CapabilityKey.ORDER_AT_CAFE,
        "content_version": JOURNEY_CONTENT_VERSION,
        "title_fr": "Un café au Mistral",
        "objective_key": "order_at_cafe.counter_drink",
        "objective_native": "Order a hot drink at the counter and say where you want to sit.",
        "level_band": "A1",
        "character_id": "margaux_barman",
        "character_name": "Margaux",
        "location_id": "le_mistral",
        "location_name": "Le Mistral",
        "image_url": "/assets/serial/locations/le_mistral-counter.webp",
        "setup_fr": "Il pleut sur le canal. Tu pousses la porte du Mistral. Margaux essuie le zinc.",
        "setup_native": (
            "It is raining on the canal. You push open the door of Le Mistral. "
            "Margaux is wiping down the zinc counter."
        ),
        "opening_line_fr": "Tiens, bonjour ! Vous vous installez ou c'est à emporter ?",
        "response_task": _response_task(),
        "resolution_lines": {
            "served_at_counter": "Un café pour vous, au comptoir. Je vous l'apporte.",
            "served_at_terrace": "Parfait. Un café en terrasse, ça arrive.",
            "takeaway": "À emporter, alors. Une minute.",
        },
        "resolution_summaries": {
            "served_at_counter": "Margaux served your coffee at the counter.",
            "served_at_terrace": "Margaux is bringing your coffee out to the terrace.",
            "takeaway": "Margaux is making your coffee to take away.",
        },
        "estimated_seconds": 264,
        "control_language": "en",
    }
    base.update(overrides)
    return ScenarioBrief(**base)


def _candidate(
    *,
    kind: TargetKind = TargetKind.VOCABULARY,
    identifier: str = "v1",
    label_fr: str = "un café",
    label_native: str | None = "a coffee",
    priority: float = 5.0,
    due_since_days: int = 2,
    is_new: bool = False,
    relevance: float = 0.0,
    metadata: dict | None = None,
) -> LearningCandidate:
    return LearningCandidate(
        target=TargetRef(
            kind=kind, id=identifier, label_fr=label_fr, label_native=label_native
        ),
        priority_score=priority,
        due_since_days=due_since_days,
        estimated_seconds=30,
        is_new=is_new,
        relevance=relevance,
        source_item_type=str(kind),
        metadata=metadata or {},
    )


SCENE_FITTING = _candidate(identifier="v-cafe", label_fr="un café", label_native="a coffee")
POLITE = _candidate(
    kind=TargetKind.GRAMMAR,
    identifier="g-polite",
    label_fr="s'il vous plaît",
    label_native="polite request",
    priority=4.0,
)
UNRELATED_URGENT = _candidate(
    identifier="v-locataire",
    label_fr="le locataire",
    label_native="the tenant",
    priority=99.0,
    due_since_days=41,
)
NEW_ANCHOR = _candidate(
    identifier="v-terrasse",
    label_fr="en terrasse",
    label_native="on the terrace",
    priority=0.0,
    due_since_days=0,
    is_new=True,
    relevance=1.0,
)


def _serialize(plan: PlannedJourney) -> str:
    return json.dumps(asdict(plan), default=str, ensure_ascii=False, sort_keys=True)


def _kinds(plan: PlannedJourney) -> list[StepKind]:
    return [step.kind for step in plan.steps]


def _assert_envelope(plan: PlannedJourney) -> None:
    """Every invariant CONTRACTS §3/§9 puts on a five-minute plan."""

    plan.validate()
    assert 3 <= len(plan.steps) <= MAX_PLANNED_STEPS
    kinds = _kinds(plan)
    assert kinds[0] is StepKind.SCENE
    assert kinds[-1] is StepKind.RESOLUTION
    assert kinds.count(StepKind.RESPOND) == 1
    assert kinds.count(StepKind.RECALL) <= MAX_RECALL_STEPS
    assert plan.estimated_active_seconds <= plan.budget_seconds
    assert plan.estimated_active_seconds == sum(s.estimated_seconds for s in plan.steps)
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert respond.public_prompt["max_turns"] <= MAX_RESPOND_TURNS
    # At most one repair, and it is the response step's, never a recall's.
    assert sum(
        1 for step in plan.steps if step.public_prompt.get("repair_allowed")
    ) <= 1
    # Nothing may follow the daily ending.
    assert plan.steps[-1].kind is StepKind.RESOLUTION
    for step in plan.steps:
        serialized = json.dumps(step.public_prompt, ensure_ascii=False, default=str)
        for marker in ANSWER_KEY_MARKERS:
            assert marker not in serialized, f"{step.kind} leaks {marker}"


# --------------------------------------------------------------------------
# Table-driven plans
# --------------------------------------------------------------------------

PLAN_TABLE = [
    ("empty_queue", [], None, InputMode.TEXT),
    ("single_fitting_target", [SCENE_FITTING], None, InputMode.TEXT),
    ("two_fitting_targets", [SCENE_FITTING, POLITE], None, InputMode.VOICE),
    (
        "fragile_queue",
        [
            _candidate(
                identifier=f"v-fragile-{index}",
                label_fr=f"mot fragile {index}",
                priority=80.0 - index,
                due_since_days=30 + index,
                metadata={"lapses": 6, "state": "relearning"},
            )
            for index in range(6)
        ],
        None,
        InputMode.TEXT,
    ),
    ("large_queue", None, None, InputMode.TEXT),  # filled in below
    ("unrelated_targets", [UNRELATED_URGENT, SCENE_FITTING], None, InputMode.TEXT),
    ("new_anchor_only", [NEW_ANCHOR], None, InputMode.TEXT),
    (
        "partially_known",
        [
            replace(SCENE_FITTING, metadata={"demonstrated_independently": True}),
            POLITE,
        ],
        None,
        InputMode.TEXT,
    ),
    ("slow_pace", [SCENE_FITTING, POLITE], PacingProfile(0.70, 1.35, 40), InputMode.TEXT),
    ("fast_pace", [SCENE_FITTING, POLITE], PacingProfile(0.30, 0.80, 40), InputMode.TEXT),
    ("untrusted_pace", [SCENE_FITTING, POLITE], PacingProfile(0.70, 1.35, 1), InputMode.TEXT),
]

LARGE_QUEUE = [
    _candidate(
        identifier=f"v-{index:03d}",
        label_fr=f"mot {index}",
        label_native=f"word {index}",
        priority=float(100 - index),
        due_since_days=index,
    )
    for index in range(100)
]
PLAN_TABLE = [
    (name, LARGE_QUEUE if name == "large_queue" else cands, pace, mode)
    for name, cands, pace, mode in PLAN_TABLE
]


@pytest.mark.parametrize(
    "name,candidates,pace,input_mode",
    PLAN_TABLE,
    ids=[row[0] for row in PLAN_TABLE],
)
def test_every_planned_journey_holds_the_five_minute_envelope(
    name, candidates, pace, input_mode
) -> None:
    plan = plan_journey(
        scenario=_brief(), candidates=list(candidates), pace=pace, input_mode=input_mode
    )
    _assert_envelope(plan)
    assert plan.budget_seconds == DEFAULT_BUDGET_SECONDS
    assert len(plan.selected_target_ids) <= planner.MAX_SELECTED_TARGETS, name


# --------------------------------------------------------------------------
# Acceptance: a real ending for both learners, without the ladder
# --------------------------------------------------------------------------


def test_a_new_learner_with_nothing_due_still_reaches_a_real_ending() -> None:
    plan = plan_journey(scenario=_brief(), candidates=[])
    assert _kinds(plan) == [StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION]
    assert plan.selected_target_ids == []
    assert plan.omitted_candidate_ids == []
    # Honest absence: it says nothing was due; it does not claim something was.
    assert "no review item was due" in plan.rationale
    resolution = plan.steps[-1]
    assert resolution.public_prompt["outcome_key"] == "served_at_counter"
    assert resolution.public_prompt["character_line_fr"]
    assert resolution.public_prompt["summary_native"]


def test_a_returning_learner_gets_one_task_per_target_not_fifteen() -> None:
    plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING, POLITE, NEW_ANCHOR])
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    assert len(recalls) == MAX_RECALL_STEPS
    # Three selected targets under the legacy ladder would owe 45 exercises.
    assert len(plan.steps) <= MAX_PLANNED_STEPS
    assert len(plan.selected_target_ids) == 3


def test_a_queue_of_one_hundred_due_words_is_not_one_hundred_obligations() -> None:
    plan = plan_journey(scenario=_brief(), candidates=list(LARGE_QUEUE))
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    assert len(recalls) <= MAX_RECALL_STEPS
    assert len(plan.selected_target_ids) <= planner.MAX_SELECTED_TARGETS
    # Everything not selected is reported as omitted — and stays due.
    assert len(plan.omitted_candidate_ids) == len(LARGE_QUEUE) - len(plan.selected_target_ids)
    assert set(plan.selected_target_ids).isdisjoint(plan.omitted_candidate_ids)
    assert "stayed due, untouched" in plan.rationale


def test_the_planner_cannot_mark_anything_reviewed() -> None:
    """No session, no writes: the ninety-eight unselected words keep their dates."""

    parameters = inspect.signature(plan_journey).parameters
    assert "db" not in parameters
    assert "session" not in parameters
    assert all(param.kind is param.KEYWORD_ONLY for param in parameters.values())

    before = copy.deepcopy(LARGE_QUEUE)
    plan = plan_journey(scenario=_brief(), candidates=LARGE_QUEUE)
    assert LARGE_QUEUE == before, "the planner mutated its candidates"
    for candidate, original in zip(LARGE_QUEUE, before, strict=True):
        assert candidate.due_since_days == original.due_since_days
        assert candidate.priority_score == original.priority_score
        assert candidate.metadata == original.metadata
    assert plan.estimated_active_seconds <= DEFAULT_BUDGET_SECONDS


def test_an_already_demonstrated_target_is_skipped_not_silently_dropped() -> None:
    known = replace(SCENE_FITTING, metadata={"demonstrated_independently": True})
    plan = plan_journey(scenario=_brief(), candidates=[known, POLITE])
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    skipped = [step for step in recalls if step.initial_status is StepStatus.SKIPPED]
    assert len(skipped) == 1, "the redundant recall must be visible, not dropped"
    assert skipped[0].target == known.target
    assert skipped[0].optional is True
    assert skipped[0].estimated_seconds == 0, "a skipped step costs the learner nothing"
    # It is still a selected target and still elicited in the real response.
    assert planner.target_identity(known.target) in plan.selected_target_ids
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert known.target.as_public() in respond.public_prompt["targets"]
    assert "already produced independently" in plan.rationale
    # The other target still gets a real, unskipped recall.
    assert any(step.initial_status is StepStatus.PENDING for step in recalls)


@pytest.mark.parametrize(
    "metadata,expected",
    [
        ({}, False),
        ({"demonstrated_independently": True}, True),
        ({"demonstrated_independently": False}, False),
        ({"already_demonstrated": True}, True),
        ({"last_evidence_kind": "produced_independent"}, True),
        ({"last_evidence_kind": "used_again_later"}, True),
        ({"last_evidence_kind": "produced_supported"}, False),
        ({"last_evidence_kind": "recognized"}, False),
        ({"state": "review", "lapses": 0}, False),
    ],
)
def test_demonstration_is_explicit_never_inferred_from_a_due_date(metadata, expected) -> None:
    assert planner.candidate_is_demonstrated(_candidate(metadata=metadata)) is expected


# --------------------------------------------------------------------------
# Selection
# --------------------------------------------------------------------------


def test_scenario_fit_beats_an_unrelated_urgent_word() -> None:
    plan = plan_journey(scenario=_brief(), candidates=[UNRELATED_URGENT, SCENE_FITTING])
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    assert recalls[0].target == SCENE_FITTING.target, "the scene's own word comes first"
    assert plan.selected_target_ids[0] == planner.target_identity(SCENE_FITTING.target)


def test_an_unrelated_target_is_rehearsed_but_never_elicited_in_the_reply() -> None:
    """CONTRACTS §7: no elicitation obligation, no manufactured lapse."""

    plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING, UNRELATED_URGENT])
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    elicited = {target["id"] for target in respond.public_prompt["targets"]}
    assert SCENE_FITTING.target.id in elicited
    assert UNRELATED_URGENT.target.id not in elicited
    assert planner.target_identity(UNRELATED_URGENT.target) in plan.selected_target_ids
    assert "not required in the reply" in plan.rationale


def test_at_most_two_due_targets_and_one_new_anchor() -> None:
    candidates = [
        SCENE_FITTING,
        POLITE,
        UNRELATED_URGENT,
        NEW_ANCHOR,
        replace(NEW_ANCHOR, target=replace(NEW_ANCHOR.target, id="v-second-new")),
    ]
    selection = planner.select_plan_targets(_brief(), candidates)
    assert sum(1 for entry in selection.selected if not entry.candidate.is_new) == 2
    assert sum(1 for entry in selection.selected if entry.candidate.is_new) == 1
    assert len(selection.selected) == planner.MAX_SELECTED_TARGETS
    assert set(selection.omission_reasons.values()) <= {
        "due_target_cap_reached",
        "new_anchor_cap_reached",
        "duplicate_candidate",
    }


def test_a_duplicate_candidate_is_reported_not_planned_twice() -> None:
    selection = planner.select_plan_targets(_brief(), [SCENE_FITTING, SCENE_FITTING])
    assert len(selection.selected) == 1
    assert selection.omission_reasons[
        planner.target_identity(SCENE_FITTING.target)
    ] == "duplicate_candidate"


def test_a_fragile_queue_keeps_the_most_urgent_two() -> None:
    fragile = [
        _candidate(
            identifier=f"v-{index}",
            label_fr=f"mot {index}",
            priority=10.0 * index,
            due_since_days=index,
            metadata={"lapses": 5},
        )
        for index in range(1, 6)
    ]
    plan = plan_journey(scenario=_brief(), candidates=fragile)
    assert plan.selected_target_ids == ["vocabulary:v-5", "vocabulary:v-4"]
    assert len(plan.omitted_candidate_ids) == 3


# --------------------------------------------------------------------------
# Estimates and pace
# --------------------------------------------------------------------------


def test_a_pace_profile_is_ignored_until_it_has_enough_observations() -> None:
    thin = PacingProfile(0.70, 1.35, planner.MIN_PACE_OBSERVATIONS - 1)
    assert thin.is_trusted is False
    assert thin.effective_seconds_per_token() == planner.DEFAULT_SECONDS_PER_TOKEN
    assert thin.effective_step_multiplier() == 1.0
    trusted = PacingProfile(0.70, 1.35, planner.MIN_PACE_OBSERVATIONS)
    assert trusted.is_trusted is True
    assert trusted.effective_seconds_per_token() == 0.70
    assert trusted.effective_step_multiplier() == 1.35

    default_plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING, POLITE])
    thin_plan = plan_journey(
        scenario=_brief(), candidates=[SCENE_FITTING, POLITE], pace=thin
    )
    assert _serialize(thin_plan).replace(thin_plan.rationale, "") == _serialize(
        default_plan
    ).replace(default_plan.rationale, "")
    assert "measured pace ignored" in thin_plan.rationale


def test_a_wild_measurement_is_clamped_rather_than_believed() -> None:
    absurd = PacingProfile(9.0, 40.0, 500)
    assert absurd.effective_seconds_per_token() == planner.SECONDS_PER_TOKEN_BOUNDS[1]
    assert absurd.effective_step_multiplier() == planner.STEP_MULTIPLIER_BOUNDS[1]
    plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING], pace=absurd)
    _assert_envelope(plan)


def test_a_slow_pace_produces_a_deterministically_shorter_plan() -> None:
    fast = plan_journey(
        scenario=_brief(),
        candidates=[SCENE_FITTING, POLITE],
        pace=PacingProfile(0.30, 0.80, 40),
    )
    slow = plan_journey(
        scenario=_brief(),
        candidates=[SCENE_FITTING, POLITE],
        pace=PacingProfile(0.70, 1.35, 40),
    )
    _assert_envelope(fast)
    _assert_envelope(slow)
    assert len(slow.steps) < len(fast.steps), "a slow learner gets fewer steps, not a longer day"
    assert len(slow.omitted_candidate_ids) > len(fast.omitted_candidate_ids)
    assert "no_budget_headroom" in slow.rationale
    # Repeating the slow plan reproduces it exactly.
    assert _serialize(slow) == _serialize(
        plan_journey(
            scenario=_brief(),
            candidates=[SCENE_FITTING, POLITE],
            pace=PacingProfile(0.70, 1.35, 40),
        )
    )


def test_a_very_slow_pace_reduces_turns_before_it_breaks_the_budget() -> None:
    heavy = _brief(
        response_task=_response_task(estimated_seconds=200),
        estimated_seconds=299,
    )
    plan = plan_journey(
        scenario=heavy, candidates=[SCENE_FITTING], pace=PacingProfile(0.70, 1.35, 40)
    )
    _assert_envelope(plan)
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert respond.public_prompt["max_turns"] == 1
    assert "reduced to one turn" in plan.rationale


def test_the_core_plan_survives_a_scenario_that_only_fits_at_the_base_pace() -> None:
    """Never delete the objective or the ending: set the measured pace aside."""

    long_scene = _brief(
        setup_fr=" ".join(["mot"] * 60),
        setup_native=" ".join(["word"] * 60),
        response_task=_response_task(estimated_seconds=150),
    )
    plan = plan_journey(
        scenario=long_scene, candidates=[], pace=PacingProfile(0.70, 1.35, 40)
    )
    _assert_envelope(plan)
    assert _kinds(plan) == [StepKind.SCENE, StepKind.RESPOND, StepKind.RESOLUTION]
    assert "set aside to the base pace" in plan.rationale


def test_content_too_long_for_five_minutes_is_refused_not_squeezed() -> None:
    """The scene, the response and the ending are not removable (CONTRACTS §3)."""

    huge = _brief(
        setup_fr=" ".join(["mot"] * 300),
        setup_native=" ".join(["word"] * 300),
        response_task=_response_task(estimated_seconds=200),
    )
    with pytest.raises(PlanUnavailable) as excinfo:
        plan_journey(scenario=huge, candidates=[])
    assert excinfo.value.reason == "scene_exceeds_budget"


def test_the_estimate_covers_answering_feedback_and_exactly_one_repair() -> None:
    with_repair = planner.respond_seconds(
        _response_task(estimated_seconds=1), turns=2, spt=0.45, multiplier=1.0
    )
    without_repair = planner.respond_seconds(
        _response_task(estimated_seconds=1, repair_allowed=False),
        turns=2,
        spt=0.45,
        multiplier=1.0,
    )
    assert with_repair - without_repair == planner.REPAIR_ALLOWANCE_SECONDS
    one_turn = planner.respond_seconds(
        _response_task(estimated_seconds=1), turns=1, spt=0.45, multiplier=1.0
    )
    assert with_repair - one_turn == planner.RESPOND_TURN_SECONDS
    # Reading is priced by the token, everything the learner does by the step.
    assert planner.scene_seconds(_brief(), spt=0.9, multiplier=1.0) > planner.scene_seconds(
        _brief(), spt=0.45, multiplier=1.0
    )


def test_the_optional_recall_is_the_first_thing_the_budget_takes() -> None:
    tight = _brief(response_task=_response_task(estimated_seconds=170))
    plan = plan_journey(scenario=tight, candidates=[SCENE_FITTING, POLITE])
    _assert_envelope(plan)
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    assert len(recalls) == 1
    assert recalls[0].optional is False, "the surviving recall is the mandatory one"
    assert len(plan.omitted_candidate_ids) == 1
    assert "no_budget_headroom" in plan.rationale


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_identical_inputs_produce_a_byte_identical_plan() -> None:
    candidates = [SCENE_FITTING, POLITE, NEW_ANCHOR]
    first = plan_journey(scenario=_brief(), candidates=list(candidates))
    second = plan_journey(scenario=_brief(), candidates=list(candidates))
    assert first == second
    assert _serialize(first) == _serialize(second)


def test_a_refresh_never_reshuffles_options_or_tiles() -> None:
    candidates = [SCENE_FITTING, POLITE]
    runs = [
        plan_journey(scenario=_brief(), candidates=list(candidates)) for _ in range(5)
    ]
    prompts = {
        json.dumps([step.public_prompt for step in run.steps], sort_keys=True, ensure_ascii=False)
        for run in runs
    }
    assert len(prompts) == 1


def test_candidate_input_order_does_not_change_the_plan() -> None:
    forward = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING, POLITE])
    backward = plan_journey(scenario=_brief(), candidates=[POLITE, SCENE_FITTING])
    assert _serialize(forward) == _serialize(backward)


# --------------------------------------------------------------------------
# Recall shaping
# --------------------------------------------------------------------------


def test_a_glossed_scene_word_becomes_a_choice_with_real_distractors() -> None:
    task = planner.build_recall_task(
        target=SCENE_FITTING.target,
        scenario=_brief(),
        affordances=planner._affordances_for(_brief()),
        optional=False,
    )
    assert task is not None
    assert task.task_type == "choice"
    assert len(task.options) == 3
    assert task.correct_option_id in {option["id"] for option in task.options}
    texts = [option["text_fr"] for option in task.options]
    assert "un café" in texts
    assert len({option["id"] for option in task.options}) == 3
    # The public projection carries the options but never which one is right.
    plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING])
    recall = next(step for step in plan.steps if step.kind is StepKind.RECALL)
    assert set(recall.public_prompt) == {
        "task_type",
        "instruction_native",
        "prompt_fr",
        "options",
        "target",
        "optional",
        "help_available",
    }
    assert recall.public_prompt["help_available"] == ["hint", "translation", "solution"]


def test_a_multiword_target_without_distractors_becomes_tiles_in_a_wrong_order() -> None:
    target = TargetRef(
        kind=TargetKind.GRAMMAR,
        id="g-futur",
        label_fr="je vais être en retard",
        label_native="near future",
    )
    task = planner.build_recall_task(
        target=target, scenario=_brief(), affordances=[], optional=False
    )
    assert task is not None
    assert task.task_type == "tiles"
    shown = [tile["id"] for tile in task.options]
    assert sorted(shown) == sorted(task.correct_tile_order)
    assert shown != task.correct_tile_order, "the displayed layout must not be the answer"
    assert " ".join(tile["text_fr"] for tile in task.options) != target.label_fr


def test_a_single_word_target_with_a_gloss_becomes_a_short_answer() -> None:
    target = TargetRef(
        kind=TargetKind.VOCABULARY, id="v-x", label_fr="parapluie", label_native="umbrella"
    )
    task = planner.build_recall_task(
        target=target, scenario=_brief(), affordances=[], optional=False
    )
    assert task is not None
    assert task.task_type == "short_answer"
    assert task.options == []
    assert task.accepted_answers == ["parapluie"]
    assert "umbrella" in task.instruction_native
    assert "parapluie" not in task.instruction_native


def test_a_target_that_cannot_be_posed_honestly_gets_no_step_at_all() -> None:
    mute = _candidate(identifier="v-mute", label_fr="zut", label_native=None)
    plan = plan_journey(scenario=_brief(), candidates=[mute])
    assert [step.kind for step in plan.steps].count(StepKind.RECALL) == 0
    assert "no recall form could be posed without revealing it" in plan.rationale
    assert planner.target_identity(mute.target) in plan.selected_target_ids


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_recall_instructions_use_the_control_language(language) -> None:
    plan = plan_journey(
        scenario=_brief(control_language=language), candidates=[SCENE_FITTING]
    )
    recall = next(step for step in plan.steps if step.kind is StepKind.RECALL)
    expected = planner._localized(planner._CHOICE_INSTRUCTION, language).format(
        native="a coffee"
    )
    assert recall.public_prompt["instruction_native"] == expected


# --------------------------------------------------------------------------
# Modality, fallbacks, refusal
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_mode,expected",
    [(InputMode.TEXT, ["text"]), (InputMode.VOICE, ["text", "voice"])],
)
def test_text_is_always_offered_and_voice_only_when_it_exists(input_mode, expected) -> None:
    plan = plan_journey(
        scenario=_brief(), candidates=[SCENE_FITTING], input_mode=input_mode
    )
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert respond.public_prompt["input_modes"] == expected


def test_an_authored_fallback_scene_still_produces_a_whole_plan() -> None:
    plan = plan_journey(
        scenario=_brief(is_authored_fallback=True), candidates=[SCENE_FITTING]
    )
    _assert_envelope(plan)
    assert "authored fallback" in plan.rationale
    assert plan.steps[-1].public_prompt["character_line_fr"]


def test_the_minimum_valid_context_is_plannable() -> None:
    minimal = _brief(
        image_url=None,
        opening_line_fr=None,
        resolution_summaries={},
        resolution_lines={"served_at_counter": "Voilà."},
        response_task=_response_task(
            allowed_outcomes=["served_at_counter"],
            hint_native=None,
            translation_native=None,
            suggested_response_fr=None,
        ),
    )
    plan = plan_journey(scenario=minimal, candidates=[])
    _assert_envelope(plan)
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert respond.public_prompt["help_available"] == []
    assert plan.steps[0].public_prompt["character_line_fr"] is None
    assert plan.steps[-1].public_prompt["summary_native"] == ""


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"setup_fr": "  "}, "scene_has_no_setup"),
        ({"objective_native": ""}, "scene_has_no_objective"),
        (
            {"response_task": _response_task(opening_line_fr="")},
            "response_task_has_no_opening_line",
        ),
        (
            {"response_task": _response_task(objective_native="")},
            "response_task_has_no_objective",
        ),
        ({"resolution_lines": {}}, "scenario_has_no_ending"),
    ],
)
def test_content_that_cannot_end_is_refused_not_faked(overrides, reason) -> None:
    with pytest.raises(PlanUnavailable) as excinfo:
        plan_journey(scenario=_brief(**overrides), candidates=[SCENE_FITTING])
    assert excinfo.value.reason == reason


def test_the_shown_ending_is_an_authored_outcome_not_an_invented_one() -> None:
    brief = _brief()
    plan = plan_journey(scenario=brief, candidates=[])
    outcome = plan.steps[-1].public_prompt["outcome_key"]
    assert outcome in brief.response_task.allowed_outcomes
    assert plan.steps[-1].public_prompt["character_line_fr"] == brief.resolution_lines[outcome]


# --------------------------------------------------------------------------
# No legacy ladder
# --------------------------------------------------------------------------


def _imported_modules() -> set[str]:
    tree = ast.parse(PLANNER_SOURCE)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_planner_imports_no_ladder_and_no_scheduler() -> None:
    """One content source (WP-03), one evidence source (WP-05), no second brain."""

    imported = _imported_modules()
    assert "app.services.atelier" not in imported
    assert "app.services.unified_srs" not in imported
    assert not any(name.startswith("app.services.atelier") for name in imported)
    assert imported <= {
        "__future__",
        "hashlib",
        "dataclasses",
        "typing",
        "app.services.journey_content",
        "app.services.journey_contracts",
    }, imported
    for banned in ("output_ladder", "ATELIER_", "UnifiedSRSService", "complete_item("):
        assert banned not in PLANNER_SOURCE, banned


def test_no_planner_constant_reproduces_the_fifteen_per_concept_formula() -> None:
    from app.services.atelier import (
        ATELIER_ITEMS_PER_RECOGNIZE_MODE,
        ATELIER_RECOGNIZE_MODES,
        ATELIER_TRANSFORM_ITEMS,
    )

    legacy_per_concept = (
        len(ATELIER_RECOGNIZE_MODES) * ATELIER_ITEMS_PER_RECOGNIZE_MODE
        + ATELIER_TRANSFORM_ITEMS
        + 3
    )
    assert legacy_per_concept == 15
    plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING, POLITE, NEW_ANCHOR])
    obligations = [
        step
        for step in plan.steps
        if not step.optional and step.initial_status is not StepStatus.SKIPPED
    ]
    assert len(obligations) < legacy_per_concept
    assert len(plan.steps) <= MAX_PLANNED_STEPS
    assert planner.MAX_DUE_TARGETS == 2
    assert planner.MAX_NEW_TARGETS == 1


def test_no_task_is_appended_after_the_daily_ending() -> None:
    for candidates in ([], [SCENE_FITTING], [SCENE_FITTING, POLITE, NEW_ANCHOR], LARGE_QUEUE):
        plan = plan_journey(scenario=_brief(), candidates=list(candidates))
        assert plan.steps[-1].kind is StepKind.RESOLUTION
        assert [step.kind for step in plan.steps[:-1]].count(StepKind.RESOLUTION) == 0
        respond_index = next(
            index for index, step in enumerate(plan.steps) if step.kind is StepKind.RESPOND
        )
        assert respond_index == len(plan.steps) - 2


# --------------------------------------------------------------------------
# Cross-package reality check: WP-03's real brief and WP-05's real candidates
# --------------------------------------------------------------------------


def test_the_real_wp03_brief_and_wp05_queue_plan_a_real_five_minute_day(db_session) -> None:
    """No hand-built fixtures: the actual services, end to end, read-only."""

    from uuid import uuid4

    from app.db.models import User
    from app.services import journey_content, journey_learning

    user = User(
        id=uuid4(),
        email=f"{uuid4()}@planner.test",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
        cefr_estimate="A1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    for scenario_key in CapabilityKey:
        brief = journey_content.resolve_scenario_brief(
            db_session,
            user=user,
            scenario_key=scenario_key,
            input_mode=InputMode.TEXT,
            allow_generation=False,
        )
        assert isinstance(brief, ScenarioBrief), brief
        candidates = journey_learning.select_learning_candidates(
            db_session, user=user, scenario=brief, limit=3
        )
        plan = plan_journey(scenario=brief, candidates=candidates)
        _assert_envelope(plan)
        assert plan.scenario is brief
        # A brand-new learner has nothing due; the day is still a real day.
        assert plan.estimated_active_seconds <= DEFAULT_BUDGET_SECONDS
        assert plan.steps[0].public_prompt["setup_fr"] == brief.setup_fr
        respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
        assert respond.public_prompt["character_id"] == brief.character_id
        assert respond.public_prompt["character_line_fr"] == brief.response_task.opening_line_fr
        outcome = plan.steps[-1].public_prompt["outcome_key"]
        assert outcome in brief.response_task.allowed_outcomes


# --------------------------------------------------------------------------
# The asking payload never carries the answer (WP-12 defect D-4)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidates",
    [
        [SCENE_FITTING],
        [SCENE_FITTING, POLITE],
        [_candidate(kind=TargetKind.GRAMMAR, identifier="g-futur",
                    label_fr="je vais être en retard", label_native="near future")],
        [_candidate(identifier="v-gloss-only", label_fr="une noisette", label_native=None)],
    ],
)
def test_no_recall_prompt_contains_its_own_answer(candidates) -> None:
    """The payload that asks the question may not also state the answer.

    ``TargetRef.label_fr`` *is* the answer to a recall step — for a choice it is
    one of the options verbatim, for tiles and short answer it is the string
    being elicited. Publishing it in ``prompt.target`` spoils the question and
    bypasses the assistance ledger: the paid ``solution`` reveal returns exactly
    that string and records ``AssistanceLevel.SOLUTION``, while reading the free
    copy records nothing at all (WP-12 defect D-4).
    """

    plan = plan_journey(scenario=_brief(), candidates=candidates)
    recalls = [step for step in plan.steps if step.kind is StepKind.RECALL]
    assert recalls, "no recall step to check"

    for step in recalls:
        prompt = step.public_prompt
        task = step.private_task
        assert task is not None
        answer = (task.solution_fr or "").strip()
        assert answer, "the private task must still hold the answer"

        # The contract shape is unchanged; only the answer is withheld.
        assert set(prompt["target"]) == {"kind", "id", "label_fr", "label_native"}
        assert prompt["target"]["kind"] == str(task.target.kind)
        assert prompt["target"]["id"] == task.target.id
        assert prompt["target"]["label_fr"] == ""

        serialized = json.dumps(
            {key: value for key, value in prompt.items() if key != "options"},
            ensure_ascii=False,
        )
        assert answer not in serialized, f"{prompt['task_type']} publishes {answer!r}"
        for accepted in task.accepted_answers:
            assert accepted not in serialized, accepted
        if prompt["task_type"] == "choice":
            # The answer is one of the options and must be told apart only by
            # answering: nothing else in the payload may single it out.
            assert answer in [option["text_fr"] for option in prompt["options"]]


def test_the_recall_prompt_still_validates_against_the_frozen_wire_contract() -> None:
    """Withholding the answer must not break the shipped renderer's payload."""

    from app.schemas.daily_journey import RecallPrompt

    plan = plan_journey(scenario=_brief(), candidates=[SCENE_FITTING, POLITE])
    for step in plan.steps:
        if step.kind is StepKind.RECALL:
            model = RecallPrompt.model_validate(step.public_prompt)
            assert model.options and model.instruction_native
            assert model.target.id == step.private_task.target.id
