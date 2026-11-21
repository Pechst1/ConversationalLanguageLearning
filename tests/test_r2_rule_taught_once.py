"""R2 item 1: a day teaches its rule ONCE.

Real play, 17 Nov (A1, de): day 1 showed the être card, then a drill on être
(«In welchem Satz steckt die Regel von heute?»), then La Forge on être — the same
rule three times in one sitting; day 2 the same with avoir. On a beginner's first
days nothing is due, so decision 8's «one guided item when the block is thin»
came back every day. Now: the rule card (its own worked example), and La Forge
as the one place the rule is practised. The drill around the scene carries no
item on today's rule — only own mistakes and due reviews, empty when none.
"""
from __future__ import annotations

from app.services import grammar_items
from app.services.journey_contracts import StepKind, TargetKind
from tests.test_p6_drill_own_mistakes import WORDS, _day, _drills, _due_rule, _etre, _mistake


def _today_rule_items(plan) -> list:
    return [step for step in _drills(plan) if step.target.kind is TargetKind.GRAMMAR and step.target.id == "7"]


def test_nothing_due_no_drill_on_todays_rule() -> None:
    """A beginner's first day: nothing due. The card stays; no drill on its rule."""

    plan = _day(list(WORDS), introduction=_etre())

    assert StepKind.RULE in [step.kind for step in plan.steps], "the rule card stays"
    assert _today_rule_items(plan) == [], "today's rule is practised in La Forge, not around the scene"
    assert _drills(plan) == [], "nothing due: the drill around the scene is empty"


def test_due_items_but_never_todays_rule() -> None:
    plan = _day([*WORDS, _due_rule(), _mistake("e-1", "une homme", "un homme")], introduction=_etre())

    assert StepKind.RULE in [step.kind for step in plan.steps]
    assert _today_rule_items(plan) == []
    assert {step.target.id for step in _drills(plan)} == {"e-1", "8"}


def test_card_stands_without_guided_items(monkeypatch) -> None:
    """The planner no longer needs two guided items for the card to exist."""

    monkeypatch.setattr(grammar_items, "guided_items", lambda *args, **kwargs: [])
    plan = _day(list(WORDS), introduction=_etre())

    assert StepKind.RULE in [step.kind for step in plan.steps], plan.rationale
