# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""#895 — a rule only slipped on in a scene spends no slot of the week's intake.

18 Nov explore walk (``a1-de-fresh``): day 1's scene slip «le appartement»
stamped «Le, la, l', les» as introduced; no card ever showed it. Day 1 taught
être. On day 2 ``introductions_in_window`` returned the slip's stamp alone
(être was tested out), so ``introduction_due`` said no new rule: the slip spent
the week's intake and set its spacing.

``introduced_at`` has two writers: the Règle read (``mark_introduced``) and the
first evidence on any surface (``note_concept_evidence``). The intake counts
only rules the learner was taught (``rule_was_taught`` or a rule card read).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat
from app.services import concept_life, vocabulary_pace
from app.services.grammar import GrammarService, apply_grammar_evidence
from tests.test_atelier import _concept
from tests.test_daily_journey_state import make_user
from tests.test_taught_rule_698 import read_rule_card

DAY1 = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _unthrottled(monkeypatch):
    # The week's rate is the rhythm's own: no review backlog halves it here.
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *a, **k: 1.0)


def _learner(db: Session, *, minutes: int):
    user = make_user(db, f"intake-895-{uuid.uuid4().hex[:8]}@example.com")
    user.daily_goal_minutes = minutes
    db.commit()
    return user


def _slip(db: Session, user, concept_id: int, *, at: datetime) -> None:
    """A scene reply corrected on this rule: one miss filed, no card shown."""

    progress = GrammarService(db).get_or_create_progress(user_id=user.id, concept_id=concept_id)
    apply_grammar_evidence(progress, Evidence(EvidenceFormat.PRODUCE, correct=False), now=at)
    db.add(progress)
    db.commit()


def test_intake_counts_taught_not_slip(db_session: Session) -> None:
    user = _learner(db_session, minutes=10)
    taught = _concept(db_session, "FR_A1_VERB_001")
    slipped = _concept(db_session, "FR_A1_ART_001")

    # Day 1: the rule card for the present-tense verbs is read, and La Forge works it.
    read_rule_card(db_session, user, taught.id, at=DAY1)
    progress = GrammarService(db_session).get_or_create_progress(user_id=user.id, concept_id=taught.id)
    progress.forge_rung = 1
    db_session.add(progress)
    db_session.commit()
    # The scene's correction of «le appartement» files a miss on the articles.
    _slip(db_session, user, slipped.id, at=DAY1 + timedelta(hours=1))
    stamp = concept_life._aware(progress.introduced_at)

    day2 = DAY1 + timedelta(days=1)
    assert concept_life.introductions_in_window(db_session, user, now=day2) == [stamp], (
        "the week's intake counted «Le, la, l', les», a rule the learner only slipped on in a scene"
    )

    # Day 1's La Forge épreuve: the learner tests out of it.
    progress.tested_out_at = DAY1 + timedelta(hours=2)
    progress.held_at = progress.tested_out_at
    db_session.add(progress)
    db_session.commit()

    assert concept_life.introductions_in_window(db_session, user, now=day2) == [], (
        "the slip-only stamp still spends a slot of the week's intake"
    )
    assert concept_life.introduction_due(db_session, user, now=day2), (
        "day 2 plans no new rule because of a scene slip on day 1"
    )


def test_slip_sets_no_spacing(db_session: Session) -> None:
    # Léger: two new rules a week, three days apart.
    user = _learner(db_session, minutes=5)
    slipped = _concept(db_session, "FR_A1_ART_001")
    assert concept_life.introduction_due(db_session, user, now=DAY1)

    _slip(db_session, user, slipped.id, at=DAY1 + timedelta(hours=1))

    assert concept_life.introduction_due(db_session, user, now=DAY1 + timedelta(days=1)), (
        "a slip in day 1's scene set the spacing: day 2 gets no new rule"
    )


def test_slips_spend_no_quota(db_session: Session) -> None:
    user = _learner(db_session, minutes=5)
    for offset, external_id in enumerate(("FR_A1_ART_001", "FR_A1_VERB_001")):
        concept = _concept(db_session, external_id)
        _slip(db_session, user, concept.id, at=DAY1 + timedelta(days=offset * 3))

    later = DAY1 + timedelta(days=5)
    assert concept_life.introductions_in_window(db_session, user, now=later) == [], (
        "two scene slips were counted as the week's new rules"
    )
    assert concept_life.introduction_due(db_session, user, now=later), (
        "two scene slips used up Léger's two new rules this week"
    )


def test_card_read_spends_a_slot(db_session: Session) -> None:
    user = _learner(db_session, minutes=5)
    taught = _concept(db_session, "FR_A1_VERB_001")
    read_rule_card(db_session, user, taught.id, at=DAY1)

    assert len(concept_life.introductions_in_window(db_session, user, now=DAY1 + timedelta(hours=1))) == 1
    assert not concept_life.introduction_due(db_session, user, now=DAY1 + timedelta(days=1))
    assert concept_life.introduction_due(db_session, user, now=DAY1 + timedelta(days=3))
