"""P1 (pilot 17 Nov): a stored fault never stamps a correct reply.

Walk 17 Nov, finding 1: after one old slip «lui → leur», every later scene reply
containing «lui» was stamped «→ leur · On dit « leur », pas « lui »» — about eight
times, on correct sentences, and once reversed («leur → lui») on a correct plural.
The stored pair was matched by its word alone, and the only gate proved that the
swapped sentence is acceptable French, not that the learner's was wrong. A stored
fault now needs independent evidence in this sentence (the model-free rule pass
flags the same span with the same fix), a season day's margin note is held to
once per scene, and the turn's own correction outranks a stored one.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.services import journey_content as jc_content
from app.services import journey_conversation as jc
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    Correction,
    InputMode,
    ResponseEvaluation,
    TaskOutcome,
)
from tests.test_wp36_self_repair import _user, record

LUI_LEUR = "On dit « leur », pas « lui » : le complément est au pluriel."
LEUR_LUI = "On dit « lui », pas « leur » : le complément est au singulier."
NOTAIRE = "«notaire» est masculin ici : à + le = au."


@pytest.fixture(autouse=True)
def _clear_content_cache():
    jc_content.reset_content_cache()
    yield
    jc_content.reset_content_cache()


def _brief(db_session, user, *, season: bool):
    brief = jc_content.resolve_scenario_brief(db_session, user=user, scenario_key=CapabilityKey.ORDER_AT_CAFE)
    if season:
        brief = replace(brief, story_context={**(brief.story_context or {}), "season": {"kind": "gap"}})
    return brief


def _decide(db_session, user, text, *, season: bool, history=None, turn_index=0):
    brief = _brief(db_session, user, season=season)
    return jc.feedback_decision(
        db_session,
        user=user,
        scenario=brief,
        task=brief.response_task,
        text=text,
        turn_index=turn_index,
        history=history,
    )


@pytest.mark.parametrize("season", [True, False], ids=["margin", "question"])
@pytest.mark.parametrize(
    "wrong,right,why,text",
    [
        # (a) the walk's own sentence: «lui» is right before a singular person.
        ("lui", "leur", LUI_LEUR, "Je vais lui poser des questions directes."),
        # (b) the reversed stamp, on a correct plural.
        ("leur", "lui", LEUR_LUI, "Je vais le leur donner."),
    ],
)
def test_a_stored_pronoun_slip_never_stamps_a_correct_reply(db_session, wrong, right, why, text, season):
    user = _user(db_session)
    record(db_session, user, wrong=wrong, right=right, why=why, label=f"{wrong}->{right}")

    decision = _decide(db_session, user, text, season=season)

    assert decision.explicit is None, decision.explicit
    assert decision.prompt is None, decision.prompt


@pytest.mark.parametrize("season", [True, False], ids=["margin", "question"])
def test_a_real_recurrence_the_rule_pass_also_flags_is_still_surfaced(db_session, season):
    # (d) stored «à la notaire → au notaire»; the rule pass flags «à la» → «au» here too.
    user = _user(db_session)
    record(db_session, user, wrong="à la notaire", right="au notaire", why=NOTAIRE, label="à la->au")

    decision = _decide(db_session, user, "Demain je dois parler à la notaire.", season=season)

    if season:
        assert decision.reason == "recurrence_in_margin"
        assert decision.explicit is not None and decision.explicit.span_fr == "à la notaire"
        assert decision.explicit.corrected_fr == "au notaire"
    else:
        assert decision.reason == "recurrence" and decision.prompt is not None


def _turn(learner: str, correction: Correction | None) -> dict:
    """One persisted turn, in the shape ``daily_journey`` writes it."""

    return {
        "learner": learner,
        "character": "D'accord, on continue.",
        "correction": (
            {"span_fr": correction.span_fr, "corrected_fr": correction.corrected_fr,
             "note_native": correction.note_native, "kind": "edit"}
            if correction is not None else None
        ),
        "free": False,
    }


def test_a_season_scene_carries_at_most_one_stored_fault_note(db_session):
    # (c) three replies, each genuinely repeating the stored slip, on one season page.
    user = _user(db_session)
    record(db_session, user, wrong="à la notaire", right="au notaire", why=NOTAIRE, label="à la->au")
    replies = [
        "Je parle à la notaire ce matin.",
        "Ensuite je retourne à la notaire avec les papiers.",
        "Et je téléphone à la notaire ce soir.",
    ]

    history: list[dict] = []
    notes = 0
    for index, reply in enumerate(replies):
        decision = _decide(db_session, user, reply, season=True, history=list(history), turn_index=index)
        if decision.explicit is not None or decision.prompt is not None:
            notes += 1
        history.append(_turn(reply, decision.explicit))

    assert notes <= 1, notes


def _graded(correction: Correction | None) -> ResponseEvaluation:
    return ResponseEvaluation(
        outcome=TaskOutcome.MET,
        assistance=AssistanceLevel.NONE,
        observations=[],
        character_reply_fr="Très bien.",
        correction=correction,
        needs_repair=False,
        turn_consumed=True,
        pending=False,
    )


def test_the_turns_own_correction_outranks_a_stored_margin_note(db_session):
    user = _user(db_session)
    record(db_session, user, wrong="à la notaire", right="au notaire", why=NOTAIRE, label="à la->au")
    text = "Je vais à la notaire et je suis fatigue."
    brief = _brief(db_session, user, season=True)
    decision = _decide(db_session, user, text, season=True)
    assert decision.reason == "recurrence_in_margin"

    own = Correction(span_fr="fatigue", corrected_fr="fatigué", note_native="Accent on the participle.")
    evaluation = jc.apply_feedback_policy(
        _graded(own),
        db_session,
        user=user,
        task=brief.response_task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        turn_index=0,
        decision=decision,
    )

    assert evaluation.correction == own
