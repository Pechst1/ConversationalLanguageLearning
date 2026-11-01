"""Night shift #379 (child of #145): «One line to say aloud» keeps the learner's facts.

Live walk 30 Oct. The learner answered Lila's «Tu vas dire quoi pour ta date et ton
retour ?» with «Je veux retourner le deux decembre, parce que je suis fatigue de
Berlin.» The recap offered «Je rentre le 19 décembre, parce que je reste pour la
fête.» to say aloud: the date and the reason were both replaced.

The mechanism: for a generated scene the line to repeat was the task's
``suggested_response_fr``, written when the question was posed, before the learner
had said anything. Nothing the learner then stated could change it. Pinned here: a
pre-written line is offered only when it keeps every date, number and reason the
learner gave; otherwise the line is the learner's own sentence, corrected.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import spoken_reply

REPLY = "Je veux retourner le deux decembre, parce que je suis fatigue de Berlin."
WRITTEN_BEFOREHAND = "Je rentre le 19 décembre, parce que je reste pour la fête."


@pytest.fixture(autouse=True)
def spoken_on(monkeypatch):
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)


def _step(learner: str, suggested: str):
    return SimpleNamespace(
        private_task={
            "turns": [{"learner": learner, "character": "« Deux », oui, je le note dans ma tête."}],
            "response_task": {"suggested_response_fr": suggested},
        }
    )


def _correction(corrected: str):
    return SimpleNamespace(corrected_fr=corrected)


def test_the_walks_line_does_not_replace_the_learners_date_and_reason():
    line = spoken_reply.repeat_line_for(
        _step(REPLY, WRITTEN_BEFOREHAND),
        _correction("Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."),
    )
    assert line == "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."
    assert "19" not in line and "fête" not in line


def test_without_a_correction_the_line_is_the_learners_own_sentence():
    line = spoken_reply.repeat_line_for(_step(REPLY, WRITTEN_BEFOREHAND))
    assert line == REPLY


def test_a_line_that_states_a_different_date_is_not_offered():
    line = spoken_reply.repeat_line_for(_step("Je rentre le 2 décembre.", "Je rentre le 19 décembre."))
    assert line == "Je rentre le 2 décembre."


def test_a_line_that_keeps_the_date_and_the_reason_is_still_offered():
    suggested = "Je veux rentrer le 2 décembre, parce que je suis très fatigué de Berlin."
    assert spoken_reply.repeat_line_for(_step(REPLY, suggested)) == suggested


def test_a_number_said_in_words_equals_the_digits():
    suggested = "Je rentre le 2 décembre, parce que je suis fatigué."
    assert spoken_reply.repeat_line_for(_step(REPLY, suggested)) == suggested


def test_a_line_that_drops_the_reason_for_another_is_not_offered():
    line = spoken_reply.repeat_line_for(
        _step("Je rentre parce que je suis fatigué de Berlin.", "Je rentre, parce que je reste pour la fête.")
    )
    assert line == "Je rentre parce que je suis fatigué de Berlin."


def test_a_reply_without_such_facts_keeps_the_scripted_line():
    """The guard is about facts the learner stated, not about every suggestion."""

    suggested = "Je voudrais un café, s'il vous plaît."
    assert spoken_reply.repeat_line_for(_step("Un café.", suggested)) == suggested


def test_an_earlier_exchange_still_vetoes_the_line():
    """Review on #405: the date stated on an earlier exchange is still the learner's."""

    step = _step("Oui, bien sûr.", "Je rentre le 19 décembre.")
    step.private_task["turns"].insert(0, {"learner": "J'arrive le 5 mars.", "character": "Ah ?"})
    assert spoken_reply.repeat_line_for(step) == "J'arrive le 5 mars."


def test_the_learners_latest_fact_wins():
    step = _step("Non, finalement le 5 mars.", "Je rentre le 19 décembre.")
    step.private_task["turns"].insert(0, {"learner": "Je rentre le 2 décembre.", "character": "Ah ?"})
    assert spoken_reply.repeat_line_for(step) == "Non, finalement le 5 mars."


@pytest.mark.parametrize(
    ("said", "same", "other"),
    [
        ("Je rentre le dix-neuf décembre.", "Je rentre le 19 décembre.", "Je rentre le 12 décembre."),
        ("Je rentre le vingt et un décembre.", "Je rentre le 21 décembre.", "Je rentre le 20 décembre."),
        ("Ça coûte quatre-vingt-dix euros.", "Ça coûte 90 euros.", "Ça coûte 14 euros."),
        ("Ça coûte deux cents euros.", "Ça coûte 200 euros.", "Ça coûte 2 euros."),
    ],
)
def test_numbers_in_words_and_digits_are_the_same_fact(said, same, other):
    assert spoken_reply.repeat_line_for(_step(said, same)) == same
    assert spoken_reply.repeat_line_for(_step(said, other)) == said


def test_an_article_is_not_a_number():
    suggested = "Je voudrais un café et une baguette."
    assert spoken_reply.repeat_line_for(_step("Un café et une baguette, s'il vous plaît.", suggested)) == suggested


def test_the_audio_door_reads_the_same_line_as_the_recap():
    """The recap is built with the correction; the audio door has only the step. The
    correction is kept with the turn, so both reach the same sentence."""

    corrected = "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."
    step = _step(REPLY, WRITTEN_BEFOREHAND)
    step.private_task["turns"][0]["correction"] = {"corrected_fr": corrected}
    assert spoken_reply.repeat_line_for(step) == corrected
    assert spoken_reply.repeat_line_for(step, _correction(corrected)) == corrected


def test_a_date_given_on_the_first_of_three_exchanges_still_counts():
    """Review on #405: a scene now has three exchanges (#378). The date and the reason
    came on the first turn; the later turns state none, and must not let the line back."""

    step = SimpleNamespace(
        private_task={
            "turns": [
                {"learner": REPLY, "character": "« Deux », oui. Et ce restaurant te fait peur ?",
                 "correction": {"corrected_fr": "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."}},
                {"learner": "Non, il ne me fait pas peur.", "character": "Tant mieux. Tu pars avec qui ?"},
                {"learner": "Je pars seul avec mon sac.", "character": "D'accord, je note."},
            ],
            "response_task": {"suggested_response_fr": WRITTEN_BEFOREHAND},
        }
    )
    line = spoken_reply.repeat_line_for(step, _correction("Je pars seul avec mon sac."))
    assert line == "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."


def test_a_fact_corrected_back_to_the_line_lets_the_line_stand():
    """Codex review on #414: «le 2», then «finalement le 19»: the 19th is the learner's."""

    step = _step("Non, finalement le 19 décembre.", "Je rentre le 19 décembre.")
    step.private_task["turns"].insert(0, {"learner": "Je rentre le 2 décembre.", "character": "Ah ?"})
    assert spoken_reply.repeat_line_for(step) == "Je rentre le 19 décembre."


def test_quatre_vingt_un_is_eighty_one():
    """Codex review on #414."""

    assert spoken_reply.repeat_line_for(_step("Ça coûte quatre-vingt-un euros.", "Ça coûte 81 euros.")) == (
        "Ça coûte 81 euros."
    )
