"""Red-thread design, slice 4b: the stand-in page of a planned day.

A contract day whose page no writer delivered used to re-read the last page: the
story stood still. With ``STORY_CONTRACT_STAND_IN`` the day is served on its own
short page, written in ``gaps.json`` (``contract.stand_in``): four short panels, the
lead's question, the task and a reply to lean on. No model writes it, every guard reads it
in the learner's life, and the day lands on its contract like any planned day. Off,
or on a day without a stand-in, the day is lost as before.

Fake models only: nothing is spent.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.pilot_event import PilotEvent
from app.services import living_story as engine
from app.services.season import clock as season_clock
from app.services.season import day_contract
from app.services.season.format import load_season, validate_season
from tests import test_journey_end_to_end as support
from tests.test_day_contract_ending import (  # noqa: F401 - fixture
    _reads,
    contract_on,
)
from tests.test_season_one import (  # noqa: F401 - fixture
    _latest_scene,
    _play,
    _thread,
    season_on,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

LANES = pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)

STAND_INS = [
    (gap.id, beat.premise)
    for gap in load_season("s1").gaps.values()
    for beat in gap.days
    if beat.contract and beat.contract.stand_in
]


@pytest.fixture
def stand_in_on(monkeypatch, contract_on):  # noqa: F811
    monkeypatch.setattr(settings, "STORY_CONTRACT_STAND_IN", True, raising=False)


@pytest.fixture
def no_writer(monkeypatch):
    """Every attempt to write a page fails (the provider is down, every draft refused)."""

    approved = engine._approved
    calls: list[str] = []

    def lost(system, payload, schema, *args, **kwargs):
        if schema is engine.SceneDraft:
            calls.append("page")
            raise engine.StoryUnavailable("generation_failed")
        return approved(system, payload, schema, *args, **kwargs)

    monkeypatch.setattr(engine, "_approved", lost)
    return calls


def _learner(assembled_client, db_session, *, gap_id: str, premise: str, cefr: str = "A1.2", language: str = "en"):
    """A learner on the planned day of ``premise``, the gap's earlier days played."""

    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    season = load_season("s1")
    beat = next(row for row in season.gaps[gap_id].days if row.premise == premise)
    index = [segment.id for segment in season.segments].index(gap_id)
    email = f"s1-standin-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr=cefr), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    user.native_language = language
    jump_to_day(db_session, user, day=sum(segment.days for segment in season.segments[:index]) + beat.day)
    thread = _thread(db_session, user.id)
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    block = dict(live.get(season_clock.SEASON_KEY) or {})
    staged = [row.premise for row in season.gaps[gap_id].days if row.day < beat.day]
    block["premises"] = [*(block.get("premises") or []), *[{"gap": gap_id, "premise": row} for row in staged]]
    thread.state = {**state, engine.STATE_KEY: {**live, season_clock.SEASON_KEY: block}}
    db_session.commit()
    return d, user


def _served(db_session, user) -> list[dict]:
    """The stand-in pages this learner was served (the pilot event of each)."""

    db_session.expire_all()
    rows = db_session.scalars(
        select(PilotEvent).where(PilotEvent.user_id == user.id, PilotEvent.event_type == "journey_story_stand_in")
    )
    return [{key: row.payload.get(key) for key in ("day", "premise", "band", "language", "reason")} for row in rows]


#: The bakery is not built in the test quarter and the day names no second place: a
#: page is never set where the learner cannot go, so that day keeps the re-read.
NOT_BUILT = {"le_lendemain"}


# --- the data ----------------------------------------------------------------------


def test_the_planned_days_with_somebody_to_ask_have_a_stand_in():
    season = load_season("s1")
    assert len(STAND_INS) == 11
    for gap_id in ("g3", "g4"):
        for beat in season.gaps[gap_id].days:
            # A day nobody leads (the ticket, alone) and Margaux's silent day keep the re-read.
            assert bool(beat.contract.stand_in) == (beat.premise not in ("le_billet_encore", "l_abattant")), beat.premise


