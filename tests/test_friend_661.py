"""#661: a Courrier friend keeps her «tu», and a plain «non» is not answered with a refusal.

Live walk 10 Nov 2026, Courrier «Le colis chez Camille», letter 4 of 4. Camille is «ton
amie»; her letters say «tu». The learner wrote a plain «non» and asked why. The reply was
the stock refusal «On ne se connaît pas encore. Reformulez plus poliment, s'il vous plaît,
et je pourrai vous aider.», and a later one «pourriez-vous me rappeler votre adresse … le
numéro de suivi … c'est le 12345».

Mechanism: the letter's contact is a name the letter writer chose («Camille»). The reply
looked her up in the cast *by name*, found Camille Marchand (who says «vous» in the season)
and used that register: the actor was told «vous», the voice guard accepted «vous», and the
learner's «tu» to a friend read as a tone mismatch, whose fallback is the refusal above.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.services.pragmatics import address_markers

LEARNER_NON = "Non, je n’ai pas des serviette. Pourquoi tu veut partager la commande avec ta voisine ?"
LEARNER_SORRY = (
    "Excuse-moi, Camille. Je suis chez moi avec une serviette, et je peux venir chercher mon colis "
    "chez ta voisine à midi."
)
#: What she answered on 10 Nov, verbatim.
STOCK_REFUSAL = "On ne se connaît pas encore. Reformulez plus poliment, s'il vous plaît, et je pourrai vous aider."
ADDRESS_AND_TRACKING = (
    "C'est parfait, mais pourriez-vous me rappeler votre adresse, s'il vous plaît ? J'ai un colis qui "
    "est arrivé à la mauvaise porte. J'ai le numéro de suivi ici, c'est le 12345."
)
#: A reply in character: tu, the neighbour, the order, and an answer to «pourquoi».
FRIEND_ANSWER = (
    "Parce que ma voisine a reçu ton colis, et la commande est trop grande pour moi seule. "
    "Tu passes chez elle à midi ?"
)


class _Recorded:
    """Gives back recorded answers in order (the last one repeats). No model is called."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls: list[dict] = []

    def generate_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        content = self.answers[min(len(self.calls), len(self.answers)) - 1]
        return SimpleNamespace(content=content, usage=None, model="recorded", cost_usd=0.0)


class _Down:
    def generate_chat_completion(self, **kwargs):
        from app.services.llm_service import LLMProviderError

        raise LLMProviderError("timeout")


def _learner_with_thread(db_session, *, season: bool):
    from app.db.models.serial import SerialThread
    from app.db.models.user import User

    user = User(id=uuid4(), email=f"camille-{uuid4().hex[:8]}@example.com", hashed_password="x", target_language="fr")
    db_session.add(user)
    db_session.flush()
    state = (
        {"living_story": {"season_script": {"id": "s1", "played": [{"segment": "t3", "day_in_segment": 2}], "flags": {}, "signals": []}}}
        if season
        else {}
    )
    db_session.add(SerialThread(user_id=user.id, status="active", current_episode_index=10, world_bible={}, state=state, news_seed={}))
    db_session.commit()
    return user


def _turn(text: str) -> SimpleNamespace:
    """The learner's message, stored before the reply is asked for (as the route does)."""

    return SimpleNamespace(role="user", text=text, turn_index=1, created_at=None, correction_payload={})


def _camille_letter(user, *, said: str | None = None) -> SimpleNamespace:
    """Letter 4 of 4 of an affair the letter writer opened with «Camille, ton amie» (tu)."""

    return SimpleNamespace(
        id=None,
        user_id=user.id,
        title="Le colis chez Camille",
        brief="Camille t'écrit à propos du colis chez sa voisine.",
        source_snapshot={},
        stakes_level=3,
        turns=[_turn(said)] if said else [],
        attempts=[],
        mission_type="message",
        correspondent_id="camille",
        chain_id="chain:camille:2026-W45:3",
        prompt_payload={
            "messenger": {
                "contact_name": "Camille",
                "contact_role": "ton amie",
                "target_register": "tu / warm informal",
                "opening_message": "Ton colis est chez ma voisine. Tu as une serviette ? On peut partager la commande après.",
            },
            "target_register": "tu / warm informal",
            "variety": {"domain": "deliveries_admin", "contact": "Camille"},
            "correspondence": {"correspondent_id": "camille", "origin": "chain"},
            "chain": {"chain_id": "chain:camille:2026-W45:3", "index": 4, "total": 4},
        },
    )


def _vous(text: str) -> bool:
    return address_markers(text)[1]


def _tu(text: str) -> bool:
    return address_markers(text)[0]


