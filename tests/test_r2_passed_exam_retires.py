"""R2 item 2: a rule whose épreuve was passed is not the day's rule again until its
spaced review is due; when nothing else qualifies the day's grammar is a short review.

Real play, 17 Nov (A1, de): the être épreuve was passed on day 2 («Ab heute gilt sie
als gefestigt»); être was La Forge's rule again on days 5 and 6. The pass is stored
(``held_at``, ``tested_out_at``, ``forge_rung`` at the top) and the «weakest in
progress» step skips held rules — but the anchor's first step after «introduced
today» is a due *erratum*: an old slip on être due for review made être the day's
rule, held or not (and «most due» did the same, the erratum's rule counting as due).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.core import forge as core
from app.db.models.grammar import UserGrammarProgress
from app.services import forge_picker
from tests.test_p6_learned_rule_leaves import NOW, _concept, _learner


def _passed_exam(db: Session, *, review_in: timedelta, with_other: bool = True):
    from app.db.models.grammar import GrammarConcept

    db.query(GrammarConcept).update({"active": False})
    user = _learner(db)
    etre = _concept(db, "Être", 1)
    db.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=etre.id,
            score=7.0,
            reps=4,
            stability=1.0,
            introduced_at=NOW - timedelta(days=4),
            last_review=NOW - timedelta(days=3),
            next_review=NOW + review_in,
            # What ``ForgeService._finish_test_out`` writes on a pass.
            tested_out_at=NOW - timedelta(days=3),
            held_at=NOW - timedelta(days=3),
            forge_rung=int(core.TOP_RUNG),
        )
    )
    other = None
    if with_other:
        other = _concept(db, "Il y a", 2)
        db.add(
            UserGrammarProgress(
                user_id=user.id, concept_id=other.id, score=5.0, reps=2, stability=3.0,
                introduced_at=NOW - timedelta(days=2), last_review=NOW - timedelta(days=1),
                next_review=NOW + timedelta(days=2), forge_rung=3,
            )
        )
    db.flush()
    return user, etre, other


def _anchor(db: Session, user, *, errata, due):
    rows = forge_picker._progress_rows(db, user, "fr")
    return forge_picker._anchor(
        db, user, now=NOW, language="fr", rows=rows, preferred_concept_id=None,
        errata_ids=list(errata), due_ids=list(due),
    )


def test_due_slip_on_a_passed_rule_does_not_make_it_the_days_rule(db_session: Session) -> None:
    user, etre, il_y_a = _passed_exam(db_session, review_in=timedelta(days=2))

    concept_id, reason, _new = _anchor(db_session, user, errata=[etre.id], due=[etre.id])

    assert concept_id == il_y_a.id, f"the passed rule came back as the day's rule ({reason})"


def test_passed_rule_returns_when_its_review_is_due(db_session: Session) -> None:
    user, etre, _other = _passed_exam(db_session, review_in=-timedelta(hours=1), with_other=False)

    concept_id, _reason, _new = _anchor(db_session, user, errata=[], due=[etre.id])

    assert concept_id == etre.id


def test_nothing_else_qualifies_short_review(db_session: Session) -> None:
    """Only the passed rule is left: the day's grammar is a review of at most four items."""

    from app.services.daily_session import forge_items
    from app.services.forge import day_seance_max_items

    user, etre, _other = _passed_exam(db_session, review_in=timedelta(days=2), with_other=False)

    concept_id, reason, _new = _anchor(db_session, user, errata=[etre.id], due=[etre.id])

    assert concept_id == etre.id and reason == forge_picker.REASON_KEEP_WARM
    assert forge_picker.short_review_anchor(db_session, user, etre.id)
    cap = day_seance_max_items(db_session, user, etre.id)
    assert cap == forge_picker.SHORT_REVIEW_ITEMS == 4
    assert forge_items(300, cap) == 4, "Home quotes the short review, not eight items"


def test_rule_in_progress_keeps_a_full_seance(db_session: Session) -> None:
    from app.services.forge import day_seance_max_items

    user, _etre, il_y_a = _passed_exam(db_session, review_in=timedelta(days=2))

    assert not forge_picker.short_review_anchor(db_session, user, il_y_a.id)
    assert day_seance_max_items(db_session, user, il_y_a.id) == core.PACE_MAX_SEANCE_ITEMS
