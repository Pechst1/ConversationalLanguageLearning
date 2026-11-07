"""#576 — one day, one rule.

The pre-scene rule card (the journey's RULE step), the Forge's «today's rule» and
the Home plan's Forge step each picked their rule on their own: the card taught
«On = nous», the Forge opened on «Les adjectifs» at Level 1. The day's rule is
the journey's rule step; the Forge entry and the Home plan name that concept.
"""
from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest

import app.services.daily_journey as journey_module
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.daily_journey import DailyJourneyService


@pytest.fixture()
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_ENABLED", True, raising=False)
    # The journey here is two rows, not a full planned scene: the snapshot is not under test.
    monkeypatch.setattr(DailyJourneyService, "snapshot", lambda self, journey: None)
    monkeypatch.setattr(journey_module.settings, "ATELIER_DAILY_JOURNEY_COHORT", "", raising=False)


def _concept(db, name: str, order: int) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A1_{uuid4().hex[:8]}",
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


def _concept_of(href: str) -> str | None:
    values = parse_qs(urlparse(href).query).get("concept")
    return values[0] if values else None


def _day_with_rule_step(db, *, review: bool = False):
    """A learner whose Forge picker would open on one rule; today's journey teaches another."""

    db.query(GrammarConcept).update({"active": False})
    user = User(
        id=uuid4(),
        email=f"one-rule-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
        timezone="UTC",
    )
    db.add(user)
    db.flush()

    # Next in teaching order, so the Forge picker's own pick: the rule it opens on by itself.
    adjectives = _concept(db, "Les adjectifs : accord et place", 5)
    # Today's rule: the scene uses it, so the pre-scene card teaches it (not read yet).
    on_we = _concept(db, "On = nous", 20)

    journey = DailyJourney(user_id=user.id, local_date=datetime.now(UTC).date(), timezone="UTC", status="active")
    db.add(journey)
    db.flush()
    prompt = {"concept_id": on_we.id, "title_native": on_we.name}
    task = {"concept_id": on_we.id}
    if review:
        prompt["review"] = True
        task = {"review_concept_id": on_we.id}
    db.add(
        DailyJourneyStep(
            journey_id=journey.id, ordinal=0, kind="rule", status="active", public_prompt=prompt, private_task=task
        )
    )
    db.flush()
    return user, adjectives, on_we


def test_forge_and_plan_follow_the_card(db_session, enabled) -> None:
    user, _adjectives, on_we = _day_with_rule_step(db_session)

    envelope = DailyJourneyService(db_session, adapters=None).get_today(user, timezone_hint="UTC")

    assert envelope.forge is not None
    assert envelope.forge.concept_id == on_we.id, "the Forge's today's rule is not the rule the card teaches"
    assert envelope.session is not None
    forge_step = next(step for step in envelope.session.steps if step.kind == "grammar")
    assert _concept_of(forge_step.href) == str(on_we.id), "the Home plan's grammar step names another rule"
    assert _concept_of(envelope.practice_href) == str(on_we.id)


def test_a_review_step_picks_no_rule(db_session, enabled) -> None:
    """A rule step that only reviews (WP-129) introduces nothing: the picker still decides."""

    user, adjectives, _on_we = _day_with_rule_step(db_session, review=True)

    envelope = DailyJourneyService(db_session, adapters=None).get_today(user, timezone_hint="UTC")

    assert envelope.forge is not None
    assert envelope.forge.concept_id == adjectives.id
