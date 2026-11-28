# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""#1108 — on a day that plans no rule, «Forge today's rule» is never a due slip's rule.

Walk of 27 Nov 2026, ``a2-en`` day 2: day 1 taught avoir and a La Forge slip on
it came due. Day 2's page (the tentpole ``t1b``) uses none of the learner's next
units, so the plan stored ``introduction: null`` and the forge entry fell back to
the picker. The picker ranked a due erratum's rule above the quota's new rule:
La Forge opened as «Forge today's rule» on avoir again (``reason='due_erratum'``).

Owner decision of 7 Nov («Nur als Extra», #443/#576/#587): a repair rule from the
learner's slips never takes the «today's rule» slot; it comes back only as a
labelled review.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.daily_journey import DailyJourney
from app.db.models.error import UserError
from app.db.models.grammar import UserGrammarProgress
from app.db.models.user import User
from app.services import concept_life, forge_picker
from app.services.daily_journey import todays_planned_rule_id
from app.services.grammar import GrammarService, apply_grammar_evidence
from tests.test_taught_rule_698 import read_rule_card
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture

DAY1 = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)
DAY2 = DAY1 + timedelta(days=1)


def _a2_learner(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"forge-1108-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
        cefr_estimate="A2.1",
        daily_goal_minutes=10,
    )
    db.add(user)
    db.commit()
    return user


def _day_one(db: Session, user: User) -> int:
    """Day 1: the rule card (introduced, read), La Forge works it, one slip on it comes due."""

    brief = concept_life.introduction_for_today(db, user, now=DAY1, control_language="en")
    assert brief is not None, "day 1 introduces the learner's first rule"
    rule_id = int(brief["concept_id"])
    read_rule_card(db, user, rule_id, at=DAY1)
    progress = GrammarService(db).get_or_create_progress(user_id=user.id, concept_id=rule_id)
    progress.forge_rung = 4
    for _ in range(3):
        apply_grammar_evidence(progress, Evidence(EvidenceFormat.PRODUCE, correct=True), now=DAY1, score=8.0)
    db.add(progress)
    db.add(
        UserError(
            user_id=user.id,
            concept_id=rule_id,
            error_category="grammar",
            error_pattern="preposition",
            original_text="ils ont écouté à",
            correction="ils ont écouté",
            next_review_date=DAY2 - timedelta(hours=1),
            occurrences=1,
        )
    )
    db.commit()
    return rule_id


def _day_two_journey(db: Session, user: User, introduction: dict | None) -> DailyJourney:
    journey = DailyJourney(
        user_id=user.id,
        local_date=date(DAY2.year, DAY2.month, DAY2.day),
        timezone="UTC",
        status="active",
        plan_selection={"introduction": introduction, "because": {"kind": "erratum"}},
    )
    db.add(journey)
    db.commit()
    return journey


def test_a_day_without_a_planned_rule_forges_the_quotas_new_rule_not_the_slips(db_session: Session, v2) -> None:
    user = _a2_learner(db_session)
    slip_rule = _day_one(db_session, user)
    _day_two_journey(db_session, user, introduction=None)  # t1b: the page uses none of the next units

    # The plan has no rule for today: the forge entry falls back to the picker.
    assert todays_planned_rule_id(db_session, user, now=DAY2) is None
    quota_rule = concept_life.introduction_for_today(db_session, user, now=DAY2, control_language="en")
    assert quota_rule is not None and int(quota_rule["concept_id"]) != slip_rule

    for origin in ("journey", "after_day", None):
        plan = forge_picker.forge_plan(db_session, user, DAY2, origin=origin)
        anchor = plan.anchor
        assert anchor is not None and anchor.role == "today"
        assert (anchor.concept_id, plan.reason) != (slip_rule, "due_erratum"), (
            f"origin={origin}: «Forge today's rule» opened on the due slip's rule (#1108): {plan.units}"
        )
        assert plan.reason != "due_erratum"
        assert anchor.concept_id == int(quota_rule["concept_id"]), plan.units
        assert plan.reason == forge_picker.REASON_NEW_FROM_QUOTA
        # The slip's rule comes back only beside it, as a review.
        assert all(unit.role != "today" for unit in plan.units if unit.concept_id == slip_rule)
        if origin is None:
            # A practice forge keeps the full mix: the slip's rule is repaired as a due unit.
            assert (slip_rule, "due") in plan.pairs(), plan.units


def test_with_no_quota_left_today_is_the_weakest_rule_in_progress(db_session: Session, v2, monkeypatch) -> None:
    from app.services.atelier import AtelierScheduler

    user = _a2_learner(db_session)
    slip_rule = _day_one(db_session, user)
    # A second rule in progress, weaker than the slip's rule; the week's quota is spent.
    weaker_id = AtelierScheduler(db_session).next_new_concepts(user, limit=1, language="fr")[0].id
    assert weaker_id != slip_rule
    db_session.add(
        UserGrammarProgress(
            user_id=user.id, concept_id=weaker_id, score=1.0, reps=1, stability=0.1, forge_rung=1,
            introduced_at=DAY1, next_review=DAY2 + timedelta(days=3),
        )
    )
    db_session.commit()
    monkeypatch.setattr(concept_life, "introduction_due", lambda *args, **kwargs: False)

    plan = forge_picker.forge_plan(db_session, user, DAY2, origin="journey")

    assert plan.reason != "due_erratum", f"no quota left, and the slip's rule took «today's rule»: {plan.units}"
    assert (plan.anchor.concept_id, plan.reason) == (weaker_id, forge_picker.REASON_WEAKEST_IN_PROGRESS), plan.units
    assert all(unit.role != "today" for unit in plan.units if unit.concept_id == slip_rule)


def test_a_planned_rule_keeps_its_slot(db_session: Session, v2) -> None:
    user = _a2_learner(db_session)
    _day_one(db_session, user)
    quota_rule = concept_life.introduction_for_today(db_session, user, now=DAY2, control_language="en")
    assert quota_rule is not None
    planned = int(quota_rule["concept_id"])
    _day_two_journey(db_session, user, introduction={"concept_id": planned, "title_native": "x"})

    assert todays_planned_rule_id(db_session, user, now=DAY2) == planned
    plan = forge_picker.forge_plan(
        db_session, user, DAY2, preferred_concept_id=planned, origin="journey"
    )
    assert (plan.anchor.concept_id, plan.reason) == (planned, forge_picker.REASON_PREFERRED)
