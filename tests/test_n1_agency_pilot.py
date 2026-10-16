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
                "checklist": {"premise_id": "la_meme_chose"}, "callback": extras["callback"],
                "callback_staged": True}
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


# ---------------------------------------------------------------------------
# Any generated day: a contract the writer proposes is checked, not trusted
# ---------------------------------------------------------------------------

KEY_PROPOSAL = {
    "speaker": "lila_bonnet",
    "subjects": {"spare_key": "Whether Lila may keep a copy of the key to Odile's flat."},
    "conditions": {"mornings_only": "Only in the mornings, before school.", "ask_first": "She texts before coming."},
    "effects": [
        {
            "id": "lila_keeps_key",
            "actions": ["accept"],
            "subject": "spare_key",
            "allowed_conditions": ["mornings_only", "ask_first"],
            "outcome_en": "Lila has a copy of the key to Odile's flat.",
            "alternative_en": "Lila can come when the learner is there instead.",
        },
        {
            "id": "lila_no_key",
            "actions": ["decline"],
            "subject": "spare_key",
            "outcome_en": "Lila has no key; she paints at her own flat.",
        },
    ],
}

KEY_DAY = {
    "id": "s1",
    "kind": "gap",
    "position": {"segment": "g2", "day_in_segment": 1, "season_day": 12},
    "checklist": {"premise_id": None, "learner_agency": KEY_PROPOSAL},
}


def test_the_writers_contract_is_checked_not_trusted(pilot) -> None:
    contract = agency.generated_contract("s1", "g2", None, KEY_PROPOSAL)
    assert contract is not None and contract.premise == "own"
    assert [e.id for e in contract.effects] == ["lila_keeps_key", "lila_no_key"]

    assert agency.generated_contract("s1", "g2", None, {**KEY_PROPOSAL, "speaker": "a_stranger"}) is None
    assert agency.generated_contract("s1", "g2", None, "not a dict") is None
    wrong = {
        **KEY_PROPOSAL,
        "effects": [
            {**KEY_PROPOSAL["effects"][0], "allowed_conditions": ["mornings_only", "forever"]},
            {**KEY_PROPOSAL["effects"][1], "actions": ["teleport"]},
            {**KEY_PROPOSAL["effects"][1], "id": "Not A Slug"},
        ],
    }
    checked = agency.generated_contract("s1", "g2", None, wrong)
    assert [e.id for e in checked.effects] == ["lila_keeps_key"]
    assert checked.effects[0].allowed_conditions == ["mornings_only"]
    assert agency.generated_contract("s1", "g2", None, {**KEY_PROPOSAL, "effects": []}) is None


def test_the_checklist_keeps_a_proposal_and_drops_junk() -> None:
    from app.services.season.director import SeasonChecklist

    assert SeasonChecklist.model_validate({"learner_agency": KEY_PROPOSAL}).learner_agency == KEY_PROPOSAL
    assert SeasonChecklist.model_validate({"learner_agency": "lots"}).learner_agency is None


def _settle_on(day: dict, details: dict, *, live: dict | None = None, event_id: str, outcome: str = "met") -> dict:
    after = settle(
        live or {"season_script": {"id": "s1"}},
        story_context={"season": day},
        details={**details, "outcome": outcome},
        event_id=event_id,
        date_iso="2026-10-20",
        day_index=12,
    )
    return after["season_script"]