@pytest.fixture(autouse=True)
def _season(monkeypatch):
    from app.services import missions

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)


@pytest.mark.parametrize("season", [True, False], ids=["s1", "none"])
def test_non_in_tu(db_session, season) -> None:
    """Done-when (a): the recorded refusal is never shown; the reply says tu and answers «pourquoi»."""

    from app.services.missions import MissionConversationService

    user = _learner_with_thread(db_session, season=season)
    llm = _Recorded(STOCK_REFUSAL, FRIEND_ANSWER)
    reply = MissionConversationService(db_session, llm_service=llm).respond(
        user=user, mission=_camille_letter(user, said=LEARNER_NON), user_text=LEARNER_NON
    )
    assert reply != STOCK_REFUSAL, "a friend answered a plain «non» with the stock «reformulez plus poliment» refusal"
    lowered = reply.lower()
    assert not _vous(reply) and "pourriez" not in lowered and "reformulez" not in lowered, (
        f"Camille («ton amie», tu) answered in vous: {reply}"
    )
    assert _tu(reply) and "parce que" in lowered, f"the reply does not answer «pourquoi» in tu: {reply}"
    context = llm.calls[0]["messages"][0]["content"]
    assert "vous / registre poli" not in context, "the actor was told to say vous to a friend"


def test_no_address(db_session) -> None:
    """Done-when (b): the 10 Nov «pourriez-vous me rappeler votre adresse … 12345» never reaches the learner."""

    from app.services.missions import MissionConversationService

    user = _learner_with_thread(db_session, season=True)
    reply = MissionConversationService(db_session, llm_service=_Recorded(ADDRESS_AND_TRACKING)).respond(
        user=user, mission=_camille_letter(user, said=LEARNER_SORRY), user_text=LEARNER_SORRY
    )
    assert "12345" not in reply and "suivi" not in reply, f"an invented tracking number reached the learner: {reply}"
    assert "adresse" not in reply.lower(), f"the friend asked for an address she already has: {reply}"
    assert not _vous(reply), reply


def test_not_rude(db_session) -> None:
    from app.services.missions import MissionConversationService

    user = _learner_with_thread(db_session, season=True)
    branch = MissionConversationService(db_session, llm_service=_Down()).branch_state(
        mission=_camille_letter(user), user_text=LEARNER_NON, assistant_text=""
    )
    assert branch["state"] != "tone_mismatch", "a «tu» to a friend who says «tu» was read as the wrong register"
    assert branch["tone_ok"] is True


@pytest.mark.parametrize(
    "text",
    [LEARNER_NON, LEARNER_SORRY, "Bonjour Camille, pourriez-vous me dire pourquoi vous partagez la commande ?"],
    ids=["non", "sorry", "vous"],
)
def test_fallback_tu(db_session, text) -> None:
    """With the model down, the fallback line still speaks to a friend in tu, never the refusal."""

    from app.services.missions import MissionConversationService

    user = _learner_with_thread(db_session, season=True)
    reply = MissionConversationService(db_session, llm_service=_Down()).respond(
        user=user, mission=_camille_letter(user, said=text), user_text=text
    )
    lowered = reply.lower()
    assert "on ne se connaît pas" not in lowered and "reformulez" not in lowered, f"stock refusal to a friend: {reply}"
    assert not _vous(reply), f"the fallback said vous to a friend: {reply}"
    assert _tu(reply), reply


def test_cast_only(monkeypatch) -> None:
    """The cast's register still binds the cast's own letters (#147); a first-name match does not."""

    from app.services import missions
    from app.services import story_correspondence as courrier

    monkeypatch.setattr(courrier, "active_thread", lambda db, user: None)

    def letter(correspondent_id, **payload):
        return SimpleNamespace(user_id=uuid4(), correspondent_id=correspondent_id, prompt_payload=payload)

    def register(mission):
        return missions.live_register(object(), None, mission)

    # The season opens Margaux on «tu»; each way the cast's own letter records her finds it.
    assert register(letter(None, serial_character_id="margaux_barman", messenger={"contact_name": "Margaux"})) == "tu"
    assert register(letter("margaux_barman", messenger={"contact_name": "Margaux"})) == "tu"
    assert register(letter("margaux", correspondence={"origin": "story_born"}, messenger={"contact_name": "Margaux"})) == "tu"
    # «Camille, ton amie» from the letter writer is not Camille Marchand («vous» in the season).
    friend = letter("camille", correspondence={"origin": "chain"}, messenger={"contact_name": "Camille", "target_register": "tu"})
    assert register(friend) is None, "a friend named Camille was given the cast's Camille Marchand's register"
    assert register(letter("boutique_anais", messenger={"contact_name": "Boutique Anaïs"})) is None
