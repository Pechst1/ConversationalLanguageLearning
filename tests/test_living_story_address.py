"""The learner's stored address preference reaches the story engine.

The engine used to have no idea how to address the learner, so characters
alternated "ma puce" and "mon grand" and once wrote "trempé·e". The learner now
sets this in Settings; these tests check the value travels from the account into
the context every prompt sees, and that the prompts actually bind to it.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.core.security import get_password_hash
from app.db.models.user import User
from app.services import living_story as engine
from tests import test_journey_end_to_end as support
from tests.test_living_story import FakeProvider

Driver = support.Driver
register = support.register
assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

VALUES = ("feminine", "masculine", "neutral")


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    fake = FakeProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def make_user(db, address_preference=None) -> User:
    user = User(
        email=f"address-{uuid4()}@example.com",
        hashed_password=get_password_hash("verysecure"),
        native_language="en",
        target_language="fr",
        cefr_estimate="A1.1",
    )
    if address_preference is not None:
        user.address_preference = address_preference
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.mark.parametrize("value", VALUES)
def test_story_context_carries_the_learner_address(db_session, value):
    user = make_user(db_session, value)

    context = engine.story_context(db_session, user)

    assert context["learner"]["address"] == value
    assert context["learner"]["grammatical_gender_note"].strip()
    # The context must stay JSON-serialisable: it is sent to the model verbatim.
    assert json.loads(json.dumps(context, default=str))["learner"]["address"] == value


def test_neutral_note_forbids_the_inclusive_dot(db_session):
    note = engine.story_context(db_session, make_user(db_session, "neutral"))["learner"][
        "grammatical_gender_note"
    ]

    assert "trempé·e" in note
    assert "never" in note.lower()


def test_unset_and_unknown_preferences_fall_back_to_neutral(db_session):
    assert engine.story_context(db_session, make_user(db_session))["learner"]["address"] == (
        "neutral"
    )
    assert engine.story_context(db_session, make_user(db_session, ""))["learner"]["address"] == (
        "neutral"
    )
    # A value no prompt understands must not be forwarded as an instruction.
    stranger = SimpleNamespace(
        address_preference="ma puce", native_language="en", cefr_estimate="A1.1", id=uuid4()
    )
    assert engine.learner_address(stranger)["address"] == "neutral"


def test_director_and_actor_prompts_bind_to_the_preference():
    for prompt in (engine.DIRECTOR, engine.ACTOR):
        assert "learner.address" in prompt
        assert "endearments" in prompt
        assert "trempé·e" in prompt


def test_critic_rejects_address_that_contradicts_the_preference():
    assert "learner.address" in engine.CRITIC
    assert "gendered address" in engine.CRITIC
    assert "trempé·e" in engine.CRITIC


@pytest.mark.parametrize("value", VALUES)
def test_a_real_journey_sends_the_saved_preference_to_the_model(
    assembled_client, db_session, journey_enabled, clock, provider, value
):
    """Settings → account → the context the director and actor actually receive."""

    headers = register(assembled_client, f"story-address-{uuid4()}@example.com")
    saved = assembled_client.patch(
        "/api/v1/users/me/settings",
        json={"address_preference": value},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["address_preference"] == value

    driver = Driver(assembled_client, headers, db=db_session)
    driver.create()
    assert driver.journey["status"] == "active", driver.journey
    driver.play(answer="Je peux apporter les affiches samedi.")

    seen = [payload for schema, payload in provider.calls if schema == "SceneDraft"]
    assert seen and all(p["learner"]["address"] == value for p in seen)
    turns = [payload for schema, payload in provider.calls if schema == "SemanticTurn"]
    assert turns and all(p["story"]["learner"]["address"] == value for p in turns)