def test_any_generated_day_remembers_and_a_later_day_acts_on_it(pilot) -> None:
    contract = agency.contract_for(KEY_DAY)
    assert contract is not None and contract.speaker == "lila_bonnet"
    turn = agency.agency_for_turn(contract)
    assert agency.contract_from_turn(turn) == contract

    text = "Oui, garde une clé, mais envoie-moi un message avant."
    act = agency.VoiceAct(action="accept", subject="spare_key", conditions=["ask_first"],
                          evidence_quotes=["garde une clé", "envoie-moi un message avant"])
    details = {"learner_text": text, **agency.acts_for_details(contract, [act], text=text)}
    assert details["agency_decisions"] == ["commit"]
    state = _settle_on(KEY_DAY, details, event_id="g2-day1")

    extras = agency.brief_extras("s1", "g2", 2, state=state, seed="s")
    assert extras["agreements"] == [
        "Lila has a copy of the key to Odile's flat. Limits the learner set: She texts before coming."
    ]
    callback = extras["callback"]
    assert callback["character"] == "lila_bonnet"
    assert callback["learner_words"] == ["garde une clé", "envoie-moi un message avant"]

    # Staged the next day, it is not dealt again; the agreement still stands.
    next_day = {**KEY_DAY, "position": {"segment": "g2", "day_in_segment": 2, "season_day": 13},
                "checklist": {"premise_id": None}, "callback": callback}
    # A page that left the callback out keeps it owed.
    skipped = _settle_on({**next_day, "callback_staged": False}, {"learner_text": "Merci."},
                         live={"season_script": state}, event_id="g2-day2")
    assert agency.brief_extras("s1", "g2", 3, state=skipped, seed="s")["callback"]["id"] == callback["id"]
    # Walk 5: a staged callback is played even when the day's answer was not met.
    state = _settle_on({**next_day, "callback_staged": True}, {"learner_text": "Merci."},
                       live={"season_script": state}, event_id="g2-day2", outcome="not_met")
    later = agency.brief_extras("s1", "g2", 3, state=state, seed="s")
    assert "callback" not in later
    assert later["agreements"]


def test_the_writer_is_asked_for_a_contract_only_with_the_pilot_on(pilot, monkeypatch) -> None:
    romy = {"state": {}, "seed": "s", "premise": "romy_enquete"}
    assert agency.brief_extras("s1", "g1", 1, **romy) == {"learner_agency_rules": agency.AGENCY_RULES}
    monkeypatch.setattr(settings, "SEASON_AGENCY_PILOT", False)
    assert agency.brief_extras("s1", "g1", 1, **romy) == {}
    assert agency.contract_for(KEY_DAY) is None


def _gap_day(gap_id: str, day: int, state: dict | None = None, *, seed: str = "x") -> dict:
    season = load_season("s1")
    index = next(i for i, seg in enumerate(season.segments) if seg.id == gap_id)
    pos = Position(
        season_id="s1", segment=season.segments[index], segment_index=index, day_in_segment=day, season_day=index + day
    )
    return gap_brief(season, pos, flags=effective_flags(season, state or {}, seed=seed), state=state or {}, seed=seed)


def _planned(gap_id: str, premise: str) -> tuple[int, dict]:
    """A day plan's day for ``premise``, with the beats before it already staged."""

    beats = sorted(load_season("s1").gaps[gap_id].days, key=lambda beat: beat.day)
    day = next(beat.day for beat in beats if beat.premise == premise)
    earlier = [{"gap": gap_id, "premise": beat.premise} for beat in beats if beat.day < day]
    return day, {"premises": earlier}


def test_only_the_day_of_an_authored_premise_shows_the_writer_the_rules(pilot) -> None:
    """Phase 1: given every day, the rules had the writer invent a contract with
    «conditions» daily, and that vocabulary leaked into the dialogue and the task."""

    romy = _gap_day("g1", *_planned("g1", "romy_enquete"))
    assert romy["today"]["required_premise"]["id"] == "romy_enquete"
    assert romy["today"]["learner_agency_rules"] == agency.AGENCY_RULES
    # A required premise without an authored contract, and a day without one at all
    # (g2's dinner is owed from day 2): no rules, so the writer leaves learner_agency null.
    order = _gap_day("g1", *_planned("g1", "la_meme_chose"))
    assert order["today"]["required_premise"]["id"] == "la_meme_chose"
    assert "learner_agency_rules" not in order["today"]
    plain = _gap_day("g2", 1)
    assert plain["today"]["required_premise"] is None
    assert "learner_agency_rules" not in plain["today"]
    # The same premise id in another gap has no contract.
    assert agency.brief_extras("s1", "g2", 1, state={}, seed="s", premise="romy_enquete") == {}


