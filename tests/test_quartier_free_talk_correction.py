"""P12 stage 4: a line said to someone in Le Quartier outside the scene's script is corrected.

Walk of 17 Nov 2026 (``logs/quartier.md``): «Bonjour Lila. Je suis fatigue, j ai faim» to Lila in
the free walk got an answer and no correction, while every scripted answer got one. The talk is
``POST /daily-journeys/{id}/choices`` (``storylet_id: talk``), answered by
``season.gestures.answer``. It now runs the model-free rule pass on the learner's line and returns
at most one correction, its note in the learner's language. No model call anywhere here.
"""

from __future__ import annotations

import pytest

from app.schemas.daily_journey import JourneyChoiceResult
from app.services import correction_contract as cc
from app.services.cast_registry import display_names
from app.services.season import gestures
from app.services.season.flags import effective_flags
from app.services.season.format import load_season

SEASON = load_season("s1")
NAMES = display_names(SEASON.cast)


@pytest.fixture(autouse=True)
def _matcher():
    from app.services.season import runtime

    runtime._ROUTE_CACHE.clear()
    yield
    runtime._ROUTE_CACHE.clear()


def _talk(text: str | None, *, to: str = "lila_bonnet", language: str = "de") -> dict:
    result, _ = gestures.answer(
        None,
        None,
        day=gestures.day_for("s1", "t1.a"),
        state={},
        journey_id="j1",
        scene_id="scene-1",
        storylet_id="talk",
        at=None,
        to=to,
        text=text,
        band="A1",
        language=language,
        names=NAMES,
        season_flags=effective_flags(SEASON, {}, seed="x"),
        routes={},
        use_model=False,
    )
    return JourneyChoiceResult.model_validate(result).model_dump(by_alias=True)


def test_je_suis_fatigue_said_to_lila_comes_back_with_one_correction_and_its_note():
    said = _talk("Je suis fatigue")
    correction = said["correction"]
    assert correction is not None, "free talk is corrected like an answer"
    assert (correction["span_fr"], correction["corrected_fr"]) == ("fatigue", "fatigué")
    assert correction["note_native"] == "Der Akzent fehlt: « fatigué »."
    assert said["beats"], "and Lila still answers"


def test_the_note_is_in_the_learners_language():
    assert _talk("Je suis fatigue", language="en")["correction"]["note_native"] == "The accent is missing: « fatigué »."
    assert _talk("Je suis fatigue", language="fr")["correction"]["note_native"] == "Il manque l’accent : « fatigué »."


def test_the_walks_whole_line_gets_one_correction_not_two():
    correction = _talk("Bonjour Lila. Je suis fatigue, j ai faim")["correction"]
    assert correction["corrected_fr"] == "fatigué"


@pytest.mark.parametrize("text", ["Je suis fatigué.", "Tu connaissais bien Odile ?", "Un verre d'eau, s'il te plaît."])
def test_a_correct_line_gets_none(text):
    assert _talk(text, to="margaux_barman")["correction"] is None


def test_the_hello_and_a_line_in_another_language_get_none():
    assert _talk(None)["correction"] is None
    assert _talk("Ich bin müde")["correction"] is None


@pytest.mark.parametrize(
    ("text", "right"),
    [
        ("Je suis fatigue", "fatigué"),
        ("Il est fatigue.", "fatigué"),
        ("Tu es presse ?", "pressé"),
        ("Je suis arrive hier.", "arrivé"),
        ("Je suis tombe.", "tombé"),
    ],
)
def test_after_je_suis_the_state_takes_its_accent(text, right):
    assert right in [edit.replacement for edit in cc.deterministic_edits(text)]


@pytest.mark.parametrize(
    "text",
    [
        "Je suis entre deux chaises.",
        "Il est calme.",
        "Je suis la rue.",
        "Je suis Marie.",
        "Elle est fatigue.",  # the participle would agree too: left to the model
        "On est fatigue.",
        "La fatigue de Berlin.",
        "Ce voyage me fatigue.",
        "Je suis triste.",
    ],
)
def test_the_rule_leaves_french_that_is_french_there(text):
    assert not [edit for edit in cc.deterministic_edits(text) if edit.span.casefold() in {"fatigue", "entre", "calme", "la", "marie", "triste"}]
