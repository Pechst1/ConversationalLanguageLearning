"""#920, #994, #1043: what a Courrier letter and a Forge prompt may say to the learner.

* #920 (live walk 19 Nov, A1.1 day 37): Zoé, «amie», asks «Quel endroit préférez-vous
  pour le repas ?» and «Vous pensez qu'il va amener des histoires de mer ?»; La Forge
  prints «Au téléphone, ton amie te demande : « Vous êtes déjà au cinéma ? »». A friend
  says «tu» to one person. The reply's guard held a friend to «tu» only when her letter
  happened to say «tu»; a letter that named no form held her to nothing, and who she is
  (``contact_role``: «amie») was never read. The Forge's validator skipped every quoted
  line, so a friend's quoted «vous» to one person passed.
* #994 (live walk 22 Nov, day 40): «New letter» printed «Assistance Fibre · Trois jours
  sans internet» again, the learner's 18 Oct letter. A played situation was kept out
  only for 28 days; after that it counted as never played.
* #1043 (live walk 24 Nov, day 42): Lila's letter is about a name on a card; her reply
  offered «un remboursement» and kept it for three turns. The reply's logistics guard
  knew order and tracking numbers and personal data, not a refund or a delivery.

No model calls: scripted writers return the exact lines quoted in the issues and the
existing Courrier and Forge code decides what is shown.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.missions as missions_module
from app.config import settings
from app.db.models.mission import RealWorldMission
from app.db.models.user import User
from app.services.missions import (
    LETTER_FIT_KEY,
    REAL_WORLD_MISSION_DOMAINS,
    MissionGenerator,
    MissionScheduler,
)

ROOT = Path(__file__).resolve().parents[1]


class _Llm:
    def __init__(self, drafts: list[str]) -> None:
        self.drafts, self.systems, self.contexts = list(drafts), [], []

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.systems.append(kwargs["system_prompt"])
        self.contexts.append(kwargs["messages"][0]["content"])
        return SimpleNamespace(content=self.drafts.pop(0))


def _thread(monkeypatch, drafts: list[str], *, name: str, role: str, opening: str, title: str, register: str = ""):
    monkeypatch.setattr(missions_module, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions_module, "_learner_level_code", lambda db, user: "A1")
    mission = SimpleNamespace(
        id=None,
        title=title,
        brief=f"Réponds à {name}.",
        prompt_payload={
            "messenger": {"contact_name": name, "contact_role": role, "opening_message": opening},
            **({"target_register": register} if register else {}),
        },
        source_snapshot={},
        turns=[],
        attempts=[],
        stakes_level=1,
        mission_type="message",
    )
    llm = _Llm(drafts)
    return missions_module.MissionConversationService(db=None, llm_service=llm), llm, mission


# ---------------------------------------------------------------------------
# #920: a friend says «tu» to one person, in the Courrier and in La Forge
# ---------------------------------------------------------------------------

#: Zoé's letter without its «Tu as la serviette pour elle ?»: nothing in it says tu or vous.
ZOE_LETTER = "Salut ! Je suis au marché. On se retrouve à midi ?"
#: What a generated letter stores when its domain has no form (missions.py).
VARIETY_REGISTER = "natural French; formal only when the scenario requires it"
ZOE_REPLY_1 = (
    "Oh, c'est dommage pour la serviette. Mais oui, on se retrouve à midi. Quel endroit préférez-vous pour le repas ?"
)
ZOE_REPLY_2 = (
    "C'est une idée amusante ! Un repas au bord du canal avec un pirate et un perroquet, ça va être une aventure. "
    "Vous pensez qu'il va amener des histoires de mer ?"
)
ZOE_GOOD = "D'accord ! On mange au bord du canal. Tu apportes le pain ?"


@pytest.mark.parametrize("draft", [ZOE_REPLY_1, ZOE_REPLY_2], ids=["preferez", "pensez"])
def test_zoe_vous(monkeypatch, draft: str) -> None:
    service, llm, mission = _thread(
        monkeypatch, [draft, ZOE_GOOD], name="Zoé", role="amie", opening=ZOE_LETTER, title="La serviette",
        register=VARIETY_REGISTER,
    )
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="On se retrouve à midi quand même ?")
    assert answer == ZOE_GOOD, f"Zoé (amie) said «vous» to the learner: {answer!r}"
    assert "«tu»" in llm.systems[1]


def test_actor_told_tu(monkeypatch) -> None:
    service, llm, mission = _thread(
        monkeypatch, [ZOE_GOOD], name="Zoé", role="une amie", opening=ZOE_LETTER, title="La serviette",
        register=VARIETY_REGISTER,
    )
    service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Oui, à midi.")
    assert "tu / registre familier" in llm.contexts[0]


def test_clerk_keeps_vous(monkeypatch) -> None:
    """The relation decides only for a friend: a service desk keeps its «vous»."""

    reply = "Merci. Quel jour préférez-vous pour le technicien ?"
    service, llm, mission = _thread(
        monkeypatch, [reply], name="Assistance Fibre", role="service internet",
        opening="Bonjour, internet ne marche pas dans la rue.", title="Trois jours sans internet",
    )
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Jeudi.") == reply
    assert len(llm.systems) == 1


@pytest.mark.parametrize(
    ("role", "register"),
    [
        ("amie", "tu"),
        ("une amie curieuse", "tu"),
        ("ton premier ami à Paris", "tu"),
        ("ta sœur", "tu"),
        ("l'amie de ton propriétaire", None),
        ("une amie de Lila", None),
        ("service internet", None),
        ("", None),
    ],
    ids=["amie", "curieuse", "marin", "soeur", "proprio", "of-lila", "clerk", "none"],
)
def test_relation(role: str, register: str | None) -> None:
    from app.services.missions import correspondent_register

    mission = SimpleNamespace(
        prompt_payload={"messenger": {"contact_role": role, "opening_message": ZOE_LETTER}, "target_register": VARIETY_REGISTER}
    )
    assert correspondent_register(mission) == register, f"{role!r} writes «{correspondent_register(mission)}»"


FORGE_PROMPT = "Au téléphone, ton amie te demande : « Vous êtes déjà au cinéma ? » Tu es encore chez toi."


def test_forge_friend_vous() -> None:
    from app.services.forge_item_validator import advice, scenario_problems

    problems = scenario_problems(FORGE_PROMPT)
    assert problems, "La Forge accepted «ton amie te demande : « Vous êtes déjà au cinéma ? »»"
    assert "tu" in advice(problems[0])


@pytest.mark.parametrize(
    "prompt",
    [
        "Ton amie te demande : « À quelle heure vous levez-vous, ton frère et toi ? » Avec ton frère, tu te lèves à sept heures.",
        "Tu vas au marché avec un ami. Ta voisine te demande : « Où allez-vous tous les deux ? » Réponds avec nous.",
        "Ton ami te demande : « Est-ce que tu aimes la musique en général ? »",
        "À la boulangerie, la vendeuse te demande : « Vous désirez ? »",
    ],
    ids=["plural-toi-et", "neighbour-plural", "friend-tu", "seller-vous"],
)
def test_forge_vous_ok(prompt: str) -> None:
    from app.services.forge_item_validator import scenario_problems

    assert scenario_problems(prompt) == []


def test_seance_data() -> None:
    from app.services.forge_item_validator import scenario_problems

    lines = (ROOT / "app/data/seance_challenges.txt").read_text(encoding="utf-8").splitlines()
    bad = [line for line in lines if line.count("|") >= 2 and scenario_problems(line.split("|", 2)[2])]
    assert bad == []


# ---------------------------------------------------------------------------
# #994: a played situation does not come back while another is unplayed
# ---------------------------------------------------------------------------

CANNED = {item["domain"]: item for item in REAL_WORLD_MISSION_DOMAINS}
#: Eight letters after 18 Oct, none of them Assistance Fibre.
LATER = ("housing", "neighbours", "deliveries_admin", "transport", "shopping", "bureaucracy", "food_dining", "social_plans")


@pytest.fixture
def model_keeps_the_given_situation(monkeypatch):
    """The model is on and keeps the title and contact it is handed, as on 22 Nov."""

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)

    def fake_scenario(self, *, variety, **_kwargs):
        return {
            "title": variety.get("title"),
            "brief": variety.get("brief"),
            "messenger": {
                "contact_name": variety.get("contact_name"),
                "contact_role": variety.get("contact_role"),
                "opening_message": variety.get("opening_message"),
            },
            "variety": {"domain": variety.get("domain"), "channel": variety.get("channel")},
        }

    monkeypatch.setattr(MissionGenerator, "_llm_scenario", fake_scenario)


def _played(db_session, user: User, domain: str, *, days_ago: float) -> None:
    item = CANNED[domain]
    served = datetime.now(UTC) - timedelta(days=days_ago)
    db_session.add(
        RealWorldMission(
            user_id=user.id,
            status="completed",
            cadence="ad_hoc",
            mission_type="message",
            title=item["title"],
            brief=item["brief"],
            completed_at=served,
            created_at=served,
            prompt_payload={
                "variety": {"domain": domain, "contact": item["contact_name"], "channel": item["channel"], "tone": item["tone"]},
                "messenger": {"contact_name": item["contact_name"]},
                LETTER_FIT_KEY: {"source": "generated", "request_key": domain, "served_at": served.isoformat(), "level": item["level"]},
            },
        )
    )
    db_session.commit()


def test_no_reprint(db_session, monkeypatch, model_keeps_the_given_situation):
    user = User(
        id=uuid4(), email=f"issue994-{uuid4().hex}@example.com", hashed_password="test",
        native_language="en", target_language="fr", proficiency_level="A1",
    )
    db_session.add(user)
    db_session.commit()
    _played(db_session, user, "services", days_ago=35)  # 18 Oct: «Trois jours sans internet»
    for offset, domain in enumerate(LATER):
        _played(db_session, user, domain, days_ago=20 - 2 * offset)
    # The learner's coverage points at technology, as the internet letter does.
    monkeypatch.setattr(MissionScheduler, "_active_coverage_category", lambda self, *, user: "technology_media")

    letter = asyncio.run(
        MissionScheduler(db_session).create(user=user, mission_type="message", cadence="ad_hoc", use_news=False)
    )

    assert letter.title != "Trois jours sans internet", (
        "«New letter» printed «Le Courrier · Trois jours sans internet», the learner's 18 Oct letter"
    )
    assert (letter.prompt_payload or {}).get("variety", {}).get("domain") not in {"services", *LATER}


# ---------------------------------------------------------------------------
# #1043: no refund, delivery or order the letter never held
# ---------------------------------------------------------------------------

LILA_LETTER = "J'ai mis le nom de ta grand-mère sur la carte. C'est bien ?"
LEARNER_NO = "Non, ce n'est pas bien. Je préfère le nom de ma grand-mère sur la carte, pas le nom de ma mère."
LILA_REFUND = (
    "D'accord, je vais changer ça tout de suite. Est-ce que tu veux que je t'envoie la carte aujourd'hui "
    "ou préfères-tu un remboursement ?"
)
LILA_REFUND_AGAIN = "Je suis contente que tu ne prennes pas de remboursement."
LILA_DELIVERY = "D'accord ! Ta commande est prête, la livraison arrive demain."
LILA_GOOD = "D'accord, je change ça : le nom de ta grand-mère sur la carte. Tu veux la voir demain ?"


@pytest.mark.parametrize("draft", [LILA_REFUND, LILA_REFUND_AGAIN, LILA_DELIVERY], ids=["refund", "refund-again", "delivery"])
def test_lila_refund(monkeypatch, draft: str) -> None:
    service, llm, mission = _thread(
        monkeypatch, [draft, LILA_GOOD], name="Lila", role="institutrice et peintre", opening=LILA_LETTER,
        title="Un petit mot de Lila",
    )
    answer = service.respond(user=SimpleNamespace(id=None), mission=mission, user_text=LEARNER_NO)
    assert answer == LILA_GOOD, f"Lila's card letter came back with a shop's line: {answer!r}"
    assert len(llm.systems) == 2


def test_guard_names_refund() -> None:
    from app.services import lane_guards

    found = lane_guards.invented_logistics(LILA_REFUND, grounded=[LILA_LETTER, LEARNER_NO], authored=[LILA_LETTER])
    assert found and any("remboursement" in item or "refund" in item for item in found), found


def test_held_refund_stays(monkeypatch) -> None:
    letter = "Bonjour, votre colis est perdu. Nous vous proposons un remboursement ou un nouvel envoi."
    reply = "D'accord, nous faisons le remboursement cette semaine."
    service, llm, mission = _thread(
        monkeypatch, [reply], name="Service clients", role="service clients", opening=letter, title="Le colis perdu",
    )
    assert service.respond(user=SimpleNamespace(id=None), mission=mission, user_text="Le remboursement, merci.") == reply
    assert len(llm.systems) == 1
