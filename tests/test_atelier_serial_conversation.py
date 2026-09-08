from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.endpoints.atelier import _serial_conversation_context, _with_serial_conversation
from app.db.models.grammar import GrammarConcept
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.services.missions import MissionConversationService


def _user(db_session, email: str) -> User:
    user = User(id=uuid4(), email=email, hashed_password="x", target_language="fr")
    db_session.add(user)
    db_session.commit()
    return user


def test_serial_conversation_uses_current_cast_and_real_second_turn(db_session):
    user = _user(db_session, "atelier-cast@example.com")
    thread = SerialThread(
        user_id=user.id,
        status="active",
        current_episode_index=2,
        world_bible={
            "cast": [
                {"id": "romy", "name": "Romy", "role": "journaliste"},
                {"id": "marin", "name": "Marin", "role": "photographe"},
            ]
        },
        state={
            "relationships": {
                "romy": {"register": "tu", "closeness": 4},
                "marin": {"register": "vous", "closeness": 2},
            }
        },
        news_seed={},
    )
    db_session.add(thread)
    db_session.flush()
    db_session.add(
        SerialEpisode(
            thread_id=thread.id,
            episode_index=2,
            kind="feuilleton",
            brief_payload={"required_cast": ["romy"], "hook_guidance": "Romy attend la réponse devant le café."},
            hook={},
            hook_from_previous={"text": "Romy a retrouvé la lettre perdue."},
            state_delta={},
            status="available",
        )
    )
    db_session.commit()

    context = _serial_conversation_context(db_session, user)
    assert context
    assert context["character"]["name"] == "Romy"
    assert context["character"]["register"] == "tu"

    concept = GrammarConcept(id=77, name="si + présent", level="A2", language="fr")
    base = {"output_ladder": {"conversation": {"items": [{"id": "turn-1", "prompt": "generic"}]}}}
    enriched = _with_serial_conversation(base, context=context, concept=concept)
    item = enriched["output_ladder"]["conversation"]["items"][0]
    assert item["character"]["name"] == "Romy"
    assert item["serial_context"]["thread_id"] == str(thread.id)

    class StubLLM:
        def generate_chat_completion(self, **kwargs):
            assert kwargs["messages"][-1]["content"] == "Si tu viens, je resterai."
            return SimpleNamespace(content="Alors viens au café demain; je garderai la lettre.")

    reply = MissionConversationService(db_session, llm_service=StubLLM()).respond_for_atelier(
        character=item["character"],
        opener=item["serial_context"]["opener"],
        scene_context=item["serial_context"]["scene_context"],
        user_text="Si tu viens, je resterai.",
    )
    assert reply == "Alors viens au café demain; je garderai la lettre."


def test_serial_conversation_has_clean_no_thread_fallback(db_session):
    user = _user(db_session, "atelier-no-cast@example.com")
    assert _serial_conversation_context(db_session, user) is None
    concept = GrammarConcept(id=78, name="le conditionnel", level="B1", language="fr")
    base = {"output_ladder": {"conversation": {"items": [{"id": "turn-1", "prompt": "generic"}]}}}
    assert _with_serial_conversation(base, context=None, concept=concept) is base

