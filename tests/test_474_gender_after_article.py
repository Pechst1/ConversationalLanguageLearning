"""#474 — a séance never asks a noun's gender after it showed the noun with its article.

Walks, 2 and 3 November: the recall drills went 5/9 «la lettre · Was bedeutet
das?», then 8/9 «lettre · Maskulin oder feminin?»; and «un appartement · What
does it mean?» straight followed by «appartement · Masculine or feminine?».
Since #465 every noun carries its article, and the article *is* the answer.

The planner filled its slots in one order (warm-up, build, word of today, ...)
and the learner meets them in another (warm-up, mid, post), so a gender drill
placed early can end up displayed *after* the item that prints the article. The
rule has to hold on the displayed order, from both directions.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from app.services import journey_planner as planner
from app.services.journey_contracts import DayShape, RecallTask, StepKind, TargetKind, TargetRef
from tests.test_journey_planner import _brief, _candidate

LETTRE = TargetRef(kind=TargetKind.VOCABULARY, id="lettre", label_fr="la lettre", label_native="Brief")
CLE = TargetRef(kind=TargetKind.VOCABULARY, id="cle", label_fr="la clé", label_native="Schlüssel")
CAFE = TargetRef(kind=TargetKind.VOCABULARY, id="cafe", label_fr="un café", label_native="Kaffee")

NOUNS = [
    ("lettre", "la lettre", "Brief"),
    ("appart", "un appartement", "Wohnung"),
    ("offre", "une offre", "Angebot"),
    ("cle", "la clé", "Schlüssel"),
    ("cafe", "un café", "Kaffee"),
    ("gare", "la gare", "Bahnhof"),
]


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


def _printed(task: RecallTask) -> str:
    parts = [task.prompt_fr, task.goal_native, task.hint_native]
    parts.extend(str(option.get("text_fr") or "") for option in task.options or [])
    return " ".join(str(part) for part in parts if part).casefold()


def _answer_already_on_screen(shown: list[RecallTask]) -> list[str]:
    """The gender drills in ``shown`` whose noun an earlier item printed with its article."""

    found = []
    for index, task in enumerate(shown):
        solution = (task.solution_fr or "").split()
        if task.task_type != "classify" or len(solution) != 2 or solution[0].casefold() not in {"un", "une", "le", "la"}:
            continue
        article, noun = solution
        if any(re.search(rf"\b(?:un|une|le|la)\s+{re.escape(noun.casefold())}\b", _printed(earlier)) for earlier in shown[:index]):
            found.append(task.solution_fr)
    return found


# -- the placement rule, from both directions -------------------------------


def test_474_a_gender_drill_is_not_placed_after_a_drill_that_showed_the_article() -> None:
    placed = [_item("warmup", 0, LETTRE, _meaning())]
    for slot in ("warmup", "mid", "post"):
        assert planner._repeats_the_day(_gender(), _entry(LETTRE), placed, slot=slot), (
            f"the gender of «lettre» is asked in {slot} after «la lettre» was shown"
        )


@pytest.mark.parametrize(("gender_slot", "meaning_slot"), [("post", "warmup"), ("post", "mid"), ("mid", "warmup")])
def test_474_an_article_is_not_shown_in_front_of_a_gender_drill_already_placed(gender_slot, meaning_slot) -> None:
    # The fill order is warm-up 0, mid 0, post 0, warm-up 1, mid 1: the gender
    # drill is placed first, and the drill that prints the article is placed
    # later but displayed *before* it.
    placed = [_item(gender_slot, 0, LETTRE, _gender())]
    assert planner._repeats_the_day(_meaning(), _entry(LETTRE), placed, slot=meaning_slot), (
        f"«la lettre» in {meaning_slot} would be shown before «lettre · Maskulin oder feminin?» in {gender_slot}"
    )


def test_474_a_gender_drill_placed_first_is_fine_and_other_nouns_are_unaffected() -> None:
    # The meaning drill is displayed after the gender drill: fine, both ways.
    later = [_item("post", 0, LETTRE, _meaning())]
    assert not planner._repeats_the_day(_gender(), _entry(LETTRE), later, slot="warmup")
    earlier = [_item("warmup", 0, LETTRE, _gender())]
    assert not planner._repeats_the_day(_meaning(), _entry(LETTRE), earlier, slot="post")
    # A different noun shown earlier says nothing about «lettre».
    other = [_item("warmup", 0, CLE, _meaning(CLE))]
    assert not planner._repeats_the_day(_gender(), _entry(LETTRE), other, slot="post")
    assert not planner._repeats_the_day(_meaning(CLE), _entry(CLE), [_item("post", 0, LETTRE, _gender())], slot="warmup")


# -- the planned day ---------------------------------------------------------


@pytest.mark.parametrize("band", ["A1", "A2"])
@pytest.mark.parametrize("language", ["de", "en"])
def test_474_no_planned_day_asks_a_gender_after_the_article_was_shown(band, language) -> None:
    """Many users, days and word queues: the displayed recall steps are checked."""

    days_checked = 0
    for user in ("a", "b", "c", "d", "e"):
        for day in (1, 5, 9, 14):
            candidates = [
                _candidate(identifier=i, label_fr=fr, label_native=native, due_since_days=2 + rank)
                for rank, (i, fr, native) in enumerate(NOUNS)
            ]
            plan = planner.plan_journey(
                scenario=_brief(level_band=band, control_language=language),
                candidates=candidates,
                practice=True,
                dice=planner.DayShapeInputs(user_id=user, local_date=date(2026, 9, day)),
                day_shape=DayShape.STANDARD,
            )
            shown = [step.private_task for step in plan.steps if step.kind is StepKind.RECALL]
            days_checked += 1
            assert not _answer_already_on_screen(shown), (
                f"{band}/{language}/{user}/day {day}: "
                + " | ".join(f"{task.task_type}:{task.prompt_fr}" for task in shown)
            )
    assert days_checked == 20


def test_474_the_final_pass_drops_a_gender_drill_displayed_after_its_article() -> None:
    from app.services.journey_planner import without_given_away_genders

    gender = _item("post", 0, LETTRE, _gender())
    meaning = _item("warmup", 1, LETTRE, _meaning())
    fine = _item("warmup", 0, CLE, _gender(CLE))
    assert without_given_away_genders([gender, meaning, fine]) == [meaning, fine]
    # Gender first, article after: nothing is dropped.
    gender_first = _item("warmup", 0, LETTRE, _gender())
    meaning_later = _item("mid", 0, LETTRE, _meaning())
    assert without_given_away_genders([meaning_later, gender_first]) == [meaning_later, gender_first]
