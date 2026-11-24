"""#953 (child of #147): a friend's note in «tu» was framed as a formal e-mail.

Walks of 20 and 22 Nov (A1, German chrome): «Un mot de Marin» / «Un mot de Gus», two
chat lines in tu, opened the composer as «Deine E-Mail · Ein Betreff, eine Anrede, der
Text, ein Gruß» with «E-Mail senden». The letter's shape was drawn from the Courrier
domain's channel (a shop's e-mail, the town hall's form) without asking who writes, so a
story letter laid over an e-mail domain, or the format die, dressed a friend's note in
the e-mail frame.

The shape is now chosen against the writer's register: a writer in tu never sends
``email_formal`` or ``admin_form``; a writer in vous still may. No model is called.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

import app.services.missions as missions_module
from app.db.models.user import User
from app.services.missions import MissionGenerator

FORMAL = {"email_formal", "admin_form"}
SEEDS = [(f"learner-{index}", index) for index in range(200)]


def _dealt(db_session, domain: str) -> set[str]:
    generator = MissionGenerator(db_session)
    return {
        generator._choose_variety(
            active_category=None,
            recent_variety=[],
            fuel_source="vocab",
            seed=seed,
            forced_domain=domain,
        )["mission_format"]
        for seed in SEEDS
    }


def test_the_format_die_never_deals_a_formal_shape_to_a_tu_writer(db_session) -> None:
    # Noémie writes on WhatsApp in tu, Luc by text in tu: the die used to deal either
    # of them a formal e-mail about one letter in ten.
    for domain in ("social_plans", "everyday_warmth"):
        dealt = _dealt(db_session, domain)

        assert "chat_message" in dealt
        assert not dealt & FORMAL, f"the tu writer of {domain} was dealt {sorted(dealt & FORMAL)}"


def test_a_vous_writer_may_still_send_an_email(db_session) -> None:
    assert "email_formal" in _dealt(db_session, "transport"), "the e-mail frame is gone for formal writers too"
    assert "email_formal" in _dealt(db_session, "bureaucracy")


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"courrier-953-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _story_letter(db_session, *, register: str, domain: str, seed: int) -> dict:
    generator = MissionGenerator(db_session)
    payload = asyncio.run(
        generator.build_payload(
            user=_user(db_session),
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            seed=("953", seed),
            # The story letter is laid over a drawn Courrier domain; force an e-mail one.
            chain={"domain": domain},
            custom_context={
                "scenario": "Marin repense à la dernière scène du feuilleton.",
                "relationship": "marin",
                "register": register,
                "source": "story_born",
                "character_name": "Marin",
            },
        )
    )
    return payload["prompt_payload"]


@pytest.mark.parametrize("domain", ["shopping", "bureaucracy", "lost_property"])
def test_a_story_letter_in_tu_is_never_framed_as_an_email(db_session, monkeypatch, domain) -> None:
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)

    for seed in range(6):
        prompt = _story_letter(db_session, register="tu / warm informal", domain=domain, seed=seed)

        assert prompt["messenger"]["channel_label"] == "Message"
        assert prompt["mission_format"] not in FORMAL, (
            f"Marin's tu note over the {domain} domain is framed as {prompt['mission_format']}"
        )
        assert prompt["variety"]["mission_format"] not in FORMAL


def test_a_story_letter_in_vous_keeps_the_domains_email(db_session, monkeypatch) -> None:
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)

    formats = {
        _story_letter(db_session, register="vous / polite formal", domain="bureaucracy", seed=seed)["mission_format"]
        for seed in range(6)
    }

    assert "email_formal" in formats


def test_a_feuilleton_act_addressed_to_a_tu_character_is_not_an_email(db_session) -> None:
    """The feuilleton's act rotates its formats too (serial_arc_planner); the same rule holds."""

    from app.db.models.mission import RealWorldMission
    from app.services.serial import SerialThreadService
    from tests.test_serial import _run
    from tests.test_serial import _user as _serial_user

    user = _serial_user(db_session, email=f"serial-953-{uuid4().hex}@example.com")
    thread = _run(SerialThreadService(db_session).get_or_create_thread(user))
    state = dict(thread.state or {})
    relationships = dict(state["relationships"])
    relationships["lila_bonnet"] = {**relationships["lila_bonnet"], "register": "tu", "closeness": 4}
    state["relationships"] = relationships
    thread.state = state
    db_session.add(thread)
    db_session.flush()

    def act(mission_format: str, cast: str) -> dict:
        mission = RealWorldMission(
            user_id=user.id,
            serial_thread_id=thread.id,
            episode_index=4,
            title="Format test",
            brief="Réponds à la note.",
            objectives=[],
            prompt_payload={"messenger": {}},
            source_snapshot={},
        )
        db_session.add(mission)
        db_session.flush()
        SerialThreadService(db_session)._apply_brief_mission_contract(
            mission=mission,
            thread=thread,
            brief_payload={
                "episode_index": 4,
                "required_cast": [cast],
                "mission_format": mission_format,
                "stakes_level": 2,
                "cefr_profile": {"min_words": 35},
            },
        )
        return mission.prompt_payload

    for shape in sorted(FORMAL):
        prompt = act(shape, "lila_bonnet")
        assert prompt["target_register"].startswith("tu")
        assert prompt["mission_format"] not in FORMAL, f"Lila, in tu, gets a {prompt['mission_format']}"
        assert "Objet" not in str(prompt.get("writing_placeholder") or "")

    landlord = act("email_formal", "landlord_marchand")
    assert landlord["mission_format"] == "email_formal", "the landlord, in vous, still writes e-mails"
