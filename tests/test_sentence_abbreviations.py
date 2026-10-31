"""#398: a sentence cut at «M.» reached a choice drill as a distractor («Sur le toit, la lampe de M.»).

Root cause: four places cut a scene into sentences with their own regex, and only one of
them knew that «M.» is a title. Every cut now goes through ``app.services.sentence_line``.
"""

from __future__ import annotations

import re

import pytest

from app.services import grammar_items, scene_items, season_lexicon
from app.services import journey_planner as planner

SCENE = "Sur le toit, la lampe de M. Marchand brille. Il ne dort pas. Mme Odile pleure."
WHOLE = "Sur le toit, la lampe de M. Marchand brille."
_ONE_LETTER_ABBREVIATION = re.compile(r"(?:^|\s)[A-ZÀ-ÖØ-Þ]\.[\s»\"”)]*$")


def test_the_scene_cut_keeps_a_title_inside_its_sentence() -> None:
    cut = planner.scene_sentences(SCENE)
    assert cut == [WHOLE, "Il ne dort pas.", "Mme Odile pleure."]


@pytest.mark.parametrize("title", ["M.", "MM.", "Mme.", "Mlle.", "Dr.", "Pr.", "St.", "Ste.", "J."])
def test_a_title_or_an_initial_does_not_end_a_sentence(title: str) -> None:
    from app.services.sentence_line import sentences

    expected = [f"Voici {title} Dupont.", "Il part."]
    assert sentences(f"Voici {title} Dupont. Il part.") == expected
    assert planner.scene_sentences(f"Voici {title} Dupont. Il part.") == expected


def test_a_real_sentence_end_still_ends_it() -> None:
    from app.services.sentence_line import ends_sentence

    for word in ("brille.", "brille!", "brille?", "brille…", "«brille.»", "dort."):
        assert ends_sentence(word), word
    assert not ends_sentence("brille,")


def test_the_scene_word_sentence_is_whole() -> None:
    entry = {"surface_fr": "lampe", "line_ref": "opening"}
    draft = {"opening_line_fr": SCENE}
    assert scene_items.sentence_of(draft, entry) == WHOLE
    assert season_lexicon._sentence_with(SCENE, "lampe") == WHOLE


def test_no_choice_option_of_a_recognition_drill_ends_in_an_abbreviation() -> None:
    brief = {"concept_id": 7, "title_fr": "La négation", "detectors": [r"\bne\b \w+ pas\b"], "level": "A1"}
    cut = planner.scene_sentences("Il ne dort pas.", WHOLE)
    task = grammar_items.recognise_item(brief, sentences=cut, language="en")
    assert task is not None and task.options
    for option in task.options:
        assert not _ONE_LETTER_ABBREVIATION.search(option["text_fr"]), option["text_fr"]
