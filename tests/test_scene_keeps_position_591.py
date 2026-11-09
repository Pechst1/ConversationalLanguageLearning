"""#591 (root cause #145): the scene remembers the character's own position.

Live walk 8 Nov 2026, «Camille et la dette» (Chez Maître Vasseur). Camille proposed
«L'appartement paie d'abord mon grand-père. Vous êtes d'accord, non ?», the learner
answered «Non, je ne suis pas daccord. Pourquoi le appartement paie grand-pere
dabord ?» and Camille said «Je ne suis pas d'accord non plus. Mais pourquoi cette
question ?»: she joined the refusal of her own proposal and skipped the question.

The scene kept the questions asked and answered (the ledger of #378) but not what
each side *stood for*. The ledger now records the character's proposal and the
learner's stance on it; the voice lane is shown it and the reply is checked against
it. No model call.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services import scene_ledger
from app.services import story_lanes as lanes

OPENING = "L'appartement paie d'abord mon grand-père. Vous êtes d'accord, non ?"
LEARNER = "Non, je ne suis pas daccord. Pourquoi le appartement paie grand-pere dabord ?"
CAMILLE_WALK = "Je ne suis pas d'accord non plus. Mais pourquoi cette question ?"
CAMILLE_KEEPS = "Parce qu'il m'a élevée. Sa dette passe avant la nôtre."


def _payload(history=None, learner_text=LEARNER, opening=OPENING) -> dict:
    return {
        "story": {"level": "A2", "learner": {"address": "neutral"}, "control_language": "en", "commitments": []},
        "scene": {
            "character_id": "camille",
            "opening_line_fr": opening,
            "objective_native": "",
            "panels": [],
        },
        "learner_text": learner_text,
        "history": history or [],
        "targets": [],
        "turn_plan": {},
    }


def _voice(reply: str) -> lanes.VoiceReply:
    return lanes.VoiceReply(reply_fr=reply, understood_intent="The learner disagrees.", needs_clarification=False)


def _refusal(reply: str, payload: dict) -> str | None:
    try:
        lanes.validate_voice(_voice(reply), payload)
    except engine.StoryUnavailable as exc:
        return exc.feedback
    return None


# ---------------------------------------------------------------------------
# The ledger knows who stands where
# ---------------------------------------------------------------------------


def test_the_ledger_records_the_proposal_and_the_learners_stance():
    ledger = scene_ledger.build(opening_line_fr=OPENING, history=[], learner_text=LEARNER)
    assert ledger["stands"] == [
        {
            "by": "character",
            "text_fr": "L'appartement paie d'abord mon grand-père.",
            "at": 0,
            "learner_stance": "disagrees",
        }
    ]
    assert ledger["learner_asked"].startswith("Pourquoi le appartement")


def test_a_proposal_waits_for_the_learner_and_an_agreement_is_recorded():
    waiting = scene_ledger.build(opening_line_fr=OPENING, history=[])
    assert waiting["stands"][0]["learner_stance"] is None
    agreed = scene_ledger.build(opening_line_fr=OPENING, history=[], learner_text="Oui, d'accord.")
    assert agreed["stands"][0]["learner_stance"] == "agrees"
    plain = scene_ledger.build(opening_line_fr="Tu vas dire quoi pour ta date ?", history=[])
    assert plain["stands"] == []


def test_a_later_proposal_is_tracked_in_its_own_exchange():
    history = [{"learner": "Oui, d'accord.", "character": "Bien. On signe demain. Ça vous va ?"}]
    ledger = scene_ledger.build(opening_line_fr=OPENING, history=history, learner_text="Non, pas demain.")
    assert [(row["at"], row["learner_stance"]) for row in ledger["stands"]] == [(0, "agrees"), (1, "disagrees")]


# ---------------------------------------------------------------------------
# The reply keeps the character's position
# ---------------------------------------------------------------------------


def test_the_walks_reply_is_refused_with_the_reason():
    """The exact line of the walk: «non plus» joins the refusal of her own proposal."""

    feedback = _refusal(CAMILLE_WALK, _payload())
    assert feedback is not None, "Camille was allowed to refuse her own proposal"
    assert "non plus" in feedback and "L'appartement paie d'abord" in feedback


@pytest.mark.parametrize(
    "reply",
    [
        "Moi non plus. Pourquoi cette question ?",
        "Ni moi. Parce que c'est injuste.",
        "Moi aussi, je ne suis pas d'accord. Parce que c'est la loi.",
        "Nous sommes d'accord, alors. Parce que c'est injuste.",
    ],
)
def test_joining_the_learners_refusal_is_refused(reply):
    assert _refusal(reply, _payload()) is not None


def test_a_reply_that_keeps_her_position_and_answers_passes():
    assert _refusal(CAMILLE_KEEPS, _payload()) is None
    assert _refusal("Je comprends. Mais il m'a élevée : il passe d'abord. Parce que c'est ma dette.", _payload()) is None


def test_joining_a_refusal_is_fine_when_nothing_was_proposed():
    payload = _payload(opening="Vous venez de Berlin ?", learner_text="Non, je ne suis pas de Berlin.")
    assert _refusal("Moi non plus, je ne suis pas de Berlin.", payload) is None


def test_agreeing_with_an_agreeing_learner_passes():
    payload = _payload(learner_text="Oui, d'accord.")
    assert _refusal("Parfait. Nous sommes d'accord, alors.", payload) is None


def test_a_proposal_answered_in_an_earlier_exchange_does_not_bind_this_reply():
    history = [{"learner": "Non, pas d'accord.", "character": "Alors, je réfléchis. Vous voulez un café ?"}]
    payload = _payload(history=history, learner_text="Oui, un café.")
    assert _refusal("Moi non plus, je n'aime pas le thé.", payload) is None


# ---------------------------------------------------------------------------
# The learner's question is answered or declined, not handed back
# ---------------------------------------------------------------------------


def test_a_reply_that_is_only_a_question_back_is_refused():
    feedback = _refusal("Mais pourquoi cette question ?", _payload())
    assert feedback is not None, "the learner's «Pourquoi…» got only a question back"
    assert "Pourquoi le appartement paie grand-pere dabord" in feedback


def test_a_reply_that_says_why_it_will_not_answer_passes():
    assert _refusal("Je ne veux pas en parler ici. Pourquoi cette question ?", _payload()) is None


@pytest.mark.parametrize(
    "reply",
    [
        "Parce qu'il m'a élevé, vous comprenez ?",
        "Oui, bien sûr, et vous ?",
        "Il m'a élevée, c'est ma dette, et vous ?",
    ],
)
def test_an_answer_that_ends_on_a_question_is_an_answer(reply):
    """Review of the first attempt (#600): one sentence that answers and then asks,
    joined by a comma, was refused in every scene."""

    assert _refusal(reply, _payload()) is None, reply


@pytest.mark.parametrize(
    ("reply", "learner"),
    [
        ("Moi, je suis de Lyon, et vous ?", "Oui. Et vous, vous venez d'où ?"),
        ("Je viens de Lyon, vous connaissez ?", "Oui. Et vous, vous venez d'où ?"),
        ("Mon chat s'appelle Napoléon, tu veux le voir ?", "Comment s'appelle ton chat ?"),
    ],
)
def test_answering_and_asking_back_passes_in_any_scene(reply, learner):
    """The guard itself, in a scene with no proposal at all (no register or level in play)."""

    from app.services import lane_guards

    payload = _payload(opening="Vous venez de Berlin ?", learner_text=learner)
    lane_guards.check_keeps_position(reply, payload)


@pytest.mark.parametrize("reply", ["Pourquoi ?", "Pourquoi cette question, Camille ?", "Mais pourquoi cette question ?"])
def test_bare_questions_back_are_still_refused(reply):
    assert _refusal(reply, _payload()) is not None, reply


def test_an_unrelated_moi_aussi_is_not_joining_the_refusal():
    reply = "Moi aussi, je n'aime pas les dettes. Il m'a élevée."
    assert _refusal(reply, _payload()) is None


def test_a_tag_question_on_a_fact_is_not_a_proposal():
    ledger = scene_ledger.build(
        opening_line_fr="Il fait beau, n'est-ce pas ?", history=[], learner_text="Non, il pleut."
    )
    assert ledger["stands"] == []
