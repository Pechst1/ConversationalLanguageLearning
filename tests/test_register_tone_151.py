"""#151: the tone check must read the register, not substrings of free text."""
from __future__ import annotations

from app.db.models.mission import RealWorldMission
from app.services.missions import MissionConversationService


def _branch(rules: list[str], reply: str) -> str:
    mission = RealWorldMission(prompt_payload={"messenger": {"realism_rules": rules}}, stakes_level=1)
    service = MissionConversationService.__new__(MissionConversationService)
    return service.branch_state(mission=mission, user_text=reply, assistant_text="")["state"]


def test_tu_reply_to_informal_letter_is_not_tone_mismatch() -> None:
    reply = "Salut Lila ! Je pense que Gus est drôle mais Margaux ne m'aime pas. Et toi, pourquoi tu peins le café ?"
    assert _branch(["Informal register: use tu."], reply) != "tone_mismatch"
    assert _branch(["Use tu with Lila, informal and warm."], reply) != "tone_mismatch"


def test_vous_reply_to_polite_formal_letter_is_not_tone_mismatch() -> None:
    reply = "Bonjour Monsieur, pourriez-vous me dire quand vous passerez réparer le radiateur dans mon appartement ?"
    assert _branch(["Polite formal register: use vous."], reply) != "tone_mismatch"


def test_real_mismatch_is_still_detected() -> None:
    assert _branch(["Use vous with M. Marchand, formal."], "Salut, tu peux venir demain matin pour le chauffage ?") == "tone_mismatch"
    assert _branch(["Informal register: use tu."], "Bonjour, pourriez-vous me répondre avant demain soir, merci par avance, pour confirmer le rendez-vous ?") == "tone_mismatch"


def test_tu_inside_other_words_is_not_a_marker() -> None:
    reply = "Bonjour, quelle attitude étrange, pourriez-vous m'expliquer votre habitude du matin ?"
    assert _branch(["Use vous, formal."], reply) != "tone_mismatch"


def test_register_kind_reads_informal_before_formal() -> None:
    from app.services.missions import register_kind

    assert register_kind("informal") == "informal"
    assert register_kind("polite formal") == "formal"
    assert register_kind("neutral") is None
