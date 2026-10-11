"""The owner's test of 2026-09-30: what it found, pinned."""

from __future__ import annotations

from app.services import journey_planner as planner
from app.services.season.turns import reaction_lines
from tests.test_journey_planner import _brief, _candidate


def test_a_word_with_its_article_is_typed_not_built_from_two_tiles():
    target = _candidate(label_fr="la clé", label_native="key").target
    task = planner.build_recall_task(target=target, scenario=_brief(), affordances=[], optional=False)
    assert task is not None and task.task_type == "short_answer", "«la» + «clé» in two tiles is not an exercise"
    phrase = _candidate(identifier="v-p", label_fr="je voudrais un café", label_native="I would like a coffee").target
    assert planner.build_recall_task(target=phrase, scenario=_brief(), affordances=[], optional=False).task_type == "tiles"
    assert planner.build_word_bank_task(target=target, affordances=["le pain"], optional=False, control_language="en") is None


def test_every_speaker_of_a_reaction_is_named_with_their_line():
    panels = [
        {"lines": [
            {"who": "augustin_de_roncourt", "name": "Augustin « Gus » de Roncourt", "kind": "speech", "text_fr": "Ah."},
            {"who": "margaux_barman", "name": "Margaux", "kind": "speech", "text_fr": "Elle prenait ça."},
            {"who": "caption", "kind": "caption", "text_fr": "Un silence."},
        ]},
    ]
    lines = reaction_lines(panels, addressee="augustin_de_roncourt")
    assert [(row["speaker_id"], row["text_fr"]) for row in lines] == [
        ("augustin_de_roncourt", "Ah."),
        ("margaux_barman", "Elle prenait ça."),
    ], "a caption stays on the page; each speaker is their own line"
