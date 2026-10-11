"""WP-125A — the walk check over life records, proven on a bad and a good record,
then run over a short real life (three days, the Courrier answered)."""
from __future__ import annotations

import copy

from tests import learner_walk as walk
from tests.test_experience_walk import live, shifted_clock  # noqa: F401 - fixture
from tests.test_learner_walk import (  # noqa: F401 - fixtures
    assembled_client,
    journey_enabled,
    production_day,
)
from tests.test_season_one import season_on  # noqa: F401 - fixture
from tests.walk_checks_wp125a import check_letter_omissions

_GOOD_LETTER = {
    "title": "Le pain blanc",
    "target_vocabulary": ["constater", "le créneau"],
    "reply": "Bonjour, je passe demain matin et je vous confirme l'heure.",
    "correction": {
        "verdict": "accepted",
        "objective_progress": [
            {"id": "real_world_task", "met": True},
            {"id": "vocabulary_1", "met": False, "observed": False},
        ],
        "missing_targets": [],
        "errata": [],
    },
    "recap": {"outcome": "kept"},
}


def _record(letter: dict) -> dict:
    return {"persona": "a1-de", "quality": "strong", "days": [{"day": 3, "courrier": {"letters": [letter]}}]}


def test_quiet_on_a_letter_whose_unused_word_changed_nothing():
    assert check_letter_omissions(_record(_GOOD_LETTER)) == []


def test_fires_on_the_pre_wp125a_shape():
    bad = copy.deepcopy(_GOOD_LETTER)
    bad["correction"]["verdict"] = "partial"
    bad["correction"]["missing_targets"] = [{"external_id": "VOCAB_1", "label": "Placer « constater »"}]
    bad["correction"]["errata"] = [
        {"display_label": "Use target word: constater", "task_error_type": "vocabulary_missing_target",
         "error_category": "vocabulary", "linked_word_id": 1}
    ]
    bad["recap"]["outcome"] = "partial"
    problems = check_letter_omissions(_record(bad))
    assert len(problems) == 4
    assert all("day 3" in problem for problem in problems)


def test_a_genuine_shortfall_is_not_this_checks_business():
    other = copy.deepcopy(_GOOD_LETTER)
    other["correction"]["objective_progress"][0]["met"] = False
    other["correction"]["verdict"] = "needs_revision"
    other["recap"]["outcome"] = "missed"
    assert check_letter_omissions(_record(other)) == []
    used = copy.deepcopy(_GOOD_LETTER)
    used["target_vocabulary"] = ["confirme"]
    used["correction"]["verdict"] = "partial"
    assert check_letter_omissions(_record(used)) == []


def test_a_short_life_answers_letters_without_omission_errors(
    monkeypatch, assembled_client, db_session, journey_enabled, production_day, shifted_clock  # noqa: F811
):
    persona = next(p for p in walk.PERSONAS if p.native == "de")
    record = live(assembled_client, db_session, monkeypatch, persona, "strong", production_day, days=3)
    letters = [
        letter
        for day in record["days"]
        for letter in (day.get("courrier") or {}).get("letters") or []
        if letter.get("reply") and letter.get("target_vocabulary")
    ]
    assert letters, "the short life answered no letter with suggested words"
    assert check_letter_omissions(record) == []
