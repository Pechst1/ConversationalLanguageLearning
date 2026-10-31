"""#267 / #266 — a Forge item agrees with itself (live walks of 21-22 Oct).

The parts of an item are written by different hands (the model's situation, the
cast's badge, the bank's coach line, the model's reaction). These tests feed the
EXACT texts quoted in the issues to the code that joins the parts, and assert
the join refuses them. No model is called: the reaction's model is a stub that
says what the live walk heard.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.endpoints.atelier import _with_serial_conversation
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services.atelier import AtelierCorrectionService, AtelierExerciseGenerator
from app.services.missions import MissionConversationService
from tests.services.test_atelier_validation import _concept, _payload

# What the walk of 21-22 Oct showed (issue #267).
BOOKSHOP = (
    "À la librairie, la vendeuse vous demande combien coûtent les deux livres, "
    "affichés à 21 euros. Que lui répondez-vous ?"
)
HOTEL = "Votre amie vous demande : « Combien de chambres y a-t-il dans cet hôtel ? »"
ROOMMATE = "Votre colocataire écrit : « Il manque du lait. » Répondez qu'il n'y en a pas."
COLLEAGUE = "Colleague: « Qu'est-ce que tu as acheté au marché ? » Reply in French: \"I bought apples.\""

LILA_TU = {"id": "lila_bonnet", "name": "Lila Bonnet", "register": "tu"}
GUS_VOUS = {"id": "augustin_de_roncourt", "name": "Gus", "register": "vous"}


def _context(character: dict) -> dict:
    return {"character": character, "thread_id": "t", "episode_index": 0, "scene_context": "Le marché."}


def _decorated(prompt: str, character: dict) -> dict:
    payload = {"output_ladder": {"conversation": {"items": [{"id": "turn-1", "prompt": prompt}]}}}
    enriched = _with_serial_conversation(payload, context=_context(character), concept=None)
    return enriched["output_ladder"]["conversation"]["items"][0]


# --------------------------------------------------------------------------- #
# Register: the badge and the text say the same thing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("prompt", [HOTEL, ROOMMATE, COLLEAGUE], ids=["hotel", "roommate", "colleague"])
def test_tu_badge_vous(prompt: str) -> None:
    item = _decorated(prompt, LILA_TU)
    assert "character" not in item, f"«{LILA_TU['name']} · tu» was set over: {prompt}"
    assert item["prompt"] == prompt, "the situation itself is kept"


def test_vous_badge_tu() -> None:
    prompt = "Ton voisin te demande : « Tu as vu mon chat ? » Réponds que non."
    assert "character" not in _decorated(prompt, GUS_VOUS)


def test_badge_kept() -> None:
    assert _decorated("Ton amie te demande : « Tu viens ? » Réponds que oui.", LILA_TU)["character"]["name"] == "Lila Bonnet"
    assert _decorated("Votre voisin vous demande : « Vous avez vu mon chat ? »", GUS_VOUS)["character"]["name"] == "Gus"
    # No address at all: any badge agrees.
    assert _decorated("Au marché, on demande où sont les pommes.", LILA_TU)["character"]["name"] == "Lila Bonnet"


# --------------------------------------------------------------------------- #
# Roles and prices: the generated situation makes sense
# --------------------------------------------------------------------------- #


def _errors_with_conversation_prompt(db_session, prompt: str) -> list[str]:
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _payload(concept)
    assert AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept) == []
    payload["output_ladder"]["conversation"]["items"][0]["prompt"] = prompt
    return AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)


def test_seller_asks(db_session) -> None:
    errors = _errors_with_conversation_prompt(db_session, BOOKSHOP)
    assert any("asks the customer the price" in error for error in errors), errors


def test_price_basis(db_session) -> None:
    errors = _errors_with_conversation_prompt(
        db_session, "À la librairie, vous achetez les deux livres, affichés à 21 euros. Dites le prix au vendeur."
    )
    assert any("per item or in total" in error for error in errors), errors


def test_fine_prices(db_session) -> None:
    for prompt in (
        "À la librairie, les deux livres coûtent 21 euros en tout. Demandez au vendeur si vous pouvez payer par carte.",
        "À la librairie, vous demandez : « Combien coûtent les deux livres ? » Le vendeur répond : 21 euros au total.",
        "Une cliente vous demande si le livre est à 21 euros. Répondez que oui.",
    ):
        assert _errors_with_conversation_prompt(db_session, prompt) == [], prompt


def test_role_label(db_session) -> None:
    errors = _errors_with_conversation_prompt(db_session, COLLEAGUE)
    assert any("role label" in error for error in errors), errors


# --------------------------------------------------------------------------- #
# #266: the reaction is the item's own speaker, in the learner's person, from the cast
# --------------------------------------------------------------------------- #

LIVE_REACTION = (
    "Ah, je vois ! Ils sont donc probablement en train de visiter des châteaux. "
    "Paul adore l'histoire, n'est-ce pas ?"
)


class _SaysWhatTheWalkHeard:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_chat_completion(self, **kwargs):
        return SimpleNamespace(content=self.text, usage=None, model="stub", cost=0)


def _react(db_session, text: str, learner: str, register: str = "tu") -> str:
    service = MissionConversationService(db_session, llm_service=_SaysWhatTheWalkHeard(text))
    return service.respond_for_atelier(
        character={"id": "margaux_barman", "name": "Margaux", "register": register},
        opener="Qu'est-ce que tu me racontes ?",
        scene_context="",
        user_text=learner,
    )


def test_il_not_ils_paul(db_session) -> None:
    reply = _react(db_session, LIVE_REACTION, "Il est en Angleterre cette semaine.")
    assert "Paul" not in reply, reply
    assert "Ils " not in reply, reply


def test_known_name(db_session) -> None:
    kept = "Ah, en Angleterre ! Lila sera jalouse. Il y reste longtemps ?"
    assert _react(db_session, kept, "Il est en Angleterre cette semaine.") == kept


def test_ils_kept(db_session) -> None:
    kept = "Ils ont de la chance ! Ils rentrent quand ?"
    assert _react(db_session, kept, "Ils sont en Angleterre cette semaine.") == kept


def _conversation_attempt(db_session, items: list[dict], exercise_id: str):
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", target_language="fr")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="in_progress", quote_payload={})
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        round="conversation",
        mode="conversation",
        exercise_id=exercise_id,
        prompt_payload={"round": "conversation", "items": items},
        answer_payload={"text": "Il est en Angleterre cette semaine."},
        correction_payload={},
        verdict="correct",
        score_0_4=4,
    )
    db_session.add(attempt)
    db_session.flush()
    return user, attempt


def test_speaker(db_session, monkeypatch) -> None:
    """Lila's serial badge sits on the set's first item; the learner answered Margaux's scene."""

    seen: dict = {}

    def respond(self, *, character, opener, scene_context, user_text, user_id=None):
        seen.update(character=character, opener=opener)
        return "Ah, en Angleterre ! Il y reste longtemps ?"

    monkeypatch.setattr(MissionConversationService, "respond_for_atelier", respond)
    lila_item = {
        "id": "conversation",
        "prompt": "Votre amie vous demande : « Tu as des nouvelles ? »",
        "character": dict(LILA_TU),
        "serial_context": {"opener": "Votre amie vous demande : « Tu as des nouvelles ? »", "scene_context": "Le marché."},
    }
    margaux_item = {
        "id": "scene-margaux",
        "prompt": 'Margaux: « Qu\'est-ce que tu me racontes ? » (What\'s new with you?) Reply in French: "He is in England this week."',
        "character": {"id": "margaux_barman", "name": "Margaux", "register": "tu"},
        "scene": {"lines": [{"speaker": "margaux_barman", "name": "Margaux", "fr": "Qu'est-ce que tu me racontes ?", "en": "What's new with you?"}]},
    }
    user, attempt = _conversation_attempt(db_session, [lila_item, margaux_item], "forge:1:conversation:scene-margaux")

    AtelierCorrectionService(db_session)._attach_world_reply(attempt, user=user)

    assert seen["character"]["name"] == "Margaux", seen
    assert seen["opener"] == "Qu'est-ce que tu me racontes ?", "the coach's own line, not the prompt with its English ask"
    assert attempt.correction_payload["world_reply"]["character"]["name"] == "Margaux"


