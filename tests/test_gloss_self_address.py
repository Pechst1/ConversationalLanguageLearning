"""#970: the line under Gus' scene prompt read «Gus asks if he should speak to Gus or
stay silent.» — the speaker named as his own addressee.

Live walk 21 Nov (A1.1, day 39, «Bastien mesure le Mistral»). Gus opens with «Je dis ce
que cette banquette est pour moi, ou je me tais et je m'assieds ?» and the model's task
line reported his question: «Gus asks if he should speak to Bastien or stay silent.»
The addressee guard (WP-103 T4) read «speak to Bastien» as an instruction to the
learner, saw Bastien was not the one who answers, and re-addressed the line to Gus.

The rule: a gloss never names the speaker as its own addressee. Fake provider only.
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


def test_a_report_of_what_the_speaker_asks_is_not_readdressed_to_the_speaker():
    served = _served_objective(WRITTEN)
    assert "speak to Gus" not in served, f"the speaker is named as his own addressee: {served!r}"
    assert served == WRITTEN


def test_a_report_of_the_speaker_is_no_addressee_mismatch():
    # «Gus asks if he should speak to Bastien»: Bastien is the one Gus might speak to,
    # not the one the learner is told to answer.
    assert engine.objective_addressee_mismatch(WRITTEN, GUS, CAST) is None
    # The instructions the guard exists for are still mismatches.
    other, word = engine.objective_addressee_mismatch("Ask Bastien to leave.", GUS, CAST)
    assert other["id"] == "bastien_roux" and word == "Bastien"


def test_the_served_gloss_from_the_walk_is_caught_and_repaired():
    served = _served_objective(SERVED)
    assert "speak to Gus" not in served, f"the speaker is named as his own addressee: {served!r}"
    assert served == "Gus asks if he should speak or stay silent."


def test_the_re_address_never_makes_the_speaker_its_own_addressee():
    # A real mismatch (the learner is told to ask Bastien while Gus answers) whose
    # re-address would also turn Gus' own act into «talk to Gus».
    served = _served_objective("Ask Bastien if Gus should talk to Bastien.")
    assert served == "Ask Gus if Gus should talk."


@pytest.mark.parametrize(
    ("text", "speaker", "expected"),
    [
        (SERVED, GUS, "Gus"),
        ("Gus wonders whether to talk to Gus.", GUS, "Gus"),
        ("Romy asks if she should call Romy.", "romy_tremblay", "Romy"),
        # The speaker spoken to, by a learner told to: no report, no self-address.
        ("Ask Gus if he wants to stay.", GUS, None),
        ("Tell Gus that Romy is late.", GUS, None),
        # Another member is the subject: not the speaker addressing himself.
        ("Romy asks if she should speak to Gus.", GUS, None),
        (WRITTEN, GUS, None),
    ],
)
def test_a_gloss_never_names_the_speaker_as_its_own_addressee(text, speaker, expected):
    from app.services.living_story import self_addressed

    assert self_addressed(text, speaker, CAST) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (SERVED, "Gus asks if he should speak or stay silent."),
        ("Gus wonders whether to talk to Gus.", "Gus wonders whether to talk."),
        ("Gus asks if he should ask Gus.", "Gus asks if he should ask himself."),
    ],
)
def test_the_self_address_is_taken_out(text, expected):
    from app.services.living_story import without_self_address

    gus = next(member for member in CAST if member["id"] == GUS)
    assert without_self_address(text, "Gus", gus) == expected
