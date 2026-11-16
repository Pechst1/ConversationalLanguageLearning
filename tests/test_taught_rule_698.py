# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""#698 — one scene slip does not make a rule «a rule you know».

11 Nov explore walk (``a2-en``, A2.1): day 1's card introduced «Passé composé
with avoir» and La Forge took it to Level 6. One scene reply said «de Odile»;
the scene corrected it and filed an error on «Le, la, l', les». Day 2 was a
tentpole page that introduced nothing: its one rule card reviewed «Le, la, l',
les» as «A rule you know», and La Forge forged it as «today's rule» at Level 1,
while yesterday's rule came only as a review.

``introduced_at`` has two meanings: the Règle read (``mark_introduced``) and the
first evidence on any surface (``note_concept_evidence``). The page review read
it as the first. A rule the learner was never shown is never the day's card.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.services import daily_journey as journey_module
from app.services.concept_life import mark_introduced
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from app.services.grammar import GrammarService, apply_grammar_evidence
from tests.test_atelier import _concept
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    enabled,
    make_user,
)


def read_rule_card(db: Session, user, concept_id: int, *, at: datetime) -> None:
    """The journey's Règle, read: a completed rule step on that day's journey, and
    ``mark_introduced`` (what ``DailyJourneyService`` does when the step completes)."""

    journey = (
        db.query(DailyJourney)
        .filter(DailyJourney.user_id == user.id, DailyJourney.local_date == at.date())
        .one_or_none()
    )
    if journey is None:
        journey = DailyJourney(user_id=user.id, local_date=at.date(), status="completed")
        db.add(journey)
        db.flush()
    ordinal = db.query(DailyJourneyStep).filter(DailyJourneyStep.journey_id == journey.id).count()
    db.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=ordinal,
            kind="rule",
            status="completed",
            completed_at=at,
            estimated_seconds=40,
            public_prompt={"concept_id": int(concept_id)},
            private_task={"concept_id": int(concept_id)},
        )
    )
    mark_introduced(db, user=user, concept_id=int(concept_id), now=at)
    db.flush()


def _day_one(db_session: Session, monkeypatch):
    """Day 1 of the walk: the card introduced (and La Forge worked) one rule;
    a scene reply slipped on another, which no card ever showed."""

    monkeypatch.setattr(journey_module.settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True, raising=False)
    user = make_user(db_session, f"taught-698-{uuid.uuid4().hex[:8]}@example.com")
    service = DailyJourneyService(db_session, build_default_adapters())
    _created, code = service.create_journey(user, create_request())
    assert code == 201
    card_rule = _concept(db_session, "FR_A2_TENSE_001")
    slip_rule = _concept(db_session, "FR_A1_ART_001")
    yesterday = datetime.now(UTC) - timedelta(days=1)

    # The Règle was read: a completed rule step, and the unit is introduced.
    read_rule_card(db_session, user, card_rule.id, at=yesterday)

    # «de Odile» → «d'Odile»: the scene's correction files a miss on the articles.
    progress = GrammarService(db_session).get_or_create_progress(user_id=user.id, concept_id=slip_rule.id)
    apply_grammar_evidence(progress, Evidence(EvidenceFormat.PRODUCE, correct=False), now=yesterday)
    db_session.add(progress)
    db_session.commit()
    return user, service, card_rule, slip_rule


def test_a_scene_slip_is_never_the_page_reviews_rule(db_session: Session, enabled, monkeypatch) -> None:
    user, service, card_rule, slip_rule = _day_one(db_session, monkeypatch)

    # Day 2's tentpole page uses the articles before the passé composé.
    review = service._page_review_for_today(user, [slip_rule.external_id, card_rule.external_id])

    assert review, "the page uses yesterday's rule: the day reviews it"
    shown = [brief["concept_id"] if isinstance(brief, dict) else getattr(brief, "concept_id", None) for brief in review]
    assert slip_rule.id not in shown, (
        "«Le, la, l', les» became «A rule you know» on day 2: the learner only slipped on it in a scene, "
        "no card ever showed it"
    )
    assert shown[0] == card_rule.id


def test_a_slip_today_is_not_the_rule_introduced_today(db_session: Session, enabled, monkeypatch) -> None:
    """The forge picker's «introduced today» anchor read the same stamp: a slip
    filed this morning made its rule today's rule for La Forge."""

    from app.services.forge_picker import REASON_INTRODUCED_TODAY, forge_plan

    monkeypatch.setattr(journey_module.settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True, raising=False)
    user = make_user(db_session, f"taught-698-{uuid.uuid4().hex[:8]}@example.com")
    slip_rule = _concept(db_session, "FR_A1_ART_001")
    now = datetime.now(UTC)
    progress = GrammarService(db_session).get_or_create_progress(user_id=user.id, concept_id=slip_rule.id)
    apply_grammar_evidence(progress, Evidence(EvidenceFormat.PRODUCE, correct=False), now=now - timedelta(minutes=5))
    db_session.add(progress)
    db_session.commit()

    plan = forge_plan(db_session, user, now=now)
    assert not (plan.reason == REASON_INTRODUCED_TODAY and plan.units and plan.units[0].concept_id == slip_rule.id), (
        "a scene slip this morning made «Le, la, l', les» the rule «introduced today»"
    )
