"""#474 — a séance never asks a noun's gender after it showed the noun with its article.

Walk, 2 November (a1-de-fresh, day 2): the recall drills went 5/9 «la lettre ·
Was bedeutet das?», then 8/9 «lettre · Maskulin oder feminin?». The answer had
been on screen three drills earlier. Since #465 every noun carries its article,
but the planner placed the gender drill as if it were independent of the drills
around it.
"""
from __future__ import annotations

from app.services import journey_planner as planner
from app.services.journey_contracts import RecallTask, TargetKind, TargetRef
from tests.test_journey_planner import _candidate

LETTRE = TargetRef(kind=TargetKind.VOCABULARY, id="lettre", label_fr="la lettre", label_native="Brief")
CLE = TargetRef(kind=TargetKind.VOCABULARY, id="cle", label_fr="la clé", label_native="Schlüssel")
CAFE = TargetRef(kind=TargetKind.VOCABULARY, id="cafe", label_fr="un café", label_native="Kaffee")


def _entry(target: TargetRef) -> planner.SelectedTarget:
    candidate = _candidate(identifier=target.id, label_fr=target.label_fr, label_native=target.label_native)
    return planner.SelectedTarget(candidate=candidate, fit=1.0, demonstrated=False)


def _meaning(target: TargetRef = LETTRE) -> RecallTask:
    task = planner.build_listen_tap_task(
        target=target, pool=[LETTRE, CLE, CAFE], optional=False, control_language="de"
    )
    assert task is not None and target.label_fr in (task.prompt_fr or ""), "the drill shows the noun with its article"
    return task


def _gender(target: TargetRef = LETTRE) -> RecallTask:
    task = planner.build_classify_task(target=target, optional=False, control_language="de")
    assert task is not None and task.instruction_native.startswith("Maskulin")
    return task


def _item(slot: str, position: int, target: TargetRef, task: RecallTask) -> planner.PracticeItem:
    return planner.PracticeItem(slot=slot, position=position, entry=_entry(target), task=task, cost=10)


def test_474_a_gender_drill_is_not_placed_after_a_drill_that_showed_the_article() -> None:
    placed = [_item("warmup", 0, LETTRE, _meaning())]
    # Before: nothing looked at what the earlier drills printed, so the planner
    # placed «lettre · Maskulin oder feminin?» after «la lettre · Was bedeutet das?».
    for slot in ("warmup", "mid", "post"):
        assert planner._repeats_the_day(_gender(), _entry(LETTRE), placed, slot=slot), (
            f"the gender of «lettre» is asked in {slot} after «la lettre» was shown"
        )


def test_474_a_gender_drill_placed_first_is_fine_and_other_nouns_are_unaffected() -> None:
    # The meaning drill comes later in the séance than the gender drill: fine.
    later = [_item("post", 0, LETTRE, _meaning())]
    assert not planner._repeats_the_day(_gender(), _entry(LETTRE), later, slot="warmup")
    # A different noun shown earlier says nothing about «lettre».
    other = [_item("warmup", 0, CLE, _meaning(CLE))]
    assert not planner._repeats_the_day(_gender(), _entry(LETTRE), other, slot="post")
