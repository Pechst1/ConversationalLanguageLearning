"""«Ton cap» (steering read 2026-10-24): where the learner stands on going home or staying.

The leaving learner told Camille «Je vends et je rentre» on T1 B, and for ten days the
generated pages kept asking «pourquoi tu restes ?». ``user.heading`` (leave, undecided
or stay) is set by the learner's own words: Camille's «Vous allez vendre, non ?» (T1 B),
Lila's balcony question (T2 B), and any generated day where they say where they now
stand. Every generated day reads it. It decides what the world asks of the learner,
never whether the story moves: every tentpole still comes.

Fake models only: nothing is spent.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.services import story_lanes as lanes
from app.services import story_split
from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
from app.services.season.director import (
    HEADING_FLAG,
    STORY_CRITIC,
    critic_payload,
    gap_brief,
    heading_for,
)
from app.services.season.flags import effective_flags
from app.services.season.format import load_season, validate_season
from app.services.season.page import resolve_day
from app.services.season.runtime import projected_turns, routes_the_story
from tests import test_journey_end_to_end as support
from tests.test_season_one import _play, _season_state, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def test_the_heading_is_a_flag_every_generated_day_may_set():
    season = load_season("s1")
    assert validate_season(season) == []
    spec = season.flag(HEADING_FLAG)
    assert spec is not None and spec.values == ["leave", "undecided", "stay"]
    assert spec.default == "undecided"
    assert effective_flags(season, {"id": "s1"}, seed="x")[HEADING_FLAG] == "undecided"
    for gap in season.gaps.values():
        assert HEADING_FLAG in gap.sets_allowed, gap.id
    lines = season.gap_rules["heading"]
    assert set(lines) - {"_about"} == {"leave", "undecided", "stay"}


# ---------------------------------------------------------------------------
# The tentpoles: Camille's question and Lila's balcony
# ---------------------------------------------------------------------------


def _tentpole_b(segment: str, routed: list[dict], state: dict | None = None) -> dict:
    season = load_season("s1")
    state = deepcopy(state or {"id": "s1"})
    page = resolve_day(season, segment, "b", flags=effective_flags(season, state, seed="u"), band="A2", language="en")
    context = {
        season_runtime.SEASON_CONTEXT_KEY: {
            "id": "s1",
            "kind": "tentpole",
            "position": {"segment": segment, "day_in_segment": 2, "season_day": 2},
            "page": page,
            "turns": [],
            "seed": "u",
        }
    }
    live = season_runtime.settle(
        {season_clock.SEASON_KEY: state},
        story_context=context,
        details={"season_turns": routed},
        event_id=f"{segment}.b",
        date_iso=None,
        day_index=2,
    )
    return live[season_clock.SEASON_KEY]


def _heading(state: dict) -> str:
    return effective_flags(load_season("s1"), state, seed="u")[HEADING_FLAG]


@pytest.mark.parametrize("reply, heading", [("a", "leave"), ("b", "undecided"), ("c", "undecided"), ("d", "undecided")])
def test_camille_hears_whether_the_learner_means_to_sell(reply, heading):
    """«Vous allez vendre, non ?» — only «Oui. Je vends et je rentre.» sets a heading;
    «pas encore», «plus simple pour qui ?» and a halting «pas vendre ce soir» leave it
    undecided."""

    state = _tentpole_b("t1", [{"turn_id": "b.turn1", "reply_id": reply}])
    assert _heading(state) == heading


@pytest.mark.parametrize("reply, signal", [("lean", "romance"), ("accomplice", "friendship")])
def test_the_learner_who_tells_lila_they_are_staying_is_staying(reply, signal):
    """«Tu restes combien de temps, en fait ?» — longer, because of her or because they
    want to know how the story ends: the heading turns to stay, even after «je vends»."""

    leaving = _tentpole_b("t1", [{"turn_id": "b.turn1", "reply_id": "a"}])
    state = _tentpole_b("t2", [{"turn_id": "b.turn2", "reply_id": reply, "gate": 1, "signal": signal}], leaving)
    assert _heading(state) == "stay"


@pytest.mark.parametrize("reply", ["joke", "clumsy"])
def test_a_joke_or_a_halting_answer_on_the_balcony_keeps_the_heading(reply):
    leaving = _tentpole_b("t1", [{"turn_id": "b.turn1", "reply_id": "a"}])
    state = _tentpole_b("t2", [{"turn_id": "b.turn2", "reply_id": reply, "gate": 1, "signal": "friendship"}], leaving)
    assert _heading(state) == "leave"


def test_a_tentpole_day_the_learner_did_not_answer_decides_nothing():
    assert _heading(_tentpole_b("t1", [])) == "undecided"


def test_camilles_question_now_routes_the_story_but_asks_no_more_of_the_day():
    """b.turn1 sets the heading, so it is never dropped from a short reply. It came
    before T1 B's letter, which the conversation already had to reach."""

    season = load_season("s1")
    page = resolve_day(season, "t1", "b", flags=effective_flags(season, {}, seed="u"), band="A2", language="en")
    assert [(turn["id"], routes_the_story(turn)) for turn in projected_turns(page)] == [
        ("b.turn1", True),
        ("b.letter", True),
    ]


