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
    # A veto: re-rolled once, and if it says it again the authored line plays
    # (``story_lanes._run_lane``). The reply is never served with the question cut out.
    assert caught.value.vetoed


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

SUMMARY_BAD = "Napoléon donne son nom au canapé du menu."
HISTORY = [
    (REPLY_1, MARIN_1),
    (REPLY_2, "Oui, bien sûr. Napoléon, c'est un beau nom pour le menu !"),
    (REPLY_3, MARIN_3),
]
REPLY_4 = "Non, on reste ici! Je fais des pâtes pour nous deux. Tu aimes les pâtes?"


def _claim(payload: dict, *texts: str):
    return lane_guards.unsupported_naming(list(texts), payload)


def test_the_summary_does_not_give_the_cats_name_to_the_sofa():
    """The walk's summary. The learner named the menu («il s'appelle Les Mots sur les cartes»)
    and a cat; the sofa was never named."""

    payload = _payload(REPLY_4, HISTORY)
    assert _claim(payload, SUMMARY_BAD) == ("Napoléon", "canapé")
    assert _claim(payload, "Napoléon donne son nom au canapé. Marin rit.") == ("Napoléon", "canapé")


@pytest.mark.parametrize(
    "line",
    [
        # What the learner meant: the cat is Napoléon, and the menu takes the name.
        "Le chat de ta grand-mère s'appelle Napoléon, et le menu prend son nom.",
        "Tu proposes d'appeler le menu Napoléon.",
        "Napoléon donne son nom au menu.",
        "Le menu s'appelle Les Mots sur les cartes.",
        "Marin et toi mangez des pâtes avec Napoléon dans le canapé.",
        # No claim at all.
        "Marin rit. Les pâtes sont prêtes.",
        "Marin s'appelle Marin.",
    ],
)
def test_what_was_named_in_the_scene_may_be_said_again(line):
    assert _claim(_payload(REPLY_4, HISTORY), line) is None


def test_a_name_from_an_earlier_day_is_the_scenes_too():
    payload = _payload(REPLY_4, HISTORY)
    payload["story"]["memory"] = {"settled": ["Le vélo de Marin s'appelle Tornade."]}
    assert _claim(payload, "Le vélo s'appelle Tornade.") is None
    assert _claim(payload, "Le vélo s'appelle Rafale.") is None, "the bicycle has a naming word on record"
    assert _claim(payload, "Le fauteuil s'appelle Tornade.") == ("Tornade", "fauteuil")


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("Napoléon donne son nom au canapé.", ("Napoléon", "canapé")),
        ("Le canapé s'appelle Napoléon.", ("Napoléon", "canapé")),
        ("Le canapé est baptisé Napoléon.", ("Napoléon", "canapé")),
        ("On va appeler le canapé Napoléon.", ("Napoléon", "canapé")),
        ("Le nom du canapé est Napoléon.", ("Napoléon", "canapé")),
    ],
)
def test_naming_claims_are_read_in_every_form(text, claim):
    assert lane_guards.naming_claims(text) == [claim]


def _story_answers(monkeypatch, *answers):
    """The story lane's answers, in order; the last one repeats. An exception is raised."""

    seen: list[dict] = []

    def call(_system, data, _schema, _collect, **_kwargs):
        seen.append(data)
        answer = answers[min(len(seen), len(answers)) - 1]
        if isinstance(answer, Exception):
            raise answer
        return lanes.StoryTurn(resolution_fr="Les pâtes sont prêtes.", summary_native=answer), None

    monkeypatch.setattr(engine, "_json_call", call)
    monkeypatch.setattr(engine, "CRITIC_ENABLED", False)
    return seen


def _run_lane(payload):
    tutor = lanes.TutorVerdict(outcome="met", evidence_quotes=["Je fais des pâtes pour nous deux."])
    return lanes.run_story_lane(payload, tutor, _voice("Super, à table."))


def test_a_moved_name_is_asked_for_once_more_with_the_reason(monkeypatch):
    seen = _story_answers(monkeypatch, SUMMARY_BAD, "Napoléon donne son nom au menu.")
    result = _run_lane(_payload(REPLY_4, HISTORY))
    assert result.turn.summary_native == "Napoléon donne son nom au menu."
    assert any("canapé" in hint for hint in seen[1]["previous_rejections"])
    assert result.firings == [{"code": "moved_name", "outcome": "corrected"}]


def test_a_moved_name_never_costs_the_written_ending(monkeypatch):
    """Rule 2 of the package: a check reads a sentence with a regex, so it can be wrong. What
    the writer wrote is served after one retry, and the firing is counted."""

    seen = _story_answers(monkeypatch, SUMMARY_BAD)
    result = _run_lane(_payload(REPLY_4, HISTORY))
    assert len(seen) == 2, "one retry, no more"
    assert result.turn.summary_native == SUMMARY_BAD
    assert result.firings == [{"code": "moved_name", "outcome": "served_anyway"}]


def test_a_retry_that_fails_outright_serves_the_first_ending(monkeypatch):
    _story_answers(monkeypatch, SUMMARY_BAD, engine.StoryUnavailable("story_generation_unavailable"))
    result = _run_lane(_payload(REPLY_4, HISTORY))
    assert result.turn.summary_native == SUMMARY_BAD, "not the authored ending"
    assert result.firings == [{"code": "moved_name", "outcome": "served_first"}]


def test_an_ending_with_no_claim_costs_no_retry(monkeypatch):
    seen = _story_answers(monkeypatch, "Marin et toi mangez des pâtes.")
    result = _run_lane(_payload(REPLY_4, HISTORY))
    assert len(seen) == 1 and not result.firings


def test_a_native_language_summary_is_not_read_for_french_claims(monkeypatch):
    """The prompt carries the rule; the check reads the French the scene holds."""

    seen = _story_answers(monkeypatch, SUMMARY_BAD)
    result = _run_lane(_payload(REPLY_4, HISTORY, control_language="en"))
    assert len(seen) == 1 and result.turn.summary_native == SUMMARY_BAD
