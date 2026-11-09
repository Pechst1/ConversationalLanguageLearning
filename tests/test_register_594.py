"""#594: a scene reply is checked against the register of the person the turn is for.

Walk 8 Nov 2026: Margaux asks «Tu vas monter ?» (T1 A, turn 2, ``to: margaux_barman``)
and the learner answers in «tu». The note said «Hier gilt „vous“: Augustin « Gus » de
Roncourt siezt dich», and the exchange header named Gus.

ROOT CAUSE: how a person speaks to the learner is a property of the person (the cast:
``address.known_register``), but the register check read it from the scene
(``expected_counterpart_register``: the scene-wide declaration, or the lines the scene had
said so far, and ``task.character_name``, the scene's first speaker). An authored
season day has several addressees; only the first one is the scene's.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db.models.user import User
from app.services import address, cast_registry
from app.services.journey_contracts import ResponseTask, ScenarioBrief
from app.services.journey_conversation import (
    expected_counterpart_register,
    register_corrections,
)
from app.services.season import runtime
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from tests.test_season_story_qa import _page, _record, _say, _scenario


@pytest.fixture
def offline(monkeypatch):
    real = runtime.classify

    def classify(db, user, **kwargs):
        kwargs["use_model"] = False
        return real(db, user, **kwargs)

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"register-594-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _brief(story_context: dict, *, opening: str) -> ScenarioBrief:
    """T1 A as the journey holds it: the scene's character is its first speaker, Gus."""

    task = ResponseTask(
        objective_native="Say who you are.",
        character_id="augustin_de_roncourt",
        character_name="Augustin « Gus » de Roncourt",
        opening_line_fr=opening,
        max_turns=4,
    )
    return ScenarioBrief(
        scenario_key="season_s1_t1_a",
        content_version="journey-content-v1",
        title_fr="Le mauvais accueil",
        objective_key="season.s1.t1.a",
        objective_native="Say who you are.",
        level_band="A1",
        character_id="augustin_de_roncourt",
        character_name="Augustin « Gus » de Roncourt",
        location_id="le_mistral",
        location_name="Le Mistral",
        image_url=None,
        setup_fr="",
        setup_native="",
        opening_line_fr=opening,
        response_task=task,
        story_context=story_context,
    )


def _after_gus_turn(offline_text: str = "Je viens pour vendre. L'appartement est à moi, maintenant."):
    """The scene at exchange 2: Gus was answered, Margaux has asked «Tu vas monter ?»."""

    page = _page()
    scenario = _scenario(page)
    history: list[dict] = []
    first = _say(scenario, offline_text, history, 0)
    _record(history, offline_text, first)
    assert first.route["turn"] == "a.turn1"
    assert "Tu vas monter ?" in first.character_reply_fr
    brief = _brief(scenario.story_context, opening="Alors ? Vous êtes qui, exactement ?")
    return brief, history


def test_tu(db_session, offline) -> None:
    brief, history = _after_gus_turn()
    _assessment, candidates = register_corrections(
        user=_user(db_session),
        text="oui je monte. Odile c est qui pour toi?",
        scenario=brief,
        task=brief.response_task,
        history=history,
    )
    shown = [(c.span_fr, c.corrected_fr, c.note_native) for c in candidates]
    assert shown == [], f"Margaux says tu to the learner; a tu reply was corrected: {shown}"


def test_who(db_session, offline) -> None:
    brief, history = _after_gus_turn()
    found = expected_counterpart_register(
        scenario=brief, task=brief.response_task, history=history, native_language="de"
    )
    assert (found.expected, found.counterpart) == ("tu", "Margaux")


def test_gus(db_session, offline) -> None:
    page = _page()
    scenario = _scenario(page)
    brief = _brief(scenario.story_context, opening="Alors ? Vous êtes qui, exactement ?")
    _assessment, candidates = register_corrections(
        user=_user(db_session),
        text="Je suis la petite-fille d'Odile. Tu veux quoi ?",
        scenario=brief,
        task=brief.response_task,
        history=[],
    )
    assert len(candidates) == 1, candidates
    assert "Gus" in candidates[0].note_native
    assert "vous" in candidates[0].note_native


def _cast_row(season, person):
    """The season's cast row for a turn's ``to`` (any spelling the registry knows), or None."""

    wanted = cast_registry.resolve_id(str(person or ""))
    return next(
        (row for row in season.cast if row.id == person or (wanted and cast_registry.resolve_id(row.id) == wanted)),
        None,
    )


def _authored_turns():
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    for tentpole_id, tentpole in season.tentpoles.items():
        for day in tentpole.days:
            page = resolve_day(season, tentpole_id, day.day, flags=flags, band="A1", language="de")
            for turn in runtime.projected_turns(page):
                if _cast_row(season, turn.get("to")) is not None:
                    yield pytest.param(page, turn, id=str(turn["id"]))


@pytest.mark.parametrize(("page", "turn"), list(_authored_turns()))
def test_turn(page, turn, monkeypatch) -> None:
    """The expected register of each S1 turn is the register of the person it is ``to``."""

    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    member = _cast_row(season, turn["to"])
    wanted = str(flags.get(f"register.{member.id}") or member.address)
    only_this = {**turn}
    only_this.pop("only_after", None)
    ctx = {
        "id": "s1",
        "kind": "tentpole",
        "page": page,
        "turns": [only_this],
        "tail": [],
        "ending": {},
        "position": {"key": "x"},
    }
    brief = _brief({"scene_id": "table", runtime.SEASON_CONTEXT_KEY: ctx}, opening="")
    found = expected_counterpart_register(
        scenario=brief, task=brief.response_task, history=[], native_language="de"
    )
    assert found.expected == wanted, (
        f"{turn['id']} is for {turn['to']} ({wanted}); the reply was checked against {found.expected} "
        f"({found.counterpart})"
    )
    assert address.known_register(None, turn["to"]) == wanted


def test_head(offline) -> None:
    """Gus asked exchange 1; the question put next is Margaux's, and so is the header."""

    scenario = _scenario(_page())
    first = _say(scenario, "Je viens pour vendre. L'appartement est à moi, maintenant.", [], 0)
    named = getattr(first, "next_addressee", None)
    assert named == "margaux_barman", f"exchange 2 is put by Margaux; the evaluation names {named!r}"

    from app.services.daily_journey import addressee_fields

    assert addressee_fields(named) == {"character_id": "margaux_barman", "character_name": "Margaux"}
    assert addressee_fields("toi") == {}
