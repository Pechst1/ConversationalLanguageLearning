"""Item quality (night shift 2026-10-23): what an item says must be what it is.

#300 a «Find the mistake» item with two wrong words says «the one mistake»; its
     miss feedback says «you wrote» for a word the app wrote.
#301 a scene gap-fill offers a grammar rule's title as a word option.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import Any

from app.services.item_bank import default_bank, transform_item
from app.services.journey_contracts import TargetKind, TargetRef
from app.services.scene_items import floor_tasks

# -- #300 ----------------------------------------------------------------------------

SOURCE = "L'été dernier, nous sommes cherchés Gus."
ANSWER = "L'été dernier, nous avons cherché Gus."


def _item(source: str, answer: str, trap: str):
    """A real passé-composé bank item with the walk's sentence swapped in."""

    base = default_bank().generate("FR2_A21_PC_AVOIR", 1, seed=3)[0]
    return dataclasses.replace(base, sentence=answer, wrong_sentences=(source,), traps=(trap,))


def _cue(payload: dict[str, Any], field: str = "instruction") -> str:
    table = payload.get(f"{field}_l10n") or {}
    return str(table.get("en") or payload.get(field) or "")


def test_a_two_word_slip_does_not_promise_the_one_mistake() -> None:
    """The card names how many words to fix when it is more than one."""

    payload = transform_item(_item(SOURCE, ANSWER, "sommes cherchés"))
    assert payload is not None
    shown = _cue(payload)
    assert "one mistake" not in shown, f"two words are wrong, the card says: {shown!r}"
    assert "2" in shown, f"the card does not say how many words to fix: {shown!r}"
    assert payload.get("fix_words") == 2


def test_a_one_word_slip_keeps_the_one_mistake_card() -> None:
    payload = transform_item(_item("L'été dernier, nous avons cherchons Gus.", ANSWER, "cherchons"))
    assert payload is not None
    assert "one mistake" in _cue(payload)
    assert payload.get("fix_words") in (None, 1)


def test_the_corrected_whole_line_counts_as_right() -> None:
    """Fixing both words in one check is right (the spot answer is the whole line)."""

    from tests.test_qa_close_2026_10_03 import _transform

    assert _transform(ANSWER, ANSWER, SOURCE)["verdict"] == "correct"


def test_a_saved_two_word_slip_carries_its_word_count_too() -> None:
    from app.services.forge import mine_payload_item

    item = mine_payload_item(item_id="m1", error_id="e1", source=SOURCE, expected=ANSWER, lesson_external_id=None)
    assert item["fix_words"] == 2
    one = mine_payload_item(
        item_id="m2", error_id="e2", source="Nous avons cherchons Gus.", expected="Nous avons cherché Gus.",
        lesson_external_id=None,
    )
    assert "fix_words" not in one


def _miss(learner: str) -> str:
    from app.services.atelier import AtelierCorrectionService

    item = {"id": "t1", "type": "rewrite", "source": SOURCE, "source_fr": SOURCE, "expected_answer": ANSWER,
            "instruction": "x"}
    correction = AtelierCorrectionService(None)._correct_transform_rule_based(
        None, {"items": [item]}, {"answers": {"t1": learner}}
    )
    assert correction["verdict"] == "incorrect"
    return str(correction["errata"][0]["why_wrong"])


def test_a_miss_never_says_you_wrote_for_a_word_the_app_wrote() -> None:
    """The learner fixed «sommes» and left «cherchés» as it was shown."""

    why = _miss("L'été dernier, nous avons cherchés Gus.")
    assert "cherchés" in why  # it still names the word to fix
    assert "you wrote «cherchés»" not in why.lower(), why


def test_a_miss_still_says_you_wrote_for_a_word_the_learner_typed() -> None:
    why = _miss("L'été dernier, nous avons cherchons Gus.")
    assert "you wrote «cherchons»" in why.lower(), why
    assert "cherchés" not in why or "you wrote «cherchés»" not in why.lower()


