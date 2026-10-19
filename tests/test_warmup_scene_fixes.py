"""Owner, 2026-10-19: the warm-up and the scene that stalled on «La scène se prépare…».

1. Margaux asked «Qu'est-ce que tu me racontes ?» and the reply to type was a
   question back («Tu es tranquille ?»): the warm-up's reply answers the coach,
   so a scene whose reply is a question is not posed.
2. A missed warm-up printed its own instruction again as the reason; it now
   carries the unit's rule, and the rule is the reason.
3. A scene retry was lost to «season_thread: at most 80 characters»: an overlong
   key is a sentence where the key belongs and is dropped, never a schema failure.
"""
from __future__ import annotations

from app.services import living_story as engine
from tests.test_living_story import _scene_context, draft


def _strong_etre_brief() -> dict:
    return {
        "concept_id": 4242,
        "external_id": "FR2_A11_ETRE",
        "title_fr": "Je suis, tu es",
        "stability": 12.0,
        "rule_short_native": "Être means to be: je suis, tu es, il est.",
    }


def test_the_etre_warmup_never_asks_a_question_back_and_a_miss_names_the_rule() -> None:
    from app.services.journey_contracts import AssistanceLevel, AttemptAnswer, InputMode
    from app.services.journey_learning import coach_scene_review_task, evaluate_recall

    posed = 0
    for day in range(1, 29):
        task = coach_scene_review_task(_strong_etre_brief(), language="en", day_key=f"2026-10-{day:02d}")
        if task is None:
            continue
        posed += 1
        assert not task.solution_fr.rstrip().endswith("?"), task.solution_fr
        evaluation = evaluate_recall(
            None, user=None, task=task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text="non"),
            assistance=AssistanceLevel.NONE,
        )
        assert evaluation.outcome != "met"
        assert evaluation.correction is not None
        assert evaluation.correction.note_native == "Être means to be: je suis, tu es, il est."
        assert evaluation.correction.note_native.strip() != task.instruction_native.strip()
    assert posed


def test_the_planner_keeps_the_coach_scenes_rule() -> None:
    from app.services.journey_learning import _with_coach_scene
    from app.services.journey_planner import _coach_scene_task

    task = _coach_scene_task(_with_coach_scene(_strong_etre_brief(), language="en"))
    assert task is not None and task.hint_native == "Être means to be: je suis, tu es, il est."


def test_an_overlong_season_thread_is_dropped_not_a_lost_draft() -> None:
    payload = draft(_scene_context(), 0)
    sentence = "Le fil de Lila et Berlin avance : elle hésite encore entre partir et rester au Mistral."
    proposal = engine.SceneDraft.model_validate({**payload, "season_thread": sentence, "arc_stage_id": sentence})
    assert proposal.season_thread is None and proposal.arc_stage_id is None
    kept = engine.SceneDraft.model_validate({**payload, "season_thread": "lila_berlin"})
    assert kept.season_thread == "lila_berlin"
