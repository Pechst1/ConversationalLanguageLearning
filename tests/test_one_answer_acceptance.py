"""#174 / #781: a tile build is right when it spells a right sentence, not one stored id order.

Walk 14 Nov 2026 (`a1-de-fresh`, day 2, «Avoir»): the tiles of «J'ai vingt-cinq ans et
j'ai faim !» hold `j'ai` and `J'ai`. The learner placed the lowercase one first and built
the right words in the right order, «j'ai vingt-cinq ans et J'ai faim !». The grader
compared the id sequence with the one stored order, so it was «Noch nicht». The
correction is dropped as a no-op (the two sentences fold equal), so the miss came with
no reason and no right sentence. The same day a typed gap took «tu as» in lowercase:
case counted in one drill and not in the next.

The order a tile build is graded against, on the server and in the device's hashed
key, is now every order of the item's tiles that spells one of its right sentences,
with case and apostrophes folded (`journey_answer_key.accepted_tile_orders`).
"""
from __future__ import annotations

from itertools import permutations

from app.services import grammar_items
from app.services.journey_contracts import AssistanceLevel, AttemptAnswer, InputMode, TaskOutcome
from app.services.journey_learning import evaluate_recall
from app.services.rule_cards import rule_card_for

SENTENCE = "J'ai vingt-cinq ans et j'ai faim !"


def _avoir_tiles():
    """The walk's item, built by the real grammar builder from the «Avoir» card."""

    brief = {
        "concept_id": 7,
        "external_id": "FR2_A11_AVOIR",
        "title_fr": "Avoir",
        "title_native": "Avoir",
        "detectors": [r"\bai\b"],
        "examples": [SENTENCE],
        "contrast_pairs": [],
        "pattern_forms": [],
        "rule_short_native": "Avoir: age, hunger.",
        "stability": 5.0,
        "rule_card": rule_card_for("FR2_A11_AVOIR"),
    }
    task = grammar_items.build_item(brief, sentences=[], language="de")
    assert task is not None and task.task_type == "tiles" and task.solution_fr == SENTENCE
    texts = {option["id"]: option["text_fr"] for option in task.options}
    assert {"j'ai", "J'ai"} <= set(texts.values()), "the walk's two tiles that differ only by case"
    return task, texts


def _case_swapped(task, texts) -> list[str]:
    order = list(task.correct_tile_order)
    first = order.index(next(tile for tile in order if texts[tile] == "J'ai"))
    second = order.index(next(tile for tile in order if texts[tile] == "j'ai"))
    order[first], order[second] = order[second], order[first]
    return order


def _grade(db_session, task, tile_ids):
    return evaluate_recall(
        db_session,
        user=None,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=list(tile_ids)),
        assistance=AssistanceLevel.NONE,
    )


def test_a_case_only_tile_swap_is_right_and_names_the_capital(db_session) -> None:
    task, texts = _avoir_tiles()
    swapped = _case_swapped(task, texts)
    assert " ".join(texts[tile] for tile in swapped) == "j'ai vingt-cinq ans et J'ai faim !"

    verdict = _grade(db_session, task, swapped)

    assert verdict.outcome is TaskOutcome.MET, (
        "the right words in the right order, only the capital on the other «j'ai», "
        f"were judged {verdict.outcome.value}"
    )
    assert verdict.correction is None
    assert verdict.slip_note_native and SENTENCE in verdict.slip_note_native, (
        f"the hit names the capital and shows the sentence: {verdict.slip_note_native!r}"
    )
    assert any(word in verdict.slip_note_native for word in ("capital", "Großbuchstaben", "majuscule"))


def test_the_device_key_takes_the_orders_the_grader_takes(db_session) -> None:
    """The client colours a build from the hashed key: it must not flash red on a build
    the server then calls right."""

    from app.services.daily_journey import _recall_task_to_json
    from app.services.journey_answer_key import answer_key_for, answer_matches_key

    task, texts = _avoir_tiles()
    key = answer_key_for("step-781", _recall_task_to_json(task), secret=b"test")
    assert answer_matches_key(key, "tiles", tile_ids=task.correct_tile_order) is True
    assert answer_matches_key(key, "tiles", tile_ids=_case_swapped(task, texts)) is True, (
        "the key holds only the one stored id order"
    )
    for order in permutations(task.correct_tile_order):
        graded = _grade(db_session, task, order).outcome is TaskOutcome.MET
        assert answer_matches_key(key, "tiles", tile_ids=list(order)) is graded, [texts[tile] for tile in order]


def test_a_tiles_miss_always_shows_the_right_sentence(db_session) -> None:
    """A «not yet» on a tile build is never served with an empty explanation."""

    task, texts = _avoir_tiles()
    for order in permutations(task.correct_tile_order):
        verdict = _grade(db_session, task, order)
        if verdict.outcome is TaskOutcome.MET:
            continue
        placed = " ".join(texts[tile] for tile in order)
        assert verdict.correction is not None, f"«{placed}» was «not yet» with no correction"
        assert verdict.correction.corrected_fr == SENTENCE
