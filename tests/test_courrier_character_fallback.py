"""Pilot P0 (experience review 17 Nov 2026, finding 7): Margaux's reply timed out and the
Courrier answered her «tu» letter with the help-desk line «Je peux vous aider, mais il me
manque un détail concret…», in «vous», ignoring what the learner wrote.

A person of the story whose reply could not be written answers with the authored
acknowledgement in their own register; the reply call is asked once more before that; a
contact outside the cast (the mairie) keeps its formal line.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

HELP_DESK = (
    "Je peux vous aider, mais il me manque un détail concret. Quel est le problème exact et que souhaitez-vous que je fasse ?",
    "Je peux vous aider, mais il me manque un détail concret. Reformulez et dites-moi exactement ce qu'il faut faire.",
)


class _TimingOut:
    def __init__(self) -> None:
        self.calls = 0

    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        raise TimeoutError("mission chat timed out")


class _TimeoutThenReply(_TimingOut):
    def generate_chat_completion(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("mission chat timed out")
        return SimpleNamespace(content="Super, merci ! Tu passes au café ce soir ?")


def _letter(*, name: str, role: str, register: str, opening: str, character_id: str | None = None):
    payload = {"messenger": {"contact_name": name, "contact_role": role, "target_register": register, "opening_message": opening}}
    if character_id:
        payload["serial_character_id"] = character_id
    return SimpleNamespace(
        id=None,
        user_id=None,
        title="t",
        brief="b",
        prompt_payload=payload,
        source_snapshot={},
        correspondent_id=None,
        turns=[SimpleNamespace(role="user", text="Oui", turn_index=1, correction_payload=None, created_at=None)],
        attempts=[],
        stakes_level=1,
        mission_type="conversation",
    )


def _margaux():
    return _letter(
        name="Margaux",
        role="barmaid au café d'Odile",
        register="tu / registre familier",
        opening="Salut ! Tu viens ce soir au café ?",
        character_id="margaux_barman",
    )


def _mairie():
    return _letter(
        name="La mairie",
        role="accueil de la mairie",
        register="vous / registre poli",
        opening="Bonjour, il manque une pièce à votre dossier.",
    )


@pytest.fixture
def service(monkeypatch):
    from app.services import missions

    monkeypatch.setattr(missions, "_record_mission_llm_cost", lambda *a, **k: None)
    monkeypatch.setattr(missions, "_learner_level_code", lambda db, user: "A2")
    # The branch that served the help-desk line: a short reply «needs detail».
    monkeypatch.setattr(
        missions.MissionConversationService, "branch_state", lambda self, **_kw: {"state": "needs_detail"}
    )

    def build(llm):
        return missions.MissionConversationService(db=None, llm_service=llm)

    return build


def _says_vous(text: str) -> bool:
    return bool(re.search(r"\b(vous|votre|vos)\b", text.lower()))


def test_a_timed_out_reply_from_a_tu_character_is_her_own_acknowledgement(service) -> None:
    llm = _TimingOut()
    reply = service(llm).respond(user=SimpleNamespace(id=None), mission=_margaux(), user_text="Oui")
    assert reply not in HELP_DESK, reply
    assert "il me manque" not in reply
    assert not _says_vous(reply), reply
    assert llm.calls == 2, "the reply call is asked once more after a timeout"


def test_a_timeout_then_a_reply_serves_the_reply(service) -> None:
    llm = _TimeoutThenReply()
    reply = service(llm).respond(user=SimpleNamespace(id=None), mission=_margaux(), user_text="Oui")
    assert reply == "Super, merci ! Tu passes au café ce soir ?"
    assert llm.calls == 2


def test_an_institution_keeps_its_formal_line(service) -> None:
    reply = service(_TimingOut()).respond(user=SimpleNamespace(id=None), mission=_mairie(), user_text="Oui")
    assert reply in HELP_DESK, reply


def test_a_serial_letter_closes_in_the_character_s_register() -> None:
    from app.services.missions import MissionScheduler

    margaux = _margaux()
    margaux.turns = []
    text = MissionScheduler._serial_reply_text(mission=margaux, state_delta={}, turns=[])
    assert text not in HELP_DESK, text
    assert not _says_vous(text), text

    mairie = _mairie()
    assert MissionScheduler._serial_reply_text(mission=mairie, state_delta={}, turns=[]) in HELP_DESK
