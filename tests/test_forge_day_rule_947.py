# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""#947 — the day's La Forge works on the rule the day's plan teaches, whenever its link was read.

The 20 Nov live walk (A1.1, day 38): the pre-scene card and its drills taught
«Question words: où, quand, comment, combien, quel»; the day's grammar step opened
``/atelier?mode=forge&concept=2`` and all six items were «Avoir».

Home reads the day's plan before the learner presses Start. The day is not planned
yet, so the only answer the server has for «today's rule» is the Forge picker's
(a due slip on Avoir comes first there). The page keeps that link while the day is
created and played; La Forge then seated whatever concept the link carried. The
day's rule is decided by the plan, so La Forge opened as the day's step asks the
plan when it starts.
"""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.daily_journey import DailyJourney
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import concept_life, forge_picker
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from tests.test_daily_journey_state import create_request, enabled  # noqa: F401 - fixture
from tests.test_wp_s4_one_picker import v2  # noqa: F401 - fixture

PASSWORD = "forge-secure-947"


def _learner(client: TestClient, db: Session) -> tuple[User, dict[str, str]]:
    email = f"forge-947-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "target_language": "fr",
            "native_language": "en",
            "cefr_estimate": "A1.1",
        },
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return db.query(User).filter(User.email == email).one(), {"Authorization": f"Bearer {token}"}


def _concept(db: Session, external_id: str) -> GrammarConcept:
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()
    assert concept.active
    return concept


def _grammar_link(client: TestClient, headers: dict[str, str]) -> str:
    """The day's grammar step as Home reads it («Next: grammar»)."""

    envelope = client.get("/api/v1/daily-journeys/today?timezone=Europe/Paris", headers=headers).json()
    steps = (envelope.get("session") or {}).get("steps") or []
    link = next((step.get("href") for step in steps if step.get("kind") == "grammar"), None)
    assert link, envelope.get("session")
    return link


def _open(client: TestClient, headers: dict[str, str], link: str) -> list[int]:
    """What the page sends for ``/atelier?mode=forge[&concept=…][&budget=…]&from=day``."""

    body: dict = {"origin": "after_day"}
    if match := re.search(r"[?&]concept=(\d+)", link):
        body["preferred_concept_id"] = int(match.group(1))
    if match := re.search(r"[?&]budget=(\d+)", link):
        body["budget_seconds"] = int(match.group(1))
    response = client.post("/api/v1/atelier/sessions", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return [int(unit["concept_id"]) for unit in response.json()["quote"]["forge"]["units"]]


def test_the_days_forge_opened_from_a_link_read_before_the_day_works_on_the_days_rule(
    client: TestClient, db_session: Session, v2, enabled
) -> None:
    user, headers = _learner(client, db_session)
    avoir = _concept(db_session, "FR2_A11_AVOIR")
    question_words = _concept(db_session, "FR2_A11_QUESTION_WORDS")
    now = datetime.now(UTC)
    # Avoir was taught days ago and a slip on it is due: the Forge picker's first choice.
    concept_life.mark_introduced(db_session, user=user, concept_id=avoir.id, now=now - timedelta(days=3))
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=avoir.id,
            error_category="grammar",
            error_pattern="age",
            original_text="je suis soixante-quatre ans",
            correction="j'ai soixante-quatre ans",
            next_review_date=now - timedelta(hours=1),
            occurrences=2,
        )
    )
    db_session.commit()
    assert forge_picker.forge_anchor_id(db_session, user, now) == avoir.id

    # Home, before Start: the day is not planned yet.
    read_before_the_day = _grammar_link(client, headers)

    # Start: the day's plan teaches question words before the scene.
    service = DailyJourneyService(db_session, build_default_adapters())
    created, code = service.create_journey(user, create_request())
    assert code == 201
    journey = db_session.get(DailyJourney, uuid.UUID(created.id))
    journey.plan_selection = {
        **dict(journey.plan_selection or {}),
        "introduction": {"concept_id": question_words.id, "title_native": question_words.name},
    }
    flag_modified(journey, "plan_selection")
    db_session.commit()
    concept_life.mark_introduced(db_session, user=user, concept_id=question_words.id, now=datetime.now(UTC))
    db_session.commit()

    assert f"concept={question_words.id}" in _grammar_link(client, headers), "Home now names the day's rule"

    # «Next: grammar» on the page that kept the plan it read before Start.
    units = _open(client, headers, read_before_the_day)
    assert units[0] == question_words.id, (
        f"La Forge opened as the day's step works on rule {units[0]} "
        f"({'Avoir' if units[0] == avoir.id else 'another rule'}), not on the day's rule, "
        f"question words ({question_words.id}); the link was {read_before_the_day!r}"
    )
