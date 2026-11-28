"""#1070 (root cause #147): a story letter's correspondent role comes only from the cast registry.

Walk 25 Nov 2026: Camille's day-2 letter read «Camille · Les services», and on 26 Nov
«Camille · La mairie». Camille had no row in ``cast_roles``, the story letter stored an
empty ``contact_role``, and ``correspondent_of`` filled the gap with ``domain_label``,
the label of whichever canned domain the story letter had been laid over. A person's
role is the registry's; a missing one stays empty, never borrowed from a domain.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.missions as missions_module
from app.config import settings
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import cast_registry
from app.services import story_correspondence as courrier
from app.services.living_story import STATE_KEY
from app.services.missions import MissionScheduler, serialize_mission

LANGUAGES = ("fr", "en", "de")
#: Every domain label a story letter could be laid over.
DOMAIN_LABELS = {
    str(item.get("label") or "").casefold()
    for item in missions_module.REAL_WORLD_MISSION_DOMAINS
    if item.get("label")
}


@pytest.fixture(autouse=True)
def provider_off(monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")


def _stored_story_letter(domain: str, label: str) -> SimpleNamespace:
    """Camille's day-2 story letter as the walk's database held it: laid over a canned
    domain, with the empty ``contact_role`` the unfixed letter stored."""

    return SimpleNamespace(
        correspondent_id="camille_marchand",
        prompt_payload={
            "custom_context": {"source": "story_born", "relationship": "camille_marchand"},
            "correspondence": {"correspondent_id": "camille_marchand", "origin": "story_born"},
            "messenger": {"contact_name": "Camille", "contact_role": "", "contact_initials": "CA"},
            "variety": {"domain": domain, "domain_label": label, "contact": "Camille", "channel": "sms"},
        },
    )


@pytest.mark.parametrize(
    ("domain", "label"), [("services", "Les services"), ("mairie", "La mairie")], ids=["services", "mairie"]
)
def test_stored_role(domain, label):
    """A Camille letter stored with an empty role shows her role, not the domain's."""

    identity = courrier.correspondent_of(_stored_story_letter(domain, label))
    assert identity["role"] != label, f"Camille's letter is signed «Camille · {identity['role']}»"
    assert identity["role"] == cast_registry.role("camille_marchand", "fr")


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"r1070-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _camille_scene(db_session, user: User) -> None:
    thread = SerialThread(
        id=uuid4(),
        user_id=user.id,
        status="active",
        world_bible={"cast": [{"id": "camille_marchand", "name": "Camille Marchand"}]},
        state={
            STATE_KEY: {
                "events": [
                    {
                        "id": "scene:t1b",
                        "scene_id": str(uuid4()),
                        "witnesses": ["camille_marchand"],
                        "summary_fr": "Camille est arrivée avec une clé du premier étage.",
                        "at": datetime.now(UTC).isoformat(),
                    }
                ],
                "commitments": [],
                "moods": {},
                "season_script": {"id": "s1"},
            }
        },
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.commit()


def test_story_role(db_session, monkeypatch):
    """Camille's day-2 story letter, laid over the `services` domain, is signed with her role."""

    monkeypatch.setattr(courrier, "STORY_LETTER_PROBABILITY", 1.0)
    services = next(item for item in missions_module.REAL_WORLD_MISSION_DOMAINS if item["domain"] == "services")
    # The story letter is laid over the `services` domain, as on the walk.
    monkeypatch.setattr(missions_module, "REAL_WORLD_MISSION_DOMAINS", (services,))
    user = _user(db_session)
    _camille_scene(db_session, user)
    candidate = courrier.story_letter_candidate(db_session, user=user)
    assert candidate and candidate["character_id"] == "camille_marchand"

    mission = asyncio.run(
        MissionScheduler(db_session).create(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            withhold_if_not_credible=True,
            story_letter=candidate,
        )
    )
    correspondent = serialize_mission(mission)["courrier"]["correspondent"]
    assert correspondent["name"] == "Camille"
    role = str(correspondent["role"] or "")
    assert role.casefold() not in DOMAIN_LABELS, f"the letter is signed «Camille · {role}»"
    assert role == cast_registry.role("camille_marchand", "fr")


def test_no_domain_role():
    """A letter from outside the cast never borrows the domain label as a role."""

    letter = SimpleNamespace(
        correspondent_id=None,
        prompt_payload={
            "messenger": {"contact_name": "Nadia"},
            "variety": {"domain": "services", "domain_label": "Les services"},
        },
    )
    assert courrier.correspondent_of(letter)["role"] == ""


@pytest.mark.parametrize("cast_id", sorted(cast_registry.all_members()), ids=lambda c: c.split("_")[0][:6])
def test_writer_role(cast_id):
    """Any person of the cast who speaks in a scene is a witness, and a witness can
    write a story letter (``story_letter_candidate``): each one has a role to sign with."""

    for language in LANGUAGES:
        assert cast_registry.role(cast_id, language), f"{cast_id} has no role in {language}"


def test_first_role():
    for cast_id in missions_module.FIRST_LETTER_WRITERS:
        assert cast_registry.role(cast_id, "fr"), cast_id
