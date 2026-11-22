"""#975 — a drill whose rule is not the day's rule says it is a review.

Walk of 21 Nov 2026 (`a2-en`, day 2): the drill around the scene dealt the Courrier
slip «cafe», then «Un, une, des» (the rule day 1's slip «sa amie → son» had been filed
under, #974) under the sticker «Quick drills on today's rule», while La Forge forged
the day's real rule, «Passé composé with être» (concept 40). Owner decision of 7 Nov
(«Nur als Extra»): a slip's rule never takes «today's rule»; it runs only as a
labelled review. The planner now says which drill is a review (``role``), and the
device labels it (``web-frontend/lib/first-steps.test.js``).
"""
from __future__ import annotations

from app.schemas.daily_journey import RecallPrompt
from app.services.daily_journey import _recall_task_from_json, _recall_task_to_json
from app.services.journey_contracts import TargetKind
from tests.test_p6_drill_own_mistakes import _day, _drills, _etre, _mistake
from tests.test_journey_planner import _candidate

DAY_RULE = 40  # «Passé composé with être, and agreement»
SLIP_RULE = 4  # «Un, une, des», due because day 1's slip was filed under it


def _due_rule(concept_id: int):
    brief = {
        "concept_id": concept_id,
        "title_fr": "Un, une, des",
        "title_native": "Un, une, des",
        "detectors": [r"\b(?:un|une|des)\b"],
        "examples": ["Je voudrais un café.", "Une table, s'il vous plaît."],
        "contrast_pairs": [{"wrong": "Je voudrais une café.", "right": "Je voudrais un café."}],
        "pattern_forms": [],
        "rule_short_native": None,
        "stability": 1.0,
        "rule_card": {"example": {"fr": "[Un] café.", "tr": {"en": "A coffee."}}, "rule": {"en": "r"}},
    }
    return _candidate(
        kind=TargetKind.GRAMMAR, identifier=str(concept_id), label_fr="Un, une, des", label_native="Un, une, des",
        metadata={"grammar_brief": brief, "stability": 1.0},
    )


def _day_rule() -> dict:
    return {**_etre(), "concept_id": DAY_RULE, "title_fr": "Passé composé avec être", "title_native": "Passé composé with être"}


def test_walk_day_two_roles() -> None:
    """The walk's day 2: own mistake «cafe», due rule «Un, une, des», day rule 40."""

    plan = _day([_due_rule(SLIP_RULE), _mistake("e-cafe", "cafe", "café")], introduction=_day_rule())
    roles = {(step.target.kind, step.target.id): step.public_prompt.get("role") for step in _drills(plan)}

    assert roles.get((TargetKind.ERROR, "e-cafe")) == "mistake", roles
    assert roles.get((TargetKind.GRAMMAR, str(SLIP_RULE))) == "review", roles
    for (kind, identifier), role in roles.items():
        if kind is TargetKind.GRAMMAR and identifier == str(DAY_RULE):
            assert role is None, "a drill on the day's rule is today's rule"
    for step in _drills(plan):
        # The public contract carries it, and a stored step keeps it.
        prompt = RecallPrompt.model_validate(step.public_prompt).model_dump()
        assert prompt.get("role") == step.public_prompt.get("role")
        assert _recall_task_from_json(_recall_task_to_json(step.private_task)).role == step.private_task.role


def test_day_rule_target() -> None:
    """The day's rule is the one the day introduces, else the folded forge's."""
    from app.services.journey_planner import day_rule_target

    assert day_rule_target({"concept_id": DAY_RULE}, {"concept_id": 7}) == str(DAY_RULE)
    assert day_rule_target(None, {"concept_id": DAY_RULE}) == str(DAY_RULE)
    assert day_rule_target({"concept_id": None}, None) is None
