"""The fixes from the real-model reads of 2026-09-30 (WP-111 §5).

* Three of seven generated days ended in the authored fallback around «Je suis un peu
  perdu ici»: the tutor «corrected» it to «perdu(e)», the ending could not say
  «tu es perdu», and a reply already shown was judged again.
* The diagnostic day lost g1.3 to an empty dialogue line and to an A2 objective too
  long only by its trailing qualifiers.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes


def _payload(learner_text: str, *, address: str = "neutral") -> dict:
    return {
        "learner_text": learner_text,
        "history": [],
        "scene": {},
        "story": {"learner": {"address": address}, "level": "A2", "commitments": []},
        "targets": [],
        "turn_plan": {},
    }


def test_what_the_learner_said_about_themselves_can_be_said_back():
    assert engine.learner_self_forms(["Je suis un peu perdu ici."]) == {"perdu"}
    assert engine.learner_self_forms(["Je me sens seule."]) == {"seule"}
    assert engine.learner_self_forms(["Tu es perdu ?"]) == frozenset()
    # the learner's own form passes; the other gender is still refused
    engine._check_address(["Tu es perdu ? Viens."], "neutral", own=frozenset({"perdu"}))
    with pytest.raises(engine.StoryUnavailable, match="gendered_agreement"):
        engine._check_address(["Tu es perdue ? Viens."], "neutral", own=frozenset({"perdu"}))


@pytest.mark.parametrize(
    ("span", "corrected", "gender_only"),
    [
        ("Je suis un peu perdu ici.", "Je suis un peu perdu(e) ici.", True),
        ("je suis perdu", "je suis perdue", True),
        ("je suis content", "je suis contente", True),
        ("je suis allé", "je suis allée", True),
        ("Je vais au café", "Je vais au café.", True),
        ("je suis perdu", "je me suis perdu", False),
        ("une café", "un café", False),
    ],
)
def test_a_gender_only_change_is_recognised(span, corrected, gender_only):
    assert engine.gender_only_change(span, corrected) is gender_only


def test_the_tutor_never_corrects_the_learners_own_gender():
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=["Je suis un peu perdu ici."],
        correction_span_fr="Je suis un peu perdu ici.",
        correction_fr="Je suis un peu perdu(e) ici.",
        correction_note_native="Use the feminine form if you identify as female.",
    )
    lanes.validate_tutor(verdict, _payload("Je suis un peu perdu ici."))
    assert verdict.correction_fr is None and verdict.correction_note_native is None
    real = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=["Je veux une café."],
        correction_span_fr="une café",
        correction_fr="un café",
        correction_note_native="Café is masculine.",
    )
    lanes.validate_tutor(real, _payload("Je veux une café."))
    assert real.correction_fr == "un café", "a real agreement error is still corrected"


def test_the_ending_is_not_refused_for_a_reply_the_learner_already_read():
    turn = engine.SemanticTurn(
        outcome="met",
        understood_intent="The learner says they feel lost.",
        evidence_quotes=["Je reste."],
        reply_fr="Tu es perdue ? Je reste avec toi.",
        needs_clarification=False,
        resolution_fr="Margaux sert deux cafés. La pluie s'arrête.",
        summary_native="Margaux stays with you.",
        callback_fr="Tu es resté.",
    )
    engine._validate_turn(turn, _payload("Je reste."), reply_checks=False)
    with pytest.raises(engine.StoryUnavailable, match="gendered_agreement"):
        engine._validate_turn(turn.model_copy(), _payload("Je reste."), reply_checks=True)


def test_the_ending_may_say_back_the_learners_own_form():
    turn = engine.SemanticTurn(
        outcome="met",
        understood_intent="The learner says they feel lost.",
        evidence_quotes=["Je suis un peu perdu ici."],
        reply_fr="Ah, d'accord. Assieds-toi.",
        needs_clarification=False,
        resolution_fr="Tu es perdu, mais Marin t'apporte une soupe.",
        summary_native="Marin brings you soup.",
        callback_fr="Marin t'a apporté une soupe.",
    )
    engine._validate_turn(turn, _payload("Je suis un peu perdu ici."), reply_checks=False)


def test_a_silent_panel_is_a_panel_without_lines():
    panel = engine.Panel.model_validate(
        {"visual_direction": "Close-up of a glass.", "dialogue": [{"character_id": "margaux", "text_fr": ""}]}
    )
    assert panel.dialogue == []


def test_an_a2_objective_too_long_only_by_its_qualifiers_keeps_its_ask():
    long = (
        "Tell Romy who you are and what you think of Solvel, as much or as little as you "
        "want, in one or two short sentences."
    )
    trimmed = engine._trimmed_objective(long, "A2")
    assert trimmed == "Tell Romy who you are and what you think of Solvel."
    engine._check_objective_scope(trimmed, "A2")
    # a genuinely chained ask is not rescued by a cut
    chained = "Order a coffee and ask the price and say when you leave and thank her."
    assert engine._trimmed_objective(chained, "A2") == chained
    assert engine._trimmed_objective("Say hello.", "A1") == "Say hello."
    assert engine._trimmed_objective(long, "B1") == long