def test_a_plain_day_keeps_the_agreements_and_the_callback(pilot) -> None:
    text = "Vous pouvez l'écrire, mais sans mon nom."
    state = _settled(_details(text, _act(text, "accept", "sans mon nom", ["no_name"])))
    plain = agency.brief_extras("s1", "g1", 2, state=state, seed="learner-1")
    assert set(plain) == {"agreements", "callback"}
    assert plain["agreements"] == ["The learner let Romy use what they told her, but not their name."]
    assert plain["callback"]["id"] == "romy_notes_without_name"
    romy = agency.brief_extras("s1", "g1", 2, state=state, seed="learner-1", premise="romy_enquete")
    assert romy == {"learner_agency_rules": agency.AGENCY_RULES, **plain}
    brief = _gap_day("g2", 1, state=state)
    assert brief["today"]["agreements"] == plain["agreements"] and "learner_agency_rules" not in brief["today"]


def test_a_plain_day_without_a_written_contract_runs_on_the_open_contract(pilot) -> None:
    plain_day = {
        "id": "s1",
        "kind": "gap",
        "position": {"segment": "g2", "day_in_segment": 1, "season_day": 12},
        "checklist": {"premise_id": None, "learner_agency": None, "turn_want": "Tell Marin if he may use the plan"},
    }
    contract = agency.contract_for(plain_day, speaker="marin_leveque")
    assert contract is not None and contract.open_conditions and contract.speaker == "marin_leveque"
    assert [effect.id for effect in contract.effects] == ["went_along", "refused"]
    assert agency.agency_for_turn(contract)["conditions_open"] is True


#: The walk's g1.2 (12 Oct 2026): the writer staged another premise, wrote no
#: learner_agency, and the turn asked exactly for the permission.
CAMERA_DAY = {
    "id": "s1",
    "kind": "gap",
    "position": {"segment": "g1", "day_in_segment": 2, "season_day": 5},
    "checklist": {"premise_id": "la_meme_chose", "learner_agency": None,
                  "turn_want": "Decide if you allow Romy to record you now or not"},
}


def test_a_day_the_writer_gave_no_contract_still_records_the_decision(pilot) -> None:
    assert agency.contract_for(CAMERA_DAY) is None  # without the scene's character
    contract = agency.contract_for(CAMERA_DAY, speaker="romy_tremblay")
    assert contract is not None and contract.open_conditions
    turn = agency.agency_for_turn(contract)
    assert turn["conditions_open"] is True
    assert agency.contract_for(CAMERA_DAY, speaker="nobody_in_the_cast") is None

    text = "Non, pas de camera. Tu peux utiliser mon histoire, mais sans mon nom."
    acts = [
        agency.VoiceAct(action="decline", subject="request", evidence_quotes=["Non, pas de camera."]),
        agency.VoiceAct(action="accept", subject="request", conditions=["Sans mon nom"],
                        evidence_quotes=["Tu peux utiliser mon histoire, mais sans mon nom"]),
    ]
    details = {"learner_text": text, **agency.acts_for_details(contract, acts, text=text)}
    assert details["agency_decisions"] == ["commit", "commit"]
    state = _settle_on(CAMERA_DAY, details, event_id="g1-day2")

    world = agency.world_of(state)
    assert [event.action for event in world.events] == ["decline", "accept"]
    assert world.events[1].conditions == ["sans_mon_nom"]
    extras = agency.brief_extras("s1", "g1", 3, state=state, seed="s")
    # Agency walk 4: the note says who asked and what the learner said, never the
    # writer's private turn_want or a raw slug.
    assert extras["agreements"][-1] == (
        "The learner went along with what Romy asked of them."
        " In their words: «Tu peux utiliser mon histoire, mais sans mon nom»"
    )
    assert extras["callback"]["learner_words"] == ["Non, pas de camera."]


