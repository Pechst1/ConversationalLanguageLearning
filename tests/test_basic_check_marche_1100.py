"""#1100: «a le marche» is not «la marche», and a basic-check fix is never tomorrow's key.

Day-7 walk, 26 Nov: the learner wrote «Il y a un ordinateur a le marche.» (for «au marché»).
With no full check, the basic check printed «le → la», and the next day La Forge dealt the
line as «Ta phrase» with «… a la marche.» as its key and raised the rule's level for it.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.forge import Rung
from app.db.models.atelier import AtelierAttempt
from app.services import correction_contract as cc
from app.services.error_memory import ErrorMemoryService
from tests.test_forge_drills import _forge_seance

WALK_LINE = "Il y a un ordinateur a le marche."


def test_walk_line_keeps_its_article():
    edits = cc.deterministic_edits(WALK_LINE)
    assert not [e for e in edits if e.rule_id == "FR_GENDER_DET"], "«le marche» was read as a gender slip"
    assert "la marche" not in cc.repair_text(WALK_LINE)


@pytest.mark.parametrize(
    ("line", "fixed"),
    [
        ("Je regarde le marche.", "Je regarde le marché."),
        ("Je vais a le marche.", "Je vais au marché."),
        ("Le marche est grand.", "Le marché est grand."),
        ("Il regarde le cote.", "Il regarde le côté."),
    ],
)
def test_the_accent_is_the_slip(line: str, fixed: str):
    assert cc.repair_text(line) == fixed
    assert cc.repair_text(fixed) == fixed


@pytest.mark.parametrize(
    ("line", "fixed"),
    [
        ("J'aime la marche.", "J'aime la marche."),
        ("Elle prend le voiture.", "Elle prend la voiture."),
        ("Il a le tache.", "Il a la tache."),
    ],
)
def test_real_gender_slips_stay(line: str, fixed: str):
    assert cc.repair_text(line) == fixed


def _attempt(db: Session, user, concept, session, *, status: str) -> AtelierAttempt:
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="sentence",
        mode="sentence",
        exercise_id="x",
        prompt_payload={},
        answer_payload={"text": "Elle prend le voiture demain."},
        correction_payload={
            "assessment_status": status,
            "errata": [
                {
                    "learner_text": "le voiture",
                    "corrected_target": "la voiture",
                    "why_wrong": "« voiture » est féminin.",
                    "task_error_type": "gender_agreement",
                    "error_category": "grammar",
                    "severity": 2,
                }
            ],
        },
        verdict="needs_review" if status == "unavailable" else "incorrect",
        score_0_4=1.0,
    )
    db.add(attempt)
    db.commit()
    return attempt


@pytest.mark.parametrize(("status", "posed"), [("unavailable", False), ("checked", True)])
def test_only_a_full_checks_fix_becomes_ta_phrase(db_session: Session, status: str, posed: bool):
    from app.services.forge import BankItemProvider

    user, concept, session, _forge = _forge_seance(db_session, rung=Rung.TRANSFORM)
    attempt = _attempt(db_session, user, concept, session, status=status)
    updates = ErrorMemoryService(db_session).record_atelier_attempt(user=user, attempt=attempt)
    db_session.commit()
    assert updates, "the slip was not saved at all"
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    found = provider.mine_candidates(concept.id)
    assert bool(found) is posed, f"{status}: {found}"
