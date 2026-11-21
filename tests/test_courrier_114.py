"""#114: a Courrier reply answers what the learner wrote; it invents no order, tracking
number or request for the learner's address.

No model calls: a scripted writer returns the exact replies quoted in the issue
(13 Oct and 24 Oct live walks) and the existing Courrier code decides what is shown.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

LEARNER_13_OCT = (
    "Salut Marin ! Je pense que Camille est bizarre, elle a une autre clé. Je ne veux plus vendre le appartement. "
    "Et j’ai un chat, Bruno, il dort dans ma valise. Il a faim. Tu as du poisson ?"
)
MARIN_13_OCT = (
    "Salut ! C'est étrange pour Camille d'avoir une autre clé. De mon côté, il y a eu une confusion avec la porte, "
    "j'ai essayé celle de l'appartement voisin par erreur. Au fait, j'ai le numéro de suivi de la commande, "
    "c'est le 123456789. Tu pourrais me confirmer ton adresse ?"
)
GOOD_13_OCT = "Un chat dans une valise ? Pauvre Bruno ! J'ai du poisson chez moi. Tu veux passer le chercher ?"
GOOD_24_OCT = "Je comprends pour le chat. Je passe après midi, vous êtes là ?"
LEARNER_24_OCT = "Non, je ne suis pas chez moi demain matin. Mon chat déteste le voisin."
VOISIN_24_OCT_ADDRESS = "Je comprends pour le chat. Pouvez-vous me donner votre adresse exacte ?"
VOISIN_24_OCT_TRACKING = "Merci. Il me faut encore le numéro de suivi ou la référence de votre commande."


class _Llm:
    def __init__(self, drafts: list[str]) -> None:
        self.drafts, self.systems = list(drafts), []

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.systems.append(kwargs["system_prompt"])
        return SimpleNamespace(content=self.drafts.pop(0))


def _service(monkeypatch, drafts: list[str], *, opening: str = "Salut ! Tu es bien arrivé ?", register: str = "tu / warm informal"):
    from app.services import missions

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions, "_learner_level_code", lambda db, user: "A1")
    mission = SimpleNamespace(
        id=None,
        title="Un mot de Marin",
        brief="Réponds à Marin.",
        prompt_payload={
            "messenger": {"contact_name": "Marin", "register": register, "opening_message": opening}
        },
        source_snapshot={},
        turns=[],
        attempts=[],
        stakes_level=1,
        mission_type="conversation",
    )
    llm = _Llm(drafts)
    return missions.MissionConversationService(db=None, llm_service=llm), llm, mission


def _respond(service, mission, text: str) -> str:
    return service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=text)


def test_13_oct_tracking_and_address(monkeypatch) -> None:
    service, llm, mission = _service(monkeypatch, [MARIN_13_OCT, GOOD_13_OCT])
    answer = _respond(service, mission, LEARNER_13_OCT)
    assert "123456789" not in answer and "adresse" not in answer.casefold(), f"the invented logistics were shown: {answer}"
    assert answer == GOOD_13_OCT
    assert "tracking" in llm.systems[1] and "Rewrite your reply" in llm.systems[1]


def test_repeat_gets_the_plain_ack(monkeypatch) -> None:
    service, _llm, mission = _service(monkeypatch, [MARIN_13_OCT, MARIN_13_OCT])
    answer = _respond(service, mission, LEARNER_13_OCT)
    assert "123456789" not in answer and "adresse" not in answer.casefold()
    assert "je l'ai bien lu" in answer


@pytest.mark.parametrize("invented", [VOISIN_24_OCT_ADDRESS, VOISIN_24_OCT_TRACKING], ids=["addr", "ref"])
def test_24_oct_requests(monkeypatch, invented: str) -> None:
    service, _llm, mission = _service(
        monkeypatch,
        [invented, GOOD_24_OCT],
        opening="Bonjour, merci pour votre réponse. Nous avons maintenant votre adresse. Le paquet arrive demain matin.",
        register="vous / registre poli",
    )
    assert _respond(service, mission, LEARNER_24_OCT) == GOOD_24_OCT


def test_prompt_invents_nothing(monkeypatch) -> None:
    service, llm, mission = _service(monkeypatch, [GOOD_13_OCT])
    _respond(service, mission, LEARNER_13_OCT)
    prompt = llm.systems[0].casefold()
    assert "answer what they wrote" in prompt and "tracking" in prompt and "home address" in prompt


@pytest.mark.parametrize(
    "reply",
    [
        "Un chat dans une valise ? Pauvre Bruno !",
        "Voici ta commande, un café et un croissant.",
        "On se retrouve à 18 h 30, rue de la Paix, au numéro 12.",
        "Le train part à 10 h 45 : le quai 3.",
    ],
    ids=["cat", "cafe", "street", "train"],
)
def test_ordinary_lines_kept(monkeypatch, reply: str) -> None:
    service, llm, mission = _service(monkeypatch, [reply])
    assert _respond(service, mission, LEARNER_13_OCT) == reply
    assert len(llm.systems) == 1


def test_grounded_lines_kept(monkeypatch) -> None:
    # The scene's own opening asks for the street, and mentions an order number.
    opening = "Bonjour, ton paquet est arrivé, mais pas chez toi. Quelle est ta rue ? Le numéro de commande est sur la photo."
    reply = "Merci. Tu peux confirmer ton adresse ? Le numéro de commande est bien sur la photo."
    service, llm, mission = _service(monkeypatch, [reply], opening=opening)
    assert _respond(service, mission, "J'habite rue Cler.") == reply
    assert len(llm.systems) == 1
    # A number the learner typed may be repeated back.
    service, llm, mission = _service(monkeypatch, ["Merci, j'ai noté le 4567890."])
    assert _respond(service, mission, "Mon numéro de suivi est le 4567890.") == "Merci, j'ai noté le 4567890."
    assert len(llm.systems) == 1


def test_statement_kept(monkeypatch) -> None:
    statement = "Bien reçu : nous avons ton adresse. Le paquet arrive demain, tu es là ?"
    service, llm, mission = _service(monkeypatch, [statement])
    assert _respond(service, mission, LEARNER_24_OCT) == statement
    assert len(llm.systems) == 1


@pytest.mark.parametrize(
    "request_text",
    ["Quelle est ton adresse e-mail ?", "Ton numéro de téléphone, s'il te plaît ?", "Où habites-tu exactement ?"],
    ids=["mail", "phone", "home"],
)
def test_personal_request_rewritten(monkeypatch, request_text: str) -> None:
    service, _llm, mission = _service(monkeypatch, [request_text, GOOD_13_OCT])
    assert _respond(service, mission, LEARNER_13_OCT) == GOOD_13_OCT


def test_goals_ask_no_number() -> None:
    from app.services.missions import MISSION_SUCCESS_OBJECTIVES

    goals = " ".join(MISSION_SUCCESS_OBJECTIVES["deliveries_admin"]).casefold()
    assert "tracking" not in goals and "order reference" not in goals and "address" not in goals


def test_atelier_held_back(monkeypatch) -> None:
    from app.services import missions

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    llm = _Llm([MARIN_13_OCT])
    service = missions.MissionConversationService(db=None, llm_service=llm)
    answer = service.respond_for_atelier(
        character={"name": "Marin", "role": "voisin", "register": "tu"},
        opener="Salut ! Tu es bien arrivé ?",
        scene_context="Marin attend devant la porte.",
        user_text=LEARNER_13_OCT,
    )
    assert "123456789" not in answer and "adresse" not in answer.casefold()