# -- #301 ----------------------------------------------------------------------------

RULE_TITLE = "passé composé avec avoir : formes régulières et irrégulières"
DRAFT = {
    "premise_fr": "Marin regarde la lettre.",
    "character_id": "marin_leveque",
    "opening_line_fr": "Leur offre est dans votre lettre.",
    "panels": [
        {
            "narration_fr": "",
            "dialogue": [{"character_id": "lila_bonnet", "text_fr": "Je veux vendre le magasin demain."}],
            "visual_direction": "x",
        }
    ],
    "lexicon": [
        {"surface_fr": "offre", "lemma": "offre", "gloss_native": "offer", "part_of_speech": "noun",
         "gender": "f", "line_ref": "opening"},
        {"surface_fr": "lettre", "lemma": "lettre", "gloss_native": "letter", "part_of_speech": "noun",
         "gender": "f", "line_ref": "premise"},
        {"surface_fr": "vendre", "lemma": "vendre", "gloss_native": "to sell", "part_of_speech": "verb",
         "line_ref": "panel:0:line:0"},
        {"surface_fr": "magasin", "lemma": "magasin", "gloss_native": "shop", "part_of_speech": "noun",
         "gender": "m", "line_ref": "panel:0:line:0"},
    ],
}
CAST = [{"id": "marin_leveque", "name": "Marin Lévêque"}, {"id": "lila_bonnet", "name": "Lila"}]


def _scenario() -> Any:
    return SimpleNamespace(
        control_language="en",
        level_band="A2",
        character_id="marin_leveque",
        character_name="Marin",
        opening_line_fr="Leur offre est dans votre lettre.",
        story_context={"draft": DRAFT, "source": {"world": {"cast": CAST}}},
    )


def _vocab(label_fr: str, label_native: str, identifier: str) -> TargetRef:
    return TargetRef(kind=TargetKind.VOCABULARY, id=identifier, label_fr=label_fr, label_native=label_native)


def _rule() -> TargetRef:
    return TargetRef(
        kind=TargetKind.GRAMMAR, id="g1", label_fr=RULE_TITLE, label_native="Perfect with avoir", concept_title=True
    )


def test_a_cloze_never_offers_a_rule_title_when_the_scene_has_few_words() -> None:
    """Two words in the scene: the rule's label used to fill the third option."""

    scenario = _scenario()
    scenario.story_context["draft"] = {**DRAFT, "lexicon": DRAFT["lexicon"][:2]}
    targets = [
        (_vocab("une offre", "offer", "w1"), {"surface_fr": "offre"}),
        (_vocab("la lettre", "letter", "w2"), {"surface_fr": "lettre"}),
        (_rule(), {}),
    ]
    tasks = [task for _t, task in floor_tasks(scenario, targets) if task.task_type == "choice"]
    assert tasks, "the scene has a cloze to build"
    for task in tasks:
        options = [card["text_fr"] for card in task.options]
        assert RULE_TITLE not in options, options


def test_a_cloze_offers_words_of_the_blanks_kind() -> None:
    rule = _rule()
    targets = [
        (_vocab("une offre", "offer", "w1"), {"surface_fr": "offre"}),
        (_vocab("la lettre", "letter", "w2"), {"surface_fr": "lettre"}),
        (_vocab("vendre", "to sell", "w3"), {"surface_fr": "vendre"}),
        (rule, {}),
    ]
    tasks = [task for _t, task in floor_tasks(_scenario(), targets) if task.task_type == "choice"]
    assert tasks, "the scene has a cloze to build"
    for task in tasks:
        options = [card["text_fr"] for card in task.options]
        assert RULE_TITLE not in options, options
        assert all(":" not in option for option in options), options
    offre = next(task for task in tasks if "Leur" in task.prompt_fr)
    options = {card["text_fr"] for card in offre.options}
    assert "vendre" not in options, f"a verb among the nouns: {options}"
