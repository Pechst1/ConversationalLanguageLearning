"""#236 / #146: a target counts as used only when the learner wrote that word.

Live walk 2026-10-19: the Courrier showed «vendre · used» for «Je préfère
vendredi». The story engine marks a target as produced when the model says so
*and* the target's label occurs in the reply; the occurrence test was a raw
substring («vendre» is the first six letters of «vendredi»). The same test was
written twice (living_story, story_lanes), so a fix in one left the other.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import living_story as engine
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    InputMode,
    ResponseTask,
    TargetKind,
    TargetRef,
)
from tests.test_living_story import _turn


def _evaluate(monkeypatch, label: str, text: str, db_session=None):
    target = TargetRef(kind=TargetKind.VOCABULARY, id="7", label_fr=label)
    task = ResponseTask(
        objective_native="Reply to the letter",
        character_id="c",
        character_name="Odile",
        opening_line_fr="Jeudi, c'est bon ?",
        targets=[target],
    )
    scenario = SimpleNamespace(story_context={}, character_id="c")
    turn = engine.SemanticTurn(**{**_turn(text), "demonstrated_target_ids": ["7"]})
    monkeypatch.setattr(engine.settings, "ATELIER_STORY_TURN_LANES_ENABLED", False)
    monkeypatch.setattr(engine, "credit_transfer", lambda *a, **k: [])
    monkeypatch.setattr(
        engine, "_turn_payload",
        lambda *a, **k: {"story": {"revision": 1}, "turn_plan": {"keep_talking": False}},
    )
    monkeypatch.setattr(engine, "reply_lexical_checker", lambda *a, **k: None)
    monkeypatch.setattr(engine, "_approved", lambda *a, **k: (turn, {}))
    answer = AttemptAnswer(mode=InputMode.TEXT, text=text)
    evaluation = engine.evaluate_turn(
        db_session, user=SimpleNamespace(id="u"), scenario=scenario, task=task, answer=answer,
        turn_index=0, assistance=AssistanceLevel.NONE,
    )
    return [f"{o.target.kind}:{o.target.id}" for o in evaluation.observations]


@pytest.mark.parametrize(
    "text",
    [
        "Je préfère vendredi, parce que la bouillotte est cassée.",
        "Vendredi, je suis libre.",
        "Je viens vendredi soir.",
    ],
)
def test_a_longer_word_that_starts_like_the_target_is_not_the_target(monkeypatch, db_session, text):
    assert _evaluate(monkeypatch, "vendre", text, db_session) == []


@pytest.mark.parametrize(
    "text",
    [
        "Je vends la bouillotte.",
        "Elle a vendu un tableau.",
        "Vous vendez l'appartement ?",
        "Je veux vendre le canapé.",
        "Nous vendions des livres.",
    ],
)
def test_the_word_and_its_real_inflections_count(monkeypatch, db_session, text):
    assert _evaluate(monkeypatch, "vendre", text, db_session) == ["vocabulary:7"]


def test_a_noun_counts_in_the_plural_but_not_inside_a_longer_word(monkeypatch, db_session):
    assert _evaluate(monkeypatch, "la lettre", "Merci pour vos lettres.", db_session) == ["vocabulary:7"]
    assert _evaluate(monkeypatch, "lettre", "Elle ouvre le lettrage.", db_session) == []


@pytest.mark.parametrize(
    ("text", "used"),
    [
        ("Je préfère vendredi", False),
        ("je vends", True),
        ("elle a vendu", True),
        ("vous vendez", True),
    ],
)
def test_the_courrier_words_counter_matches_whole_words_and_inflections(text, used):
    from app.services.missions import MissionCorrectionService, _normalize_phrase

    item = {"word": "vendre", "normalized_word": "vendre"}
    found = MissionCorrectionService._contains_vocabulary_form(None, _normalize_phrase(text), item)
    assert found is used


def test_no_service_compares_a_target_label_to_learner_text_with_a_substring_test():
    """The class of bug (#146): each caller wrote its own «is the word in the text»."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    pattern = re.compile(r"label_fr[^\n]*\b(?:casefold|lower)\(\)\s+in\s")
    offenders = [
        f"{path.relative_to(root)}:{number}"
        for path in root.rglob("*.py")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if pattern.search(line)
    ]
    assert offenders == [], f"use word_match.target_occurs_in instead: {offenders}"


def test_the_chapter_goal_check_does_not_prefix_match():
    """story_service's goal check matched «vend…» to «vendre» by stem prefix."""
    from uuid import uuid4

    from app.services.story_service import StoryService

    def goals_met(text: str) -> list[str]:
        messages = [SimpleNamespace(content=text)]

        class Result:
            def scalars(self):
                return SimpleNamespace(all=lambda: messages)

        service = StoryService.__new__(StoryService)
        service.db = SimpleNamespace(execute=lambda stmt: Result())
        chapter = SimpleNamespace(narrative_goals=[{"goal_id": "g", "required_words": ["vendre"]}])
        return service.check_narrative_goals(uuid4(), chapter).goals_completed

    assert goals_met("Je préfère vendredi.") == []
    assert goals_met("Je vends le tableau.") == ["g"]
