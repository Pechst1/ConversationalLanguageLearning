"""P6 stage 2 · decision 8 (proposal): the drill around the scene keeps only the
learner's own past mistakes and one due rule.

The 17 Nov experience review (finding 3): the «Rappel» around the scene was mostly
dictation and cloze of the scene's own lines, and its second item was often the
rule card's own ✗/✓ pair seen seconds earlier. Decision 8: the block deals the
learner's own due mistakes, then one due rule, then — only when fewer than two
items so far — one guided item on today's rule that is not the card's pair; at
most four at the ten-minute rhythm.
"""
from __future__ import annotations

from datetime import date

from app.services import journey_planner as planner
from app.services.journey_contracts import RHYTHM_CAPS, StepKind, TargetKind
from app.services.journey_day_shapes import DayShapeInputs
from tests.test_journey_planner import SCENE_FITTING, _brief, _candidate

NORMAL = 600  # «Normal»: the ten-minute rhythm
CARD_WRONG, CARD_RIGHT = "Je es français.", "Je suis français."


def _etre() -> dict:
    """Today's rule: its card prints «Je es français.» ✗ / «Je suis français.» ✓."""

    return {
        "concept_id": 7,
        "title_fr": "Être",
        "title_native": "Être",
        "detectors": [r"\b(?:je suis|il est|vous êtes)\b"],
        "examples": ["Je suis étudiante.", "Il est à Lyon.", "Je suis ici."],
        "contrast_pairs": [{"wrong": CARD_WRONG, "right": CARD_RIGHT}],
        "pattern_forms": [],
        "rule_short_native": None,
        "stability": 0.0,
        "rule_card": {
            "example": {"fr": "[Je suis] ici.", "tr": {"en": "I am here."}},
            "rule": {"en": "Être changes with the person."},
            "contrast": {"wrong": CARD_WRONG, "right": CARD_RIGHT},
        },
    }


def _due_rule():
    brief = {
        "concept_id": 8,
        "title_fr": "Un, une",
        "title_native": "Un, une",
        "detectors": [r"\b(?:un|une)\b"],
        "examples": ["Je voudrais un café.", "Une table, s'il vous plaît."],
        "contrast_pairs": [{"wrong": "Je voudrais une café.", "right": "Je voudrais un café."}],
        "pattern_forms": [],
        "rule_short_native": None,
        "stability": 1.0,
        "rule_card": {"example": {"fr": "[Un] café.", "tr": {"en": "A coffee."}}, "rule": {"en": "r"}},
    }
    return _candidate(
        kind=TargetKind.GRAMMAR, identifier="8", label_fr="Un, une", label_native="Un, une",
        metadata={"grammar_brief": brief, "stability": 1.0},
    )


def _mistake(identifier: str, wrong: str, right: str):
    return _candidate(
        kind=TargetKind.ERROR, identifier=identifier, label_fr=right, label_native="wrong form",
        priority=9.0, metadata={"erratum_learner": wrong, "target_reason": f"erratum:{identifier}"},
    )


WORDS = [
    SCENE_FITTING,
    _candidate(identifier="v-table", label_fr="une table", label_native="a table"),
    _candidate(identifier="v-pluie", label_fr="la pluie", label_native="the rain"),
    _candidate(identifier="v-porte", label_fr="la porte", label_native="the door"),
]


def _day(candidates, *, introduction=None):
    plan = planner.plan_journey(
        scenario=_brief(),
        candidates=candidates,
        budget_seconds=NORMAL,
        practice=True,
        audio_available=True,
        dice=DayShapeInputs(user_id="p6-normal", local_date=date(2026, 11, 18)),
        introduction=introduction,
    )
    plan.validate()
    return plan


def _drills(plan):
    return [step for step in plan.steps if step.kind is StepKind.RECALL]


def _shown(step) -> set[str]:
    task = step.private_task
    texts = [task.prompt_fr, task.source_fr, task.solution_fr, *(o.get("text_fr") for o in task.options or [])]
    return {str(text).strip() for text in texts if text}


def _scene_lines() -> list[str]:
    brief = _brief()
    return [brief.setup_fr, brief.opening_line_fr]


