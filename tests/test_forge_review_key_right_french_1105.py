"""#1105: La Forge's review item («Ta phrase») refused the right fix «grande» + «blancs».

Live walk 27 Nov 2026 (production, day 45). The item «Adjectives: agreement and position»,
«You wrote this earlier. Fix the mistake.», showed the learner's own line «Ta chambre est
très grand et tes murs sont blanc, c'est une belle chambre.». The learner wrote the right
sentence «… très grande et tes murs sont blancs …» and read «Not yet», the corrected line
«Ta chambre est très grand et tes murs sont blancs …» and the note «you wrote «grande», the
form here is «grand»». The end sheet listed the same wrong line under «Still practising».

The saved mistake was «blanc» → «blancs» only: the key was the learner's line with that one
slip fixed, and the rest of the line was trusted as right French. Nothing checked it
(#174: one stored string; #250: a correction never checked against the learner's line).
The key is now read by the rule pass before it is posed; what the rules still find in the
learner's line is repaired in the line and the key, as a sibling mistake is.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.core.forge import Rung

LINE = "Ta chambre est très grand et tes murs sont blanc, c'est une belle chambre."
RIGHT = "Ta chambre est très grande et tes murs sont blancs, c'est une belle chambre."
WRONG_KEY = "très grand et tes murs"


def _walk_item(db_session):
    from app.db.models.atelier import AtelierAttempt
    from app.services.forge import _mine_sentence, mine_payload_item
    from tests.test_forge_drills import _error, _forge_seance

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, concept_id=concept.id, round="sentence", mode="sentence",
        exercise_id="x", prompt_payload={}, answer_payload={"text": LINE}, correction_payload={},
        verdict="incorrect", score_0_4=1.0,
    )
    db_session.add(attempt)
    db_session.commit()
    # The only mistake saved from the line: the model's correction missed «grand».
    error = _error(
        db_session, user, learner="sont blanc", corrected="sont blancs",
        concept_id=concept.id, source_type="atelier", source_attempt_id=attempt.id,
    )
    source, expected = _mine_sentence(db_session, error)
    item = mine_payload_item(
        item_id="mine-1105", error_id=error.id, source=source, expected=expected,
        lesson_external_id=concept.external_id,
    )
    return concept, item


def _grade(concept, item, answer: str) -> dict:
    from app.services.atelier import AtelierCorrectionService

    return AtelierCorrectionService(None)._correct_transform_rule_based(
        concept, {"items": [item]}, {"answers": {item["id"]: answer}}
    )


def test_the_review_key_is_right_french(db_session) -> None:
    _concept, item = _walk_item(db_session)
    assert WRONG_KEY not in item["expected_answer"], (
        f"the review item keys wrong French: «{item['expected_answer']}»"
    )
    assert item["expected_answer"] == RIGHT


def test_the_right_fix_is_accepted_and_no_screen_shows_the_wrong_line(db_session) -> None:
    concept, item = _walk_item(db_session)
    correction = _grade(concept, item, RIGHT)
    shown = json.dumps(correction, ensure_ascii=False)
    assert correction["verdict"] == "correct", f"the right sentence was refused: {shown}"
    assert WRONG_KEY not in shown, shown
    assert "the form here is «grand»" not in shown and "you wrote «grande»" not in shown, shown


def test_the_end_sheet_prints_the_right_line(db_session) -> None:
    from app.services.atelier import AtelierSRSService

    concept, item = _walk_item(db_session)
    for answer in (RIGHT, LINE):
        correction = _grade(concept, item, answer)
        attempt = SimpleNamespace(
            correction_payload={**correction, "assessment_status": "checked"},
            verdict=correction["verdict"],
            prompt_payload={"items": [item]},
            answer_payload={"answers": {item["id"]: answer}},
            round="transform",
            mode="rewrite",
        )
        proof = AtelierSRSService._forge_proof_line(attempt)
        assert proof is not None
        assert WRONG_KEY not in proof[0], f"the end sheet lists wrong French after «{answer}»: {proof}"


def test_the_rules_hold_the_predicate_adjective_to_its_noun() -> None:
    from app.services.correction_contract import deterministic_edits

    edits = deterministic_edits("Ta chambre est très grand.")
    assert [(e.span, e.replacement) for e in edits] == [("grand", "grande")]
    for right in (
        "Ta chambre est très grande.",
        "Le prix de la chambre est grand.",
        "Mon frère est grand.",
        "La maison est rouge.",
        "Ta chambre est trop petite pour deux.",
    ):
        assert deterministic_edits(right) == [], right
