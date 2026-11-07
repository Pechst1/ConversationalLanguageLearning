"""#580 — a recall block never asks a recognition drill whose answer an earlier drill printed.

Walk 7 Nov 2026 (a2-en): recall 6/9 «Which French phrase means "to sell"?» ·
vendre / adresser / aimer, then 7/9 «vendre · What does it mean?» · to love /
to sell / to address. One word, two directions, back to back: the first item
prints the answer to the second. The #474 guard knew this for genders only.
"""
from __future__ import annotations

from app.services import journey_planner as planner
from app.services.journey_contracts import RecallTask, TargetKind, TargetRef
from tests.test_journey_planner import _brief, _candidate

VENDRE = TargetRef(kind=TargetKind.VOCABULARY, id="vendre", label_fr="vendre", label_native="to sell")
ADRESSER = TargetRef(kind=TargetKind.VOCABULARY, id="adresser", label_fr="adresser", label_native="to address")
AIMER = TargetRef(kind=TargetKind.VOCABULARY, id="aimer", label_fr="aimer", label_native="to love")


def _entry(target: TargetRef) -> planner.SelectedTarget:
    candidate = _candidate(identifier=target.id, label_fr=target.label_fr, label_native=target.label_native)
    return planner.SelectedTarget(candidate=candidate, fit=1.0, demonstrated=False)


def _which_phrase(target: TargetRef = VENDRE) -> RecallTask:
    scenario = _brief(control_language="en")
    task = planner.build_recall_task(
        target=target, scenario=scenario, affordances=["vendre", "adresser", "aimer"], optional=False
    )
    assert task is not None and task.task_type == "choice"
    assert 'Which French phrase means "to sell"?' == task.instruction_native or target is not VENDRE
    return task


def _what_does_it_mean(target: TargetRef = VENDRE) -> RecallTask:
    task = planner.build_listen_tap_task(
        target=target, pool=[VENDRE, ADRESSER, AIMER], optional=False, control_language="en"
    )
    assert task is not None and task.prompt_fr == target.label_fr
    return task


# The final pass keeps its #474 name (it is now the general «answer already printed» pass).


def _item(slot: str, position: int, target: TargetRef, task: RecallTask) -> planner.PracticeItem:
    return planner.PracticeItem(slot=slot, position=position, entry=_entry(target), task=task, cost=10)


def test_580_one_drill_served() -> None:
    for first, second in ((_which_phrase, _what_does_it_mean), (_what_does_it_mean, _which_phrase)):
        items = [_item("warmup", 0, VENDRE, first()), _item("warmup", 1, VENDRE, second())]
        served = planner.without_given_away_genders(items)
        assert [item.task.task_type for item in served] == [items[0].task.task_type], (
            f"{first.__name__} then {second.__name__}: the second prints what the first answered"
        )


def test_580_item_between() -> None:
    # Day 1 of the walk: one item between the two.
    between = _item("warmup", 1, AIMER, _which_phrase(AIMER))
    items = [_item("warmup", 0, VENDRE, _what_does_it_mean()), between, _item("warmup", 2, VENDRE, _which_phrase())]
    served = planner.without_given_away_genders(items)
    shown = [(item.entry.target.id, item.task.task_type) for item in served]
    assert shown == [("vendre", "listen_tap"), ("aimer", "choice")], f"the second vendre drill is still served: {shown}"


def test_580_placement() -> None:
    placed = [_item("warmup", 0, VENDRE, _which_phrase())]
    assert planner._repeats_the_day(_what_does_it_mean(), _entry(VENDRE), placed, slot="warmup"), (
        "«vendre · What does it mean?» is placed right after «Which French phrase means to sell?»"
    )
    placed = [_item("post", 0, VENDRE, _what_does_it_mean())]
    # a later fill landing earlier on screen (mid, same block as post) would print it first
    assert planner._repeats_the_day(_which_phrase(), _entry(VENDRE), placed, slot="mid"), (
        "«Which French phrase means to sell?» would be shown before the drill that answers it"
    )


def test_580_spacing_is_fine() -> None:
    before = [_item("warmup", 0, VENDRE, _which_phrase())]
    assert not planner._repeats_the_day(_what_does_it_mean(), _entry(VENDRE), before, slot="post")
    assert not planner._repeats_the_day(_what_does_it_mean(AIMER), _entry(AIMER), before, slot="warmup")
    other_word = [_item("warmup", 0, VENDRE, _which_phrase()), _item("warmup", 1, ADRESSER, _what_does_it_mean(ADRESSER))]
    assert planner.without_given_away_genders(other_word) == other_word
    across = [_item("warmup", 0, VENDRE, _which_phrase()), _item("post", 0, VENDRE, _what_does_it_mean())]
    assert planner.without_given_away_genders(across) == across
