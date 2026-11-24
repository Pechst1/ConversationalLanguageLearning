"""#970: the line under Gus' scene prompt read «Gus asks if he should speak to Gus or
stay silent.» — the speaker named as his own addressee.

Live walk 21 Nov (A1.1, day 39, «Bastien mesure le Mistral»). Gus opens with «Je dis ce
que cette banquette est pour moi, ou je me tais et je m'assieds ?» and the model's task
line reported his question: «Gus asks if he should speak to Bastien or stay silent.»
The addressee guard (WP-103 T4) read «speak to Bastien» as an instruction to the
learner, saw Bastien was not the one who answers, and re-addressed the line to Gus.

The rule: a gloss never names the speaker as its own addressee. An addressing verb is
the learner's only when the learner is its subject (an imperative, «you …»); a verb
whose subject is a cast member («he should speak to», «Gus wonders whether to talk
to») is that member's act. The WP-103 T4 guard keeps every real instruction to the
learner (the #1013 review's table). Fake provider only.
"""

from __future__ import annotations

import pytest

from app.services import living_story as engine
from tests import test_living_story as story

CAST = [
    {"id": "marin_leveque", "name": "Marin Lévêque", "gender": "m"},
    {"id": "lila_bonnet", "name": "Lila Bonnet", "gender": "f"},
    {"id": "augustin_de_roncourt", "name": "Augustin « Gus » de Roncourt", "gender": "m"},
    {"id": "romy_tremblay", "name": "Romane « Romy » Tremblay", "gender": "f"},
    {"id": "bastien_roux", "name": "Bastien Roux", "gender": "m"},
]
GUS = "augustin_de_roncourt"

#: What the model wrote under Gus' line (the served text before the guard re-addressed it).
WRITTEN = "Gus asks if he should speak to Bastien or stay silent."
#: What the learner was shown on the walk, quoted from the issue.
SERVED = "Gus asks if he should speak to Gus or stay silent."
GUS_LINE = "Je dis ce que cette banquette est pour moi, ou je me tais et je m'assieds ?"


def _gus_scene(context: dict, objective: str) -> dict:
    value = story.draft(context, 0)
    value.update(
        {
            "character_id": GUS,
            "location_id": "le_mistral",
            "objective_native": objective,
            "objective_semantics": "Answer Gus: should he speak, or sit down and stay silent?",
            "hint_native": "Tell Gus what you think he should do.",
            "suggested_response_fr": "Parle, Gus.",
            "opening_line_fr": GUS_LINE,
        }
    )
    for panel in value["panels"]:
        for line in panel.get("dialogue") or []:
            line["character_id"] = GUS
    return value


def _served_objective(objective: str) -> str:
    """The objective the learner reads: the draft's own, or the page a soft rejection
    carries to be served when the retry repeats it."""

    context = story._scene_context(world={"cast": CAST, "locations": [{"id": "le_mistral"}]})
    draft = engine.SceneDraft.model_validate(_gus_scene(context, objective))
    try:
        engine._check_addressee(draft, context)
    except engine.SoftRejection as refused:
        return (refused.proposal or draft).objective_native
    return draft.objective_native


def test_report_kept():
    """The model's report of Gus' own question is never re-addressed to Gus."""

    served = _served_objective(WRITTEN)
    assert "speak to Gus" not in served, f"the speaker is named as his own addressee: {served!r}"
    assert served == WRITTEN


def test_walk_gloss():
    """The exact line the walk served is caught and served without the self-address."""

    served = _served_objective(SERVED)
    assert "speak to Gus" not in served, f"the speaker is named as his own addressee: {served!r}"
    assert served == "Gus asks if he should speak or stay silent."


def test_walk_hint():
    context = story._scene_context(world={"cast": CAST, "locations": [{"id": "le_mistral"}]})
    draft = engine.SceneDraft.model_validate(_gus_scene(context, SERVED))
    with pytest.raises(engine.SoftRejection) as refused:
        engine._check_addressee(draft, context)
    assert str(refused.value) == "objective_addresses_its_speaker"
    assert "Gus" in refused.value.hint


def test_readdress():
    # A real mismatch (the learner is told to ask Bastien while Gus answers) whose
    # re-address would also turn Gus' own act into «talk to Gus».
    served = _served_objective("Ask Bastien if Gus should talk to Bastien.")
    assert served == "Ask Gus if Gus should talk."


@pytest.mark.parametrize(
    ("objective", "served"),
    [
        # The speaker addressing himself: refused, and served without the self-address.
        (SERVED, "Gus asks if he should speak or stay silent."),
        ("Gus wonders whether to talk to Gus.", "Gus wonders whether to talk."),
        ("Gus asks if he should ask Gus.", "Gus asks if he should ask himself."),
        ("Gus hesitates: should he speak to Gus?", "Gus hesitates: should he speak?"),
        # The speaker spoken to by the learner, or another member as the subject: kept.
        ("Ask Gus if he wants to stay.", "Ask Gus if he wants to stay."),
        ("Tell Gus that Romy is late.", "Tell Gus that Romy is late."),
        ("Romy asks if she should speak to Gus.", "Romy asks if she should speak to Gus."),
        (WRITTEN, WRITTEN),
    ],
    ids=["walk", "talk", "ask", "inverted", "learner-asks", "learner-tells", "other-subject", "report"],
)
def test_never_self(objective, served):
    assert _served_objective(objective) == served


@pytest.mark.parametrize(
    "objective",
    [
        WRITTEN,
        "Gus wonders whether to talk to Bastien.",
        "Gus wants to thank Bastien first.",
        "Gus hesitates: should he speak to Bastien?",
        "Ask Gus if he should talk to Romy.",
    ],
    ids=["report", "wonders", "wants", "inverted", "pronoun"],
)
def test_own_act(objective):
    mismatch = engine.objective_addressee_mismatch(objective, GUS, CAST)
    assert mismatch is None, f"Gus' own act read as an order to the learner: {mismatch[1]}"


@pytest.mark.parametrize(
    "objective",
    [
        # The #1013 review: real instructions to the learner, after a clause that names
        # another cast member. Gus answers, so each is the WP-103 T4 mismatch.
        "Gus is nervous, so ask Bastien to help him.",
        "While Romy is away, ask Bastien where the keys are.",
        "Romy is late: ask Bastien where she is.",
        "Since Lila is late, talk to Bastien about the bench.",
        "Lila left her coat, tell Bastien.",
        "Gus asks you to speak to Bastien.",
        "Bastien is at the bar; tell Bastien you're here.",
        "Gus is here. Then ask Bastien to sit down.",
        "Ask Bastien to leave.",
        "Gus asks if you should speak to Bastien.",
        "Gus says to ask Bastien first.",
        "Romy wants you to thank Bastien.",
    ],
    ids=["so", "while", "colon", "since", "comma", "asks-you", "semicolon", "then", "bare",
         "if-you", "says-to", "wants-you"],
)
def test_still_t4(objective):
    mismatch = engine.objective_addressee_mismatch(objective, GUS, CAST)
    assert mismatch is not None, f"the WP-103 T4 guard lets «{objective}» through"
    other, word = mismatch
    assert other["id"] == "bastien_roux" and word == "Bastien"
