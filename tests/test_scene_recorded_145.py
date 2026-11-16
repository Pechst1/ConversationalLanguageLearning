"""#145 done-when: a «non», an off-script reply and a question each change the next line.

These are the real model's answers, recorded once under the owner's cap (decision 4,
9 Nov 2026; the run cost US$0.0045 on production's model, gpt-6-luna), and replayed here
with no network. A recording shows one answer the model gave to the prompt, not every
answer it could give, and only the live walks after deployment can say more.

The same scene takes all three replies, at A1, A2 and B1, so the only thing that differs
is what the learner wrote.
"""

from __future__ import annotations

import pytest

from app.services import lane_guards
from tests.prompt_regression import harness

SCENES = {
    "A1 Margaux": ("turn-a1-margaux-says-no", "turn-a1-margaux-off-script", "turn-a1-margaux-learner-asks"),
    "A2 Camille": ("turn-a2-camille-says-no", "turn-a2-camille-off-script", "turn-a2-camille-learner-asks"),
    "B1 Camille": ("turn-b1-camille-says-no", "turn-b1-camille-off-script", "turn-b1-camille-learner-asks"),
}
ALL = [case_id for ids in SCENES.values() for case_id in ids]


def _result(case_id: str) -> harness.Result:
    return harness.run_case(harness.load_cases([case_id])[0])


def _reply(case_id: str) -> str:
    return _result(case_id).observed["reply_fr"]


@pytest.mark.parametrize("scene", SCENES)
def test_the_same_scene_answers_each_reply_differently(scene):
    replies = [_reply(case_id) for case_id in SCENES[scene]]
    assert len(set(replies)) == 3, replies


@pytest.mark.parametrize("case_id", ALL)
def test_these_are_the_models_answers_not_handwritten_ones(case_id):
    case = harness.load_cases([case_id])[0]
    for rows in case.answers.values():
        assert all(row["origin"].startswith("live 2026-11-09") for row in rows), case_id


@pytest.mark.parametrize("case_id", ALL)
def test_no_served_reply_says_anything_against_the_scenes_record(case_id):
    result = _result(case_id)
    payload = harness._with_ledger(harness.json.loads(harness.json.dumps(result.case.input["payload"])))
    assert lane_guards.scene_findings(result.observed["reply_fr"], payload) == []


def test_camille_keeps_her_position_after_the_walks_non():
    """The walk's reply to this exact sentence was «Je ne suis pas d'accord non plus.»."""

    reply = _reply("turn-a2-camille-says-no").casefold()
    assert "non plus" not in reply and "pas d'accord" not in reply and "pas d’accord" not in reply
    assert reply.startswith("parce qu"), "her «pourquoi» is answered first"


def test_the_dinosaur_gets_a_reaction_not_the_stock_exit():
    """#518: this reply got «Attends, on m'appelle» in the walk."""

    for case_id in ("turn-a1-margaux-off-script", "turn-a2-camille-off-script"):
        reply = _reply(case_id).casefold()
        assert "dinosaure" in reply and "on m'appelle" not in reply


def test_the_off_script_cat_is_taken_up_and_the_question_stands():
    reply = _reply("turn-b1-camille-off-script").casefold()
    assert "chat" in reply and "grand-père" in reply


@pytest.mark.parametrize("case_id", ["turn-a1-margaux-learner-asks", "turn-a2-camille-learner-asks", "turn-b1-camille-learner-asks"])
def test_a_question_is_answered_before_anything_is_asked_back(case_id):
    first = harness.load_cases([case_id])[0]
    assert not lane_guards.question_handed_back(_reply(case_id), {"learner_asked": first.input["payload"]["learner_text"]})


@pytest.mark.parametrize(
    ("case_id", "intent"),
    [
        ("turn-a1-margaux-says-no", "no"),
        ("turn-a2-camille-says-no", "no"),
        ("turn-b1-camille-says-no", "no"),
        ("turn-a1-margaux-learner-asks", "question"),
        ("turn-a2-camille-learner-asks", "question"),
        ("turn-b1-camille-learner-asks", "question"),
        ("turn-a1-margaux-off-script", "other"),
        ("turn-a2-camille-off-script", "other"),
        ("turn-b1-camille-off-script", "other"),
    ],
)
def test_the_model_reads_the_turn_the_way_the_ledger_does(case_id, intent):
    case = harness.load_cases([case_id])[0]
    assert case.answers["VoiceReply"][-1]["content"]["learner_intent"] == intent
