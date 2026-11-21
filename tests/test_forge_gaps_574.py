"""#574: a free-production check where the gaps, the right sentence and the
corrections list agree, and the item's word range is enforced.

Live walk 7 Nov 2026: «Oui, j ai aime ce cafe, il est petit et tres agreable,
avec de grandes fenetres claires.» The check listed corrections and offered gaps
for them, missed «agreable» (the right sentence above shows «agréable»), and after
the gaps were fixed said «Line fixed» with «agreable» still in the line. The item
asked for 7–16 words and took 17. The gaps, the right sentence and the list came
from raw model output that was never reconciled with each other.
"""
from __future__ import annotations

import pytest

LEARNER = "Oui, j ai aime ce cafe, il est petit et tres agreable, avec de grandes fenetres claires."
CORRECTED = "Oui, j'ai aimé ce café, il est petit et très agréable, avec de grandes fenêtres claires."


def _erratum(wrong: str, fix: str, kind: str = "spelling") -> dict:
    return {"learner_text": wrong, "corrected_target": fix, "task_error_type": kind, "why_wrong": "x", "display_label": "x"}


#: The model's reading: it names four of the five differences and misses «agreable».
MODEL_ERRATA = [
    _erratum("j ai aime", "j'ai aimé"),
    _erratum("cafe", "café"),
    _erratum("tres", "très"),
    _erratum("fenetres", "fenêtres"),
]


def _model_result(errata: list[dict], corrected: str = CORRECTED) -> dict:
    return {
        "verdict": "partial", "score_0_4": 2.0, "errata": errata, "corrected_answer": corrected,
        "missing_targets": [], "lexical_gaps": [], "concept_hits": [],
    }


def test_every_difference_in_the_shown_correction_is_a_gap() -> None:
    from app.services.atelier import repair_line_from_parts, repair_parts
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(
        _model_result(MODEL_ERRATA), learner_text=LEARNER, accepted=[], language="en"
    )

    parts = repair_parts(LEARNER, refined["errata"])
    assert parts is not None
    gaps = [part for part in parts if "wrong" in part]
    wrong_words = {part["wrong"].strip(",. ") for part in gaps}
    assert "agreable" in wrong_words, f"the shown correction changes «agreable», but no gap covers it: {gaps}"
    # j ai aime / cafe / tres / agreable / fenetres: one gap per stretch that differs.
    assert len(gaps) == 5, gaps
    # Fixing every gap gives exactly the corrected sentence — nothing the check knew stays wrong.
    assert repair_line_from_parts(LEARNER, refined["errata"]) == CORRECTED


def test_the_gaps_follow_the_corrected_sentence_whatever_the_model_listed() -> None:
    from app.services.atelier import repair_line_from_parts
    from app.services.forge_grading import refine_production_correction

    # N differences, N = 1 .. 3: the model lists none of them, only the sentence.
    for learner, corrected, gaps in (
        ("Elle est parti hier.", "Elle est partie hier.", 1),
        ("Je mange un pomme rouge.", "Je mange une pomme rouge.", 1),
        ("Il a deux chats noir et un chien.", "Il a deux chats noirs et un chiens.", 2),
        ("tu es fatigue ce matin", "Tu es fatigué ce matin.", 1),
    ):
        refined = refine_production_correction(
            _model_result([], corrected), learner_text=learner, accepted=[], language="en"
        )
        from app.services.atelier import repair_parts

        parts = repair_parts(learner, refined["errata"])
        assert parts is not None, (learner, refined["errata"])
        assert len([part for part in parts if "wrong" in part]) == gaps, (learner, parts)
        fixed = repair_line_from_parts(learner, refined["errata"])
        assert fixed is not None
        assert fixed.strip(" .").lower() == corrected.strip(" .").lower()


def test_a_line_that_differs_only_in_case_and_the_full_stop_gets_no_gap() -> None:
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(
        _model_result([_erratum("tres", "très")], "Il est très petit."), learner_text="il est très petit", accepted=[], language="en"
    )
    # No gap is derived from case or the full stop. The model's «tres» -> «très» quotes a
    # word the learner did not write (they wrote «très»), so it is not shown either (#250).
    assert [item["learner_text"] for item in refined["errata"]] == []


def _attempt(db_session, errata: list[dict], *, learner: str = LEARNER, corrected: str = CORRECTED):
    from app.db.models.atelier import AtelierAttempt, AtelierSession
    from tests.test_atelier import _user

    user = _user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], quote_payload={}, status="active", recap_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, round="sentence", mode="sentence", exercise_id="s:1",
        prompt_payload={}, answer_payload={"text": learner}, verdict="partial", score_0_4=2.0,
        correction_payload={
            "verdict": "partial", "assessment_status": "checked", "errata": errata, "corrected_answer": corrected,
        },
    )
    db_session.add(attempt)
    db_session.commit()
    return attempt


