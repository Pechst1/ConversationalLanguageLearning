"""The closing hook says nothing before its question that no one in the scene said (#822).

Live walk of 16 Nov 2026 (Nº 34 «La lettre sous la caisse», A1.1): the last panel's
«À suivre…» read

    «J’ai rien entendu. Mais quand même… Margaux lira-t-elle la lettre avec toi ?»

The question is good; what comes before it is a stock voice opener (``TEASER_VOICES``)
printed as an unvoiced caption: a speech act nobody in the scene made («I heard nothing»),
with a dropped «ne» an A1.1 learner has not been taught, and a «Mais quand même…» that is a
fragment of nothing. The opener was keyed to the register (``tu`` → the colloquial form),
never checked against the scene, so every Margaux day ended on it.
"""

from __future__ import annotations

import re

import pytest

from app.services import living_story as engine

TODAY = "2026-11-16"
#: The walk's hook, word for word, and the question it led into.
WALK_HOOK = "J’ai rien entendu. Mais quand même… Margaux lira-t-elle la lettre avec toi ?"
WALK_QUESTION = "Margaux lira-t-elle la lettre avec toi ?"

_NEGATIVE = re.compile(r"\b(?:rien|jamais|personne)\b", re.IGNORECASE)
_NE = re.compile(r"\bn(?:e\b|['’])", re.IGNORECASE)
_FIRST_PERSON = re.compile(r"(?:^|[\s,;:…(])(?:(?:je|me|moi)\b|[jm]['’])", re.IGNORECASE)


def _before_question(hook: dict) -> str:
    text, question = hook["text_fr"], hook["open_fr"]
    assert text.endswith(question), hook
    return text[: -len(question)].strip()


def _hook(**kwargs):
    defaults = {"character_id": "margaux_barman", "register": "tu", "date": TODAY, "seed": "walk-822"}
    return engine.next_teaser({}, {}, **{**defaults, **kwargs})


def test_walk_hook():
    """Done when: «Margaux lira-t-elle la lettre avec toi ?» alone is accepted, and is what
    the last panel prints."""

    hook = _hook(question=WALK_QUESTION)
    assert "rien entendu" not in hook["text_fr"], hook["text_fr"]
    assert "quand même" not in hook["text_fr"], hook["text_fr"]
    assert hook["text_fr"] == WALK_QUESTION
    assert hook["open_fr"] == WALK_QUESTION


PLANT = {
    "id": "e2:plant",
    "text_fr": "Margaux range une lettre sans nom dans le tiroir.",
    "status": "open",
    "character_id": "margaux_barman",
}
PROMISE = {
    "id": "e3:commitment:0",
    "status": "open",
    "witnesses": ["margaux_barman", "lila_bonnet", "marin_leveque"],
    "text_fr": "Venir samedi.",
    "source_quote": "Je viens samedi.",
}


@pytest.mark.parametrize("register", ["tu", "vous"])
@pytest.mark.parametrize(
    "character",
    ["margaux_barman", "marin_leveque", "lila_bonnet", "augustin_de_roncourt", "romy_tremblay", "tiago_moreira", None],
)
@pytest.mark.parametrize("source", ["question", "plant", "promise"])
def test_no_hook_puts_a_line_nobody_said_before_its_question(register, character, source):
    """Whatever the cast member and the row: before the question, no «je» nobody said and
    no negation without its «ne»."""

    kwargs = {"character_id": character, "register": register}
    if source == "question":
        hook = _hook(question=WALK_QUESTION, **kwargs)
    elif source == "plant":
        hook = engine.next_teaser({"planted": [PLANT]}, {}, date=TODAY, seed="walk-822", **kwargs)
    else:
        hook = engine.next_teaser(
            {"commitments": [PROMISE]}, {}, date=TODAY, seed="walk-822",
            said=["Je viens samedi."], clean=["Je viens samedi."], **kwargs,
        )
    assert hook is not None
    lead = _before_question(hook)
    assert not _FIRST_PERSON.search(lead), f"a speech act no character made: {hook['text_fr']!r}"
    for sentence in re.split(r"(?<=[.!?…])\s+", lead):
        if _NEGATIVE.search(sentence):
            assert _NE.search(sentence), f"a dropped «ne»: {hook['text_fr']!r}"


