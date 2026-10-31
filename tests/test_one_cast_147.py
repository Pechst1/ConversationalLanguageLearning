"""ROOT CAUSE #147, re-test 31 Oct: every screen reads one cast.

Three surfaces still carried a cast of their own after the registry (#199) went live:

* La Forge's conversation item was put under the beat's character («Lila Bonnet · tu»)
  while its words were said to someone else («Say in French: "She is at the church,
  Gus."»), and Lila answered a line said to Gus. The coaches file had its own names and
  its own «tu» for Gus, and Romy coached before the learner had met her.
* The Courrier's reply read the register its letter was written in. A thread that
  reopened after T3 kept Gus on «Que diriez-vous…» while every scene said «tu».
* The Trombinoscope listed the whole season: Maître Vasseur and Mme Diallo on day 19.

The registry now answers who the learner has met (``met_ids``), who a line is said to
(``people_addressed``), and every one of those surfaces asks it.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import cast_registry, forge_coaches
from app.services.cast_registry import (
    has_met,
    met_ids,
    people_addressed,
    people_named,
    season_reach,
)


def _day_19(**relationships) -> dict:
    """The walk account on 31 Oct: T1, gap 1, T2, gap 2, T3 played, two gap-3 days in.
    Gus is «tu» since T3 A; the engine has spoken with Lila, Marin, Gus, Margaux,
    M. Marchand and Camille."""

    played = [
        {"segment": seg, "kind": "tentpole" if seg[0] == "t" else "gap", "day_in_segment": day}
        for seg, days in (("t1", 2), ("g1", 5), ("t2", 2), ("g2", 6), ("t3", 2), ("g3", 2))
        for day in range(1, days + 1)
    ]
    rows = {
        "lila_bonnet": {"register": "tu", "closeness": 5, "callbacks": ["pizza"]},
        "augustin_de_roncourt": {"register": "tu", "closeness": 2, "callbacks": ["fête"]},
        "landlord_marchand": {"register": "vous", "closeness": 2, "last_summary": "le toit"},
        "romy_tremblay": {"register": "tu", "closeness": 0},
        "mme_diallo": {"register": "vous", "closeness": 0},
        **relationships,
    }
    return {
        "relationships": rows,
        "living_story": {
            "season_script": {
                "id": "s1",
                "played": played,
                "flags": {"register.augustin_de_roncourt": "tu"},
                "signals": [],
            }
        },
    }


# --------------------------------------------------------------------------- #
# Who has the learner met
# --------------------------------------------------------------------------- #


def test_reach_of_day_19() -> None:
    assert season_reach(_day_19()) == (3, "z")
    assert season_reach({"living_story": {"season_script": {"played": [{"segment": "t1", "day_in_segment": 1}]}}}) == (1, "a")
    assert season_reach({}) is None


def test_met_on_day_19() -> None:
    met = met_ids(_day_19())
    for person in ("margaux_barman", "augustin_de_roncourt", "marin_leveque", "lila_bonnet", "camille_marchand", "bastien_roux"):
        assert person in met, person
    # Put on a page by the story's own scenes before T4 (the roof, «non»).
    assert "landlord_marchand" in met
    # Seeded relationship rows are not a meeting; T4 and T6 are still ahead.
    for person in ("romy_tremblay", "mme_diallo", "odile_ferrand", "maitre_vasseur"):
        assert person not in met, person


def test_no_season_no_filter() -> None:
    assert met_ids({"relationships": {"romy": {"closeness": 3}}}) is None
    assert has_met({}, "maitre_vasseur") is True


# --------------------------------------------------------------------------- #
# Who a line names, and who it is said to
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, named, addressed",
    [
        ('Say in French: "She is at the church, Gus."', ["augustin_de_roncourt"], ["augustin_de_roncourt"]),
        ("Gus, tu viens samedi ?", ["augustin_de_roncourt"], ["augustin_de_roncourt"]),
        ("Lila est à l'école.", ["lila_bonnet"], []),
        ("Monsieur Marchand a laissé le chat.", ["landlord_marchand"], []),
        ("Je parle avec Camille Marchand.", ["camille_marchand"], []),
        ("Elle a déjà un titre.", [], []),
    ],
)
def test_names_in_a_line(text, named, addressed) -> None:
    assert people_named(text) == named
    assert people_addressed(text) == addressed


# --------------------------------------------------------------------------- #
# La Forge: the badge is the person the line is said to, by the registry's name
# --------------------------------------------------------------------------- #


def _member(cid: str, register: str = "tu") -> dict:
    return {"id": cid, "name": cast_registry.member(cid).name, "role": None, "relationship": {"register": register, "closeness": 2}}


def _context(state: dict, character: str = "lila_bonnet") -> dict:
    from app.api.v1.endpoints.atelier import _cast_badge

    met = {cid: _member(cid) for cid in met_ids(state)}
    return {
        "thread_id": "t",
        "episode_index": 18,
        "scene_context": "Sur le toit.",
        "opener": "…",
        "character": _cast_badge(met[character], state=state),
        "met": met,
        "state": state,
    }


def _payload(prompt: str, answer: str = "") -> dict:
    item = {"id": "turn-1", "prompt": prompt, "example_answer": answer}
    return {"output_ladder": {"conversation": {"items": [item]}}}


def _served(payload: dict) -> dict:
    return payload["output_ladder"]["conversation"]["items"][0]


def test_forge_item_goes_to_its_addressee() -> None:
    """The EXACT item of 31 Oct: under Lila, said to Gus. It is Gus's now, «Gus · tu»."""

    from app.api.v1.endpoints.atelier import _with_serial_conversation

    state = _day_19()
    item = _served(
        _with_serial_conversation(
            _payload('Say in French: "She is at the church, Gus."', "Elle est à l'église, Gus."),
            context=_context(state),
            concept=SimpleNamespace(id=1, name="être"),
        )
    )
    assert item["character"]["id"] == "augustin_de_roncourt"
    assert item["character"]["name"] == "Gus"
    assert item["character"]["register"] == "tu"


