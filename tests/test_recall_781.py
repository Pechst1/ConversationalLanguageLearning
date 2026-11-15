"""#174 / #781, #804, #805: a recall drill judges against every right answer, not one stored string.

* #781 (walk 14 Nov, `a1-de-fresh`, day 2, «Avoir»): the tiles of «J'ai vingt-cinq ans et
  j'ai faim !» hold `j'ai` and `J'ai`. Built with the lowercase one first, the right words
  in the right order were «Noch nicht» (the grader compared the one stored id order), and
  the miss came with no reason and no right sentence (the correction folded to a no-op).
  Attempt 1 (#787) listed right orders up to a cap of 24: a sentence with four «le» and two
  «,» has 48 orders, so swapping two «le» was a miss with an empty explanation again.
* #804 (live walk 15 Nov): «What does it mean?» for «une» offered «you», «a, an (f.); one»
  and «one». «one» is a meaning of «une»: the distractor was checked against the key's
  whole gloss, never against each of its meanings.
* #805 (live walk 15 Nov): «Write this correctly» over «le bureau de poste», answer «la
  poste». The learner's line already was a right way to say it (the accept-list's other
  word for «la poste»): the repair was posed because the line differed from the one stored
  key.
"""

from __future__ import annotations

from itertools import permutations
from types import SimpleNamespace

from app.services import grammar_items
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
from app.services.journey_learning import evaluate_recall
from app.services.repair_context import RepairContext
from app.services.rule_cards import rule_card_for
from tests.test_journey_planner import _brief

SENTENCE = "J'ai vingt-cinq ans et j'ai faim !"
ENGLISH = SimpleNamespace(native_language="en", cefr_estimate="A1.1", proficiency_level="A1")


# -- #781: tiles ---------------------------------------------------------------


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


def _build(db_session, task, tile_ids, user=None):
    return evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=list(tile_ids)),
        assistance=AssistanceLevel.NONE,
    )


def _one_tile_per_word(sentence: str) -> RecallTask:
    """Reviewer's input on #787: one tile per word and punctuation mark."""

    words = sentence.replace(",", " ,").replace(".", " .").split()
    tiles = [{"id": f"t{index}", "text_fr": word} for index, word in enumerate(words)]
    return RecallTask(
        task_type="tiles",
        instruction_native="Build the sentence.",
        prompt_fr=None,
        options=list(reversed(tiles)),
        target=TargetRef(kind=TargetKind.VOCABULARY, id="v-cheval", label_fr=sentence, label_native="I see …"),
        optional=False,
        correct_tile_order=[tile["id"] for tile in tiles],
        accepted_answers=[sentence],
        solution_fr=sentence,
        estimated_seconds=0,
    )


def test_case_swap_is_right(db_session) -> None:
    task, texts = _avoir_tiles()
    swapped = _case_swapped(task, texts)
    assert " ".join(texts[tile] for tile in swapped) == "j'ai vingt-cinq ans et J'ai faim !"

    verdict = _build(db_session, task, swapped)

    assert verdict.outcome is TaskOutcome.MET, (
        "the right words in the right order, only the capital on the other «j'ai», "
        f"were judged {verdict.outcome.value} with correction {verdict.correction!r}"
    )
    assert verdict.correction is None
    assert verdict.slip_note_native and SENTENCE in verdict.slip_note_native, (
        f"the hit names the capital and shows the sentence: {verdict.slip_note_native!r}"
    )
    assert any(word in verdict.slip_note_native for word in ("capital", "Großbuchstaben", "majuscule"))


def test_twin_tiles_swap(db_session) -> None:
    """Attempt 1's cap: four «le» and two «,» are 48 orders; any of them is the sentence."""

    task = _one_tile_per_word("Je vois le chat, le chien, le lapin et le cheval.")
    order = list(task.correct_tile_order)
    texts = {option["id"]: option["text_fr"] for option in task.options}
    assert texts[order[2]] == texts[order[11]] == "le"
    order[2], order[11] = order[11], order[2]

    verdict = _build(db_session, task, order)

    assert verdict.outcome is TaskOutcome.MET, (
        f"swapping two «le» tiles was {verdict.outcome.value}, correction {verdict.correction!r}"
    )


def test_key_matches_grader(db_session) -> None:
    """The client colours a build from the hashed key: it must never flash red on a
    build the server then calls right, nor green on a miss."""

    from app.services.daily_journey import _recall_task_to_json
    from app.services.journey_answer_key import answer_key_for, answer_matches_key

    task, texts = _avoir_tiles()
    key = answer_key_for("step-781", _recall_task_to_json(task), secret=b"test")
    assert answer_matches_key(key, "tiles", tile_ids=task.correct_tile_order) is True
    assert answer_matches_key(key, "tiles", tile_ids=_case_swapped(task, texts)) is True, (
        "the key holds only the one stored id order"
    )
    for order in permutations(task.correct_tile_order):
        graded = _build(db_session, task, order).outcome is TaskOutcome.MET
        assert answer_matches_key(key, "tiles", tile_ids=list(order)) is graded, [texts[tile] for tile in order]

    many = _one_tile_per_word("Je vois le chat, le chien, le lapin et le cheval.")
    key = answer_key_for("step-781b", _recall_task_to_json(many), secret=b"test")
    if key is not None:
        swapped = list(many.correct_tile_order)
        swapped[2], swapped[11] = swapped[11], swapped[2]
        assert answer_matches_key(key, "tiles", tile_ids=swapped) is True, (
            "a key that is served must hold every order the grader takes"
        )