def test_promise_lead():
    """The kind's own lead is grounded (the learner promised it): only the voice goes."""

    hook = engine.next_teaser(
        {"commitments": [PROMISE]}, {}, character_id="lila_bonnet", register="tu", date=TODAY,
        seed="walk-822", said=["Je viens samedi."], clean=["Je viens samedi."],
    )
    assert "caches" not in hook["text_fr"]
    assert hook["text_fr"].startswith(("Tu n'as pas oublié", "Tu as promis")), hook["text_fr"]
    assert "« Je viens samedi. »" in hook["text_fr"]


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "code"),
    [
        (WALK_HOOK, "hook_dropped_ne"),
        ("J'ai rien entendu. Mais quand même… " + WALK_QUESTION, "hook_dropped_ne"),
        # The «vous» form keeps its «ne» and is still nobody's line.
        ("Je n'ai rien entendu. Mais quand même… " + WALK_QUESTION, "hook_unsaid_speech_act"),
        ("Tu viens jamais au café. " + WALK_QUESTION, "hook_dropped_ne"),
        ("C'est rien. " + WALK_QUESTION, "hook_dropped_ne"),
        ("Personne a vu la lettre. " + WALK_QUESTION, "hook_dropped_ne"),
        ("Toi, tu me caches quelque chose… " + WALK_QUESTION, "hook_unsaid_speech_act"),
        ("Dis, j'y repense… C'est peut-être un signe. " + WALK_QUESTION, "hook_unsaid_speech_act"),
    ],
)
def test_the_guard_rejects_what_no_one_said_before_the_question(text, code):
    from app.services.story_teaser import hook_problem

    assert hook_problem(text, open_fr=WALK_QUESTION) == code


@pytest.mark.parametrize(
    ("text", "open_fr"),
    [
        (WALK_QUESTION, WALK_QUESTION),
        (WALK_QUESTION, None),
        ("Tu as promis, hein : « Je viens samedi. » C'est toujours d'accord ?", "« Je viens samedi. » C'est toujours d'accord ?"),
        ("Règle numéro un de La Méthode : on n'oublie rien. " + WALK_QUESTION, WALK_QUESTION),
        ("Au fait… " + WALK_QUESTION, WALK_QUESTION),
        ("Il faudra qu'on en parle. Qui était Odile ?", "Qui était Odile ?"),
    ],
)
def test_the_guard_accepts_a_question_and_a_grounded_lead(text, open_fr):
    from app.services.story_teaser import hook_problem

    assert hook_problem(text, open_fr=open_fr) is None


def test_a_writers_question_that_drops_its_ne_is_not_tomorrows():
    """The same rule on the question itself: «Tomorrow» prints it whole."""

    from app.services import story_teaser

    known = "Margaux, la lettre, le café, Lila."
    assert story_teaser.question_problem("Tu viens jamais au café avec Lila ?", known=known) == "tomorrow_dropped_ne"
    assert story_teaser.question_problem("Tu ne viens jamais au café avec Lila ?", known=known) is None
    assert story_teaser.question_problem(WALK_QUESTION, known=known) is None


def test_a_line_a_character_said_in_the_scene_may_lead():
    from app.services.story_teaser import hook_problem

    said = ["J'ai rien entendu."]
    assert hook_problem("Je n'ai rien entendu. " + WALK_QUESTION, open_fr=WALK_QUESTION, spoken=["Je n'ai rien entendu."]) is None
    # A character's own line still may not drop the «ne» on the learner's page.
    assert hook_problem("J'ai rien entendu. " + WALK_QUESTION, open_fr=WALK_QUESTION, spoken=said) == "hook_dropped_ne"