# ---------------------------------------------------------------------------
# The generated days
# ---------------------------------------------------------------------------


def _g1_brief(state_flags: dict | None = None, *, day: int = 2) -> dict:
    season = load_season("s1")
    played = [{"segment": "t1", "day_in_segment": n, "event_id": str(n)} for n in (1, 2)]
    played += [{"segment": "g1", "day_in_segment": n, "event_id": f"g{n}"} for n in range(1, day)]
    state = {"id": "s1", "played": played, **({"flags": state_flags} if state_flags else {})}
    pos = season_clock.position(season, state, today=date(2026, 11, 12 + day))
    assert pos.key == f"g1.{day}"
    return gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")


@pytest.mark.parametrize("heading", ["leave", "undecided", "stay"])
def test_every_generated_day_tells_the_page_where_the_learner_stands(heading):
    brief = _g1_brief({HEADING_FLAG: heading})
    rules = load_season("s1").gap_rules["heading"]
    assert brief["today"]["heading"] == {"value": heading, "means": rules[heading]}
    assert HEADING_FLAG in brief["today"]["may_set"]


def test_a_learner_who_never_said_is_undecided():
    assert _g1_brief()["today"]["heading"]["value"] == "undecided"


def test_the_lines_ask_the_world_and_never_the_learner():
    rules = load_season("s1").gap_rules["heading"]
    assert "Nobody pleads with them to stay, asks whether they really will go, or talks as if" in rules["leave"]
    assert "Nobody decides for them or pushes them either way" in rules["undecided"]
    assert "never a reproach" in rules["stay"]
    assert "never whether the story moves" in rules["_about"]


def test_a_season_without_the_flag_or_its_lines_has_no_heading():
    season = load_season("s1")
    assert heading_for(season, {HEADING_FLAG: "maybe"}) is None
    bare = season.model_copy(update={"gap_rules": {**season.gap_rules, "heading": {}}})
    assert heading_for(bare, {HEADING_FLAG: "leave"}) is None


def test_the_critic_reads_the_heading():
    brief = _g1_brief({HEADING_FLAG: "leave"})
    assert critic_payload(brief, {})["today"]["heading"]["value"] == "leave"
    assert "When today.heading is set" in STORY_CRITIC
    assert "«pourquoi tu restes ?» to a learner who" in STORY_CRITIC


def _settle_g1(details: dict, state: dict | None = None, *, day: int = 2, segment: str = "g1") -> dict:
    context = {
        "id": "s1",
        "kind": "gap",
        "position": {"segment": segment, "day_in_segment": day},
        "checklist": {"premise_id": "soupe_de_marin" if segment == "g1" else None},
    }
    return season_runtime._settle_gap(load_season("s1"), state or {"id": "s1"}, context, details, event_id="e", day=day + 2)


def test_the_learner_says_where_they_now_stand_on_a_generated_day():
    said = {"outcome": "met", "season_flags": [{"flag": HEADING_FLAG, "value": "stay"}]}
    state = _settle_g1(said, {"id": "s1", "flags": {HEADING_FLAG: "leave"}})
    assert state["flags"][HEADING_FLAG] == "stay"
    assert state["learner_set"] == {HEADING_FLAG: "g1"}
    # The next day's page is told.
    assert _g1_brief(state["flags"], day=3)["today"]["heading"]["value"] == "stay"


