"""Drill miss notes read from the task the item declares, never from its widget alone.

* #967 (live walk 21 Nov, A1.1 day 39): the repair «une café» built from the tiles
  «café», «un». «café un» was told «It does not start with “café”.», which the learner
  read as a lie about their own line (it does start with «café»), and neither the
  order nor the gender slip the item repairs («une» → «un») was named.
* #1024 (live walk 23 Nov, A1.1 day 41): a missed word item («regarder»: to look)
  whose answer waits for the retry said «Not this one. Look at the rule again and
  choose once more.»: a word has no rule, and the choices are locked until the item
  comes back at the end of the set.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.services import journey_learning
from app.services import journey_planner as planner
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    RecallTask,
    TargetKind,
    TargetRef,
    TaskOutcome,
)
from tests.test_journey_planner import _brief

LANGUAGES = ("en", "de", "fr")


def _user(language: str) -> SimpleNamespace:
    return SimpleNamespace(native_language=language, cefr_estimate="A1.1", proficiency_level="A1")


def _miss(task: RecallTask, answer: AttemptAnswer, language: str):
    evaluation = journey_learning.evaluate_recall(
        None, user=_user(language), task=task, answer=answer, assistance=AssistanceLevel.NONE  # type: ignore[arg-type]
    )
    assert evaluation.outcome is TaskOutcome.NOT_YET
    assert evaluation.correction is not None
    return evaluation.correction


# -- #967: «une café» rebuilt as «café un» ---------------------------------------------

#: What a note may never say about the learner's own first word.
_DOES_NOT_START = {
    "en": "does not start with “{word}”",
    "de": "beginnt nicht mit „{word}“",
    "fr": "ne commence pas par « {word} »",
}
_MASCULINE = {"en": "masculine", "de": "maskulin", "fr": "masculin"}
_ARTICLE = {"en": "article", "de": "Artikel", "fr": "article"}


def _une_cafe(language: str) -> RecallTask:
    """The walk's item, as the planner builds it from the erratum «une café» → «un café»."""

    target = TargetRef(kind=TargetKind.ERROR, id="err-cafe", label_fr="un café", label_native="why")
    with pytest.MonkeyPatch.context() as mp:
        # #1098 types a two-word fix in its sentence; this note is about a tile build,
        # so the item is built the way the walk's build was.
        mp.setattr(planner, "_SHORT_SLIP_WORDS", 2)
        task = planner.build_recall_task(
            target=target,
            scenario=_brief(control_language=language),
            affordances=[],
            optional=False,
            learner_text="une café",
        )
    assert task is not None and task.task_type == "tiles", "the repair is still a build"
    assert {tile["text_fr"] for tile in task.options} == {"café", "un"}
    return task


