# ruff: noqa: F811 - the journey fixtures are imported by name and requested as arguments
"""WP-86 — scene words reach the catalogue learner-safely, and a thin day is
topped up from the scene's own lines, inside its minutes, graded on the device."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.schemas.daily_journey import RecallPrompt
from app.services import journey_learning
from app.services import journey_planner as planner
from app.services.journey_answer_key import answer_key_for, answer_matches_key
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    DayShape,
    InputMode,
    StepKind,
    TargetKind,
    TaskOutcome,
)
from app.services.kept_words import (
    SCENE_LEXICON_INTERACTION_TYPE,
    director_vocabulary,
    record_scene_lexicon,
)
from app.services.scene_items import floor_tasks
from tests.test_journey_end_to_end import assembled_client, learner_id, register  # noqa: F401
from tests.test_journey_planner import _brief, _candidate
from tests.test_wp78_practice_day import _dice

DRAFT = {
    "premise_fr": "La pluie a inondé la cave de l'immeuble.",
    "character_id": "margaux_barman",
    "opening_line_fr": "Vous pouvez nous aider ?",
    "panels": [
        {"narration_fr": "La pluie glisse sur la vitre.", "dialogue": [], "visual_direction": "x"},
        {
            "narration_fr": "",
            "dialogue": [
                {"character_id": "lila_bonnet", "text_fr": "Il faut vider la cave ce soir."},
                {"character_id": "margaux_barman", "text_fr": "Vous avez une idée ?"},
            ],
            "visual_direction": "y",
        },
    ],
    "lexicon": [
        {"surface_fr": "cave", "lemma": "cave", "gloss_native": "cellar",
         "part_of_speech": "noun", "gender": "f", "line_ref": "premise"},
        {"surface_fr": "idée", "lemma": "idée", "gloss_native": "idea",
         "part_of_speech": "noun", "gender": "f", "line_ref": "panel:1:line:1"},
        {"surface_fr": "vitre", "lemma": "vitre", "gloss_native": "window pane",
         "part_of_speech": "noun", "gender": "f", "line_ref": "panel:0:narration"},
    ],
}
CAST = [
    {"id": "margaux_barman", "name": "Margaux"},
    {"id": "lila_bonnet", "name": "Lila"},
    {"id": "romy_tremblay", "name": "Romy"},
]


def _scene_brief(**overrides):
    return _brief(
        story_context={"draft": DRAFT, "source": {"world": {"cast": CAST}}}, **overrides
    )


def _lexicon_candidates():
    """What `journey_learning` hands the planner for this scene: its words, new."""

    return [
        _candidate(
            identifier=f"lx{index}",
            label_fr=label,
            label_native=gloss,
            priority=0.0,
            due_since_days=0,
            is_new=True,
            relevance=1.0,
            metadata={"surface_fr": surface, "anchor": "scene_lexicon"},
        )
        for index, (label, surface, gloss) in enumerate(
            [("la cave", "cave", "cellar"), ("une idée", "idée", "idea"), ("la vitre", "vitre", "window pane")]
        )
    ]


def test_a_thin_day_is_topped_up_from_the_scene_inside_its_minutes() -> None:
    for language in ("en", "de", "fr"):
        plan = planner.plan_journey(
            scenario=_scene_brief(control_language=language),
            # Two words and nothing due: the fill alone cannot make a day of it.
            candidates=_lexicon_candidates()[:2],
            practice=True,
            dice=_dice(),
            day_shape=DayShape.STANDARD,
        )
        plan.validate()
        fill_only = planner.fill_practice_items(
            scenario=plan.scenario,
            shape=DayShape.STANDARD,
            entries=planner.practice_entries(
                plan.scenario,
                planner.select_plan_targets(plan.scenario, _lexicon_candidates()[:2]),
                [],
            ),
            affordances=[],
            sentences=[],
            safe_sentences=[],
            dice=_dice(),
            headroom=plan.budget_seconds,
            spt=0.45,
            multiplier=1.0,
        )
        assert len(fill_only) < 5, "the pool is thin without the floor"
        assert planner.graded_interactions(plan) >= 6, plan.rationale
        assert plan.estimated_active_seconds <= plan.budget_seconds
        kinds = [step.kind for step in plan.steps]
        scene_at = kinds.index(StepKind.SCENE)
        formats = [step.private_task.task_type for step in plan.steps if step.kind is StepKind.RECALL]
        assert "who_said" in formats, plan.rationale
        for index, step in enumerate(plan.steps):
            if step.kind is StepKind.RECALL and step.private_task.task_type in ("who_said", "unscramble"):
                assert index > scene_at, "a scene item is never posed before the scene"


def test_the_floor_never_quotes_the_reply_and_ties_every_item_to_a_word() -> None:
    brief = _scene_brief()
    targets = [(c.target, c.metadata) for c in _lexicon_candidates()]
    tasks = floor_tasks(brief, targets, expected_reply="Vous avez une idée ?")
    assert tasks, "the scene still has lines to build from"
    for target, task in tasks:
        assert target.kind is TargetKind.VOCABULARY
        assert "Vous avez une idée" not in json.dumps(task.options, ensure_ascii=False)
        assert task.prompt_fr != "Vous avez une idée ?"
    kinds = {task.task_type for _t, task in tasks}
    assert {"who_said", "choice"} <= kinds


def _who_said_task():
    brief = _scene_brief()
    targets = [(c.target, c.metadata) for c in _lexicon_candidates()]
    return next(task for _t, task in floor_tasks(brief, targets) if task.task_type == "who_said")


def test_who_said_grades_by_id_on_the_device_and_schedules_nothing() -> None:
    task = _who_said_task()
    assert {option["character_id"] for option in task.options} <= {c["id"] for c in CAST}
    right = task.correct_option_id
    wrong = next(option["id"] for option in task.options if option["id"] != right)
    key = answer_key_for("step-1", {"task_type": "who_said", "correct_option_id": right})
    assert key and answer_matches_key(key, "who_said", option_id=right)
    assert not answer_matches_key(key, "who_said", option_id=wrong)

    good = journey_learning.evaluate_recall(
        None, user=None, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", option_id=right),
        assistance=AssistanceLevel.NONE,
    )
    assert good.outcome is TaskOutcome.MET and good.observations == []
    bad = journey_learning.evaluate_recall(
        None, user=None, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", option_id=wrong),
        assistance=AssistanceLevel.NONE,
    )
    assert bad.outcome is TaskOutcome.NOT_YET and bad.observations == []
    speaker = next(o["text_fr"] for o in task.options if o["id"] == right)
    # The correction names who said it, never the line itself.
    assert bad.correction is None or bad.correction.corrected_fr == speaker


def test_who_said_travels_the_wire_with_faces_and_without_its_answer() -> None:
    task = _who_said_task()
    prompt = RecallPrompt.model_validate(
        {
            "task_type": task.task_type,
            "instruction_native": task.instruction_native,
            "prompt_fr": task.prompt_fr,
            "options": [dict(option) for option in task.options],
            "target": planner.public_recall_target(task.target),
            "optional": task.optional,
            "help_available": [],
        }
    ).model_dump(mode="json")
    assert all(option.get("character_id") for option in prompt["options"])
    assert "correct_option_id" not in json.dumps(prompt)
    older = RecallPrompt.model_validate(
        {**prompt, "task_type": "choice", "options": [{"id": "a", "text_fr": "un café"}]}
    ).model_dump(mode="json")
    assert "character_id" not in older["options"][0], "older formats stay byte-identical"


def test_scene_words_reach_the_catalogue_learner_safely(
    assembled_client: TestClient, db_session: Session
) -> None:
    email = f"wp86-{uuid.uuid4().hex[:8]}@example.com"
    register(assembled_client, email)
    user = db_session.get(User, learner_id(db_session, email))
    user.native_language = "de"
    shared = VocabularyWord(
        language="fr", word="cave", normalized_word="cave",
        english_translation="cellar", difficulty_level=1,
    )
    db_session.add(shared)
    db_session.commit()
    before = {
        column: getattr(shared, column)
        for column in ("english_translation", "german_translation", "example_sentence", "topic_tags")
    }
    entries = [
        {"surface_fr": "cave", "lemma": "cave", "gloss_native": "Keller", "part_of_speech": "noun", "gender": "f"},
        {"surface_fr": "vitre", "lemma": "vitre", "gloss_native": "Fensterscheibe", "part_of_speech": "noun", "gender": "f"},
    ]
    sentences = {"cave": "La pluie a inondé la cave de l'immeuble.", "vitre": "La pluie glisse sur la vitre."}
    words = record_scene_lexicon(db_session, user=user, entries=entries, sentences=sentences, level="A1")
    again = record_scene_lexicon(db_session, user=user, entries=entries, sentences=sentences, level="A1")
    db_session.commit()

    assert [w.word_id for w in words] == [w.word_id for w in again], "matched by lemma, once"
    assert words[0].word_id == shared.id and not words[0].created
    db_session.refresh(shared)
    assert {column: getattr(shared, column) for column in before} == before, "the shared row is read, never written"

    created = db_session.get(VocabularyWord, words[1].word_id)
    assert words[1].created and created.german_translation == "Fensterscheibe"
    assert created.english_translation is None, "no placeholder in another language"
    assert created.gender == "f" and "scene_lexicon" in (created.topic_tags or [])

    rows = db_session.query(WordInteraction).filter_by(
        user_id=user.id, interaction_type=SCENE_LEXICON_INTERACTION_TYPE
    ).all()
    assert len(rows) == 2 and {row.correction for row in rows} == {"Keller", "Fensterscheibe"}
    assert db_session.query(UserVocabularyProgress).filter_by(user_id=user.id).count() == 0, (
        "a word enters the Lexique once practised, not when a scene names it"
    )
    assert set(director_vocabulary(db_session, user_id=user.id)["lexicon_history"]) == {"cave", "vitre"}
