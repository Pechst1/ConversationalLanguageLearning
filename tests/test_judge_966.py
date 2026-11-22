"""#966 / #562 — one La Forge judge for spelling variants and accents (root cause #174).

#966 (live walk 21 Nov, «Mon, ma, mes»): the find-the-mistake item «Mon clé est dans mon
sac, avec mes lunettes.» refused «Ma clef …» («The ending is off: you wrote «clef», the
form here is «clé»»), although «clef» is a correct spelling of «clé» and only the
possessive was the task. The one answer judge (``answer_acceptance.judge``) knew accents
and typos but not the second spellings ``spelling_variants`` lists, so a right word in
its other spelling was a different word.

#562 (walk 22 Nov, Regelprüfung on être): the rule check's free item «Seid ihr im
Mistral ?» refused «Vous etes au Mistral ?». The key read it as right up to an accent
(the item even printed «Vous êtes au Mistral ?»), but the rule check graded it by the
rule's detector alone, which did not see «êtes» without its accent: «Noch nicht», 2 of 3.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.services import forge_grading as grading
from app.services.atelier import AtelierCorrectionService
from tests import test_rule_check_one_verdict_954 as rule_check

SOURCE = "Mon clé est dans mon sac, avec mes lunettes."


def _find_the_mistake(db_session, typed: str, key: str, source: str = SOURCE) -> dict[str, Any]:
    service = AtelierCorrectionService(db_session)
    service.explanation_language = "en"
    return service.correct(
        concept=None,
        round_name="transform",
        mode="rewrite",
        exercise_id="forge:1:transform:t1",
        prompt_payload={"items": [{"id": "t1", "source": source, "expected_answer": key}]},
        answer_payload={"answers": {"t1": typed}},
    )


def _own_sentence(db_session, typed: str, key: str) -> dict[str, Any]:
    service = AtelierCorrectionService(db_session)
    service.explanation_language = "en"
    return service.correct(
        concept=None,
        round_name="sentence",
        mode="sentence",
        exercise_id="forge:1:sentence:s1",
        prompt_payload={"items": [{"id": "s1", "accepted_answers": [key]}]},
        answer_payload={"text": typed},
    )


@pytest.mark.parametrize(
    ("key", "typed"),
    [
        ("Ma clé est dans mon sac, avec mes lunettes.", "Ma clef est dans mon sac, avec mes lunettes."),
        ("Ma clé est dans mon sac, avec mes lunettes.", "Ma clé est dans mon sac, avec mes lunettes."),
        ("Ma clef est dans mon sac, avec mes lunettes.", "Ma clé est dans mon sac, avec mes lunettes."),
    ],
    ids=["clef", "cle", "key-clef"],
)
def test_fix_cle(db_session, key, typed):
    correction = _find_the_mistake(db_session, typed, key)
    assert correction["verdict"] == "correct", (
        f"«{typed}» fixes the marked word and writes «clé» in an accepted spelling; "
        f"the item said {correction['verdict']!r}: {[e.get('why_wrong') for e in correction['errata']]}"
    )
    assert correction["errata"] == []


def test_miss_names_mon(db_session):
    correction = _find_the_mistake(db_session, "Mon clef est dans mon sac, avec mes lunettes.", "Ma clé est dans mon sac, avec mes lunettes.")
    assert correction["verdict"] != "correct", "the possessive is still wrong"
    why = " ".join(str(item.get("why_wrong") or "") for item in correction["errata"])
    assert "clef" not in why, f"«clef» is a right spelling and not the marked mistake: {why!r}"


@pytest.mark.parametrize(
    ("key", "typed"),
    [
        ("Ils cherchent leurs clés.", "Ils cherchent leurs clefs."),
        ("Ils cherchent leurs clefs.", "Ils cherchent leurs clés."),
    ],
    ids=["clefs", "key-clefs"],
)
def test_own_cle(db_session, monkeypatch, key, typed):
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    correction = _own_sentence(db_session, typed, key)
    assert correction["local_status"] == grading.LOCAL_RIGHT, (
        f"«{typed}» is the key in its other spelling; the local check said {correction.get('local_status')!r}"
    )
    assert correction["verdict"] == "correct", correction
    assert correction["assessment_status"] == "checked"


def test_rule_check_etes(db_session, monkeypatch):
    key = "Vous êtes au Mistral ?"
    learner = "Vous etes au Mistral ?"
    monkeypatch.setattr(rule_check, "KEY", key)
    corrections, result = rule_check._play_rule_check(db_session, monkeypatch, learner)
    free = next(item for item in corrections if item["_free"])
    assert rule_check.client_says_right(free), (
        f"«{learner}» is the key up to a spelling accent; the rule check said {free.get('verdict')!r} "
        f"(detector {(free.get('local_check') or {}).get('detector')!r}, "
        f"key {(free.get('local_check') or {}).get('local_status')!r})"
    )
    assert result["production_correct"] is True and result["correct"] == 3, result
    assert free["corrected_answer"] == key, "the line is printed with its accent"
    assert "«êtes»" in str(free.get("slip_note_native") or ""), free.get("slip_note_native")