def test_the_ending_is_told_only_what_the_learner_refused_in_their_words() -> None:
    voice = story_lanes.VoiceReply.model_validate(
        {"reply_fr": "D'accord.", "understood_intent": "x", "needs_clarification": False, "acts": [
            {"action": "decline", "evidence_quotes": ["pas de camera"]},
            {"action": "accept", "conditions": ["no_name", "off_record"], "evidence_quotes": ["c'est moi, Paul"]},
            {"action": "withhold", "evidence_quotes": ["peut-être"], "clarity": "ambiguous"},
        ]}
    )
    tutor = story_lanes.TutorVerdict.model_validate({"outcome": "met", "evidence_quotes": ["pas de camera"]})
    released = story_lanes.released_view(tutor, voice)
    assert released["learner_refused"] == ["pas de camera"]
    assert "no_name" not in str(released), "an act's limits never reach the ending lane"
    voice.acts = []
    assert "learner_refused" not in story_lanes.released_view(tutor, voice)


def test_a_plain_answer_sets_no_limit(pilot) -> None:
    """Second agency walk: «Oui, c'est moi, Paul» heard as tell + the contract's two limits."""

    contract = agency.contract_for(ROMY_DAY)
    text = "Oui, c'est moi, Paul, le petit-fils d'Odile."
    act = agency.VoiceAct(action="tell", subject="learner_account", conditions=["no_name", "off_record"],
                          evidence_quotes=["Oui, c'est moi, Paul"])
    details = agency.acts_for_details(contract, [act], text=text)
    assert details["season_acts"][0]["conditions"] == []


def test_a_callback_to_what_the_learner_decided_is_this_lifes_past():
    """Third agency walk, 12 Oct 2026: the writer staged the offered callback in its own
    French and the memory guard refused it as invented, so the day was lost."""

    from app.services import living_story

    context = {
        "cast": [{"id": "romy", "name": "Romy Delacroix"}],
        "season_script": {
            "brief": {
                "today": {
                    "agreements": ["The learner let Romy use what they told her, but not their name."],
                    "callback": {
                        "id": "romy_notes_without_name",
                        "character": "romy",
                        "instruction": "Romy shows her notes, the learner's name left out.",
                        "learner_words": ["Oui, tu peux utiliser mon histoire, mais sans mon nom."],
                        "source_event": "g1.1:accept:learner_account",
                    },
                }
            }
        },
    }
    staged = "Romy montre ses notes où tes mots sont anonymes, comme tu as demandé."
    ledger = living_story._callback_ledger(context)
    assert not living_story._callback_grounded(staged, None, ledger)
    ref = living_story._names_agency_callback(staged, context)
    # The guard fills the ref in even when the text is grounded elsewhere (walk 4).
    assert living_story._names_agency_callback("Romy sourit.", context) == "romy_notes_without_name"
    assert ref == "romy_notes_without_name"
    assert living_story._callback_grounded(staged, ref, ledger)
    assert living_story._callback_grounded(staged, "g1.1:accept:learner_account", ledger)
    # Someone else's invented past is still refused.
    invented = "Gus se souvient de la fête que tu as organisée hier soir."
    assert living_story._names_agency_callback(invented, context) is None
    assert not living_story._callback_grounded(invented, None, ledger)
    # No offered callback: nothing changes.
    assert living_story._names_agency_callback(staged, {"cast": context["cast"]}) is None


def test_a_day_records_whether_its_page_claimed_the_offered_callback() -> None:
    """Codex review on PR #82: a page that left the offered callback out must not
    mark it played."""

    from types import SimpleNamespace

    from app.services import living_story

    offered = {"id": "romy_notes_without_name", "source_event": "ev_1", "character": "romy"}
    context = {"season_script": {"id": "s1", "brief": {"today": {"callback": offered}}}}

    def day(callback_fr: str, ref: str | None) -> dict:
        draft = SimpleNamespace(season_checklist=None, callback_fr=callback_fr, callback_ref=ref)
        return living_story._season_gap_day(context, draft)

    assert day("Romy montre ses notes.", "romy_notes_without_name")["callback_staged"] is True
    assert day("Romy montre ses notes.", "ev_1")["callback_staged"] is True
    assert day("", None)["callback_staged"] is False
    assert day("Gus se souvient.", "cons_9")["callback_staged"] is False
