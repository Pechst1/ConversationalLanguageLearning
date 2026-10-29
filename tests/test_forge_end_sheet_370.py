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
) -> AtelierAttempt:
    return AtelierAttempt(
        concept_id=concept_id,
        round="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept_id}:sentence:{key}",
        prompt_payload={"items": [{"id": key, "example_answer": example}]},
        answer_payload={"text": typed},
        correction_payload={"checked": True, **({"corrected_answer": corrected} if corrected else {})},
        verdict=verdict,
        score_0_4=4.0 if verdict in {"correct", "accepted"} else 1.0,
    )


def _lines(db_session, user, concept, attempts) -> list[tuple[str, bool]]:
    progress = AtelierSRSService(db_session)._forge_rule_progress(
        user=user, concept_id=concept.id, stage_before="introduced", attempts=attempts, started_at=None
    )
    return [(line["fr"], line["fixed"]) for line in progress["proof"]]


def test_a_kept_line_is_what_the_learner_wrote_not_a_clipped_echo(db_session):
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


def test_a_missed_free_line_is_never_replaced_by_the_models_example(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        # Wrong, and the checker gave no correction: the item's example_answer
        # is the model's sentence, not the learner's and not a correction of it.
        _sentence(concept.id, typed="Je acheté des pomme", verdict="incorrect", example="J'ai acheté des pommes", key="b"),
    ]
    assert _lines(db_session, user, concept, attempts) == []


def test_a_correction_that_only_drops_words_is_not_shown_as_a_fix(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        _sentence(
            concept.id, typed="J'ai acheté des pomme de terre", verdict="incorrect",
            corrected="J'ai acheté des pomme", key="c",
        ),
    ]
    assert _lines(db_session, user, concept, attempts) == []


def test_a_checked_correction_of_a_miss_is_shown_as_fixed(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    attempts = [
        _sentence(
            concept.id, typed="J'ai acheté des pomme de terre", verdict="incorrect",
            corrected="J'ai acheté des pommes de terre", key="d",
        ),
    ]
    assert _lines(db_session, user, concept, attempts) == [("J'ai acheté des pommes de terre", True)]


def test_the_level_on_the_sheet_is_the_level_after_the_rules_last_item(db_session):
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