@pytest.mark.parametrize("language", LANGUAGES)
def test_cafe_un(language: str) -> None:
    task = _une_cafe(language)
    by_text = {tile["text_fr"]: tile["id"] for tile in task.options}
    answer = AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=[by_text["café"], by_text["un"]])

    note = _miss(task, answer, language).note_native or ""

    assert _DOES_NOT_START[language].format(word="café") not in note, (
        f"the note contradicts the learner's own line «café un»: {note!r}"
    )
    assert _ARTICLE[language] in note, f"the order (article first) is not named: {note!r}"
    assert re.search(r"\bun\b", note) and _MASCULINE[language] in note, (
        f"the slip the item repairs (café is masculine: un, not une) is not named: {note!r}"
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_order_note_never_contradicts_the_line(language: str) -> None:
    """A build whose first word is wrong names that word as out of place, in words that
    cannot be read as «your line does not start with it»."""

    task = RecallTask(
        task_type="tiles",
        instruction_native="?",
        prompt_fr=None,
        options=[{"id": "t1", "text_fr": "Je"}, {"id": "t2", "text_fr": "suis"}, {"id": "t3", "text_fr": "là"}],
        target=TargetRef(kind=TargetKind.GRAMMAR, id="etre", label_fr="être"),
        optional=False,
        correct_tile_order=["t1", "t2", "t3"],
        solution_fr="Je suis là",
    )
    note = journey_learning.tile_order_note(task, ["t2", "t1", "t3"], language) or ""
    assert note and "suis" in note
    assert _DOES_NOT_START[language].format(word="suis") not in note, note


# -- #1024: a word item's withheld miss ------------------------------------------------

#: Rule wording, and the promise of a second choice now, per language.
_RULE = {"en": r"\brule\b", "de": r"\bRegel\b", "fr": r"\brègle\b"}
_CHOOSE_AGAIN = {"en": r"choose once more|choose again", "de": r"wähle neu|wähle noch", "fr": r"choisis à nouveau|choisis encore"}


def _regarder() -> RecallTask:
    return RecallTask(
        task_type="listen_tap",
        instruction_native="What does it mean?",
        prompt_fr="regarder",
        options=[
            {"id": "o1", "text_fr": "to look, to watch"},
            {"id": "o2", "text_fr": "to buy"},
            {"id": "o3", "text_fr": "to hate"},
        ],
        target=TargetRef(kind=TargetKind.VOCABULARY, id="w-regarder", label_fr="regarder", label_native="to look, to watch"),
        optional=False,
        correct_option_id="o1",
        solution_fr="regarder",
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_word_miss(language: str) -> None:
    task = _regarder()
    assert journey_learning.solution_waits_for_retry(task), "three cards: the answer waits for the retry"
    correction = _miss(task, AttemptAnswer(mode=InputMode.TEXT, text="", option_id="o3"), language)

    note = journey_learning.withheld_recall_note(task, correction, language=language)

    assert note, "a withheld miss still says something"
    assert not re.search(_RULE[language], note, re.IGNORECASE), f"a word item has no rule: {note!r}"
    assert not re.search(_CHOOSE_AGAIN[language], note, re.IGNORECASE), (
        f"the choices are locked until the item comes back; the note promises a choice now: {note!r}"
    )
    assert "regarder" in note, f"the note does not name the word task: {note!r}"
    assert "to look" not in note, f"the withheld note gives the answer away: {note!r}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_rule_miss_promises_no_choice_now(language: str) -> None:
    """A grammar pick whose reason names the answer keeps its rule wording, but never
    promises a second choice the locked screen does not give."""

    task = RecallTask(
        task_type="choice",
        instruction_native="?",
        prompt_fr=None,
        options=[
            {"id": "o1", "text_fr": "C'est qui, vous ?"},
            {"id": "o2", "text_fr": "Il pleut."},
            {"id": "o3", "text_fr": "Prenez une chaise."},
        ],
        target=TargetRef(kind=TargetKind.GRAMMAR, id="cest-qui", label_fr="c'est qui"),
        optional=False,
        correct_option_id="o1",
        solution_fr="C'est qui, vous ?",
    )
    correction = _miss(task, AttemptAnswer(mode=InputMode.TEXT, text="", option_id="o2"), language)
    note = journey_learning.withheld_recall_note(task, correction, language=language)
    assert note
    assert not re.search(_CHOOSE_AGAIN[language], note, re.IGNORECASE), note


def test_node_pin_matches_the_server() -> None:
    """The sheet's node test (drill-solution-gate.test.js) renders the server's own lines."""

    from pathlib import Path

    pinned = (
        Path(__file__).resolve().parents[1] / "web-frontend/components/atelier-v2/journey/drill-solution-gate.test.js"
    ).read_text(encoding="utf-8")
    task = _regarder()
    for language in LANGUAGES:
        correction = _miss(task, AttemptAnswer(mode=InputMode.TEXT, text="", option_id="o3"), language)
        note = journey_learning.withheld_recall_note(task, correction, language=language)
        assert f"'{note}'" in pinned, f"{language}: the node test pins another line than the server's {note!r}"