@pytest.mark.parametrize(("gap_id", "premise"), STAND_INS)
@pytest.mark.parametrize("band", ["A1", "A2", "B1"])
@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_every_stand_in_is_a_page_at_every_level_and_in_every_language(gap_id, premise, band, language):
    season = load_season("s1")
    gap, beat = day_contract.beat_for(season, gap_id, premise)
    contract = beat.contract
    written = day_contract.stand_in_draft(
        season, gap, beat, band=band, language=language, places={contract.place}, speakers={contract.lead}, chapter=None
    )
    draft = engine.SceneDraft.model_validate(written)
    assert (draft.character_id, draft.location_id) == (contract.lead, contract.place)
    assert draft.season_checklist.premise_id == premise
    assert draft.season_checklist.hook_fr == contract.hook.fr.text(band)
    assert len(draft.panels) >= engine.MIN_SCENE_PANELS
    for panel, written_panel in zip(draft.panels, contract.stand_in.panels, strict=True):
        # A caption, or one line of the day's lead: nobody else speaks on this page.
        assert bool(panel.narration_fr) != bool(panel.dialogue)
        assert [line.character_id for line in panel.dialogue] == ([contract.lead] if written_panel.says else [])
    level = "a1" if band == "A1" and contract.stand_in.asks.a1 else "a2"
    assert draft.opening_line_fr == getattr(contract.stand_in.asks, level)
    if language == "fr":
        assert draft.translation_native == draft.opening_line_fr
    else:
        assert draft.translation_native != draft.opening_line_fr
        assert all(panel.alt_native and panel.alt_native != panel.narration_fr for panel in draft.panels)
    # One task, in the reader's language; English reads the turn's own ask.
    asks = contract.turns[0].ask
    if language == "en":
        assert draft.objective_native == (asks.get("b1") if band == "B1" else None or asks["a1"])
    else:
        assert draft.objective_native in {row[language] for row in contract.stand_in.task.values()}


def test_a_stand_in_needs_its_lead_and_one_of_its_places():
    season = load_season("s1")
    gap, beat = day_contract.beat_for(season, "g3", "les_canapes")
    contract = beat.contract
    common = {"band": "A1", "language": "en", "chapter": None}
    assert day_contract.stand_in_draft(season, gap, beat, places=set(), speakers={contract.lead}, **common) is None
    assert day_contract.stand_in_draft(season, gap, beat, places={contract.place}, speakers=set(), **common) is None
    # The place the quarter has not built yet: the day's second place.
    moved = day_contract.stand_in_draft(season, gap, beat, places={contract.place_alt}, speakers={contract.lead}, **common)
    assert moved["location_id"] == contract.place_alt
    # An open chapter is kept, never replaced.
    chapter = {"title_fr": "La fête", "dramatic_question": "La fête aura-t-elle lieu ?", "possible_developments": ["Oui.", "Non."]}
    kept = day_contract.stand_in_draft(
        season, gap, beat, places={contract.place}, speakers={contract.lead}, band="A1", language="en", chapter=chapter
    )
    assert kept["chapter"] == chapter


def test_a_stand_in_that_breaks_the_format_is_named():
    season = load_season("s1")
    gap = season.gaps["g3"]
    beat = next(row for row in gap.days if row.premise == "les_canapes")
    page = beat.contract.stand_in

    def problems(**update) -> list[str]:
        contract = beat.contract.model_copy(update=update)
        days = [row.model_copy(update={"contract": contract}) if row is beat else row for row in gap.days]
        changed = season.model_copy(update={"gaps": {**season.gaps, "g3": gap.model_copy(update={"days": days})}})
        return [row for row in validate_season(changed) if "stand-in" in row]

    assert problems() == []
    assert any("needs a lead" in row for row in problems(lead=None))
    slotted = page.model_copy(update={"reply_fr": {"a2": "Le {g3.canape_name}."}})
    assert any("carries no slot" in row for row in problems(stand_in=slotted))
    untranslated = page.model_copy(update={"asks": page.asks.model_copy(update={"native": {"en": "Taste."}})})
    assert any("asks has no de translation" in row for row in problems(stand_in=untranslated))
    # Gap 3 never says where Lila is going.
    spoiled = page.model_copy(update={"reply_fr": {"a2": "Lila part à Berlin."}})
    assert any("forbids" in row for row in problems(stand_in=spoiled))


