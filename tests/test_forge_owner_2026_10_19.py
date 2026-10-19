"""Owner, 2026-10-19: three La Forge screens.

* A rule check («Regelprüfung») whose free answer the rule's detector passed
  on the spot showed «Die zweite Prüfung brach ab» (client side, see
  ``lib/seance-feedback.test.js``); its «Neu starten» must not send a final
  placement to the model either.
* «Ta phrase ne dit pas que tu as réservé une table au Mistral…»: the grader
  read the English meaning the learner's French screen never showed.
* A long line is repaired by fixing only its wrong parts.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService


def _say_item() -> tuple[ib.BankItem, dict]:
    item = ib.default_bank().generate("FR2_A11_LE_LA", 1, seed="wp-s6")[0]
    return item, ib.output_item(item, round_name="sentence", requirement={"label": "X", "target_count": 1})


def _service(language: str, native: str | None = None) -> AtelierCorrectionService:
    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = language
    service._learner_native = native
    return service


def test_a_french_screen_without_the_meaning_is_graded_as_an_own_sentence():
    item, payload = _say_item()
    task = _service("fr", "de")._compact_llm_task({"items": [payload]})
    asked = task["items"][0]
    assert asked["own_sentence"] is True
    assert item.en not in asked["prompt"] and (item.de or "") not in asked["prompt"]
    assert "Écris une courte phrase à toi en français" in asked["prompt"]
    # The sample stays a sample; nothing the screen did not show is required.
    assert asked["example_answer"] == item.sentence and "expected_answer" not in asked


def test_a_screen_that_quoted_the_meaning_keeps_it_as_the_task():
    item, payload = _say_item()
    assert item.de
    german = _service("de")._compact_llm_task({"items": [payload]})["items"][0]
    assert "own_sentence" not in german and german["prompt"] == payload["prompt"]
    english = _service("en")._compact_llm_task({"items": [payload]})["items"][0]
    assert "own_sentence" not in english and english["prompt"] == f'Say in French: "{item.en}"'


def test_a_rule_checks_final_verdict_is_never_sent_for_a_second_reading(db_session):
    service = AtelierCorrectionService(db_session)
    attempt = SimpleNamespace(
        round="conversation",
        correction_payload={
            "verdict": "correct", "assessment_status": "checked", "graded_by": "local_test_out",
            "correction_debug": {"fallback_used": True}, "ai_review": {"status": "not_applicable"},
        },
    )
    same, started = service.mark_ai_review_pending(attempt, auto_started=False)
    assert started is False and same.correction_payload["ai_review"]["status"] == "not_applicable"


SC2_LINE = "J'ai fini les taches avec un grand motivation"
SC2_ERRATA = [
    {"learner_text": "taches", "corrected_target": "tâches", "task_error_type": "spelling"},
    {"learner_text": "un grand", "corrected_target": "une grande", "task_error_type": "agreement"},
    {"learner_text": "", "corrected_target": "", "why_wrong": "x", "task_error_type": "task_compliance"},
]


def test_a_line_is_cut_into_the_parts_to_fix_and_the_parts_to_keep():
    from app.services.atelier import repair_line_from_parts, repair_parts

    parts = repair_parts(SC2_LINE, SC2_ERRATA)
    assert parts == [
        {"text": "J'ai fini les "},
        {"wrong": "taches", "fix": "tâches", "erratum": 0},
        {"text": " avec "},
        {"wrong": "un grand", "fix": "une grande", "erratum": 1},
        {"text": " motivation"},
    ]
    assert repair_line_from_parts(SC2_LINE, SC2_ERRATA) == "J'ai fini les tâches avec une grande motivation"
    # A correction the line cannot hold in place: the line is retyped whole.
    assert repair_parts(SC2_LINE, [{"learner_text": "", "corrected_target": "le", "task_error_type": "article"}]) is None
    assert repair_parts(SC2_LINE, [{"learner_text": "chaises", "corrected_target": "tables"}]) is None
    # «a» inside «avec» is not the word «a».
    assert repair_parts("Il avec a fini", [{"learner_text": "a", "corrected_target": "est"}])[1] == {"wrong": "a", "fix": "est", "erratum": 0}


def test_a_line_repaired_in_parts_is_accepted_and_accents_count(db_session):
    from app.db.models.atelier import AtelierAttempt, AtelierSession
    from tests.test_atelier import _user

    user = _user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], quote_payload={}, status="active", recap_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="sentence", mode="sentence", exercise_id="s:1",
        prompt_payload={}, answer_payload={"text": SC2_LINE}, verdict="partial", score_0_4=2.0,
        correction_payload={
            "verdict": "partial", "assessment_status": "checked", "errata": SC2_ERRATA,
            # The model's rewrite also added the full stop.
            "corrected_answer": "J'ai fini les tâches avec une grande motivation.",
        },
    )
    db_session.add(attempt)
    db_session.commit()
    service = AtelierCorrectionService(db_session)
    unaccented = service.record_micro_repair(attempt=attempt, text="J'ai fini les taches avec une grande motivation", erratum_index=0)
    assert unaccented.correction_payload["micro_repairs"]["0"]["status"] == "no"
    fixed = service.record_micro_repair(attempt=attempt, text="J'ai fini les tâches avec une grande motivation", erratum_index=0)
    assert fixed.correction_payload["micro_repairs"]["0"]["status"] == "ok"
