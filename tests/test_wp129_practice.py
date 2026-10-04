"""WP-129 — better practice at B1+, grammar from the page, and the owner's A1/A2 day.

* **Owner decision 2026-10-04, «fewer replies, more items».** On Léger and
  Régulier an A1/A2 core reply is two exchanges (never fewer than the page
  needs: a turn that routes the story or sets a flag is never dropped); the
  rest is optional and outside the core estimate.
* **B1+ practice** fills the day's free time with mixed-unit production: a
  contrast between two *introduced* partner units, a repair, a free sentence of
  the learner's own — interleaved, inside WP-128's budget, never to meet a count.
* **Content program D7.** After a tentpole's ending, a unit the learner met
  earlier, shown in a line of the page they read; it introduces and credits
  nothing, and none is shown when no met unit is on the page.
* **One sentence, one item.** No two items of a day work on one sentence, and no
  two matching grids share their cards.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.db.models.grammar import GrammarConcept
from app.services import daily_journey as daily_journey_module
from app.services import grammar_items, journey_contracts, journey_learning
from app.services import journey_planner as planner
from app.services.grammar_catalog import (
    FRENCH_CORE_CATALOG_V2_VERSION,
    catalog_rows,
    concept_syllabus,
)
from app.services.grammar_units import unit_brief
from app.services.journey_contracts import (
    DayShape,
    LearningCandidate,
    RecallTask,
    StepKind,
    TargetKind,
    TargetRef,
)
from app.services.journey_day_shapes import DayShapeInputs
from app.services.season.page import exchanges_for
from app.services.season.runtime import projected_turns, routes_the_story
from tests import walk_checks_wp129
from tests.test_journey_planner import _candidate
from tests.wp93_briefs import engine_brief

DICE = DayShapeInputs(user_id="wp129", local_date=date(2026, 10, 4))
SEASON = Path(__file__).resolve().parents[1] / "app" / "data" / "season" / "s1"


# ---------------------------------------------------------------------------
# Helpers: real catalogue units, as the learning adapter briefs them
# ---------------------------------------------------------------------------

_ROWS = {row["external_id"]: row for row in catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION)}
_COLUMNS = {column.name for column in GrammarConcept.__table__.columns}


def concept(external_id: str, concept_id: int) -> GrammarConcept:
    row = _ROWS[external_id]
    return GrammarConcept(id=concept_id, **{key: value for key, value in row.items() if key in _COLUMNS})


def brief(external_id: str, concept_id: int, *, stability: float = 4.0) -> dict[str, Any]:
    unit = concept(external_id, concept_id)
    out = unit_brief(unit, control_language="fr", stability=stability)
    return {**out, "contrast_partners": list(concept_syllabus(unit).get("contrast_partners") or [])}


def practice_unit(external_id: str, concept_id: int, **kwargs: Any) -> LearningCandidate:
    unit = brief(external_id, concept_id, **kwargs)
    return LearningCandidate(
        target=grammar_items.grammar_target(unit),
        priority_score=0.0,
        due_since_days=0,
        estimated_seconds=40,
        is_new=False,
        source_item_type="grammar",
        metadata={"practice_unit": True, "concept_id": concept_id, "grammar_brief": unit},
    )


#: Introduced units of a B1 learner, two partner pairs among them.
B1_UNITS = (
    ("FR2_B11_PLUS_QUE_PARFAIT", 901),
    ("FR2_A21_PC_AVOIR", 902),
    ("FR2_A22_IMPARFAIT", 903),
    ("FR2_A21_PC_ETRE", 904),
    ("FR2_B11_NARRATION", 905),
)


def _words(count: int = 6) -> list[LearningCandidate]:
    words = [("la clé", "the key"), ("la chaise", "the chair"), ("la poche", "the pocket"),
             ("le sac", "the bag"), ("le parapluie", "the umbrella"), ("la pluie", "the rain")]
    return [
        _candidate(identifier=f"w{index}", label_fr=fr, label_native=native, priority=20 - index)
        for index, (fr, native) in enumerate(words[:count])
    ]


def _day(band: str, budget: int = 600, *, units: tuple = (), scenario=None, **extra):
    return planner.plan_journey(
        scenario=scenario or engine_brief(level_band=band, control_language="fr" if band[0] in "BC" else "en"),
        candidates=[*_words(), *(practice_unit(ext, cid) for ext, cid in units)],
        budget_seconds=budget,
        practice=True,
        dice=DICE,
        day_shape=DayShape.STANDARD,
        **extra,
    )


def _recalls(plan) -> list:
    return [step for step in plan.steps if step.kind is StepKind.RECALL]


def _respond(plan):
    return next(step for step in plan.steps if step.kind is StepKind.RESPOND)


# ---------------------------------------------------------------------------
# 0. The owner's A1/A2 day: fewer replies, more items
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2"])
def test_an_a1_a2_regulier_reply_asks_two_exchanges_and_the_day_holds_more_items(band: str) -> None:
    plan = _day(band)
    plan.validate()
    assert _respond(plan).public_prompt["max_turns"] == 2
    assert "more optional, not in the core estimate" in plan.rationale
    assert plan.estimated_active_seconds <= plan.budget_seconds
    # The reply's third exchange bought items: more than the WP-128 day held.
    assert len(_recalls(plan)) >= 6, plan.rationale


def test_soutenu_keeps_its_story_and_b1_keeps_its_three_exchanges() -> None:
    assert _respond(_day("A2", 1200)).public_prompt["max_turns"] == 4
    assert _respond(_day("B1")).public_prompt["max_turns"] == 3


def test_an_authored_minimum_is_never_cut_for_items() -> None:
    scenario = engine_brief(level_band="A1")
    scenario = replace(scenario, response_task=replace(scenario.response_task, min_turns=3))
    plan = _day("A1", scenario=scenario)
    assert _respond(plan).public_prompt["max_turns"] >= 3


def _season_day(segment: str, index: int) -> dict[str, Any]:
    days = json.loads((SEASON / f"{segment}.json").read_text())["days"]
    return list(days.values())[index] if isinstance(days, dict) else days[index]


def test_a_turn_that_sets_a_flag_after_the_choice_counts_in_the_minimum() -> None:
    # T6 day B: «Le choix», then a turn whose replies set flags. The page's
    # minimum reaches that turn (it used to stop at the choice, so a short
    # reply dropped what the learner's answer would have set).
    turns = projected_turns(_season_day("t6", 1))
    routing = [index for index, turn in enumerate(turns) if routes_the_story(turn)]
    assert routing and routing[-1] == len(turns) - 1
    assert sum(exchanges_for(turn) for turn in turns[: routing[-1] + 1]) == len(turns)
    # A turn whose sets hold whatever is said does not route.
    assert not routes_the_story({"id": "x", "sets": {"s1.flag": True}, "replies": [{"id": "a"}]})


# ---------------------------------------------------------------------------
# 1. B1+: mixed-unit production inside the budget
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("band", ["B1", "B2", "C1"])
def test_a_b1_plus_day_fills_its_time_with_mixed_unit_production(band: str) -> None:
    plan = _day(band, units=B1_UNITS)
    plan.validate()
    assert plan.estimated_active_seconds <= plan.budget_seconds
    recalls = _recalls(plan)
    grammar = [step for step in recalls if step.private_task.target.kind is TargetKind.GRAMMAR]
    assert len(recalls) >= 6, plan.rationale
    assert len(grammar) * 2 >= len(recalls), "about half the day is interleaved practice"
    formats = {
        "contrast" if step.private_task.task_type == "classify"
        else "free" if step.private_task.evidence_format == grammar_items.FREE_SENTENCE_FORMAT
        else step.private_task.task_type
        for step in grammar
    }
    assert {"contrast", "free", "transform"} <= formats, formats
    # Interleaved: never the same unit twice running.
    ids = [step.private_task.target.id for step in grammar]
    assert all(a != b for a, b in zip(ids, ids[1:], strict=False)), ids
    # All after the ending: the episode is never interrupted.
    resolution_at = next(i for i, s in enumerate(plan.steps) if s.kind is StepKind.RESOLUTION)
    practice_ids = {str(cid) for _ext, cid in B1_UNITS}
    assert all(
        index > resolution_at
        for index, step in enumerate(plan.steps)
        if step.kind is StepKind.RECALL and step.private_task.target.id in practice_ids
    )


def test_practice_units_are_never_a_reply_obligation() -> None:
    plan = _day("B1", units=B1_UNITS)
    asked = {target.id for target in _respond(plan).private_task.targets}
    assert not asked & {str(cid) for _ext, cid in B1_UNITS}


def test_without_introduced_units_a_b1_day_invents_nothing() -> None:
    plan = _day("B1")
    assert not [
        step for step in _recalls(plan)
        if step.private_task.evidence_format == grammar_items.FREE_SENTENCE_FORMAT
        or step.private_task.task_type == "classify"
    ]


def test_below_b1_the_fill_leaves_the_day_alone() -> None:
    plan = _day("A2", units=B1_UNITS)
    assert not [s for s in _recalls(plan) if s.private_task.target.id in {str(c) for _e, c in B1_UNITS}]


def test_the_contrast_has_exactly_one_answer() -> None:
    a, b = brief("FR2_B11_PLUS_QUE_PARFAIT", 1), brief("FR2_A21_PC_AVOIR", 2)
    task = grammar_items.contrast_item(a, b, language="fr", day_key="d")
    assert task is not None and task.task_type == "classify" and len(task.options) == 2
    owner = a if task.target.id == "1" else b
    other = b if owner is a else a
    assert grammar_items.rule_span(owner, task.prompt_fr) is not None
    assert not grammar_items.mentions_rule(other, task.prompt_fr)
    assert task.hint_native is None, "the rule's line would name the answer"


def test_a_free_sentence_is_graded_by_the_unit_on_the_learners_words() -> None:
    unit = brief("FR2_B11_PLUS_QUE_PARFAIT", 1)
    task = grammar_items.free_sentence_item(unit, language="fr")
    assert task is not None and task.prompt_fr is None and task.goal_native
    assert task.instruction_native.endswith("Le plus-que-parfait.")
    assert grammar_items.free_sentence_uses_unit(unit, "Quand je suis arrivé, il était déjà parti.")
    assert not grammar_items.free_sentence_uses_unit(unit, "Je suis arrivé hier soir.")
    assert not grammar_items.free_sentence_uses_unit(unit, "Il était parti.")  # under four words
    db = SimpleNamespace(get=lambda _cls, _id: concept("FR2_B11_PLUS_QUE_PARFAIT", 1))
    assert journey_learning._is_free_sentence(task)
    assert journey_learning._free_sentence_uses_unit(db, task, "Nous avions déjà mangé à midi.")
    assert not journey_learning._free_sentence_uses_unit(db, task, "Nous mangeons à midi ensemble.")


# ---------------------------------------------------------------------------
# 2. D7: a unit met earlier, in a line of the page
# ---------------------------------------------------------------------------


def test_the_page_review_shows_a_met_unit_in_a_line_the_learner_read() -> None:
    scenario = engine_brief(level_band="A2")
    met = [brief("FR2_A22_IMPARFAIT", 7), brief("FR2_A21_PC_AVOIR", 8)]
    step = planner.page_review_step(scenario, met, spt=0.6, multiplier=1.0, band="A2")
    assert step is not None and step.kind is StepKind.RULE
    prompt = step.public_prompt
    assert prompt["review"] is True and prompt["concept_id"] == 8
    line = prompt["scene_example_fr"]
    page = " ".join(planner.page_texts(planner.scene_page(scenario)))
    assert "[" in line and grammar_items.plain(line) in page
    assert prompt["rule_card"]["example"] == {"fr": line} and prompt["rule_card"]["from_scene"]
    assert 0 < step.estimated_seconds < 60


def test_no_met_unit_on_the_page_means_no_review() -> None:
    scenario = engine_brief(level_band="A2")
    assert planner.page_review_step(scenario, [brief("FR2_B11_PLUS_QUE_PARFAIT", 1)], spt=0.6, multiplier=1.0) is None
    assert planner.page_review_step(scenario, [], spt=0.6, multiplier=1.0) is None


def test_without_the_contract_a_tentpole_day_plans_no_review() -> None:
    if journey_contracts.__dict__.get("PAGE_REVIEW_AFTER_ENDING"):
        pytest.skip("the contract carries the review: see the next test")
    plan = _day("A2", page_review=[brief("FR2_A21_PC_AVOIR", 8)])
    assert not [step for step in plan.steps if step.kind is StepKind.RULE]


@pytest.mark.skipif(
    not journey_contracts.__dict__.get("PAGE_REVIEW_AFTER_ENDING"),
    reason="needs the WP-129 contract patch (journey_contracts.PAGE_REVIEW_AFTER_ENDING)",
)
def test_a_tentpole_day_reviews_after_the_ending_and_introduces_nothing() -> None:
    plan = _day("A2", page_review=[brief("FR2_A21_PC_AVOIR", 8)])
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    review_at = kinds.index(StepKind.RULE)
    assert kinds[review_at - 1] is StepKind.RESOLUTION, "straight after the ending"
    assert plan.steps[review_at].public_prompt["review"] is True
    assert plan.estimated_active_seconds <= plan.budget_seconds
    assert daily_journey_module._planned_introduction(plan) is None


def test_reading_the_review_introduces_and_credits_nothing(monkeypatch) -> None:
    from app.services import concept_life

    def refuse(*_args, **_kwargs):
        raise AssertionError("a review must not introduce its unit")

    monkeypatch.setattr(concept_life, "mark_introduced", refuse)
    service = SimpleNamespace(db=None)
    step = SimpleNamespace(private_task={"review_concept_id": 8})
    daily_journey_module.DailyJourneyService._mark_rule_read(service, SimpleNamespace(), step)
    plan = SimpleNamespace(steps=[SimpleNamespace(kind=StepKind.RULE, public_prompt={"concept_id": 8, "review": True})])
    assert daily_journey_module._planned_introduction(plan) is None


# ---------------------------------------------------------------------------
# 3. One sentence, one item
# ---------------------------------------------------------------------------


def _task(task_type: str, **kwargs: Any) -> RecallTask:
    base = {
        "instruction_native": "x", "prompt_fr": None, "options": [], "optional": False,
        "target": TargetRef(kind=TargetKind.GRAMMAR, id="1", label_fr="u"),
    }
    base.update(kwargs)
    return RecallTask(task_type=task_type, **base)


def test_two_units_never_rebuild_one_sentence() -> None:
    first = _task("choice", solution_fr="Tu as une minute ?")
    second = _task("word_bank", solution_fr="Tu as une minute ?")
    assert planner.overlaps_the_day(second, [first])
    assert not planner.overlaps_the_day(_task("word_bank", solution_fr="Il pleut sur le canal."), [first])


def test_two_grids_sharing_their_cards_are_one_grid_twice() -> None:
    def grid(*words: str) -> RecallTask:
        return _task("match_pairs", options=[{"id": w, "text_fr": w, "side": "fr"} for w in words])

    assert planner.overlaps_the_day(grid("chose", "lettre", "pas", "votre"), [grid("vendredi", "pas", "chose", "lettre")])
    assert not planner.overlaps_the_day(grid("chose", "clé", "sac", "votre"), [grid("vendredi", "pas", "porte", "lettre")])


def test_a_rappel_gives_way_when_its_sentence_is_taken() -> None:
    unit = {**brief("FR2_A21_PC_AVOIR", 2, stability=5.0), "level": "B1"}
    first = grammar_items.review_item(unit, sentences=[], language="fr", day_key="k")
    assert first is not None
    again = grammar_items.review_item(
        unit, sentences=[], language="fr", day_key="k", avoid=grammar_items.item_sentences(first)
    )
    assert again is None or not (grammar_items.item_sentences(again) & grammar_items.item_sentences(first))


def test_the_essai_never_rebuilds_the_sentence_it_just_answered() -> None:
    unit = brief("FR2_A21_PC_AVOIR", 2)
    items = grammar_items.guided_items({**unit, "level": "A2"}, sentences=[], language="en")
    seen: set[str] = set()
    for task in items:
        assert not grammar_items.item_sentences(task) & seen
        seen |= grammar_items.item_sentences(task)


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "C1"])
def test_no_planned_day_works_on_one_sentence_twice(band: str) -> None:
    plan = _day(band, units=B1_UNITS if band in ("B1", "C1") else ())
    seen: set[str] = set()
    for step in _recalls(plan):
        own = grammar_items.item_sentences(step.private_task)
        assert not own & seen, (band, own & seen)
        seen |= own


# ---------------------------------------------------------------------------
# 4. The walk checks fire on a bad life and stay quiet on a good one
# ---------------------------------------------------------------------------


def _event(kind: str, **prompt: Any) -> dict[str, Any]:
    key = prompt.pop("key", None)
    event = {"step": {"kind": kind, "prompt": prompt}}
    if key is not None:
        event["key"] = key
    return event


def _record(days: list[list[dict[str, Any]]], persona: str = "b1-en") -> dict[str, Any]:
    return {
        "persona": persona,
        "quality": "average",
        "days": [
            {"day": index + 1, "journey": {"budget_seconds": 600, "events": events}}
            for index, events in enumerate(days)
        ],
    }


def _grammar(unit: str, task_type: str = "transform", sentence: str | None = None) -> dict[str, Any]:
    return _event(
        "recall", task_type=task_type, target={"kind": "grammar", "id": unit}, prompt_fr=sentence,
        key={"solution_fr": sentence},
    )


def test_the_sentence_check_fires_on_a_shared_sentence_only() -> None:
    bad = _record([[_grammar("1", "choice", "Tu as une minute ?"), _grammar("2", "word_bank", "Tu as une minute ?")]])
    good = _record([[_grammar("1", "choice", "Tu as une minute ?"), _grammar("2", "word_bank", "Il pleut sur le canal.")]])
    assert walk_checks_wp129.check_one_sentence_one_item(bad)
    assert not walk_checks_wp129.check_one_sentence_one_item(good)


def test_the_review_check_needs_a_unit_introduced_earlier() -> None:
    rule = _event("rule", concept_id=5)
    review = _event("rule", concept_id=5, review=True)
    early = _record([[rule], [_event("resolution"), review]])
    new = _record([[_event("resolution"), _event("rule", concept_id=6, review=True)]])
    assert not walk_checks_wp129.check_page_review_is_a_met_unit(early)
    assert walk_checks_wp129.check_page_review_is_a_met_unit(new)


def test_the_practice_check_reports_thin_or_blocked_b1_days() -> None:
    mixed = [_grammar(str(1 + index % 3), "transform", f"Phrase numéro {index} ici.") for index in range(8)]
    thin = [_grammar("1", "transform", "Une seule phrase ici.")]
    assert not walk_checks_wp129.check_b1_practice(_record([mixed] * 10))
    assert walk_checks_wp129.check_b1_practice(_record([thin] * 10))
    # Below B1 the volume check does not apply.
    assert not walk_checks_wp129.check_b1_practice(_record([thin] * 10, persona="a1-de-fresh"))