# --- a whole day -------------------------------------------------------------------


@LANES
def test_the_day_nobody_could_write_is_still_todays_day_of_the_story(
    assembled_client, db_session, journey_enabled, clock, season_on, stand_in_on, no_writer, monkeypatch  # noqa: F811
):
    _reads(season_on, monkeypatch, route="named", mark="le petit bateau")
    d, user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    journey = _play(d, season_on, clock, "Le deux. Le petit bateau.")
    assert no_writer and not season_on.director_contexts()
    assert _served(db_session, user) == [
        {"day": "g3.5", "premise": "les_canapes", "band": "A1", "language": "en", "reason": "generation_failed"}
    ]
    payload = _latest_scene(db_session, user.id).script_payload or {}
    assert payload.get("season", {}).get("key") == "g3.5"
    assert payload["season"].get("reprise") is None
    page = load_season("s1").gaps["g3"].days[4].contract.stand_in
    episodes = assembled_client.get(f"/api/v1/story-engine/episodes?journey_id={journey['id']}", headers=d.headers)
    printed = json.dumps(episodes.json(), ensure_ascii=False)
    assert page.asks.a1 in printed
    for row in page.panels:
        assert (row.text.a1 or row.text.a2) in printed
    # The day lands on its contract: the season has moved to the next planned day.
    assert journey["status"] in ("completed", "complete")
    thread = _thread(db_session, user.id)
    block = (thread.state or {})[engine.STATE_KEY][season_clock.SEASON_KEY]
    assert {"gap": "g3", "premise": "les_canapes"} in [
        {"gap": row.get("gap"), "premise": row.get("premise")} for row in block.get("premises") or []
    ]


@LANES
def test_off_the_lost_day_is_a_re_read_as_before(
    assembled_client, db_session, journey_enabled, clock, season_on, contract_on, no_writer  # noqa: F811
):
    d, user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    _play(d, season_on, clock, "Le petit bateau.")
    assert _served(db_session, user) == []
    thread = _thread(db_session, user.id)
    block = (thread.state or {})[engine.STATE_KEY][season_clock.SEASON_KEY]
    # A re-read settles nothing: the planned day is still owed.
    assert "les_canapes" not in [row.get("premise") for row in block.get("premises") or []]


@LANES
@pytest.mark.parametrize(("gap_id", "premise"), STAND_INS)
@pytest.mark.parametrize(("cefr", "language"), [("A1.2", "de"), ("B1.1", "en")], ids=["A1-de", "B1-en"])
def test_every_stand_in_passes_every_guard_in_a_life(
    assembled_client, db_session, journey_enabled, clock, season_on, stand_in_on, no_writer, gap_id, premise, cefr, language  # noqa: F811
):
    from app.services.journey_contracts import InputMode

    _d, user = _learner(assembled_client, db_session, gap_id=gap_id, premise=premise, cefr=cefr, language=language)
    brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    if premise in NOT_BUILT:
        assert isinstance(brief, engine.ContentUnavailable)
        return
    assert not isinstance(brief, engine.ContentUnavailable), brief
    assert brief.story_context["stand_in"] == {"reason": "generation_failed"}
    assert brief.story_context["draft"]["season_checklist"]["premise_id"] == premise


@LANES
def test_the_night_before_leaves_the_morning_its_try(
    assembled_client, db_session, journey_enabled, clock, season_on, stand_in_on, no_writer  # noqa: F811
):
    from app.services.journey_contracts import InputMode

    _d, user = _learner(assembled_client, db_session, gap_id="g3", premise="les_canapes")
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert isinstance(brief, engine.ContentUnavailable)
    assert _served(db_session, user) == []