# --------------------------------------------------------------------------- #
# The submit hands the correction the item that was answered
# --------------------------------------------------------------------------- #


def test_scoped_submit(client, db_session, monkeypatch) -> None:
    """With a serial thread the submit rebuilt the prompt from the set's conversation
    items and kept all of them: the correction read the first item's model answer
    and the reaction took Lila, the serial cast member, over Margaux's scene."""

    from uuid import UUID

    from app.core.security import decode_token
    from app.db.models.grammar import GrammarConcept
    from app.db.models.serial import SerialThread
    from app.services.atelier import AtelierScheduler
    from app.services.forge import BankItemProvider
    from tests.test_atelier import _FakeLLMService, _prime_core_exercise_sets, _token

    monkeypatch.setattr(
        AtelierCorrectionService,
        "_get_llm_service",
        lambda self: _FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": [], "corrected_answer": "Il est en Angleterre."}),
    )
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    AtelierScheduler(db_session).ensure_catalog()
    _prime_core_exercise_sets(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    start = client.post("/api/v1/atelier/sessions", json={"preferred_concept_id": concept.id}, headers=headers)
    session_id = start.json()["session_id"]
    user = db_session.get(User, UUID(str(decode_token(token)["sub"])))
    db_session.add(
        SerialThread(
            user_id=user.id,
            status="active",
            current_episode_index=0,
            world_bible={"cast": [{"id": "lila", "name": "Lila Bonnet", "role": "colocataire"}]},
            state={"relationships": {"lila": {"register": "tu", "closeness": 4}}},
            news_seed={},
        )
    )
    db_session.commit()
    session = db_session.get(AtelierSession, UUID(session_id))
    scene = {
        "id": "scene-margaux",
        "type": "conversation_turn",
        "instruction": "Reply in French",
        "prompt": 'Margaux: « Qu\'est-ce que tu me racontes ? » (What\'s new?) Reply in French: "He is in England this week."',
        "character": {"id": "margaux_barman", "name": "Margaux", "register": "tu"},
        "scene": {"lines": [{"speaker": "margaux_barman", "name": "Margaux", "fr": "Qu'est-ce que tu me racontes ?", "en": "What's new?"}]},
        "example_answer": "Il est en Angleterre cette semaine.",
        "requirements": [{"label": "x", "target_count": 1}],
        "min_words": 2,
        "max_words": 24,
    }
    BankItemProvider.for_session(db_session, user=user, session=session)._seat(
        concept, round_name="conversation", mode="conversation", built=scene, rung=6
    )

    response = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        json={
            "concept_id": concept.id,
            "round": "conversation",
            "mode": "conversation",
            "exercise_id": f"forge:{concept.id}:conversation:scene-margaux",
            "answer_payload": {"text": "Il est en Angleterre cette semaine."},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    attempt = db_session.query(AtelierAttempt).filter(AtelierAttempt.atelier_session_id == session.id).one()
    assert [item["id"] for item in attempt.prompt_payload["items"]] == ["scene-margaux"]
    assert attempt.prompt_payload["items"][0]["character"]["name"] == "Margaux"


def test_scene_register() -> None:
    from app.services.forge_coaches import mini_scene

    item = SimpleNamespace(
        sentence="Tu prends la confiture ? Oui, je prends la confiture.",
        en="Are you taking the jam? Yes, I am taking the jam.",
        de=None,
        target="prends",
        fingerprint="fp-267",
        ask=None,
    )
    marchand = {"id": "landlord_marchand", "name": "M. Marchand", "register": "vous"}
    margaux = {"id": "margaux_barman", "name": "Margaux", "register": "tu"}
    assert mini_scene(item, marchand) is None, "«tu» line under a «vous» badge"
    assert mini_scene(item, margaux) is not None
