"""#752: a reply is graded against the person it answers, not a person from another day.

Walk 13 Nov 2026 (persona ``b1-fr-chrome``), day 2 «La lettre», turn ``b.turn1``
(``to: camille_marchand``). Camille asks «Vous allez vendre, j'imagine ?» and the learner
answers «… Plus simple pour vous et pour votre grand-père …». The margin showed
«Forme corrigée : → te» with «On dit « te », pas « vous ». Ici, c'est « tu » : Margaux te
tutoie, et le verbe suit.»

The register check itself (``register_corrections`` → ``addressee_of``) reads Camille and
«vous» on that turn: those cases are pinned below as guards. The correction came from the
*recurrence* check (``feedback_decision``, «recurrence_in_margin»): on day 1 the learner
said «je vous …» to Margaux, the register rule filed «vous → te» with Margaux's reason,
and on day 2 any «vous» in any sentence matched that stored pair again.

ROOT CAUSE (#147): whether «vous» is wrong is a property of the person the learner is
talking to, but a register correction was filed and replayed as a bare word pair, so the
recurrence path re-applied it to whoever the learner answered next, with the old
person's name in the note.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models.user import User
from app.services import address
from app.services.journey_contracts import ResponseTask, ScenarioBrief
from app.services.journey_conversation import (
    expected_counterpart_register,
    feedback_decision,
    register_corrections,
)
from app.services.season import runtime
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from tests.test_register_594 import offline  # noqa: F401 - the offline router fixture
from tests.test_season_story_qa import _record, _say, _scenario
from tests.test_wp36_self_repair import record

#: Every reply is routed by the matcher alone: no model, no margin lane.
pytestmark = pytest.mark.usefixtures("offline")

#: The learner's reply on the walk, verbatim.
TO_CAMILLE = (
    "Non, pas encore. Plus simple pour vous et pour votre grand-père, peut-être. "
    "La lettre du notaire, je vais lui la montrer à Margaux avant de décider. "
    "Pourquoi Solvel veut tout l immeuble ?"
)
#: What day 1 filed when the learner said «je vous …» to Margaux (``register_corrections``
#: wrote it; ``_record_correction_erratum`` stored it as a word pair with this note).
MARGAUX_NOTE = "Ici, c’est « tu » : Margaux te tutoie, et le verbe suit."


def _user(db_session) -> User:
    """The walk's persona: French chrome, B1.1."""

    user = User(
        id=uuid4(),
        email=f"register-752-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
        proficiency_level="B1",
        cefr_estimate="B1.1",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _day_two(state: dict | None = None) -> dict:
    season = load_season("s1")
    flags = effective_flags(season, state or {}, seed="x")
    return resolve_day(season, "t1", "b", flags=flags, band="B1", language="fr")


def _brief(story_context: dict, *, opening: str, title: str = "La lettre") -> ScenarioBrief:
    """Day 2 as the journey holds it: the scene's character is its first speaker."""

    task = ResponseTask(
        objective_native="Réponds à Camille.",
        character_id="camille_marchand",
        character_name="Camille Marchand",
        opening_line_fr=opening,
        max_turns=4,
    )
    return ScenarioBrief(
        scenario_key="season_s1_t1_b",
        content_version="journey-content-v1",
        title_fr=title,
        objective_key="season.s1.t1.b",
        objective_native="Réponds à Camille.",
        level_band="B1",
        character_id="camille_marchand",
        character_name="Camille Marchand",
        location_id="le_mistral",
        location_name="Le Mistral",
        image_url=None,
        setup_fr="",
        setup_native="",
        opening_line_fr=opening,
        response_task=task,
        story_context=story_context,
    )


def _first_reply():
    """``b.turn1`` is owed: nothing has been answered yet on this page."""

    scenario = _scenario(_day_two())
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    assert turns[0]["id"] == "b.turn1" and turns[0]["to"] == "camille_marchand"
    brief = _brief(scenario.story_context, opening="Vous allez vendre, j'imagine ? Ce serait plus simple pour tout le monde.")
    return brief, []


def _only(turn_id: str, page: dict) -> ScenarioBrief:
    """A page reduced to the one turn being answered (as ``test_register_594.test_turn``)."""

    turn = next(row for row in runtime.projected_turns(page) if row["id"] == turn_id)
    only_this = {**turn}
    only_this.pop("only_after", None)
    ctx = {
        "id": "s1",
        "kind": "tentpole",
        "page": page,
        "turns": [only_this],
        "tail": [],
        "ending": {},
        "position": {"key": "t1:b"},
    }
    return _brief({"scene_id": f"752-{turn_id}", runtime.SEASON_CONTEXT_KEY: ctx}, opening="")


def _margaux_filed_vous_to_te(db_session, user):
    return record(
        db_session,
        user,
        wrong="vous",
        right="te",
        why=MARGAUX_NOTE,
        label="Reprise : vous",
        task_type="journey_correction",
    )


# ---------------------------------------------------------------------------
# The bug: day 1's «vous → te» (to Margaux) corrected a «vous» to Camille
# ---------------------------------------------------------------------------


def test_camille(db_session) -> None:
    """The walk: day 1 filed «vous → te» (Margaux); the «vous» to Camille is right."""

    user = _user(db_session)
    _margaux_filed_vous_to_te(db_session, user)
    brief, history = _first_reply()

    decision = feedback_decision(
        db_session, user=user, scenario=brief, task=brief.response_task, text=TO_CAMILLE,
        turn_index=0, history=history,
    )

    shown = decision.explicit or decision.prompt
    assert shown is None, (
        f"Camille says vous to the learner (b.turn1, to camille_marchand); the reply's «vous» "
        f"was corrected anyway ({decision.reason}): {shown}"
    )


def test_who(db_session) -> None:
    """Guard (the triage's done-when): the register check itself reads Camille, vous."""

    brief, history = _first_reply()

    found = expected_counterpart_register(
        scenario=brief, task=brief.response_task, history=history, native_language="fr"
    )
    _assessment, candidates = register_corrections(
        user=_user(db_session), text=TO_CAMILLE, scenario=brief, task=brief.response_task, history=history
    )

    assert (found.expected, found.counterpart) == ("vous", "Camille")
    assert [(c.span_fr, c.corrected_fr) for c in candidates] == []


# ---------------------------------------------------------------------------
# The same slip to someone who does say tu is still a slip, under their own name
# ---------------------------------------------------------------------------


def test_margaux(db_session) -> None:
    """``b.key`` is to Margaux, who says tu: a «vous» there is still corrected, naming her."""

    user = _user(db_session)
    brief = _only("b.key", _day_two({"flags": {"s1.key_with": "margaux"}}))
    text = "Bonsoir. Je vous demande ma clé, s'il vous plaît."

    _assessment, candidates = register_corrections(
        user=user, text=text, scenario=brief, task=brief.response_task, history=[]
    )
    assert [(c.span_fr, c.corrected_fr) for c in candidates] == [("vous", "te")]
    assert "Margaux" in candidates[0].note_native

    _margaux_filed_vous_to_te(db_session, user)
    decision = feedback_decision(
        db_session, user=user, scenario=brief, task=brief.response_task, text=text, turn_index=0, history=[]
    )
    assert decision.reason == "recurrence_in_margin", decision
    assert (decision.explicit.span_fr, decision.explicit.corrected_fr) == ("vous", "te")
    assert "Margaux" in decision.explicit.note_native


def _turn_to(person: str):
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    for tentpole_id, tentpole in season.tentpoles.items():
        for day in tentpole.days:
            page = resolve_day(season, tentpole_id, day.day, flags=flags, band="B1", language="fr")
            for turn in runtime.projected_turns(page):
                if turn.get("to") == person and turn.get("kind") == "turn":
                    return page, turn["id"]
    raise AssertionError(f"no S1 turn is to {person}")


def test_lila(db_session) -> None:
    """Lila says tu as well: the «vous» is a slip again, but the note is about Lila."""

    user = _user(db_session)
    _margaux_filed_vous_to_te(db_session, user)
    page, turn_id = _turn_to("lila_bonnet")
    brief = _only(turn_id, page)

    decision = feedback_decision(
        db_session, user=user, scenario=brief, task=brief.response_task,
        text="Oui, je vous attends au Mistral.", turn_index=0, history=[],
    )

    assert decision.explicit is not None, decision
    assert "Lila" in decision.explicit.note_native, decision.explicit.note_native
    assert "Margaux" not in decision.explicit.note_native, decision.explicit.note_native


# ---------------------------------------------------------------------------
# Guard: through every S1 page, the person the register check reads is the person
# the scene puts the next question in the mouth of
# ---------------------------------------------------------------------------


def _pages():
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    for tentpole_id, tentpole in season.tentpoles.items():
        for day in tentpole.days:
            page = resolve_day(season, tentpole_id, day.day, flags=flags, band="B1", language="fr")
            if runtime.projected_turns(page):
                yield pytest.param(page, id=f"{tentpole_id}:{day.day}")


@pytest.mark.parametrize("page", list(_pages()))
def test_page(page, monkeypatch) -> None:
    """Answered turn by turn, each owed turn's register is read from its own ``to``, and
    the person the header names next is the person the next reply is checked against."""

    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    scenario = _scenario(page)
    turns = scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    history: list[dict] = []
    checked: list[str] = []
    for exchange in range(len(turns) + 2):
        owed = runtime.current_turn(scenario, history)
        found = runtime.addressee_of(scenario, history)
        to = str((owed or {}).get("to") or "")
        if found is not None:
            assert found.id == to, f"{owed['id']} is to {to}; the register check reads {found.id}"
            assert found.register == address.known_register(None, to), (
                f"{owed['id']}: {to} says {address.known_register(None, to)}; the check expects {found.register}"
            )
            checked.append(str(owed["id"]))
        evaluation = _say(scenario, "D'accord.", history, exchange)
        _record(history, "D'accord.", evaluation)
        if evaluation.consequence is not None or not evaluation.character_reply_fr:
            break
        named = getattr(evaluation, "next_addressee", None)
        after = runtime.addressee_of(scenario, history)
        if named and after is not None:
            assert after.id == named, (
                f"after {owed['id']} the header names {named}; the next reply is checked against {after.id}"
            )
    assert checked, f"{page['title_fr']}: no turn was checked"
