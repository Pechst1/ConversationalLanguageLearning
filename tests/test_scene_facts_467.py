"""The scene keeps what the learner established (#467; root cause #145).

Live walk 2 Nov 2026 (Nº 20, «L'appartement de Marin et Lila», A1.1), four free replies:

1. «Je garde la canapé rouge. Le menu, il s'appelle Les Mots sur les cartes.»
2. «Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon, on peut
   l'appeler Napoléon?»
3. «Oui, je garde Napoléon. Il est dans le canapé. Marin, tu as faim?»
4. «Non, on reste ici! Je fais des pâtes pour nous deux. Tu aimes les pâtes?»

Both broke from one flaw: the scene reads its last line and its opening question
and keeps no ledger of what was asked and answered or who said what.

* Marin answered reply 2 with «Oui, bien sûr. Tu me le fais garder ?» — «garder» was his own
  question to reply 1, which reply 2 had just answered with «non».
* The exchange total went from 3 to 4 mid-scene (the answer to an open question was added to
  it; so was an exchange a nudge did not use).

Fake models and pure functions only: nothing is spent.
"""

from __future__ import annotations

import pytest

from app.services import lane_guards, scene_ledger
from app.services import living_story as engine
from app.services import story_lanes as lanes

OPENING = "Pour samedi, on garde quel canapé ? Et sur le menu, il s'appelle comment ?"
REPLY_1 = "Je garde la canapé rouge. Le menu, il s'appelle Les Mots sur les cartes."
MARIN_1 = "Le canapé rouge, oui ! Tu veux garder ce nom ?"
REPLY_2 = "Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon, on peut l'appeler Napoléon?"
MARIN_2_BAD = "Oui, bien sûr. Tu me le fais garder ?"
REPLY_3 = "Oui, je garde Napoléon. Il est dans le canapé. Marin, tu as faim?"
MARIN_3 = "Napoléon est un bon nom pour le menu ! Oui, j'ai faim. Tu cuisines ?"
REPLY_4 = "Non, on reste ici! Je fais des pâtes pour nous deux. Tu aimes les pâtes?"

SUMMARY_BAD = "Napoléon donne son nom au canapé du menu."


def _payload(learner_text: str, history, *, control_language: str = "fr") -> dict:
    """The voice/story lane payload of one turn, as ``_lane_payload`` builds it."""

    rows = [{"learner": learner, "character": character} for learner, character in history]
    return {
        "story": {
            "level": "A1",
            "learner": {"address": "neutral"},
            "control_language": control_language,
            "commitments": [],
        },
        "scene": {"opening_line_fr": OPENING, "objective_native": "", "panels": []},
        "learner_text": learner_text,
        "history": rows,
        "targets": [],
        "turn_plan": {},
        "ledger": scene_ledger.build(opening_line_fr=OPENING, history=rows, learner_text=learner_text),
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent="Marin answers.", needs_clarification=False)


# ---------------------------------------------------------------------------
# 1. A question the learner already answered is not asked again
# ---------------------------------------------------------------------------


def test_marin_does_not_ask_again_the_question_reply_2_just_answered():
    """Golden transcript, exchange 2: «Tu veux garder ce nom ?» was answered «Non, je veux pas
    ce nom.»; «Tu me le fais garder ?» asks it again (and about the wrong thing)."""

    payload = _payload(REPLY_2, [(REPLY_1, MARIN_1)])
    voice = _voice(MARIN_2_BAD)
    with pytest.raises(engine.SoftRejection) as caught:
        lanes.validate_voice(voice, payload)
    assert str(caught.value) == "reply_reasks_answered_question"
    # Even if the retry says it again, what is served no longer asks it.
    served = caught.value.proposal.reply_fr
    assert "garder" not in served.casefold() and served == "Oui, bien sûr."


def test_a_reply_that_takes_up_the_answer_passes():
    payload = _payload(REPLY_2, [(REPLY_1, MARIN_1)])
    lanes.validate_voice(_voice("Oui, bien sûr. Napoléon, c'est un beau nom pour le menu !"), payload)


def test_the_guard_reads_the_ledger_not_a_word_list():
    ledger = _payload(REPLY_2, [(REPLY_1, MARIN_1)])["ledger"]
    assert lane_guards.reasked_question(MARIN_2_BAD, ledger) == "Tu veux garder ce nom ?"
    # A new question on the same verb about something else is a new question.
    assert lane_guards.reasked_question("Oui. Tu veux garder le chat ?", ledger) is None
    # A question that is not answered yet is not «settled».
    assert lane_guards.reasked_question("Tu veux garder ce nom ?", _payload("", [])["ledger"]) is None
    assert lane_guards.reasked_question("Oui, bien sûr.", ledger) is None


def test_a_question_the_learner_has_not_answered_may_be_asked_again():
    """Exchange 3's reply from the walk: «Tu cuisines ?» is new, and «Tu as faim ?» was the
    learner's question, answered by Marin, not a question to the learner."""

    history = [(REPLY_1, MARIN_1), (REPLY_2, "Oui, bien sûr. Napoléon, c'est un beau nom pour le menu !")]
    payload = _payload(REPLY_3, history)
    lanes.validate_voice(_voice(MARIN_3), payload)


# ---------------------------------------------------------------------------
# 2. The total is fixed when the scene starts (backend and client tests:
#    tests/test_story_exchanges.py, tests/test_wp89_le_fil.py, respond-thread.test.js)
# ---------------------------------------------------------------------------
