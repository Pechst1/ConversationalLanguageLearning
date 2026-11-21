"""#967: a missed build of «article + noun» is told why, and never the opposite of what it did.

Live walk 21 Nov (A1.1, day 39): the pre-scene repair «une café» («Write this correctly in
French», tiles «café», «un»), built «café un», was answered «It does not start with
“café”.»: the learner's line does start with it, and neither the order nor the gender
slip was explained. The note was read from where the two orders first differ (#146: not
from the item's own concept). It now names the article first and why «un» (masculine).
"""

from __future__ import annotations

import re
from itertools import permutations
from types import SimpleNamespace

import pytest

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
from app.services.journey_learning import evaluate_recall, tile_order_note
from tests.test_journey_planner import _brief

LEARNERS = {
    language: SimpleNamespace(native_language=language, cefr_estimate="A1.1", proficiency_level="A1")
    for language in ("en", "de", "fr")
}


def _repair(label_fr: str, learner_text: str, language: str = "en") -> RecallTask:
    target = TargetRef(kind=TargetKind.ERROR, id=f"err-{label_fr}", label_fr=label_fr, label_native="gender")
    task = planner.build_recall_task(
        target=target,
        scenario=_brief(control_language=language, level_band="A1"),
        affordances=[],
        optional=False,
        learner_text=learner_text,
    )
    assert task is not None and task.task_type == "tiles", task
    return task


def _ids(task: RecallTask, *texts: str) -> list[str]:
    by_text = {option["text_fr"]: option["id"] for option in task.options}
    return [by_text[text] for text in texts]


def _miss_note(task: RecallTask, tile_ids: list[str], language: str) -> str:
    evaluation = evaluate_recall(
        None,
        user=LEARNERS[language],
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=tile_ids),
        assistance=AssistanceLevel.NONE,
    )
    assert evaluation.outcome is TaskOutcome.NOT_YET
    assert evaluation.correction is not None
    return evaluation.correction.note_native


EXPECTED = {
    "en": "The article comes before its noun: “un”, then “café”. “café” is masculine, so “un”, not “une”.",
    "de": "Der Artikel steht vor seinem Nomen: erst „un“, dann „café“. „café“ ist maskulin, also „un“, nicht „une“.",
    "fr": "L'article vient avant son nom : d'abord « un », puis « café ». « café » est masculin, donc « un », pas « une ».",
}


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_cafe_un_is_told_the_order_and_the_gender(language):
    """#967 done-when: «café un» for «une café» never hears «It does not start with
    “café”»; it hears the article first and «un» (masculine)."""
    task = _repair("un café", "une café", language)
    note = _miss_note(task, _ids(task, "café", "un"), language)
    assert "does not start with" not in note and "beginnt nicht mit" not in note and "ne commence pas" not in note
    assert note == EXPECTED[language], note


def test_a_feminine_slip_names_its_own_gender():
    task = _repair("une tarte", "un tarte")
    assert _miss_note(task, _ids(task, "tarte", "une"), "en") == (
        "The article comes before its noun: “une”, then “tarte”. “tarte” is feminine, so “une”, not “un”."
    )


def test_an_object_pronoun_is_no_article():
    """«le» before a verb is a pronoun: no «article before its noun» about it."""
    task = RecallTask(
        task_type="tiles",
        instruction_native="Build the sentence.",
        prompt_fr=None,
        options=[{"id": "t1", "text_fr": "Je"}, {"id": "t2", "text_fr": "le"}, {"id": "t3", "text_fr": "vois."}],
        target=TargetRef(kind=TargetKind.GRAMMAR, id="cod", label_fr="le, la"),
        optional=False,
        correct_tile_order=["t1", "t2", "t3"],
        solution_fr="Je le vois.",
    )
    note = _miss_note(task, ["t1", "t3", "t2"], "en")
    assert "article" not in note, note


# -- no miss sentence contradicts the learner's line ---------------------------------

_KEYS = [
    ("un café", "une café"),
    ("une tarte aux pommes", "un tarte aux pommes"),
    ("je voudrais un croissant", "je voudrais une croissant"),
]
_QUOTED = re.compile(r"[“„«]\s?([^”“»]+?)\s?[”“»]")


@pytest.mark.parametrize(("label", "learner"), _KEYS, ids=["cafe", "tarte", "croissant"])
@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_no_miss_note_contradicts_the_line(label, learner, language):
    """Every wrong order of every item: the note never says the line does not start with
    the word it starts with, a «From X on» names a word the learner placed where the key
    has another, and an order + article item names the article or its gender."""
    task = _repair(label, learner, language)
    key = list(task.correct_tile_order)
    texts = {option["id"]: option["text_fr"] for option in task.options}
    for order in permutations(key):
        order = list(order)
        if order == key:
            continue
        note = _miss_note(task, order, language)
        first = texts[order[0]]
        for old in (f"does not start with “{first}”", f"beginnt nicht mit „{first}“", f"ne commence pas par « {first} »"):
            assert old not in note, (order, note)
        plain = tile_order_note(task, order, language) or ""
        if plain.startswith(("From", "Ab", "À partir")):
            word = _QUOTED.search(plain).group(1)
            index = [texts[tile] for tile in order].index(word)
            assert order[index] != key[index], (order, plain)
        if [texts[tile] for tile in order].index(label.split()[-2 if "voudrais" in label else 0]) > 0:
            assert "un" in _QUOTED.findall(note) or "une" in _QUOTED.findall(note), (order, note)
