"""#928: the Courrier's «words used» is the server's record, not a substring test.

The walk of 19 Nov wrote «Je n ai pas vendu l appartement. J ai garde la cle…» to
a letter asking for vendre, clé, appartement, and read «1/3 words used»: the
screen matched the raw text against each lemma («vendre» is not in «vendu», «clé»
is not in «cle»). The check already records which targets a reply used; these
tests hold that record and its way onto the mission the screen reads.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.db.models.mission import RealWorldMission, RealWorldMissionTurn
from app.services import missions as missions_module
from app.services.missions import MissionCorrectionService
from tests.test_story_correspondence import _user

WALK_REPLY = "Je n ai pas vendu l appartement. J ai garde la cle dans ma poche, je ne sais pas pourquoi."
TARGETS = [
    {"word_id": 9281, "word": "vendre", "normalized_word": "vendre", "translation": "to sell"},
    {"word_id": 9282, "word": "la clé", "normalized_word": "la cle", "translation": "the key"},
    {"word_id": 9283, "word": "l'appartement", "normalized_word": "l appartement", "translation": "the flat"},
]


def _checked(mission) -> dict:
    service = MissionCorrectionService.__new__(MissionCorrectionService)
    service._shown_vocabulary_items = lambda _mission: [dict(item) for item in TARGETS]
    return service._apply_vocabulary_feedback(
        mission=mission, text=WALK_REPLY, correction={"verdict": "accepted", "errata": []}, language="en"
    )


def test_the_walk_reply_is_recorded_as_using_all_three_targets():
    mission = SimpleNamespace(turns=[], attempts=[], prompt_payload={"target_vocabulary": TARGETS})
    correction = _checked(mission)
    used = {
        event["word_id"]
        for event in correction["vocabulary_events"]
        if event.get("event_type") == "produced_correct"
    }
    assert used == {9281, 9282, 9283}
    assert correction["unused_targets"] == []


def test_the_mission_the_screen_reads_carries_the_used_targets(db_session):
    user = _user(db_session)
    mission = RealWorldMission(
        user_id=user.id,
        status="in_progress",
        cadence="ad_hoc",
        mission_type="message",
        title="Un mot de Marin",
        brief="Réponds à Marin.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[item["word_id"] for item in TARGETS],
        source_snapshot={},
        objectives=[],
        prompt_payload={"target_vocabulary": TARGETS, "messenger": {"contact_name": "Marin"}},
        recap_payload={},
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionTurn(
            id=uuid4(),
            mission_id=mission.id,
            user_id=user.id,
            turn_index=1,
            role="user",
            mode="text",
            text=WALK_REPLY,
            audio_payload={},
            correction_payload=_checked(SimpleNamespace(turns=[], attempts=[])),
        )
    )
    db_session.commit()
    db_session.refresh(mission)

    payload = missions_module.serialize_mission(mission)

    assert sorted(payload.get("used_target_word_ids") or []) == [9281, 9282, 9283]