def test_miss_shows_answer(db_session) -> None:
    """A «not yet» on a tile build is never served with an empty explanation."""

    task, texts = _avoir_tiles()
    for order in permutations(task.correct_tile_order):
        verdict = _build(db_session, task, order)
        if verdict.outcome is TaskOutcome.MET:
            continue
        placed = " ".join(texts[tile] for tile in order)
        assert verdict.correction is not None, f"«{placed}» was «not yet» with no correction"
        assert verdict.correction.corrected_fr == SENTENCE


# -- #804: meaning distractors ---------------------------------------------------


def _vocab(label_fr: str, gloss: str, ident: str | None = None) -> TargetRef:
    return TargetRef(kind=TargetKind.VOCABULARY, id=ident or f"v:{label_fr}", label_fr=label_fr, label_native=gloss)


UNE = _vocab("une", "a, an (f.); one")
#: Today's other words in the walk: «tu» (you) and a word whose gloss is one of «une»'s meanings.
POOL = [_vocab("tu", "you"), _vocab("on", "one"), _vocab("un", "a, an (m.); one"), _vocab("chat", "cat"),
        _vocab("maison", "house")]


def _senses(gloss: str) -> set[str]:
    import re

    text = re.sub(r"\([^)]*\)", " ", gloss)
    return {" ".join(part.split()).casefold() for part in re.split(r"[;,/]", text) if part.strip()}


def test_no_key_meaning_decoy(db_session) -> None:
    # The partners are drawn in an order seeded by the target's id: try a spread of ids.
    for band in (None, "B1", "A1"):
        for seed in range(12):
            une = _vocab("une", UNE.label_native, ident=f"vocab:une:{seed}")
            task = planner.build_listen_tap_task(
                target=une, pool=POOL, optional=False, control_language="en", band=band
            )
            assert task is not None
            key = _senses(une.label_native)
            for option in task.options:
                if option["id"] == task.correct_option_id:
                    continue
                shown = option["text_fr"]
                assert not (_senses(shown) & key) and shown.casefold() not in une.label_native.casefold(), (
                    f"band {band}: distractor «{shown}» is a meaning of «une» («{une.label_native}»)"
                )
        # Picking the key's meaning is right; no other card says what «une» means.
        right = _build_pick(db_session, task, task.correct_option_id)
        assert right.outcome is TaskOutcome.MET


def test_pairs_one_meaning() -> None:
    task = planner.build_match_pairs_task(target=UNE, pool=POOL, optional=False, control_language="en")
    if task is None:
        return
    natives = [option["text_fr"] for option in task.options if option.get("side") == "native"]
    key = _senses(UNE.label_native)
    others = [text for text in natives if _senses(text) != key]
    assert not any(_senses(text) & key for text in others), natives


def _build_pick(db_session, task, option_id):
    return evaluate_recall(
        db_session,
        user=ENGLISH,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", option_id=option_id),
        assistance=AssistanceLevel.NONE,
    )


# -- #805: «Write this correctly» over a line that is already right ---------------


def test_no_repair_of_right() -> None:
    target = TargetRef(kind=TargetKind.ERROR, id="err-poste", label_fr="la poste", label_native="the post office")
    task = planner.build_recall_task(
        target=target,
        scenario=_brief(control_language="en", level_band="A1"),
        affordances=[],
        optional=False,
        learner_text="le bureau de poste",
        repair=RepairContext(rule="Le, la, l', les: the"),
    )
    if task is None:
        return
    from app.services.answer_acceptance import fold_typography, widened_answers

    shown = task.prompt_fr or ""
    right = {fold_typography(text) for text in widened_answers([target.label_fr])}
    assert fold_typography(shown) not in right, (
        f"«{task.instruction_native}» over «{shown}», which is already a right way to say «{target.label_fr}»"
    )
    texts = {option["id"]: option["text_fr"] for option in task.options}
    assert " ".join(texts[tile] for tile in task.correct_tile_order) == target.label_fr


def test_real_repair_posed() -> None:
    target = TargetRef(kind=TargetKind.ERROR, id="err-ai", label_fr="j'ai faim", label_native="avoir faim")
    task = planner.build_recall_task(
        target=target,
        scenario=_brief(control_language="en", level_band="A1"),
        affordances=[],
        optional=False,
        learner_text="je suis faim",
    )
    assert task is not None and task.prompt_fr == "je suis faim"
    assert task.instruction_native == "Write this correctly in French."
