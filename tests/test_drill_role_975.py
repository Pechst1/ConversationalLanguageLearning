"""#469 / #975: a drill step carries what it is for in the day, so the device never
names a review «today's rule» nor a learner's own slip «the words».

The walk of 21 Nov (A2, day 2): the drill around the scene dealt the learner's own
slip («cafe») and P6's one due rule («Un, une, des», concept 4) while the day's rule
was concept 40; the device chose the sticker from the target's kind alone and said
«Quick drills on today's rule» over «Un, une, des». The planner knows which item is
an own mistake (the errata), which is a due rule (the Rappel) and which is today's
rule (the introduction's guided items); the step now says so as ``prompt.role``.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.schemas.daily_journey import RecallPrompt
from app.services import journey_planner as planner
from app.services.journey_contracts import StepKind, TargetKind
from app.services.journey_day_shapes import DayShapeInputs
from tests.test_journey_planner import _brief, _candidate
from tests.test_p6_drill_own_mistakes import WORDS, _etre


def _todays_rule() -> dict:
    """Concept 40 («Passé composé with être») stands in as the day's new rule."""

    return {**_etre(), "concept_id": 40, "title_fr": "Passé composé avec être"}


def _due_articles():
    brief = {
        "concept_id": 4,
        "title_fr": "Un, une, des",
        "title_native": "Un, une, des: a, an, some (and gender)",
        "detectors": [r"\b(?:un|une|des)\b"],
        "examples": ["Je voudrais un café.", "Une table, s'il vous plaît."],
        "contrast_pairs": [{"wrong": "Je voudrais une café.", "right": "Je voudrais un café."}],
        "pattern_forms": [],
        "rule_short_native": None,
        "stability": 1.0,
        "rule_card": {"example": {"fr": "[Un] café.", "tr": {"en": "A coffee."}}, "rule": {"en": "r"}},
    }
    return _candidate(
        kind=TargetKind.GRAMMAR, identifier="4", label_fr="Un, une, des",
        label_native="Un, une, des", metadata={"grammar_brief": brief, "stability": 1.0},
    )


def _slip_cafe():
    return _candidate(
        kind=TargetKind.ERROR, identifier="e-cafe", label_fr="café", label_native="wrong form",
        priority=9.0, metadata={"erratum_learner": "cafe", "target_reason": "erratum:e-cafe"},
    )


def _day(*, introduction):
    plan = planner.plan_journey(
        scenario=_brief(),
        candidates=[*WORDS, _due_articles(), _slip_cafe()],
        budget_seconds=600,
        practice=True,
        audio_available=True,
        dice=DayShapeInputs(user_id="975-day-2", local_date=date(2026, 11, 21)),
        introduction=introduction,
    )
    plan.validate()
    return plan


def _roles(plan) -> dict[str, str | None]:
    return {
        f"{step.target.kind}:{step.target.id}": (step.public_prompt or {}).get("role")
        for step in plan.steps
        if step.kind is StepKind.RECALL
    }


@pytest.mark.parametrize("introduction", [_todays_rule(), None], ids=["rule-40-today", "no-rule-card"])
def test_the_walks_day_two_tells_the_slip_and_the_due_rule_from_todays_rule(introduction) -> None:
    roles = _roles(_day(introduction=introduction))

    assert "error:e-cafe" in roles and "grammar:4" in roles, roles
    assert roles["error:e-cafe"] == "mistake", f"the own slip «cafe» reaches the client as {roles['error:e-cafe']!r}"
    assert roles["grammar:4"] == "review", (
        f"«Un, une, des» on a day whose rule is 40 reaches the client as {roles['grammar:4']!r}"
    )


def test_a_guided_item_on_todays_rule_is_the_day_rule(monkeypatch) -> None:
    monkeypatch.setattr(planner, "RULE_TAUGHT_ONCE", False)
    plan = planner.plan_journey(
        scenario=_brief(),
        candidates=list(WORDS),
        budget_seconds=600,
        practice=True,
        audio_available=True,
        dice=DayShapeInputs(user_id="p6-normal", local_date=date(2026, 11, 18)),
        introduction=_todays_rule(),
    )
    roles = _roles(plan)

    assert roles.get("grammar:40") == "day_rule", roles
    assert all(role is None for key, role in roles.items() if key.startswith("vocabulary:")), roles


def test_the_role_survives_the_public_schema() -> None:
    plan = _day(introduction=_todays_rule())
    for step in plan.steps:
        if step.kind is StepKind.RECALL:
            wire = RecallPrompt.model_validate(step.public_prompt).model_dump(mode="json")
            assert wire.get("role") == step.public_prompt.get("role")
            if step.public_prompt.get("role") is None:
                assert "role" not in wire, "a word drill's prompt is unchanged"
