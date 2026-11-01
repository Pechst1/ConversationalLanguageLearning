"""#155 — a recall item cut from a line of the scene is that line's speaker's.

Walk of 21 Oct (b1, day 1): «Complète la phrase de la scène» over Marin's line
«…Vous allez vraiment … l'appartement d'Odile ?» drew Gus beside it and cheered
«Gus te sourit». The item had no speaker of its own, so the device took the day's
character. Now the planner looks the item's French up among today's lines and
sends who says it (``RecallPrompt.speaker``); the device draws that face and names
that person (``journey-faces.drillSpeaker``). The day-1 walk of every persona
checks it on real days (``tests/walk_checks_155.py``).
"""
from __future__ import annotations

from dataclasses import replace

from app.schemas.daily_journey import RecallPrompt
from app.services import journey_planner as planner
from app.services.daily_journey import _recall_task_from_json, _recall_task_to_json
from app.services.journey_contracts import RecallTask, TargetKind, TargetRef
from tests.test_journey_planner import _brief

MARIN_LINE = "…Vous allez vraiment visiter l'appartement d'Odile ? À Solvel ?"
GUS_LINE = "Alors ? Vous êtes qui, exactement ?"

PANELS = [
    {
        "narration_fr": "Le Mistral, un mardi. Il pleut sur le canal.",
        "dialogue": [
            {"character_id": "augustin_de_roncourt", "text_fr": "Ah ! Vous voilà."},
            {"character_id": "marin_leveque", "text_fr": MARIN_LINE},
            {"character_id": "lila_bonnet", "text_fr": "Regarde ses chaussures, Marin."},
            {"character_id": "augustin_de_roncourt", "text_fr": GUS_LINE},
        ],
    }
]


def _scenario():
    # The day belongs to Gus: he is the scenario's character.
    return _brief(
        character_id="augustin_de_roncourt",
        character_name="Augustin « Gus » de Roncourt",
        panels=PANELS,
        opening_line_fr=GUS_LINE,
    )


def _task(task_type: str = "short_answer", **fields) -> RecallTask:
    base = {
        "task_type": task_type,
        "instruction_native": "Complete the line from the scene.",
        "prompt_fr": None,
        "options": [],
        "target": TargetRef(kind=TargetKind.VOCABULARY, id="v1", label_fr="visiter", label_native="to visit"),
        "optional": True,
    }
    base.update(fields)
    return RecallTask(**base)


def test_the_written_cloze_of_the_walk_is_marins_not_the_days_character():
    gap = "…Vous allez vraiment … l'appartement d'Odile ?"
    task = _task(prompt_fr=gap, source_fr=gap, accepted_answers=["visiter"], solution_fr="visiter")
    assert planner.recall_speaker(task, _scenario()) == "marin_leveque"


def test_each_scene_format_names_the_line_it_is_cut_from():
    scenario = _scenario()
    chosen_cloze = _task(
        "choice", prompt_fr="Vous allez vraiment ___ l'appartement d'Odile ?",
        solution_fr="Vous allez vraiment visiter l'appartement d'Odile ?",
        options=[{"id": "a", "text_fr": "visiter"}, {"id": "b", "text_fr": "vendre"}], correct_option_id="a",
    )
    rebuilt = _task(
        "unscramble", solution_fr="Alors ? Vous êtes qui, exactement ?",
        accepted_answers=["Alors ? Vous êtes qui, exactement ?"],
    )
    one_sentence = _task("unscramble", solution_fr="Vous êtes qui, exactement ?")
    dictated = _task("dictation", solution_fr="Regarde ses chaussures, Marin.", accepted_answers=["Regarde ses chaussures, Marin."])
    assert planner.recall_speaker(chosen_cloze, scenario) == "marin_leveque"
    assert planner.recall_speaker(rebuilt, scenario) == "augustin_de_roncourt"
    assert planner.recall_speaker(one_sentence, scenario) == "augustin_de_roncourt", "one sentence of a longer line"
    assert planner.recall_speaker(dictated, scenario) == "lila_bonnet"


