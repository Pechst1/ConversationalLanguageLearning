"""#745: a free-sentence repair accepts the minimal fix and explains the slip the learner made.

Live walk 13 Nov 2026, La Forge «Le, la, l', les: the». The learner wrote «J'aime la
oiseau dans le parc.» (an article slip). The check rewrote the line to «J'aime les
oiseaux dans le parc.», explained «the plural “les oiseaux” is needed to refer to
birds» (the learner wrote a singular), and in «Fix only the underlined words» refused
the minimal fix «l'oiseau»: only the invented plural read «Line fixed».

The model's fix of «la oiseau» passed the one checker because «oiseaux» is the same
word as «oiseau»: nothing asked whether the fix kept what the learner said. The rules
had the minimal fix of the same words all along («la» elides before a vowel).
"""
from __future__ import annotations

LEARNER = "J'aime la oiseau dans le parc."
MODEL_SENTENCE = "J'aime les oiseaux dans le parc."
MODEL_ERRATUM = {
    "learner_text": "la oiseau",
    "corrected_target": "les oiseaux",
    "why_wrong": "You wrote “la oiseau”; the plural “les oiseaux” is needed to refer to birds.",
    "repair_hint": "Use the plural article and noun.",
    "display_label": "Article",
    "task_error_type": "grammar",
    "severity": 2,
}


def _model_result() -> dict:
    return {
        "verdict": "partial", "score_0_4": 2.0, "errata": [dict(MODEL_ERRATUM)], "corrected_answer": MODEL_SENTENCE,
        "missing_targets": [], "lexical_gaps": [], "concept_hits": [],
    }


def _attempt(db_session, correction: dict):
    from app.db.models.atelier import AtelierAttempt, AtelierSession
    from tests.test_atelier import _user

    user = _user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], quote_payload={}, status="active", recap_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="sentence", mode="sentence", exercise_id="s:745",
        prompt_payload={}, answer_payload={"text": LEARNER}, verdict="partial", score_0_4=2.0,
        correction_payload={**correction, "assessment_status": "checked"},
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_l_oiseau_fixes_it(db_session) -> None:
    from app.services.atelier import AtelierCorrectionService, repair_parts
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(_model_result(), learner_text=LEARNER, accepted=[], language="en")

    parts = repair_parts(LEARNER, refined["errata"])
    assert parts is not None
    gaps = [(part["wrong"], part["fix"]) for part in parts if "wrong" in part]
    assert len(gaps) == 1 and gaps[0][1] == "l'oiseau", f"the gap asks for an invented plural: {gaps}"
    assert refined["corrected_answer"] == "J'aime l'oiseau dans le parc.", refined["corrected_answer"]

    attempt = _attempt(db_session, refined)
    service = AtelierCorrectionService(db_session)
    # The learner types «l'oiseau» (an iPhone apostrophe) in the one underlined gap.
    fixed = service.record_micro_repair(attempt=attempt, text="J'aime l’oiseau dans le parc.", erratum_index=0)
    assert fixed.correction_payload["micro_repairs"]["0"]["status"] == "ok", "«l'oiseau» is the fix: «Line fixed»"


def test_note_is_elision() -> None:
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(_model_result(), learner_text=LEARNER, accepted=[], language="en")
    [erratum] = [item for item in refined["errata"] if item.get("task_error_type") != "task_compliance"]
    assert (erratum["learner_text"], erratum["corrected_target"]) == ("la oiseau", "l'oiseau")
    note = f"{erratum.get('why_wrong')} {' '.join(refined.get('notes_native') or [])}"
    assert "vowel" in note, note
    assert "plural" not in note and "oiseaux" not in note, f"the learner wrote no plural: {note}"


def test_all_surfaces() -> None:
    """The cause is the one checker's, so the Journal, the Courrier and the scene see it too."""
    from app.services import correction_contract

    checked = correction_contract.verify_correction(LEARNER, MODEL_SENTENCE, [dict(MODEL_ERRATUM)], language="en")
    assert checked.corrected == "J'aime l'oiseau dans le parc.", checked.corrected
    assert [(item["learner_text"], item["corrected_target"]) for item in checked.errata] == [("la oiseau", "l'oiseau")]

    span, fix, note = correction_contract.first_valid_edit(
        LEARNER, MODEL_ERRATUM["learner_text"], MODEL_ERRATUM["corrected_target"], MODEL_ERRATUM["why_wrong"], language="en"
    )
    assert (span, fix) == ("la oiseau", "l'oiseau")
    assert "plural" not in str(note)


def test_unruled_plural_stays() -> None:
    """The rules overrule a model's number only where they fix the same words keeping it:
    «Le chat sont noirs» has no rule fix on «Le chat», so the model's plural stays."""
    from app.services import correction_contract

    erratum = {"learner_text": "Le chat", "corrected_target": "Les chats", "why_wrong": "«sont» is plural.",
               "task_error_type": "grammar"}
    verified = correction_contract.verify_erratum("Le chat sont noirs.", erratum, strict_span=False)
    assert verified is not None and verified["corrected_target"] == "Les chats"
