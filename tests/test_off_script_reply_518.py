"""Live walk 4 Nov 2026 (#518): an off-script reply got the stock «on m'appelle» exit.

Day 23, «Une lettre pour Margaux», A1.1, real model. The third free reply was
«Mon voisin a un dinosaure dans le jardin. Il mange la lettre !». The scene answered
«Attends, on m'appelle — je reviens vers toi très vite, promis.» and closed on
«Margaux doit partir avant de répondre … your words are noted and the scene picks this
up next time»: a fixed exit, the dinosaur never acknowledged.

Root cause: when the actor's turn is refused twice the engine settles an authored ending
(``fallback_turn``), and every line of it was a constant per language. The one thing the
engine does hold at that point, the learner's sentence (it is even stored as the turn's
evidence), was never read by the reply, the closing panel or the summary. The ending now
quotes the learner's own sentence, so a refused turn still shows that it was heard.

No model call anywhere below.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine

DINOSAUR = "Mon voisin a un dinosaure dans le jardin. Il mange la lettre !"
STOCK_EXIT = "Attends, on m’appelle — je reviens vers toi très vite, promis."
HEARD = "Mon voisin a un dinosaure dans le jardin"
PHRASE = "un dinosaure dans le jardin"


def _turn(text: str = DINOSAUR, *, language: str = "en", answered: bool = False):
    return engine.fallback_turn(
        character_name="Margaux", learner_text=text, language=language, reason="test", answered=answered
    )


def test_the_reply_to_an_off_script_sentence_is_not_the_bare_stock_exit():
    turn = _turn()
    assert turn.reply_fr != STOCK_EXIT, "the learner wrote a new fact and got the stock exit"
    assert PHRASE in turn.reply_fr.casefold(), f"the reply never mentions what the learner said: «{turn.reply_fr}»"
    assert turn.reply_fr.endswith(STOCK_EXIT), "the exit stays what it was"


def test_the_authored_reply_passes_the_echo_guard_a_models_reply_faces():
    """WP-133b: a character never hands the learner's sentence back. The authored line obeys it too."""

    from app.services import lane_guards

    for text in (DINOSAUR, "Merci pour la soupe.", "Je peux apporter les affiches samedi, et du pain.",
                 "Je veux retourner le deux decembre, parce que je suis fatigue de Berlin."):
        reply = _turn(text).reply_fr
        assert lane_guards.echo_hit(reply, text) is None, f"«{reply}» repeats «{text}»"


@pytest.mark.parametrize("language", ["en", "de", "fr"])
@pytest.mark.parametrize("answered", [False, True])
def test_the_closing_panel_and_summary_carry_a_phrase_the_learner_wrote(language, answered):
    turn = _turn(language=language, answered=answered)
    assert HEARD in turn.resolution_fr, f"the closing panel is a fixed exit: «{turn.resolution_fr}»"
    assert HEARD in turn.summary_native, f"the summary is a fixed exit: «{turn.summary_native}»"


def test_the_exit_still_says_the_character_leaves_before_answering():
    # prose_detector's ``leaves_without_answer`` and the R2-5 wording keep their meaning.
    assert "doit partir avant de répondre" in _turn().resolution_fr
    answered = _turn(answered=True)
    assert "doit partir" in answered.resolution_fr and "avant de répondre" not in answered.resolution_fr


def test_the_phrase_is_the_noun_phrase_not_the_whole_sentence():
    assert engine.heard_phrase(DINOSAUR) == PHRASE
    assert engine.heard_phrase("« Mon voisin a un dinosaure. »   Il mange la lettre !") == "un dinosaure"
    assert _turn("« Mon voisin a un dinosaure. »   Il mange la lettre !").reply_fr.startswith("Un dinosaure ?")


def test_the_closing_quote_is_clean_and_clipped_at_a_word():
    turn = _turn("« Mon voisin a un dinosaure. »   Il mange la lettre !")
    assert "« Mon voisin a un dinosaure »" in turn.resolution_fr
    assert "«« " not in turn.resolution_fr and "»»" not in turn.resolution_fr
    long = "Mon voisin a un dinosaure très gentil qui habite dans le jardin derrière la maison de ma grand-mère à Lyon"
    heard = engine.heard_sentence(long)
    assert heard.endswith("…") and long.startswith(heard[:-1].rstrip()) and len(heard) <= 85


def test_a_sentence_with_no_noun_phrase_keeps_the_stock_reply_but_the_ending_still_quotes_it():
    turn = _turn("Margaux, ça va bien.")
    assert turn.reply_fr == STOCK_EXIT
    assert "Margaux, ça va bien" in turn.resolution_fr


@pytest.mark.parametrize("short", ["Non, merci.", "Oui !", "   ", ""])
def test_a_one_word_answer_keeps_the_stock_exit(short):
    """Nothing new was said: the old ending stands (and a blank reply never reaches here)."""

    turn = _turn(short)
    assert turn.reply_fr == STOCK_EXIT
    assert "«" not in turn.resolution_fr and "«" not in turn.summary_native


def test_the_lane_ending_around_a_shown_reply_quotes_the_learner_too():
    """The story lane's authored ending (``settle_with_fallback``) reads the stored lane."""

    from app.services import story_lanes

    lane = {
        "learner_text": DINOSAUR,
        "tutor": {"outcome": "partially_met", "evidence_quotes": [], "demonstrated_target_ids": []},
        "voice": {"reply_fr": "Un dinosaure ? Sérieusement ?", "understood_intent": "an off-script claim",
                  "needs_clarification": False},
    }
    turn = story_lanes.fallback_story(lane, character_name="Margaux", language="en", reason="test")
    assert HEARD in turn.resolution_fr and HEARD in turn.summary_native