def test_forge_badge_uses_the_registry_name() -> None:
    from app.api.v1.endpoints.atelier import _with_serial_conversation

    item = _served(
        _with_serial_conversation(
            _payload('Say in French: "The café is closed today."', "Le café est fermé aujourd'hui."),
            context=_context(_day_19()),
            concept=SimpleNamespace(id=1, name="être"),
        )
    )
    assert item["character"]["name"] == "Lila"


@pytest.mark.parametrize(
    "prompt",
    [
        'Say in French: "Are you coming tonight, Romy?"',  # said to someone not met
        'Say in French: "Lila is at school."',  # about the badge's own person
        'Say in French: "Maître Vasseur has the papers."',  # about someone not met
    ],
)
def test_forge_item_without_a_fitting_speaker_is_plain(prompt) -> None:
    from app.api.v1.endpoints.atelier import _with_serial_conversation

    item = _served(
        _with_serial_conversation(
            _payload(prompt), context=_context(_day_19()), concept=SimpleNamespace(id=1, name="être")
        )
    )
    assert "character" not in item


def test_coach_names_are_the_registry_names() -> None:
    for cid in forge_coaches.cast_ids():
        assert forge_coaches.coach(cid)["name"] == cast_registry.display_name(cid), cid


def test_coach_register_follows_the_story(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    before_t3 = {
        "living_story": {"season_script": {"id": "s1", "played": [{"segment": "t2", "day_in_segment": 2}], "flags": {}, "signals": []}}
    }
    assert forge_coaches.coach("augustin_de_roncourt", state=before_t3)["register"] == "vous"
    assert forge_coaches.coach("augustin_de_roncourt", state=_day_19())["register"] == "tu"


def test_unmet_coach_has_a_stand_in() -> None:
    family = next(f for f in forge_coaches._data()["families"] if f["coach"] == "romy_tremblay")
    state = _day_19()
    coach = forge_coaches.coach_for_unit(family["units"][0], state=state)
    assert coach is not None
    assert coach["id"] != "romy_tremblay"
    assert has_met(state, coach["id"])
    assert coach["family_title"] is None  # «Romy's interview» is not the stand-in's
    # Without a learner, the file's coach as before.
    assert forge_coaches.coach_for_unit(family["units"][0])["id"] == "romy_tremblay"


# --------------------------------------------------------------------------- #
# The Courrier reads the register today, not the letter's copy
# --------------------------------------------------------------------------- #


def _thread(db_session, state: dict, world: dict | None = None):
    from app.db.models.serial import SerialThread
    from app.db.models.user import User

    user = User(id=uuid4(), email=f"cast-{uuid4().hex[:8]}@example.com", hashed_password="x", target_language="fr")
    db_session.add(user)
    db_session.flush()
    thread = SerialThread(user_id=user.id, status="active", current_episode_index=18, world_bible=world or {}, state=state, news_seed={})
    db_session.add(thread)
    db_session.commit()
    return user, thread


def _gus_letter(user) -> SimpleNamespace:
    """A letter written before T3 (vous), reopened on day 19."""

    return SimpleNamespace(
        id=None,
        user_id=user.id,
        title="La fête",
        brief="Gus écrit.",
        source_snapshot={},
        stakes_level=1,
        turns=[],
        attempts=[],
        mission_type="conversation",
        correspondent_id=None,
        prompt_payload={
            "serial_character_id": "augustin_de_roncourt",
            "messenger": {"contact_name": "Gus", "target_register": "vous / registre poli", "opening_message": "Bonjour, c'est Gus."},
        },
    )


def test_live_register_outranks_the_letter(db_session) -> None:
    from app.services.missions import live_register

    user, _thread_row = _thread(db_session, _day_19())
    assert live_register(db_session, user, _gus_letter(user)) == "tu"
    # Without the user object, the letter's own user id finds the thread.
    assert live_register(db_session, None, _gus_letter(user)) == "tu"


def test_live_register_leaves_outside_contacts(db_session) -> None:
    from app.services.missions import live_register

    user, _thread_row = _thread(db_session, _day_19())
    letter = _gus_letter(user)
    letter.prompt_payload = {"messenger": {"contact_name": "Boutique Anaïs", "target_register": "vous / registre poli"}}
    assert live_register(db_session, user, letter) is None


class _VousLLM:
    """Writes the EXACT reply of 31 Oct every time: Gus on «vous»."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content="Je comprends que Lila ne soit pas facile à aborder. Que diriez-vous de trouver un moyen de régler ça ensemble ?",
            usage=None,
            model="fake",
            cost_usd=0.0,
        )


def test_gus_reply_never_vous_after_t3(db_session, monkeypatch) -> None:
    from app.services import missions

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    user, _thread_row = _thread(db_session, _day_19())
    llm = _VousLLM()
    service = missions.MissionConversationService(db_session, llm_service=llm)
    reply = service.respond(user=user, mission=_gus_letter(user), user_text="Non Gus, je ne veux pas fermer le café. Tu es d'accord ?")
    assert "vous" not in reply.lower().split() and "votre" not in reply.lower(), reply
    # The actor was told «tu», and asked to rewrite the «vous» reply.
    assert "tu / registre familier" in llm.calls[0]["messages"][0]["content"]
    assert len(llm.calls) == 2


# --------------------------------------------------------------------------- #
# The Trombinoscope lists only people the learner has met
# --------------------------------------------------------------------------- #


def test_trombinoscope_lists_only_met_people(db_session) -> None:
    from app.services.serial import SerialThreadService

    world = {"cast": [{"id": cid, "name": m.name} for cid, m in cast_registry.all_members().items()]}
    _user, thread = _thread(db_session, _day_19(), world=world)
    service = SerialThreadService(db_session)
    rows = {row["id"]: row for row in service.cast_payload(thread)}
    assert "maitre_vasseur" not in rows
    assert "mme_diallo" not in rows
    assert "romy_tremblay" not in rows
    assert {"lila_bonnet", "augustin_de_roncourt", "margaux_barman", "landlord_marchand"} <= set(rows)
    assert rows["augustin_de_roncourt"]["register"] == "tu"
    assert rows["landlord_marchand"]["register"] == "vous"
