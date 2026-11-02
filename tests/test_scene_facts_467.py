"""The scene keeps what the learner established (#467; root cause #145).

Live walk 2 Nov 2026 (Nº 20, «L'appartement de Marin et Lila», A1.1), four free replies:

1. «Je garde la canapé rouge. Le menu, il s'appelle Les Mots sur les cartes.»
2. «Non, je veux pas ce nom. Ma grand-mère avait une chat qui s'appelle Napoléon, on peut
   l'appeler Napoléon?»
3. «Oui, je garde Napoléon. Il est dans le canapé. Marin, tu as faim?»
4. «Non, on reste ici! Je fais des pâtes pour nous deux. Tu aimes les pâtes?»

Three things broke, all from one flaw: the scene reads its last line and its opening question
and keeps no ledger of what was asked and answered or who said what.

* Marin answered reply 2 with «Oui, bien sûr. Tu me le fais garder ?» — «garder» was his own
  question to reply 1, which reply 2 had just answered with «non».
* The exchange total went from 3 to 4 mid-scene (the answer to an open question was added to
  it; so was an exchange a nudge did not use).
* The summary said «Napoléon donne son nom au canapé du menu»: nobody named the sofa.

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

# ---------------------------------------------------------------------------
# 3. An ending never gives a name to a thing nobody named
# ---------------------------------------------------------------------------


def _ending(**story) -> engine.SemanticTurn:
    tutor = lanes.TutorVerdict(outcome="met", evidence_quotes=["Je fais des pâtes pour nous deux."])
    defaults = {
        "resolution_fr": "Marin rit. Les pâtes sont prêtes.",
        "summary_native": "Marin et toi mangez des pâtes.",
    }
    return lanes.merged_turn(tutor, _voice("Super, à table."), lanes.StoryTurn(**{**defaults, **story}))


HISTORY = [(REPLY_1, MARIN_1), (REPLY_2, "Oui, bien sûr. Napoléon, c'est un beau nom pour le menu !"), (REPLY_3, MARIN_3)]


def _reason(payload: dict, **story) -> str | None:
    try:
        lanes.validate_story(_ending(**story), payload)
    except engine.StoryUnavailable as exc:
        return str(exc)
    return None


def test_the_summary_does_not_give_the_cats_name_to_the_sofa():
    """The walk's summary: «Napoléon donne son nom au canapé du menu». The learner named the
    menu («il s'appelle Les Mots sur les cartes») and a cat; the sofa was never named."""

    payload = _payload(REPLY_4, HISTORY)
    assert _reason(payload, summary_native=SUMMARY_BAD) == "invented_name"
    assert _reason(payload, resolution_fr="Napoléon donne son nom au canapé. Marin rit.") == "invented_name"
    # The same line in an English chrome day is the model's to keep right (the prompt says so):
    # the guard reads the French the thread holds.
    english = _payload(REPLY_4, HISTORY, control_language="en")
    assert _reason(english, summary_native=SUMMARY_BAD) is None


@pytest.mark.parametrize(
    "summary",
    [
        # What the learner meant: the cat is Napoléon, and the menu takes the name.
        "Le chat de ta grand-mère s'appelle Napoléon, et le menu prend son nom.",
        "Tu proposes d'appeler le menu Napoléon.",
        "Napoléon donne son nom au menu.",
        "Le menu s'appelle Les Mots sur les cartes.",
        "Marin et toi mangez des pâtes avec Napoléon dans le canapé.",
    ],
)
def test_what_was_named_in_the_thread_may_be_said_again(summary):
    assert _reason(_payload(REPLY_4, HISTORY), summary_native=summary) is None


def test_naming_claims_are_read_in_every_form():
    texts = {
        "Napoléon donne son nom au canapé.": ("Napoléon", "canapé"),
        "Le canapé s'appelle Napoléon.": ("Napoléon", "canapé"),
        "Vous appelez le canapé Napoléon.": ("Napoléon", "canapé"),
        "Le nom du canapé est Napoléon.": ("Napoléon", "canapé"),
        "Le canapé est nommé Napoléon.": ("Napoléon", "canapé"),
    }
    for text, (name, thing) in texts.items():
        assert lane_guards.naming_claims(text) == [(name, thing)], text
    assert lane_guards.naming_claims("Marin s'appelle Marin. Tu t'appelles Vincent.") == []
