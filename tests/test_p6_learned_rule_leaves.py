"""P6 stage 1 — one grammar step a day, and a rule that is learned leaves.

The 17 Nov experience review (finding 3): A1 «être» came back as La Forge's rule
on days 2 and 5 at Level 6 (the top), and four more times after an absence; at
B1 one rule stayed the daily rule for four days. La Forge ran 9–13 items against
«about five minutes».

* A rule at the top rung whose last séance had no checked miss is not the day's
  anchor again while another rule qualifies; when its review is due it may sit
  beside the anchor as the review. Alone, it is still the day's rule (never an
  empty step).
* A séance on a stored pace deals at most eight items, reprises included.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Verdict
from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services import forge_picker
from app.services.forge import _store_state

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def _concept(db: Session, name: str, order: int) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A1_P6_{uuid.uuid4().hex[:8]}",
        language="fr",
        name=name,
        level="A1",
        category="Grammaire",
        difficulty_order=order,
        active=True,
    )
    db.add(concept)
    db.flush()
    return concept


def _learner(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"p6-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
        timezone="UTC",
        daily_pace="normal",
    )
    db.add(user)
    db.flush()
    return user


def _last_seance(db: Session, user: User, concept_id: int, *, missed: bool) -> None:
    """Yesterday's séance on this rule, climbing to the top; one checked miss when ``missed``."""

    state = ForgeState.seance([ForgeUnit(concept_id, "today", rung=int(core.TOP_RUNG) - 1)], length=8)
    if missed:
        state.record(concept_id=concept_id, rung=int(core.TOP_RUNG) - 1, verdict=Verdict.wrong())
    state.record(concept_id=concept_id, rung=int(core.TOP_RUNG) - 1, verdict=Verdict.right())
    state.record(concept_id=concept_id, rung=int(core.TOP_RUNG), verdict=Verdict.right())
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept_id],
        status="completed",
        quote_payload={},
        started_at=NOW - timedelta(days=1),
        completed_at=NOW - timedelta(days=1),
    )
    _store_state(session, state)
    db.add(session)
    db.flush()


def _two_rules(db: Session, *, a_due: bool = False, a_missed: bool = False, with_b: bool = True):
    """Rule A at Level 6 after yesterday's séance; rule B in progress, further along its schedule."""

    db.query(GrammarConcept).update({"active": False})
    user = _learner(db)
    etre = _concept(db, "Être", 1)
    db.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=etre.id,
            score=7.0,
            reps=4,
            # The weakest by stability: before P6 it is the anchor every day.
            stability=1.0,
            introduced_at=NOW - timedelta(days=4),
            last_review=NOW - timedelta(days=1),
            next_review=NOW - timedelta(hours=1) if a_due else NOW + timedelta(days=4),
            forge_rung=int(core.TOP_RUNG),
        )
    )
    other = None
    if with_b:
        other = _concept(db, "Avoir", 2)
        db.add(
            UserGrammarProgress(
                user_id=user.id,
                concept_id=other.id,
                score=5.0,
                reps=2,
                stability=3.0,
                introduced_at=NOW - timedelta(days=2),
                last_review=NOW - timedelta(days=1),
                next_review=NOW + timedelta(days=2),
                forge_rung=2,
            )
        )
    db.flush()
    _last_seance(db, user, etre.id, missed=a_missed)
    return user, etre, other


def test_rule_at_top_leaves(db_session: Session) -> None:
    """Level 6 on A after a clean séance, B in progress: tomorrow's anchor is B."""

    user, etre, avoir = _two_rules(db_session)

    plan = forge_picker.forge_plan(db_session, user, NOW, origin="journey")

    assert plan.anchor is not None
    assert plan.anchor.concept_id == avoir.id, "a rule learned to the top is the day's rule again"
    assert etre.id not in plan.concept_ids, "a rule whose review is not due sits beside it"


def test_resting_rule_due_is_review(db_session: Session) -> None:
    """A's review is due: A may come as the review, never as the anchor."""

    user, etre, avoir = _two_rules(db_session, a_due=True)

    plan = forge_picker.forge_plan(db_session, user, NOW, origin="journey")

    assert plan.anchor is not None and plan.anchor.concept_id == avoir.id
    roles = {unit.concept_id: unit.role for unit in plan.units}
    assert roles.get(etre.id) in (None, forge_picker.ROLE_DUE)


def test_miss_keeps_rule(db_session: Session) -> None:
    """A checked miss in A's last séance keeps it in the rotation (the weakest stays first)."""

    user, etre, _avoir = _two_rules(db_session, a_missed=True)

    plan = forge_picker.forge_plan(db_session, user, NOW, origin="journey")

    assert plan.anchor is not None and plan.anchor.concept_id == etre.id


def test_lone_rule_never_empty(db_session: Session) -> None:
    """Nothing else qualifies: the resting rule is still the day's rule, never an empty step."""

    user, etre, _none = _two_rules(db_session, with_b=False)

    plan = forge_picker.forge_plan(db_session, user, NOW, origin="journey")

    assert plan.anchor is not None and plan.anchor.concept_id == etre.id


def test_preferred_rule_wins(db_session: Session) -> None:
    """The day's own rule (the card's, #587's ``preferred_concept_id``) wins even at the top."""

    user, etre, _avoir = _two_rules(db_session)

    plan = forge_picker.forge_plan(db_session, user, NOW, origin="journey", preferred_concept_id=etre.id)

    assert plan.anchor is not None and plan.anchor.concept_id == etre.id


# ---------------------------------------------------------------------------
# At most eight items on a stored pace
# ---------------------------------------------------------------------------


class _OneRule:
    def __init__(self, concept_id: int) -> None:
        self.concept_id = concept_id

    def pick(self, user, *, now):  # noqa: ANN001 - the Composer protocol
        from app.services.forge import PickedUnit

        return [PickedUnit(self.concept_id, "today")]


def test_normal_seance_max_eight(db_session: Session) -> None:
    """A séance at «Normal» deals at most eight items, even with three checked misses."""

    from app.services.forge import ForgeService, forge_state_of
    from tests.test_forge_integration import _forge_session

    user, concept, session, _shared = _forge_session(db_session, "FR_A2_NEG_001")
    user.daily_pace = "normal"
    db_session.add(user)
    db_session.commit()
    service = ForgeService(db_session)
    service.attach(user=user, session=session, composer=_OneRule(concept.id))
    db_session.commit()

    dealt = 0
    misses = 0
    for _ in range(40):
        view = service.view(user=user, session=session)
        if view["finished"] or view["next"] is None:
            break
        item = view["next"]
        state = forge_state_of(session)
        verdict = Verdict.wrong() if misses < 3 else Verdict.right()
        misses += verdict.outcome == core.OUTCOME_INCORRECT
        state.record(concept_id=concept.id, rung=int(item["rung"]), verdict=verdict, fingerprint=item["fingerprint"])
        _store_state(session, state)
        db_session.commit()
        dealt += 1

    assert misses == 3
    assert dealt <= 8, f"La Forge dealt {dealt} items at «Normal»"


def test_home_quotes_eight_items() -> None:
    """Home's grammar step quotes what the séance deals: eight items, four minutes."""

    from app.services.daily_session import PACES, forge_items, minutes

    for pace in PACES.values():
        assert forge_items(pace.forge_seconds) == 8
    assert minutes(forge_items(PACES["normal"].forge_seconds) * 25) == 4