def test_a_heading_outside_the_three_is_never_stored():
    said = {"outcome": "met", "season_flags": [{"flag": HEADING_FLAG, "value": "rester"}]}
    state = _settle_g1(said, {"id": "s1", "flags": {HEADING_FLAG: "leave"}})
    assert state["flags"][HEADING_FLAG] == "leave"


def test_gaps_four_and_six_let_the_learner_say_it_too():
    """Gap 4 (after the argument) and gap 6 (the plan) set no flag before «Ton cap»."""

    for segment in ("g4", "g6"):
        said = {"outcome": "met", "season_flags": [{"flag": HEADING_FLAG, "value": "leave"}]}
        state = _settle_g1(said, segment=segment)
        assert state["flags"][HEADING_FLAG] == "leave", segment


# ---------------------------------------------------------------------------
# The lanes
# ---------------------------------------------------------------------------


def _voice_payload(season_turn: dict | None) -> dict:
    story = {"level": "A2", "learner": {"address": "neutral"}, "control_language": "en", "commitments": []}
    if season_turn is not None:
        story["season_turn"] = season_turn
    return {
        "story": story,
        "scene": {"character_id": "lila_bonnet", "opening_line_fr": "Tu restes ?", "objective_native": "", "panels": []},
        "learner_text": "Je pars dimanche.",
        "history": [],
        "targets": [],
        "turn_plan": {},
    }


def test_the_character_is_told_where_the_learner_stands():
    heading = {"value": "leave", "means": "The learner means to sell and go home."}
    assert lanes.voice_payload(_voice_payload({"may_set": [], "heading": heading}))["heading"] == heading
    assert "heading" not in lanes.voice_payload(_voice_payload({"may_set": []}))
    assert "heading" not in lanes.voice_payload(_voice_payload(None))


def test_the_prompts_say_the_heading_is_the_learners():
    assert "8. The learner holds their heading." in story_split.PLANNER
    assert "never whether the story\n   moves" in story_split.PLANNER
    assert "talks as if they had decided otherwise" in story_split.PLANNER
    assert "never argue them out of it or talk\nas if they had decided otherwise" in lanes.VOICE
    assert "user.heading: leave, undecided or stay, only when their\nwords say it" in lanes.STORY


@pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
def test_a_generated_day_hands_the_lanes_the_heading_and_keeps_what_the_learner_says(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    provider = season_on
    answer = "Finalement, je reste un peu."
    reply = provider.generate_chat_completion

    def says_where_they_stand(messages, **kwargs):
        # The story lane reads «je reste» as the learner's heading.
        response = reply(messages, **kwargs)
        data = json.loads(messages[0]["content"])
        season_turn = ((data["data"].get("story") or {}).get("season_turn")) or {}
        if data["output_schema"]["title"] != "StoryTurn" or HEADING_FLAG not in (season_turn.get("may_set") or []):
            return response
        value = json.loads(response.content)
        if "je reste" in str(data["data"].get("learner_text") or ""):
            value["season_flags"] = [*value.get("season_flags", []), {"flag": HEADING_FLAG, "value": "stay"}]
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", says_where_they_stand)
    email = f"s1-heading-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=3, flags={HEADING_FLAG: "leave"})
    db_session.commit()
    _play(d, provider, clock, answer)

    assert provider.director_contexts()[-1]["season_script"]["brief"]["today"]["heading"]["value"] == "leave"
    voices = [payload for schema, payload in provider.calls if schema == "VoiceReply"]
    assert voices and voices[-1]["heading"]["value"] == "leave"
    endings = [payload for schema, payload in provider.calls if schema == "StoryTurn"]
    assert endings and endings[-1]["story"]["season_turn"]["heading"]["value"] == "leave"
    state = _season_state(db_session, user.id)
    assert state["flags"][HEADING_FLAG] == "stay"
    assert state["learner_set"][HEADING_FLAG].startswith("g")

    _play(d, provider, clock, "D'accord.")
    assert provider.director_contexts()[-1]["season_script"]["brief"]["today"]["heading"]["value"] == "stay"