def test_items_not_cut_from_a_characters_line_name_nobody():
    scenario = _scenario()
    narration = _task("dictation", solution_fr="Le Mistral, un mardi.")
    word = _task(prompt_fr=None, solution_fr="visiter", accepted_answers=["visiter"])
    elsewhere = _task("transform", prompt_fr="Hier, j'ai mangé une pizza.", solution_fr="Hier, nous avons mangé une pizza.")
    for task in (narration, word, elsewhere):
        assert planner.recall_speaker(task, scenario) is None, task


def test_who_said_and_sentence_picks_never_show_the_answers_face():
    scenario = _scenario()
    who_said = _task("who_said", prompt_fr=GUS_LINE, accepted_answers=["Gus"])
    assert planner.recall_speaker(who_said, scenario) is None, "the face would be the answer"
    pick = _task(
        "choice", solution_fr="Vous êtes qui, exactement ?", options_kind="sentences",
        options=[{"id": "a", "text_fr": "Vous êtes qui, exactement ?"}, {"id": "b", "text_fr": "Regarde ses chaussures, Marin."}],
    )
    assert planner.recall_speaker(pick, scenario) is None, "the right card's speaker would give it away"


def test_a_speaker_the_builder_knew_is_kept():
    task = _task("listen_tap", prompt_fr="visiter", speaker_id="marin_leveque")
    assert planner.recall_speaker(task, _scenario()) == "marin_leveque"


def test_the_prompt_names_the_cast_short_name_and_survives_storage():
    scenario = _scenario()
    task = _task("unscramble", solution_fr=GUS_LINE)
    assert planner.recall_speaker_prompt(task, scenario) == {
        "speaker": {"id": "augustin_de_roncourt", "name": "Gus"}
    }
    assert planner.recall_speaker_prompt(_task(solution_fr="visiter"), scenario) == {}
    stored = replace(task, speaker_id="augustin_de_roncourt")
    assert _recall_task_from_json(_recall_task_to_json(stored)).speaker_id == "augustin_de_roncourt"
    legacy = _recall_task_to_json(task)
    assert "speaker_id" not in legacy, "a task without a speaker is stored exactly as before"
    assert _recall_task_from_json(legacy).speaker_id is None


def test_the_wire_carries_the_speaker_only_when_there_is_one():
    base = {
        "task_type": "unscramble", "instruction_native": "Rebuild.", "prompt_fr": None, "options": [],
        "target": {"kind": "vocabulary", "id": "v1", "label_fr": ""}, "optional": True, "goal_native": "Rebuild.",
        "source_fr": None,
    }
    named = RecallPrompt.model_validate({**base, "speaker": {"id": "marin_leveque", "name": "Marin"}}).model_dump()
    assert named["speaker"] == {"id": "marin_leveque", "name": "Marin"}
    assert "speaker" not in RecallPrompt.model_validate(base).model_dump()


def test_a_planned_step_carries_its_lines_speaker():
    scenario = _scenario()
    entry = planner.SelectedTarget(
        candidate=planner.LearningCandidate(
            target=TargetRef(kind=TargetKind.VOCABULARY, id="v1", label_fr="visiter", label_native="to visit"),
            priority_score=1.0, due_since_days=0, estimated_seconds=30, is_new=True,
            source_item_type="vocabulary", metadata={},
        ),
        fit=1.0,
        demonstrated=False,
    )
    item = planner.PracticeItem(slot="post", position=0, entry=entry, task=_task("unscramble", solution_fr=GUS_LINE), cost=20)
    step = planner._recall_step(3, item, scenario)
    assert step.public_prompt["speaker"] == {"id": "augustin_de_roncourt", "name": "Gus"}
    assert step.private_task.speaker_id == "augustin_de_roncourt"
    word = planner._recall_step(4, replace(item, task=_task(solution_fr="visiter")), scenario)
    assert "speaker" not in word.public_prompt
