"""#193: a correction must be about the sentence the learner wrote.

Live walk 2026-10-17 (A1.1, day 6): «Ma grand-mère est mort» got «est → es» with the
note «after 'tu' you must use 'es'». There is no «tu» in the sentence, «Ma grand-mère
est» is right, and the real slip («Je suis froid» for «J'ai froid») was missed.

The first fix (#201) was rejected for the opposite flaw: it dropped real corrections
(«Marie et moi suis → sommes») and invented others («Je suis froid avec elle»). Both
directions are pinned here: a correction whose «before» form is already right for its
subject is dropped, a genuine one survives whatever the subject is.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from app.services import story_lanes as lanes
from tests.test_living_story import turn_fixture

TEXT = "Je suis froid et un peu triste. Ma grand-mère est mort et je ne sais pas quoi faire avec le studio."
NOTE = "It is \"es\", not \"est\". 'est' is the third-person form; after 'tu' you must use 'es'."


def _payload(learner_text: str, language: str = "en", turn_plan: dict | None = None) -> dict:
    return {
        "learner_text": learner_text,
        "history": [],
        "scene": {},
        "story": {
            "learner": {"address": "neutral"},
            "level": "A1",
            "commitments": [],
            "control_language": language,
        },
        "targets": [],
        "turn_plan": turn_plan or {},
    }


def _tutor(text: str, span: str | None, fix: str | None, note: str | None = None, **payload):
    verdict = lanes.TutorVerdict(
        outcome="met",
        evidence_quotes=[text.split(".")[0].strip()],
        correction_span_fr=span,
        correction_fr=fix,
        correction_note_native=note,
    )
    lanes.validate_tutor(verdict, _payload(text, **payload))
    return verdict


def _scene_turn(text: str, span: str, fix: str, note: str | None = None) -> engine.SemanticTurn:
    turn = engine.SemanticTurn.model_validate(
        {
            **turn_fixture(text),
            "correction_span_fr": span,
            "correction_fr": fix,
            "correction_note_native": note,
        }
    )
    engine._validate_turn(turn, _payload(text), reply_checks=False)
    return turn


def test_193_tutor():
    """«est → es» is dropped and «Je suis froid» is what gets corrected."""

    verdict = _tutor(TEXT, "est", "es", NOTE)
    assert verdict.correction_fr == "J'ai froid"
    assert verdict.correction_span_fr == "Je suis froid"
    assert "es" not in (verdict.correction_note_native or "").split()
    assert "tu" not in (verdict.correction_note_native or "").lower().split()


def test_193_scene():
    turn = _scene_turn(TEXT, "est", "es", NOTE)
    assert turn.correction_fr == "J'ai froid"
    assert turn.correction_span_fr == "Je suis froid"


def test_span_absent():
    verdict = _tutor("Je veux un café.", "tu est", "tu es", "Tu takes es.")
    assert verdict.correction_fr is None and verdict.correction_span_fr is None
    assert verdict.correction_note_native is None


@pytest.mark.parametrize(
    ("text", "span", "fix"),
    [
        # a form that is already right for a noun subject
        ("Ma grand-mère est contente.", "est", "es"),
        ("Mes parents sont ici.", "sont", "est"),
        # right for the pronoun in front of it, whatever the replacement says
        ("Elle est contente.", "est", "es"),
        ("Je suis content.", "suis", "es"),
        ("Nous sommes amis.", "sommes", "suis"),
        # a negation or a clitic between subject and verb does not hide the subject
        ("Je ne suis pas content.", "suis", "es"),
        # a new clause after «et»: its subject is «ma grand-mère», not the «je» before
        ("Je suis triste et ma grand-mère est morte.", "est", "es"),
        # an object pronoun before the verb: the subject is the one in front of it
        ("Je lui ai donné un cadeau.", "ai", "a"),
        ("Il nous a donné le livre.", "a", "avons"),
        ("Nous nous sommes vus.", "sommes", "est"),
        # a replacement for another person than the subject in front of it
        ("Mes parents est ici.", "est", "es"),
    ],
    ids=[
        "noun-sg",
        "noun-pl",
        "elle",
        "je",
        "nous",
        "ne",
        "new-clause",
        "je-lui-ai",
        "il-nous-a",
        "nous-nous",
        "wrong-person",
    ],
)
def test_right_form(text, span, fix):
    """A form already right for its subject is never corrected."""

    assert _tutor(text, span, fix, "Wrong form.").correction_fr is None
    assert _scene_turn(text, span, fix, "Wrong form.").correction_fr is None


@pytest.mark.parametrize(
    ("text", "span", "fix"),
    [
        # #201 review: «moi», «toi» and noun phrases are subjects too
        ("Marie et moi suis contents.", "suis", "sommes"),
        ("Anna et moi sont ici.", "sont", "sommes"),
        ("Tu et moi est amis.", "est", "sommes"),
        ("Toi est gentil.", "est", "es"),
        ("Marie et Anna est ici.", "est", "sont"),
        ("Mes parents est ici.", "est", "sont"),
        ("Tu est content.", "est", "es"),
        ("Nous suis contents.", "suis", "sommes"),
        ("Je veux une café.", "une café", "un café"),
        ("Je suis allé au marché hier, et tu a faim ?", "a", "as"),
        # #220 review: an object pronoun before the verb is not its subject
        ("Je lui a donné un cadeau.", "a", "ai"),
        ("Je lui est donné un cadeau.", "est", "ai"),
        ("Je vous est vu hier.", "est", "ai"),
        ("Il nous ont donné le livre.", "ont", "a"),
        ("Il vous ont parlé.", "ont", "a"),
        ("Je ne lui a pas parlé.", "a", "ai"),
        # a complement's determiner does not make the head noun plural or singular
        ("La maison de mes parents sont grandes.", "sont", "est"),
        ("Les parents de la fille est ici.", "est", "sont"),
    ],
    ids=[
        "x-et-moi",
        "x-et-moi-pl",
        "tu-et-moi",
        "toi",
        "x-et-y",
        "noun-pl",
        "tu",
        "nous",
        "article",
        "tu-a",
        "je-lui-a",
        "je-lui-est",
        "je-vous-est",
        "il-nous-ont",
        "il-vous-ont",
        "je-ne-lui-a",
        "de-mes",
        "de-la",
    ],
)
def test_real_fix(text, span, fix):
    """A genuine correction survives whatever the subject is."""

    assert _tutor(text, span, fix, "Wrong form.").correction_fr == fix
    assert _scene_turn(text, span, fix, "Wrong form.").correction_fr == fix


@pytest.mark.parametrize(
    ("text", "span", "fix"),
    [
        ("Je suis froid et triste.", "Je suis", "J'ai"),
        ("Moi, je suis faim.", "je suis faim", "j'ai faim"),
        ("Il fait chaud mais je suis soif.", "je suis soif", "j'ai soif"),
    ],
    ids=["froid", "faim", "soif"],
)
def test_model_slip(text, span, fix):
    """The model may name the être/avoir slip itself."""

    assert _tutor(text, span, fix, "Cold is had, not been.").correction_fr == fix


@pytest.mark.parametrize(
    "text",
    [
        "Je suis froid avec elle.",
        "Je suis chaud pour ça !",
        "Je suis froid envers lui.",
        "Je suis froid et distant.",
        "Je suis froid de nature.",
    ],
    ids=["avec", "chaud", "envers", "et-distant", "de-nature"],
)
def test_valid_fr(text):
    """#201 review: «être froid avec quelqu'un» and «être chaud pour» are real French."""

    verdict = _tutor(text, None, None)
    assert verdict.correction_fr is None and verdict.correction_span_fr is None
    assert _scene_turn(text, "est", "es", NOTE).correction_fr is None


@pytest.mark.parametrize(
    ("language", "word"),
    [("en", "In French you"), ("de", "Auf Französisch"), ("fr", "En français")],
    ids=["en", "de", "fr"],
)
def test_slip_note(language, word):
    """The note is in the story's control language."""

    verdict = _tutor("Je suis froid.", None, None, language=language)
    assert verdict.correction_fr == "J'ai froid"
    assert word in verdict.correction_note_native


@pytest.mark.parametrize(
    "text",
    ["Je suis froid.", "Je suis froid ici.", "Je suis froid et je veux rentrer.", "Je suis froid, et toi ?"],
    ids=["bare", "ici", "et-je", "comma"],
)
def test_cold_slip(text):
    """The temperature reading of «je suis froid» is still corrected."""

    assert _tutor(text, None, None).correction_fr == "J'ai froid"


def test_no_slip_clarify():
    """No slip is offered while the app asks about the form."""

    verdict = _tutor("Je suis froid.", None, None, turn_plan={"clarify_form_fr": "froid"})
    assert verdict.correction_fr is None
