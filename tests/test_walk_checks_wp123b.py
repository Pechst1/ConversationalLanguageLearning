"""WP-123b — the La Forge walk checks, proven on a good and on bad life records."""
from __future__ import annotations

import copy

from tests.walk_checks_wp123b import check_life_wp123b


def _record(native: str = "de") -> dict:
    seance = {
        "offered_concept_id": 2,
        "budget_seconds": 300,
        "start_status": 201,
        "mode": "seance",
        "length": 12,
        "rules": [2, 1],
        "answered": 3,
        "finished": True,
        "complete_status": 200,
        "items": [
            {"round": "recognize", "mode": "fill", "status_code": 200, "verdict": "correct", "answer": '{"x": "sont"}',
             "cues": ["Ergänze den Satz: „Sie sind mit Lila im Mistral.“"]},
            {"round": "sentence", "mode": "sentence", "status_code": 200, "verdict": "incorrect", "answer": "je ne sais pas",
             "cues": ["Sag auf Französisch: „Sie sind in der Kirche.“"]},
            {"round": "conversation", "mode": "conversation", "status_code": 200, "verdict": "correct",
             "answer": "Nous sommes à la rédaction.", "cues": ["Antworte auf Französisch, mit der Regel von heute."]},
        ],
    }
    return {
        "persona": "a1-de-fresh",
        "quality": "average",
        "native": native,
        "days": [{"day": 3, "forge": seance, "time": {"forge": {"total": 340.0}}}],
    }


def test_a_good_seance_is_quiet():
    assert check_life_wp123b(_record()) == []


def test_a_day_without_la_forge_is_quiet():
    record = _record()
    record["days"][0].pop("forge")
    assert check_life_wp123b(record) == []


def test_a_refused_start_answer_or_filing_is_flagged():
    record = _record()
    record["days"][0]["forge"]["start_status"] = 500
    assert any("did not open" in p for p in check_life_wp123b(record))
    record = _record()
    record["days"][0]["forge"]["items"][1]["status_code"] = 422
    record["days"][0]["forge"]["complete_status"] = 409
    problems = check_life_wp123b(record)
    assert any("refused 1 answer" in p for p in problems)
    assert any("could not be filed" in p for p in problems)


def test_a_seance_that_overruns_its_length_or_never_ends_is_flagged():
    record = _record()
    seance = record["days"][0]["forge"]
    seance["length"] = 2
    seance["finished"] = False
    problems = check_life_wp123b(record)
    assert any("served 3 items for a séance of 2" in p for p in problems)
    assert any("did not end" in p for p in problems)


def test_a_seance_on_another_rule_than_the_chip_is_flagged():
    record = _record()
    record["days"][0]["forge"]["rules"] = [7]
    assert any("the chip named rule 2" in p for p in check_life_wp123b(record))


def test_a_seance_far_over_its_budget_is_flagged():
    record = _record()
    record["days"][0]["time"]["forge"]["total"] = 451.0
    assert any("against a 5-min chip" in p for p in check_life_wp123b(record))


def test_english_for_a_german_learner_is_flagged_but_not_for_an_english_one():
    record = _record()
    record["days"][0]["forge"]["items"][0]["cues"].append("Build the sentence with the right form.")
    assert any("English on a German learner's forge item" in p for p in check_life_wp123b(record))
    english = copy.deepcopy(record)
    english["native"] = "en"
    assert check_life_wp123b(english) == []


def test_a_give_up_graded_correct_is_flagged():
    record = _record()
    record["days"][0]["forge"]["items"][1]["verdict"] = "correct"
    assert any("«je ne sais pas» graded correct" in p for p in check_life_wp123b(record))
