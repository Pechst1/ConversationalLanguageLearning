"""#370 — the end sheet («Today's rules, forged») is built from what the learner did.

Live walk 29 Oct: the sheet listed «J'ai acheté des pommes» under a red
triangle as a line the learner kept, but they had written «J'ai acheté des
pommes de terre» (the first line); the second was the model's own example /
clipped echo. And every rule read «Level 6» though the answers had moved the
levels between 3 and 6.

Done when: every line on the sheet is a verbatim learner answer or the checked
correction of one, and the level shown per rule equals the level after the last
item of that rule.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Role
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierSRSService
from app.services.forge import ForgeService, _store_state
from tests.test_atelier import _concept, _user


def _sentence(
    concept_id: int,
    *,
    typed: str,
    verdict: str,
    corrected: str | None = None,
    example: str = "",
    key: str = "a",
    flagged: str | None = None,
) -> AtelierAttempt:
    return AtelierAttempt(
        concept_id=concept_id,
        round="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept_id}:sentence:{key}",
        prompt_payload={"items": [{"id": key, "example_answer": example}]},
        answer_payload={"text": typed},
        correction_payload={
            "checked": True,
            **({"corrected_answer": corrected} if corrected else {}),
            **({"errata": [{"learner_text": flagged}]} if flagged else {}),
        },
        verdict=verdict,
        score_0_4=4.0 if verdict in {"correct", "accepted"} else 1.0,
    )


def _lines(db_session, user, concept, attempts) -> list[tuple[str, bool]]:
    progress = AtelierSRSService(db_session)._forge_rule_progress(
        user=user, concept_id=concept.id, stage_before="introduced", attempts=attempts, started_at=None
    )
    return [(line["fr"], line["fixed"]) for line in progress["proof"]]


def test_kept_line_is_verbatim(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        # Right: the corrector's «corrected_answer» is a clipped echo of the line.
        _sentence(
            concept.id, typed="J'ai acheté des pommes de terre", verdict="accepted",
            corrected="J'ai acheté des pommes", key="a",
        ),
    ]
    assert _lines(db_session, user, concept, attempts) == [("J'ai acheté des pommes de terre", False)]


def test_miss_not_models_example(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        # Wrong, and the checker gave no correction: the item's example_answer
        # is the model's sentence, not the learner's and not a correction of it.
        _sentence(concept.id, typed="Je acheté des pomme", verdict="incorrect", example="J'ai acheté des pommes", key="b"),
    ]
    assert _lines(db_session, user, concept, attempts) == []


def test_clip_is_not_a_fix(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        _sentence(
            concept.id, typed="J'ai acheté des pomme de terre", verdict="incorrect",
            corrected="J'ai acheté des pomme", key="c",
        ),
    ]
    assert _lines(db_session, user, concept, attempts) == []


def test_checked_deletion_is_a_fix(db_session):
    """A correction that only drops the words an erratum flagged is a real fix."""

    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        _sentence(
            concept.id, typed="Je peux de venir demain.", verdict="incorrect",
            corrected="Je peux venir demain.", key="d", flagged="de",
        ),
    ]
    assert _lines(db_session, user, concept, attempts) == [("Je peux venir demain.", True)]


def test_checked_fix_shown(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        _sentence(
            concept.id, typed="J'ai acheté des pomme de terre", verdict="incorrect",
            corrected="J'ai acheté des pommes de terre", key="d",
        ),
    ]
    assert _lines(db_session, user, concept, attempts) == [("J'ai acheté des pommes de terre", True)]


def test_level_after_last_item(db_session):
    """A recorded run: free line read as a hit at once (+1), then the model reads
    it as a miss. The sheet must say the level the learner stands on now."""

    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    other = db_session.query(GrammarConcept).filter(GrammarConcept.id != concept.id).order_by(GrammarConcept.id).first()
    state = ForgeState.seance(
        [ForgeUnit(concept.id, Role.TODAY.value, int(core.Rung.PRODUCE)), ForgeUnit(other.id, Role.DUE.value, 2)],
        length=6,
    )
    session = AtelierSession(
        user_id=user.id, selected_concept_ids=[concept.id, other.id], status="in_progress", quote_payload={},
        started_at=datetime.now(UTC),
    )
    db_session.add(session)
    db_session.flush()
    _store_state(session, state)
    service = ForgeService(db_session)

    # The rule's last item: a free sentence at «produce». The instant detector
    # hit climbs the staircase; the relecture then says «not yet».
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, concept_id=concept.id,
        round="sentence", mode="sentence", exercise_id="forge:x:sentence:z",
        prompt_payload={"items": [{"id": "z"}]}, answer_payload={"text": "Je ne mange pas pomme"},
        correction_payload={
            "assessment_status": "provisional", "local_check": {"detector": "hit"},
        },
        verdict="accepted", score_0_4=3.0,
    )
    db_session.add(attempt)
    db_session.flush()
    service.observe_attempt(user=user, session=session, attempt=attempt)
    assert core.step_rung(core.Rung.PRODUCE, core.Verdict(core.OUTCOME_INCORRECT, checked=False, local=core.OUTCOME_CORRECT)) == core.Rung.FREE_USE
    attempt.verdict = "incorrect"
    attempt.score_0_4 = 1.0
    attempt.correction_payload = {"assessment_status": "checked", "checked": True}
    service.amend_attempt(user=user, session=session, attempt=attempt)
    db_session.refresh(session)

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    rule = next(row for row in recap["forge"]["rules"] if row["concept_id"] == concept.id)
    # The last (and only) item of the rule was posed at «produce» and missed:
    # the learner stands on «produce», not on «free use».
    assert rule["rung"] == int(core.Rung.PRODUCE), (
        f"the sheet says level {rule['rung'] + 1} for a rule whose last item was a miss at level "
        f"{int(core.Rung.PRODUCE) + 1}"
    )


@pytest.mark.parametrize(
    ("prompt", "verdict", "answer"),
    [
        ("Tu ___ malade ? Tu devrais rester au lit. (You (informal) are ill? You should stay in bed.)", "correct", "es"),
        ("Tu ___ malade ? Tu devrais rester au lit. (You (informal) are ill? You should stay in bed.)", "incorrect", "est"),
        ("Tu ___ (être) malade ? Tu devrais rester au lit.", "correct", "es"),
    ],
    ids=["nested-gloss-kept", "nested-gloss-missed", "cue-beside-gap"],
)
def test_a_gap_line_prints_no_english_and_no_cue(prompt, verdict, answer):
    """A bank gloss can hold its own brackets («(You (informal) …)»): the sheet's
    line is the French alone, as the repair field reads it, kept or missed."""

    item = {"id": "f", "prompt": prompt, "choices": ["es", "est"], "correct_answer": "es"}
    attempt = SimpleNamespace(
        correction_payload={"assessment_status": "checked"},
        verdict=verdict,
        prompt_payload={"items": [item]},
        answer_payload={"answers": {"f": answer}},
        round="recognize",
        mode="fill",
    )
    assert AtelierSRSService._forge_proof_line(attempt) == (
        "Tu es malade ? Tu devrais rester au lit.",
        verdict != "correct",
    )


#: #927 (walk of 19 Nov): the spot item, its key, and the right variant the learner wrote.
SPOT_927 = {
    "id": "t927",
    "type": "spot",
    "instruction": "Fix the mistake.",
    "source": "Vous avez chercher les clés hier.",
    "source_fr": "Vous avez chercher les clés hier.",
    "expected_answer": "Vous avez cherché les clés hier.",
    "accepted_answers": ["Tu as cherché les clés hier."],
}


@pytest.mark.parametrize(
    ("verdict", "answer", "line"),
    [
        ("correct", "Tu as cherché les clés hier.", "Tu as cherché les clés hier."),
        ("correct", "tu as cherché les clés hier", "Tu as cherché les clés hier."),
        ("correct", "Vous avez cherché les clés hier.", "Vous avez cherché les clés hier."),
        ("correct", "cherché", "Vous avez cherché les clés hier."),
        ("incorrect", "Tu as cherchée les clés hier.", "Vous avez cherché les clés hier."),
    ],
    ids=["variant", "variant-typo", "key", "part", "miss"],
)
def test_right_rewrite_line(verdict, answer, line):
    """#927: «Tu as cherché les clés hier.» was right; the sheet listed «Vous avez cherché
    les clés hier.», a sentence the learner never wrote. A right answer is the accepted line
    it was read as (the learner's sentence in its authored spelling); a miss shows the key."""

    attempt = SimpleNamespace(
        correction_payload={"assessment_status": "checked"},
        verdict=verdict,
        prompt_payload={"items": [dict(SPOT_927)]},
        answer_payload={"answers": {"t927": answer}},
        round="transform",
        mode="transform",
    )
    assert AtelierSRSService._forge_proof_line(attempt) == (line, verdict != "correct"), (
        f"the end sheet's line for «{answer}» ({verdict})"
    )


def test_right_rewrite_accent_restored():
    """#927 (23 Nov): a right variant accepted up to an accent is printed as a model, with
    the accent the judge named."""

    attempt = SimpleNamespace(
        correction_payload={"assessment_status": "checked"},
        verdict="correct",
        prompt_payload={"items": [dict(SPOT_927)]},
        answer_payload={"answers": {"t927": "Tu as cherché les cles hier."}},
        round="transform",
        mode="transform",
    )
    assert AtelierSRSService._forge_proof_line(attempt) == ("Tu as cherché les clés hier.", False)


@pytest.mark.parametrize(
    ("verdict", "answer", "line"),
    [
        ("correct", "etes", "Avant-hier, vous êtes arrivés en retard."),
        ("correct", "êtes", "Avant-hier, vous êtes arrivés en retard."),
        ("incorrect", "avez", "Avant-hier, vous êtes arrivés en retard."),
    ],
    ids=["accent-slip", "exact", "miss"],
)
def test_right_gap_accent_restored(verdict, answer, line):
    """#927 (walk of 23 Nov): «Still practising: Avant-hier, vous etes arrivés en retard.»
    The typed gap was right up to its accent («Right — watch the accent: «êtes».»), and the
    sheet printed the learner's «etes» as the model line."""

    item = {"id": "g", "prompt": "Avant-hier, vous ___ arrivés en retard.", "correct_answer": "êtes"}
    attempt = SimpleNamespace(
        correction_payload={"assessment_status": "checked"},
        verdict=verdict,
        prompt_payload={"items": [item]},
        answer_payload={"answers": {"g": answer}},
        round="recognize",
        mode="fill",
    )
    assert AtelierSRSService._forge_proof_line(attempt) == (line, verdict != "correct"), (
        f"the end sheet's line for «{answer}» ({verdict})"
    )


def test_right_variant_is_the_corrected_line():
    """#927: the corrector records a right variant as the line it accepted, not the key,
    and its accent note names that line («watch the accent» on a sentence never written
    was the same flaw)."""

    from app.services.atelier import AtelierCorrectionService

    correction = AtelierCorrectionService(None)._correct_transform_rule_based(
        None, {"items": [dict(SPOT_927)]}, {"answers": {"t927": "Tu as cherché les cles hier."}}
    )
    assert correction["verdict"] == "correct"
    assert correction["corrected_answer"] == {"t927": "Tu as cherché les clés hier."}, (
        "the corrector filed the key «Vous avez cherché les clés hier.» for the learner's right «Tu as …»"
    )
    assert [note["corrected_target"] for note in correction["accent_notes"]] == ["Tu as cherché les clés hier."]
