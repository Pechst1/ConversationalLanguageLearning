"""A thread keeps its facts (#253, #254; root cause #145).

The scene and the Courrier generated each reply from the beat plan and the last message.
Nothing held what the thread had already settled — whose grandmother it is, what the
learner just said — so a character could take the learner's grandmother for her own, or
answer a reasoned reply with a line about something else.

Two deterministic checks next to the existing lane guards (``app/services/lane_guards``):

* **Who owns the relative** (#253). Once the thread says «ta grand-mère» (the character)
  or «ma grand-mère» (the learner), the character does not say «ma grand-mère» of
  her own. The Courrier retries once, then repairs the possessive; the scene's voice lane
  repairs it.
* **A reasoned reply is picked up** (#254). A reply to a learner turn of some substance
  shares at least one content word with it; a reply that does not is refused once with
  the reason (a soft rejection, so the learner never loses the turn to it).

Exact texts are the ones quoted in the issues. Fake models only: nothing is spent.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.db.models.user import User
from app.services import lane_guards
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.missions import MissionConversationService

# ---------------------------------------------------------------------------
# #253: Lila, the Courrier «Un message à Lila»
# ---------------------------------------------------------------------------

LILA_OPENING = "La boulangerie de ta grand-mère est là aussi."
LILA_FLIPPED = "La boulangerie de ma grand-mère est juste au coin de la rue. Tu viens la voir ?"
LILA_KEPT = "La boulangerie de ta grand-mère est juste au coin de la rue. Tu viens la voir ?"


class _ScriptedLLM:
    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []

    def generate_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=self.replies.pop(0), usage=None)


def _lila_thread(db_session, *, learner_says: str):
    user = User(id=uuid4(), email="lila-thread@example.com", hashed_password="x", proficiency_level="A2")
    db_session.add(user)
    db_session.flush()
    mission = RealWorldMission(
        user_id=user.id,
        serial_thread_id=uuid4(),
        cadence="ad_hoc",
        mission_type="message",
        title="Un message à Lila",
        brief="Réponds à Lila.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={"messenger": {"contact_name": "Lila", "contact_role": "une amie"}},
        recap_payload={},
    )
    mission.turns = [
        RealWorldMissionTurn(
            mission_id=mission.id, user_id=user.id, turn_index=1, role="assistant", mode="chat",
            text=LILA_OPENING, correction_payload={},
        ),
        RealWorldMissionTurn(
            mission_id=mission.id, user_id=user.id, turn_index=2, role="user", mode="chat",
            text=learner_says, correction_payload={},
        ),
    ]
    return user, mission


def test_lila_does_not_take_the_learners_grandmother_for_her_own(db_session):
    """#253: «La boulangerie de ma grand-mère est juste au coin de la rue…» after her own
    «La boulangerie de ta grand-mère est là aussi.» The owner stays with the learner."""

    user, mission = _lila_thread(db_session, learner_says="Oui, c'est bien. Elle aimait le pain.")
    llm = _ScriptedLLM(LILA_FLIPPED, LILA_FLIPPED)
    reply = MissionConversationService(db_session, llm_service=llm).respond(
        user=user, mission=mission, user_text="Oui, c'est bien. Elle aimait le pain."
    )
    assert "ma grand-mère" not in reply.casefold(), reply
    assert "ta grand-mère" in reply.casefold(), reply


def test_a_retry_that_keeps_the_owner_is_served_as_written(db_session):
    user, mission = _lila_thread(db_session, learner_says="Non, je ne vends pas.")
    llm = _ScriptedLLM(LILA_FLIPPED, LILA_KEPT)
    reply = MissionConversationService(db_session, llm_service=llm).respond(
        user=user, mission=mission, user_text="Non, je ne vends pas."
    )
    assert reply == LILA_KEPT
    assert len(llm.calls) == 2
    assert "ma grand-mère" in llm.calls[1]["system_prompt"], "the retry is told which words changed owner"


def test_a_clean_reply_costs_one_call(db_session):
    user, mission = _lila_thread(db_session, learner_says="Oui.")
    llm = _ScriptedLLM("Ta grand-mère devait avoir de belles choses.")
    reply = MissionConversationService(db_session, llm_service=llm).respond(
        user=user, mission=mission, user_text="Oui."
    )
    assert reply == "Ta grand-mère devait avoir de belles choses."
    assert len(llm.calls) == 1


@pytest.mark.parametrize(
    "reply, repaired",
    [
        (LILA_FLIPPED, LILA_KEPT),
        ("Mon frère aussi ? Et mes parents.", "Mon frère aussi ? Et mes parents."),  # nothing settled about them
        ("Ma grand-mère aussi aimait le pain.", "Ma grand-mère aussi aimait le pain."),  # shared, not taken
        (
            "Ta grand-mère a un four. Ma grand-mère n'en avait pas.",
            "Ta grand-mère a un four. Ma grand-mère n'en avait pas.",  # a deliberate contrast
        ),
    ],
)
def test_the_owner_repair_is_narrow(reply, repaired):
    assert lane_guards.settle_kin_owner(reply, learner_texts=[], speaker_texts=[LILA_OPENING]) == repaired


def test_the_learner_naming_their_relative_settles_the_owner_too():
    learner = ["Mon frère vend le café."]
    assert lane_guards.kin_owner_flips("Mon frère est gentil.", learner_texts=learner, speaker_texts=[])
    assert lane_guards.settle_kin_owner("Mon frère est gentil.", learner_texts=learner, speaker_texts=[]) == (
        "Ton frère est gentil."
    )
    # In the vous register the learner's relative is «votre».
    assert lane_guards.settle_kin_owner(
        "Ma mère le sait.", learner_texts=[], speaker_texts=["Et votre mère, elle vient ?"]
    ) == "Votre mère le sait."


def test_the_scene_voice_lane_repairs_the_owner_too():
    payload = {
        "story": {"level": "B1", "learner": {"address": "neutral"}, "commitments": []},
        "scene": {"opening_line_fr": LILA_OPENING, "panels": []},
        "learner_text": "Oui, c'est bien. Elle aimait le pain.",
        "history": [],
        "targets": [],
        "turn_plan": {},
    }
    voice = lanes.VoiceReply(reply_fr=LILA_FLIPPED, understood_intent="The learner agrees.", needs_clarification=False)
    lanes.validate_voice(voice, payload)
    assert voice.reply_fr == LILA_KEPT


# ---------------------------------------------------------------------------
# #254: Lila answers a reasoned reply with a line about something else
# ---------------------------------------------------------------------------

LEARNER_REASON = "Je ne sais pas beaucoup. Odile est parti parce que la restaurant était très difficile, je pense."
LILA_AWAY = "Fatiguée. Ici : « courageuse ». Les gens ont des mots différents."


def _scene_payload(learner_text: str) -> dict:
    return {
        "story": {"level": "B1", "learner": {"address": "neutral"}, "commitments": []},
        "scene": {"opening_line_fr": "Pourquoi elle est partie, Odile ?", "panels": []},
        "learner_text": learner_text,
        "history": [],
        "targets": [],
        "turn_plan": {},
    }


def test_a_line_about_something_else_is_refused_once_with_the_reason():
    """#254: «Fatiguée. Ici : «courageuse».» after «…la restaurant était très difficile»."""

    voice = lanes.VoiceReply(reply_fr=LILA_AWAY, understood_intent="Lila reflects.", needs_clarification=False)
    with pytest.raises(engine.SoftRejection) as caught:
        lanes.validate_voice(voice, _scene_payload(LEARNER_REASON))
    assert str(caught.value) == "reply_ignores_learner"
    assert "restaurant" in caught.value.feedback or "difficile" in caught.value.feedback


@pytest.mark.parametrize(
    "reply",
    [
        "Le restaurant, oui. C'était dur pour elle.",
        "Difficile, tu dis ? Elle ne parlait jamais de ça.",
    ],
)
def test_a_line_that_takes_up_a_word_of_the_reply_passes(reply):
    voice = lanes.VoiceReply(reply_fr=reply, understood_intent="Lila reflects.", needs_clarification=False)
    lanes.validate_voice(voice, _scene_payload(LEARNER_REASON))


def test_a_turn_without_a_reason_and_a_clarification_are_not_held_to_it():
    """«Oui, je viens samedi avec des affiches.» is rightly answered «Merci ! On prépare la
    salle.» with no shared word (a retry on every such reaction would double the voice lane's
    cost); a clarifying question may be about anything."""

    thanks = lanes.VoiceReply(
        reply_fr="Merci ! On prépare la salle ensemble.", understood_intent="x", needs_clarification=False
    )
    lanes.validate_voice(thanks, _scene_payload("Oui, je viens samedi avec des affiches."))
    asking = lanes.VoiceReply(reply_fr="Pardon ? Tu peux répéter ?", understood_intent="x", needs_clarification=True)
    lanes.validate_voice(asking, _scene_payload(LEARNER_REASON))
