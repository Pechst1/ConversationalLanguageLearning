"""#250 / #93: a stored mistake is only a mistake again if it is wrong *here*.

The scene's margin note and the self-repair question matched a stored erratum
by its word alone. «suis → est» (right after «Lila») was shown on «je suis
fatigue»; a drill's «est → sont» (right after «ils») was shown on «mon chat est»
and «Elle est», with a subject «ils» none of those sentences had (live walks
26, 27, 28, 29 and 30 Oct). The pair is now put back into the learner's own
sentence and passes ``correction_contract.verify_edit`` first.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services.journey_contracts import CapabilityKey
from tests.test_wp36_self_repair import _user, record

SUIS_EST = "You wrote «suis», the form for «je»; this subject requires «est»."
EST_SONT = "With the plural subject « ils », the expected form is « sont »."


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc_content.reset_content_cache()
    yield
    jc_content.reset_content_cache()


def _decide(db_session, user, text, *, season: bool):
    brief = jc_content.resolve_scenario_brief(db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE)
    if season:
        brief = replace(brief, story_context={**(brief.story_context or {}), "season": {"kind": "gap"}})
    return jc.feedback_decision(
        db_session, user=user, scenario=brief, task=brief.response_task, text=text, turn_index=0, history=None
    )


LIVE = [
    # (stored wrong, stored right, stored why, the learner's new sentence)
    ("suis", "est", SUIS_EST, "Je suis à Paris parce que je suis fatigue de Berlin. Mais j ai peur de le restaurant."),
    ("est", "sont", EST_SONT, "Ecris: mon chat est tres grand. Lila, tu a un chat aussi ?"),
    ("est", "sont", EST_SONT, "Je ne vends pas la appartement a la coop. Elle est a ma grand-mère."),
    ("est", "sont", EST_SONT, "Non, Gus, je ne promets pas. Je pense que Solvel est une bon offre pour la maison."),
    ("est", "es", "With « tu », « est » must be « es ».", "Odile est parti parce que la restaurant est fermé."),
]


@pytest.mark.parametrize("season", [True, False], ids=["margin", "question"])
@pytest.mark.parametrize("wrong,right,why,text", LIVE)
def test_a_stored_form_that_is_right_in_the_new_sentence_is_never_corrected(
    db_session, wrong, right, why, text, season
):
    user = _user(db_session)
    record(db_session, user, wrong=wrong, right=right, why=why, label=f"{wrong}->{right}")

    decision = _decide(db_session, user, text, season=season)

    assert decision.explicit is None, decision.explicit
    assert decision.prompt is None, decision.prompt


@pytest.mark.parametrize("season", [True, False], ids=["margin", "question"])
def test_the_same_slip_in_a_sentence_where_it_is_wrong_still_recurs(db_session, season):
    user = _user(db_session)
    record(db_session, user, wrong="suis", right="est", why="After «Lila», être is «est».", label="suis->est")

    decision = _decide(db_session, user, "Lila suis très contente aujourd'hui.", season=season)

    if season:
        assert decision.reason == "recurrence_in_margin"
        assert decision.explicit is not None and decision.explicit.span_fr == "suis"
        assert decision.explicit.corrected_fr == "est"
    else:
        assert decision.reason == "recurrence" and decision.prompt is not None


def test_a_gender_slip_still_recurs_in_the_margin(db_session):
    user = _user(db_session)
    record(db_session, user)  # une café -> un café

    decision = _decide(db_session, user, "Je voudrais une café, s'il vous plaît.", season=True)

    assert decision.reason == "recurrence_in_margin"
    assert decision.explicit is not None and decision.explicit.corrected_fr == "un café"


# ---------------------------------------------------------------------------
# The checker itself: two holes the recurrence walked through
# ---------------------------------------------------------------------------


def test_a_note_that_hangs_its_rule_on_the_plural_subject_ils_needs_ils():
    from app.services.answer_acceptance import correction_is_grounded

    text = "Je ne vends pas la appartement. Elle est a ma grand-mère."
    assert not correction_is_grounded(text, "est", "sont", EST_SONT)
    assert not correction_is_grounded(text, "est", "sont", "mit dem Subjekt „ils“ heißt es «sont»")
    assert correction_is_grounded("Ils est contents.", "est", "sont", EST_SONT)


@pytest.mark.parametrize(
    "text,ok",
    [
        ("Je pense que Solvel est une bon offre.", False),
        ("Ecris: mon chat est tres grand.", False),
        ("Mes amis est contents.", True),
        ("Paul et Marie est là.", True),
        ("Les enfants est fatigués.", True),
        ("Où est les toilettes ?", True),  # the plural subject follows the verb
    ],
)
def test_a_singular_form_is_made_plural_only_after_something_plural(text, ok):
    from app.services import correction_contract

    assert correction_contract.verify_edit(text, "est", "sont").ok is ok


def test_free_production_shows_only_errata_about_the_answer():
    from app.services.forge_grading import refine_production_correction

    answer = "Je pense que Solvel est une bon offre."
    refined = refine_production_correction(
        {
            "verdict": "partial",
            "errata": [
                {"learner_text": "est", "corrected_target": "sont", "why_wrong": EST_SONT,
                 "task_error_type": "grammar_target"},
                {"learner_text": "une bon", "corrected_target": "une bonne",
                 "why_wrong": "«offre» is feminine.", "task_error_type": "grammar_target"},
            ],
        },
        learner_text=answer,
        accepted=["Je pense que Solvel est une bonne offre."],
    )
    shown = [(e["learner_text"], e["corrected_target"]) for e in refined["errata"]]
    assert ("est", "sont") not in shown
    assert ("une bon", "une bonne") in shown
    assert {"learner_text": "est", "reason": "not_in_sentence"} in refined["dropped_errata"]


def test_free_production_shows_the_settled_fix_even_when_nothing_is_dropped():
    from app.services.forge_grading import refine_production_correction

    refined = refine_production_correction(
        {
            "verdict": "partial",
            "errata": [
                {"learner_text": "la", "corrected_target": "le", "why_wrong": "«appartement» is masculine.",
                 "task_error_type": "grammar_target"},
            ],
        },
        learner_text="Je visite la appartement.",
        accepted=["Je visite l'appartement."],
    )
    assert [(e["learner_text"], e["corrected_target"]) for e in refined["errata"]] == [
        ("la appartement", "l'appartement")
    ]


# ---------------------------------------------------------------------------
# The Feuilleton short sentence goes through the same checker
# ---------------------------------------------------------------------------


def _model_reading(errata, *, verdict="partial", corrected=""):
    return {"verdict": verdict, "score_0_4": 2, "corrected_answer": corrected, "why": "model why",
            "repair": "model repair", "errata": errata}


def test_the_feuilleton_drops_a_correction_about_a_subject_the_sentence_lacks():
    from app.services.graphic_novel import _held_to_sentence

    text = "Mon chat est très grand."
    out = _held_to_sentence(
        _model_reading(
            [{"learner_text": "est", "corrected_target": "sont", "why_wrong": EST_SONT, "repair_hint": "",
              "task_error_type": "grammar"}],
            corrected="Mon chat sont très grand.",
        ),
        text,
    )
    assert out["errata"] == []
    assert out["corrected_answer"] == text and out["verdict"] == "accepted"
    assert "ils" not in out["why"]


def test_the_feuilleton_keeps_a_real_fix_and_adds_what_the_model_missed():
    from app.services.graphic_novel import _held_to_sentence

    text = "Je ne vends pas la appartement. Elle est a ma grand-mère."
    out = _held_to_sentence(
        _model_reading(
            [{"learner_text": "est", "corrected_target": "sont", "why_wrong": EST_SONT, "repair_hint": "",
              "task_error_type": "grammar"}]
        ),
        text,
    )
    shown = {(e["learner_text"], e["corrected_target"]) for e in out["errata"]}
    assert ("est", "sont") not in shown
    assert ("la appartement", "l'appartement") in shown
    assert out["verdict"] == "partial" and "l'appartement" in out["corrected_answer"]


def test_the_feuilleton_leaves_a_verified_reading_as_the_model_wrote_it():
    from app.services.graphic_novel import _held_to_sentence

    reading = _model_reading(
        [{"learner_text": "une café", "corrected_target": "un café", "why_wrong": "«café» is masculine.",
          "repair_hint": "un café", "task_error_type": "gender"}],
        corrected="Je voudrais un café.",
    )
    out = _held_to_sentence(reading, "Je voudrais une café.")
    assert out["verdict"] == "partial" and out["why"] == "model why"
    assert [(e["learner_text"], e["corrected_target"]) for e in out["errata"]] == [("une café", "un café")]
