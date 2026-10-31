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


def test_the_learners_earlier_exchanges_do_not_veto_the_line():
    step = _step("Oui, bien sûr.", "Je rentre le 19 décembre.")
    step.private_task["turns"].insert(0, {"learner": "J'arrive le 5 mars.", "character": "Ah ?"})
    assert spoken_reply.repeat_line_for(step) == "Je rentre le 19 décembre."


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("le deux decembre", {2}),
        ("le 19 décembre", {19}),
        ("dix-neuf heures", {19}),
        ("vingt et un jours", {21}),
        ("quatre-vingt-dix euros", {90}),
        ("deux cents euros", {200}),
        ("un café et une baguette", set()),
    ],
)
def test_numbers_in_words_and_digits(text, numbers):
    from app.services.learner_facts import numbers_of

    assert numbers_of(text) == frozenset(numbers)


def test_the_audio_door_reads_the_same_line_as_the_recap():
    """The recap is built with the correction; the audio door has only the step. The
    correction is kept with the turn, so both reach the same sentence."""

    corrected = "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."
    step = _step(REPLY, WRITTEN_BEFOREHAND)
    step.private_task["turns"][0]["correction"] = {"corrected_fr": corrected}
    assert spoken_reply.repeat_line_for(step) == corrected
    assert spoken_reply.repeat_line_for(step, _correction(corrected)) == corrected