def test_a_repaired_line_that_still_has_a_known_error_is_not_fixed(db_session) -> None:
    from app.services.atelier import AtelierCorrectionService

    # A stored correction that does not cover «agreable» (rows written before the gaps
    # were reconciled with the sentence): fixing its gaps must not read as «Line fixed».
    attempt = _attempt(db_session, MODEL_ERRATA)
    still_wrong = "Oui, j'ai aimé ce café, il est petit et très agreable, avec de grandes fenêtres claires."
    service = AtelierCorrectionService(db_session)
    result = service.record_micro_repair(attempt=attempt, text=still_wrong, erratum_index=0)
    assert result.correction_payload["micro_repairs"]["0"]["status"] == "no", "«agreable» is still in the line"
    fixed = service.record_micro_repair(attempt=attempt, text=CORRECTED, erratum_index=0)
    assert fixed.correction_payload["micro_repairs"]["0"]["status"] == "ok"


@pytest.mark.parametrize(
    ("line", "filled"),
    [
        ("Elle a achete livre.", "Elle a acheté livre."),  # a word missing beside a listed fix
        ("Elle a achete le un livre.", "Elle a acheté le un livre."),  # a word too many beside it
    ],
)
def test_a_difference_beside_a_listed_fix_sends_the_line_back_whole(db_session, line: str, filled: str) -> None:
    """#634: «Elle a achete livre.» kept the one gap «achete → acheté». Filling it gave a
    line the check refuses, because «un» is still missing, so the learner could never
    finish. The line is retyped whole instead, and that retype is what finishes it."""
    from app.services.atelier import AtelierCorrectionService, repair_parts
    from app.services.forge_grading import refine_production_correction

    corrected = "Elle a acheté un livre."
    refined = refine_production_correction(
        _model_result([_erratum("achete", "acheté")], corrected), learner_text=line, accepted=[], language="en"
    )
    errata = refined["errata"]
    assert repair_parts(line, errata) is None, "no gap may be offered: filling them cannot give the sentence"
    assert (errata[0]["learner_text"], errata[0]["corrected_target"]) == (line, corrected)
    assert [item["learner_text"] for item in errata[1:]] == ["achete"], "the model's note on the accent stays"

    attempt = _attempt(db_session, errata, learner=line, corrected=corrected)
    service = AtelierCorrectionService(db_session)
    refused = service.record_micro_repair(attempt=attempt, text=filled, erratum_index=0)
    assert refused.correction_payload["micro_repairs"]["0"]["status"] == "no"
    fixed = service.record_micro_repair(attempt=attempt, text=corrected, erratum_index=0)
    assert fixed.correction_payload["micro_repairs"]["0"]["status"] == "ok"


def test_a_line_sent_back_whole_keeps_no_other_retype() -> None:
    """A line repair has one target, index 0, so a second multi-word correction would get a
    retype field the server refuses."""
    from app.services.forge_grading import refine_production_correction

    line = "Elle a achete livre et une grand chat."
    refined = refine_production_correction(
        _model_result(
            [_erratum("achete", "acheté"), _erratum("une grand chat", "un grand chat")],
            "Elle a acheté un livre et un grand chat.",
        ),
        learner_text=line, accepted=[], language="en",
    )
    assert [item["learner_text"] for item in refined["errata"]] == [line, "achete"]


def test_the_item_word_range_is_enforced(db_session) -> None:
    from app.services.atelier import AtelierCorrectionService
    from tests.test_forge_integration import _forge_session

    user, concept, session, _shared = _forge_session(db_session)
    service = AtelierCorrectionService(db_session)

    def submit(text: str, item: dict, n: int):
        return service.submit_attempt(
            session=session, user=user, concept=concept, round_name="sentence", mode="sentence",
            exercise_id=f"s:574:{n}", answer_payload={"text": text},
            prompt_payload_override={"round": "sentence", "mode": "sentence", "items": [{"id": f"s:574:{n}", **item}]},
        )

    item = {"min_words": 7, "max_words": 16, "prompt": "Dis ce que tu as pensé du café."}
    seventeen = " ".join(["mot"] * 17)
    with pytest.raises(ValueError, match="words"):
        submit(seventeen, item, 1)
    # The ceiling is the rule; the floor stays a hint (items carry a generic default one).
    assert submit("trop court", item, 2).id
    assert submit(" ".join(["mot"] * 16), item, 3).id
    assert submit(seventeen, {"prompt": "Libre."}, 5).id
