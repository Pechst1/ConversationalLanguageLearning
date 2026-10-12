"""N1 pilot — gap 1's «Romy enquête» day, where what the learner decides stays decided.

The learner tells Romy she may use what they said, but not their name. The
voice lane hears it (``acts``), the turn stores it before the reply is shown,
the day's settle commits it, and the next generated day of the gap is briefed
with the agreement and a callback that quotes the learner. Off by default.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.services import story_lanes
from app.services.season import agency
from app.services.season.clock import Position
from app.services.season.director import gap_brief
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.runtime import settle

ROMY_DAY = {
    "id": "s1",
    "kind": "gap",
    "position": {"segment": "g1", "day_in_segment": 1, "season_day": 3},
    "checklist": {"premise_id": "romy_enquete"},
}


@pytest.fixture()
def pilot(monkeypatch) -> None:
    monkeypatch.setattr(settings, "SEASON_AGENCY_PILOT", True)


def _act(text: str, action: str, quote: str, conditions=()) -> agency.VoiceAct:  # type: ignore[no-untyped-def]
    return agency.VoiceAct(
        action=action, subject="learner_account", conditions=list(conditions), evidence_quotes=[quote]
    )


def _details(text: str, *acts: agency.VoiceAct) -> dict:
    contract = agency.contract_for(ROMY_DAY)
    assert contract is not None
    return {"learner_text": text, **agency.acts_for_details(contract, list(acts), text=text)}


def _settled(details: dict, *, event_id: str = "day-romy") -> dict:
    live = {"season_script": {"id": "s1"}}
    after = settle(
        live,
        story_context={"season": ROMY_DAY},
        details={**details, "outcome": "met"},
        event_id=event_id,
        date_iso="2026-10-12",
        day_index=3,
    )
    return after["season_script"]


def test_off_by_default_the_day_is_untouched(monkeypatch) -> None:
    assert type(settings).model_fields["SEASON_AGENCY_PILOT"].default is False
    monkeypatch.setattr(settings, "SEASON_AGENCY_PILOT", False)
    assert agency.contract_for(ROMY_DAY) is None
    state = _settled({"learner_text": "Oui.", "season_acts": [{"action": "accept"}]})
    assert agency.STATE_KEY not in state
    assert agency.brief_extras("s1", "g1", 2, state={"agency": {"events": [{}]}}, seed="x") == {}


def test_only_the_premise_with_a_contract_gets_one(pilot) -> None:
    assert agency.contract_for(ROMY_DAY).speaker == "romy_tremblay"
    other = {**ROMY_DAY, "checklist": {"premise_id": "la_meme_chose"}}
    assert agency.contract_for(other) is None
    assert agency.contract_for({**ROMY_DAY, "kind": "tentpole"}) is None


def test_the_voice_reads_what_may_be_decided_and_the_turn_finds_its_contract_again(pilot) -> None:
    turn = agency.agency_for_turn(agency.contract_for(ROMY_DAY))
    assert turn["character"] == "romy_tremblay"
    assert set(turn["conditions"]) == {"no_name", "off_record"}
    assert {"accept", "decline"} <= set(turn["may_decide"][0]["actions"])
    assert agency.contract_from_turn(turn).premise == "romy_enquete"

    payload = {
        "story": {"season_turn": {"agency": turn}, "world": {"cast": []}},
        "scene": {"character_id": "romy_tremblay", "panels": []},
        "learner_text": "Oui, mais sans mon nom.",
        "history": [{"learner": "Je suis la petite-fille d'Odile.", "character": "Ah !"}],
    }
    assert story_lanes.voice_payload(payload)["agency"] == turn
    voice = story_lanes.VoiceReply(
        reply_fr="D'accord, sans ton nom.",
        understood_intent="Romy may use it without the name.",
        needs_clarification=False,
        acts=[_act(payload["learner_text"], "accept", "sans mon nom", ["no_name"])],
    )
    details = story_lanes._agency_details(payload, voice, payload["learner_text"])
    assert details["agency_decisions"] == ["commit"]
    assert details["agency_text"].startswith("Je suis la petite-fille d'Odile.")
    assert details["season_acts"][0]["evidence"][0]["text"] == "sans mon nom"


def test_a_day_without_agency_stores_nothing_extra() -> None:
    payload = {"story": {"season_turn": {}}, "learner_text": "Bonjour"}
    voice = story_lanes.VoiceReply(reply_fr="Salut.", understood_intent="Hello.", needs_clarification=False)
    assert story_lanes._agency_details(payload, voice, "Bonjour") == {}
    assert "agency" not in story_lanes.voice_payload(
        {"story": {"world": {"cast": []}}, "scene": {"panels": []}, "learner_text": "Bonjour"}
    )


def test_yes_but_not_my_name_is_committed_once_and_called_back(pilot) -> None:
    text = "Vous pouvez l'écrire, mais sans mon nom."
    state = _settled(_details(text, _act(text, "accept", "sans mon nom", ["no_name"])))
    world = agency.world_of(state)
    permission = world.permissions["learner_account>romy_tremblay"]
    assert permission.granted is True and permission.conditions == ["no_name"]

    again = _settled(_details(text, _act(text, "accept", "sans mon nom", ["no_name"])))
    assert agency.world_of(again).version == world.version  # one settle per day

    extras = agency.brief_extras("s1", "g1", 2, state=state, seed="learner-1")
    assert extras["agreements"] == ["The learner let Romy use what they told her, but not their name."]
    assert extras["callback"]["id"] == "romy_notes_without_name"
    assert extras["callback"]["learner_words"] == ["sans mon nom"]


def test_a_refusal_is_kept_as_a_refusal(pilot) -> None:
    text = "Non, je ne veux pas parler aux journalistes."
    state = _settled(_details(text, _act(text, "decline", "je ne veux pas parler aux journalistes")))
    assert agency.world_of(state).permissions["learner_account>romy_tremblay"].granted is False
    extras = agency.brief_extras("s1", "g1", 2, state=state, seed="s")
    assert extras["callback"]["id"] == "romy_leaves_her_card"


def test_a_limit_romy_cannot_keep_commits_nothing(pilot) -> None:
    text = "Oui, si je relis l'article avant."
    details = _details(text, _act(text, "accept", "si je relis l'article avant", ["approve_before_print"]))
    assert details["agency_decisions"] == ["acknowledge"]
    state = _settled(details)
    assert agency.STATE_KEY not in state


def test_a_quote_the_learner_never_wrote_commits_nothing(pilot) -> None:
    text = "Euh… oui ?"
    details = _details(text, _act(text, "accept", "Oui, publiez tout"))
    assert details["agency_decisions"] == ["clarify"]
    assert agency.STATE_KEY not in _settled(details)


def test_a_staged_callback_is_played_once(pilot) -> None:
    text = "Oui, mais off the record."
    state = _settled(_details(text, _act(text, "accept", "off the record", ["off_record"])))
    extras = agency.brief_extras("s1", "g1", 2, state=state, seed="s")
    assert extras["callback"]["id"] == "romy_keeps_it_off_record"

    next_day = {**ROMY_DAY, "position": {"segment": "g1", "day_in_segment": 2, "season_day": 4},
                "checklist": {"premise_id": "la_meme_chose"}, "callback": extras["callback"]}
    live = settle(
        {"season_script": state},
        story_context={"season": next_day},
        details={"learner_text": "Un café.", "outcome": "met"},
        event_id="day-after",
        date_iso="2026-10-13",
        day_index=4,
    )
    later = agency.brief_extras("s1", "g1", 3, state=live["season_script"], seed="s")
    assert "callback" not in later
    assert later["agreements"]  # the agreement still stands


def test_the_director_brief_carries_the_agreement_and_the_callback(pilot) -> None:
    text = "Vous pouvez l'écrire, mais sans mon nom."
    state = _settled(_details(text, _act(text, "accept", "sans mon nom", ["no_name"])))
    season = load_season("s1")
    gap_start = next(i for i, seg in enumerate(season.segments) if seg.id == "g1")
    segment = season.segments[gap_start]
    pos = Position(season_id="s1", segment=segment, segment_index=gap_start, day_in_segment=2, season_day=4, flex=0)
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    assert brief["today"]["agreements"]
    assert brief["today"]["callback"]["id"] == "romy_notes_without_name"
