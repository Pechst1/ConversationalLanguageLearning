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

import re
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.db.models.user import User
from app.services import lane_guards, story_page
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.missions import MissionConversationService
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import project, resolve_day

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
        # Her own grandmother, in a sentence about something the thread never said of the learner's.
        ("Ma grand-mère habite à Lyon.", "Ma grand-mère habite à Lyon."),
    ],
)
def test_the_owner_repair_is_narrow(reply, repaired):
    assert lane_guards.settle_kin_owner(reply, learner_texts=[], speaker_texts=[LILA_OPENING]) == repaired


def test_the_learner_naming_their_relative_settles_the_owner_too():
    learner = ["Mon frère vend le café au marché."]
    flipped = "Mon frère vend le café ? C'est bien."
    assert lane_guards.kin_owner_flips(flipped, learner_texts=learner, speaker_texts=[])
    assert lane_guards.settle_kin_owner(flipped, learner_texts=learner, speaker_texts=[]) == (
        "Ton frère vend le café ? C'est bien."
    )
    # In the vous register the learner's relative is «votre».
    assert lane_guards.settle_kin_owner(
        "Ma mère vient samedi, c'est sûr.", learner_texts=[], speaker_texts=["Et votre mère, elle vient samedi ?"]
    ) == "Votre mère vient samedi, c'est sûr."


@pytest.mark.parametrize(
    "learner, reply",
    [
        # Review of #257: the repair rewrote a character's own brother into the learner's.
        (["Mon frère habite à Paris."], "Mon frère est pâtissier."),
        (["Ma mère est malade."], "Ma mère m'appelle tous les jours."),
    ],
)
def test_a_relative_of_the_speakers_own_is_left_as_written(learner, reply):
    assert lane_guards.kin_owner_flips(reply, learner_texts=learner, speaker_texts=[]) == []
    assert lane_guards.settle_kin_owner(reply, learner_texts=learner, speaker_texts=[]) == reply


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
        # Sharing a word of the turn is not taking up its reason: «était», or the name asked about.
        "Elle était fatiguée. Ici : « courageuse ».",
        "Odile ? Elle aimait les chats.",
    ],
)
def test_a_line_that_shares_only_a_word_outside_the_reason_is_refused_too(reply):
    voice = lanes.VoiceReply(reply_fr=reply, understood_intent="Lila reflects.", needs_clarification=False)
    with pytest.raises(engine.SoftRejection):
        lanes.validate_voice(voice, _scene_payload(LEARNER_REASON))


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


# ---------------------------------------------------------------------------
# #254: the finished page of Nº 9 «Là-haut» — the day it names, and its last panel
# ---------------------------------------------------------------------------

_WEEKDAY = re.compile(r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b", re.IGNORECASE)


def _la_haut_page(band: str = "A1") -> tuple[dict, str]:
    """T2 day a as the reader's finished page («Là-haut · 16/16»)."""

    season = load_season("s1")
    day = resolve_day(season, "t2", "a", flags=effective_flags(season, {}, seed="x"), band=band, language="en")
    ending = project(day)["ending"]["text_fr"]
    scene = SimpleNamespace(
        status="completed",
        script_payload={"season_page": day, "season_routing": [], story_page.HOOK_PAYLOAD_KEY: ending},
        recap_payload={"resolution_fr": ending},
    )
    return story_page.episode_page(scene, [], {}), ending


@pytest.mark.parametrize("band", ["A1", "A2", "B1"])
def test_the_page_names_one_day_and_a_polaroids_caption_reads_as_written_on_it(band):
    """«Mercredi» in panel 1, then «Mardi. Marin pleure devant une pub.»: Odile's old
    Polaroid, read under the place's plate as if the narrator said it."""

    page, _ending = _la_haut_page(band)
    narration = [row["narration_fr"] for row in page["rows"] if row["narration_fr"]]
    outside_quotes = [re.sub(r"«[^»]*»", "", text) for text in narration]
    named = {day.casefold() for text in outside_quotes for day in _WEEKDAY.findall(text)}
    assert named <= {"mercredi"}, outside_quotes
    assert any("«Mardi. Marin pleure devant une pub. Encore.»" in text for text in narration)


def test_the_last_panel_is_the_polaroid_and_the_hook_one_sentence_that_sets_the_question():
    """Live, A1: «Lila. Elle part ou elle reste ? — juin 2021 Odile savait une chose sur
    Lila. Lila aussi. À suivre…» — the Polaroid glued to the hook, and the hook two
    fragments that answer nothing."""

    page, ending = _la_haut_page("A1")
    last = page["rows"][-1]
    assert last["movement"] == "ending"
    assert last["narration_fr"] == "«Lila. Elle part ou elle reste ? — juin 2021»"
    body = ending.removesuffix("À suivre…").strip()
    assert body.endswith("?") and not re.search(r"[.!?…]", body[:-1]), ending