def test_normal_day_four_drills() -> None:
    """An A1 day at «Normal»: at most four drills, no scene-line dictation or cloze,
    never the rule card's own ✗/✓ pair."""

    plan = _day([*WORDS, _due_rule(), _mistake("e-1", "une homme", "un homme")], introduction=_etre())
    drills = _drills(plan)

    assert StepKind.RULE in [step.kind for step in plan.steps], "the rule card stays"
    assert len(drills) <= 4, [step.private_task.task_type for step in drills]
    for step in drills:
        task = step.private_task
        assert task.task_type != "dictation", f"a dictation of a scene line: {task.solution_fr}"
        if task.task_type == "short_answer" and task.prompt_fr and "…" in task.prompt_fr:
            raise AssertionError(f"a cloze of a scene line: {task.prompt_fr}")
        assert not ({CARD_WRONG, CARD_RIGHT} <= _shown(step)), "the rule card's own pair, seconds later"


def test_own_mistakes_first() -> None:
    """Two due own mistakes: the block opens on them, then the due rule; no word drills."""

    plan = _day(
        [
            *WORDS,
            _due_rule(),
            _mistake("e-1", "une homme", "un homme"),
            _mistake("e-2", "le maison", "la maison"),
        ],
        introduction=_etre(),
    )
    drills = _drills(plan)

    assert [step.target.kind for step in drills[:2]] == [TargetKind.ERROR, TargetKind.ERROR]
    assert {step.target.id for step in drills[:2]} == {"e-1", "e-2"}
    assert [step.target.id for step in drills[2:]] == ["8"], "then one due rule, and nothing else"


def test_guided_item_when_thin() -> None:
    """Nothing due: one guided item on today's rule, not the card's pair."""

    plan = _day(list(WORDS), introduction=_etre())
    drills = _drills(plan)

    assert len(drills) == 1
    assert drills[0].target.kind is TargetKind.GRAMMAR and drills[0].target.id == "7"
    assert not ({CARD_WRONG, CARD_RIGHT} <= _shown(drills[0]))


def test_rappel_cap_scales() -> None:
    caps = [planner.rappel_cap(RHYTHM_CAPS[budget]) for budget in (300, 600, 1200, 1800)]
    assert caps == [2, 4, 8, 12]
    assert all(cap <= RHYTHM_CAPS[budget].max_recall // 2 for cap, budget in zip(caps, (300, 600, 1200, 1800), strict=True))


# ---------------------------------------------------------------------------
# The day as a whole, with decision 8 on: every band, rhythm and shape
# ---------------------------------------------------------------------------


def _matrix_days():
    import itertools

    from app.services.journey_contracts import DayShape
    from tests.wp93_briefs import engine_brief

    queue = [*WORDS, _due_rule(), _mistake("e-1", "une homme", "un homme"), _mistake("e-2", "le maison", "la maison")]
    for band, budget, shape, audio, intro in itertools.product(
        ("A1", "A2", "B1"),
        (300, 600, 1200, 1800),
        (DayShape.STANDARD, DayShape.LISTENING, DayShape.REPRISE),
        (False, True),
        (False, True),
    ):
        plan = planner.plan_journey(
            scenario=engine_brief(level_band=band),
            candidates=list(queue),
            budget_seconds=budget,
            practice=True,
            audio_available=audio,
            day_shape=shape,
            dice=DayShapeInputs(user_id=f"p6-{band}", local_date=date(2026, 11, 18)),
            introduction=_etre() if intro else None,
        )
        yield (band, budget, shape, audio, intro), plan


def test_every_day_holds_decision_8() -> None:
    from app.services.journey_contracts import DayShape

    for key, plan in _matrix_days():
        plan.validate()
        assert plan.longer_day or plan.estimated_active_seconds <= plan.budget_seconds, key
        if plan.day_shape is DayShape.LISTENING:
            continue  # a listening day keeps its own listening items
        drills = _drills(plan)
        assert len(drills) <= planner.rappel_cap(RHYTHM_CAPS[key[1]]), (key, [s.private_task.task_type for s in drills])
        for step in drills:
            task = step.private_task
            assert task.task_type != "dictation", key
            assert step.target.kind is not TargetKind.VOCABULARY, (key, "no word drills around the scene")
            assert not ({CARD_WRONG, CARD_RIGHT} <= _shown(step)), key


def test_preview_never_overpromises() -> None:
    """The minutes stated before a day is planned never exceed what a learner with
    nothing due plans (the WP-L9 harness day, decision 8 on)."""

    import tests.test_wp_l9_rhythm_harness as harness

    for rhythm in harness.RHYTHMS:
        budget = harness.RHYTHM_BUDGET[rhythm]
        prior = planner.expected_day_seconds(budget)
        for audio in (False, True):
            plan = harness._day.__wrapped__(rhythm, audio)
            assert prior <= plan.estimated_active_seconds, (rhythm, audio, prior)
