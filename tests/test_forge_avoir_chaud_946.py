"""#946: La Forge printed «Elle a chaude ce soir.» and refused the right «Elle a chaud ce soir».

Live walk 20 Nov 2026, item «Say in French: She is hot tonight.» The learner wrote
«Elle est chaud ce soir». The model marked «est» -> «a» and «chaud» -> «chaude» and
printed «Elle a chaude ce soir.»: each fix reads well on its own (after «est» the
adjective agrees), together they are wrong French (avoir chaud is invariable). The
corrected line was never read by the rules as a whole, and the retype was judged
against that one stored line, so the right sentence was «Not quite».
"""
from __future__ import annotations

LEARNER = "Elle est chaud ce soir"
MODEL_LINE = "Elle a chaude ce soir."
RIGHT = "Elle a chaud ce soir"
PROMPT = {"items": [{"prompt_en": "She is hot tonight.", "accepted_answers": ["Elle a chaud ce soir."]}]}


def _erratum(wrong: str, fix: str, note: str = "x") -> dict:
    return {
        "learner_text": wrong, "corrected_target": fix, "task_error_type": "grammar",
        "why_wrong": note, "display_label": "Grammar", "repair_hint": "",
    }


#: The model's reading, as the walk printed it.
MODEL_ERRATA = [
    _erratum("est", "a", "French uses «a» (avoir), not «est», to express feeling hot."),
    _erratum("chaud", "chaude", "The adjective agrees with «elle»: «chaude»."),
]


def _model_result() -> dict:
    return {
        "verdict": "partial", "score_0_4": 2.0, "errata": [dict(item) for item in MODEL_ERRATA],
        "corrected_answer": MODEL_LINE, "missing_targets": [], "lexical_gaps": [], "concept_hits": [],
    }


def test_the_rules_read_avoir_chaud_as_invariable() -> None:
    from app.services.correction_contract import repair_text

    assert repair_text("Elle a chaude ce soir.") == "Elle a chaud ce soir."
    assert repair_text("Nous avons froids.") == "Nous avons froid."
    assert repair_text("Elle a eu très froide hier.") == "Elle a eu très froid hier."
    # Right French is left alone: «être chaude», a noun between, the idiom «l'avoir chaude».
    for right in (
        "Elle est chaude ce soir.",
        "La soupe est chaude.",
        "Elle a les mains froides.",
        "On l'a eue chaude !",
        "Elle a chaud ce soir.",
    ):
        assert repair_text(right) == right, right


def test_the_printed_correction_is_elle_a_chaud() -> None:
    from app.services.atelier import repair_line_from_parts
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(_model_result(), learner_text=LEARNER, accepted=[], language="en")

    assert "chaude" not in refined["corrected_answer"], f"the guard let «{refined['corrected_answer']}» through"
    assert refined["corrected_answer"] == "Elle a chaud ce soir."
    fixes = [str(item.get("corrected_target") or "") for item in refined["errata"]]
    assert not any("chaude" in fix for fix in fixes), fixes
    # The note that names the real mistake (être -> avoir) is kept.
    assert any(item.get("corrected_target") == "a" for item in refined["errata"]), refined["errata"]
    # Filling the gaps gives the right sentence, not «chaude».
    filled = repair_line_from_parts(LEARNER, refined["errata"])
    assert filled is not None and filled.strip(" .") == RIGHT


def test_every_surface_reads_the_fixes_as_one_line() -> None:
    """The same flaw on the Courrier, the Journal and the scenes (``verify_correction``):
    the list kept «chaud -> chaude» beside a rule's «chaude -> chaud»."""
    from app.services.correction_contract import verify_correction

    checked = verify_correction(LEARNER, MODEL_LINE, [dict(item) for item in MODEL_ERRATA], language="en")

    assert checked.corrected.strip(" .") == RIGHT
    fixes = [(item["learner_text"], item["corrected_target"]) for item in checked.errata]
    assert fixes == [("est", "a")], fixes


def _attempt(db_session, correction: dict, prompt: dict | None = None):
    from app.db.models.atelier import AtelierAttempt, AtelierSession
    from tests.test_atelier import _user

    user = _user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], quote_payload={}, status="active", recap_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="sentence", mode="sentence", exercise_id="s:946",
        prompt_payload=prompt or {}, answer_payload={"text": LEARNER}, verdict="partial", score_0_4=2.0,
        correction_payload={"assessment_status": "checked", **correction},
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_the_right_sentence_is_accepted_in_the_correction_box(db_session) -> None:
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(_model_result(), learner_text=LEARNER, accepted=[], language="en")
    attempt = _attempt(db_session, refined)
    service = AtelierCorrectionService(db_session)

    wrong = service.record_micro_repair(attempt=attempt, text="Elle a chaude ce soir", erratum_index=0)
    assert wrong.correction_payload["micro_repairs"]["0"]["status"] == "no", "«chaude» is the wrong French"
    right = service.record_micro_repair(attempt=attempt, text=RIGHT, erratum_index=0)
    assert right.correction_payload["micro_repairs"]["0"]["status"] == "ok", "the right sentence was refused"


def test_an_accepted_answer_of_the_item_is_right_against_an_old_stored_line(db_session) -> None:
    """#174: a row stored before the guard still holds «Elle a chaude ce soir.». The
    retype is judged against the item's accept-list too, not that one stored string."""
    from app.services.atelier import AtelierCorrectionService

    attempt = _attempt(
        db_session,
        {"verdict": "partial", "errata": [dict(item) for item in MODEL_ERRATA], "corrected_answer": MODEL_LINE},
        PROMPT,
    )
    service = AtelierCorrectionService(db_session)
    right = service.record_micro_repair(attempt=attempt, text=RIGHT, erratum_index=0)
    assert right.correction_payload["micro_repairs"]["0"]["status"] == "ok", "the item's own answer was refused"
    wrong = service.record_micro_repair(attempt=attempt, text="Elle est chaude ce soir", erratum_index=0)
    assert wrong.correction_payload["micro_repairs"]["0"]["status"] == "no"
