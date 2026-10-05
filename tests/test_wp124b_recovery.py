"""WP-124b: recovery that cannot stall the season.

WP-124a re-reads the last season page on a lost day; repeated failures re-read it
forever. WP-124b: the first lost day of a run is the reprise; the next consecutive
lost day in the same gap is an authored continuation — the next tentpole when the
gap's required moments have all happened, else the gap's bridge, which stages the
moments still owed — and never a blind cursor jump. Shortened gaps are recorded.

The bridges are an owner-approval item (``app/data/season/s1/bridges.json`` is a
proposal, see docs/implementation/atelier-v2/WP-124B-BRIDGES-PROPOSAL.md). Tests that
need them are skipped when the file is absent; everything else — the policy, the
tentpole jump, the counter, the safe fallback without bridges — runs on the code alone.
"""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import date

import pytest
from sqlalchemy import select

from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.services import living_story as engine
from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
from app.services.season.bridges import Bridge, load_bridges, validate_bridges
from app.services.season.clock import SHORTENED_KEY, position, shortened_gaps
from app.services.season.flags import effective_flags
from app.services.season.format import SEASON_ROOT, load_season
from app.services.season.recovery import (
    MAX_CONSECUTIVE_REPRISES,
    RECOVER_AT_FAILURE,
    RECOVERY_FALLBACK_KIND,
    decide,
    missing_required,
    prerequisites_hold,
)
from app.services.season.reprise import REPRISE_FALLBACK_KIND, REPRISE_SCENARIO_PREFIX
from tests import test_journey_end_to_end as support
from tests.test_learner_walk import production_day  # noqa: F401 - fixture
from tests.test_season_one import (  # noqa: F401 - fixture
    _chooser,
    _season_state,
    _thread,
    season_on,
)
from tests.test_wp124a_season_reprise import _director_fails

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

HAS_BRIDGES = (SEASON_ROOT / "s1" / "bridges.json").is_file()
needs_bridges = pytest.mark.skipif(
    not HAS_BRIDGES, reason="the WP-124b bridges are an owner proposal (app/data/season/s1/bridges.json absent)"
)
#: Nominal season days (bible §8): g1 opens on day 3, g2 on 10, g5 on 35.
G1_DAY1, G2_DAY1, G5_DAY1 = 3, 10, 35


@pytest.fixture(autouse=True)
def _fresh_bridges():
    load_bridges.cache_clear()
    yield
    load_bridges.cache_clear()


def _season():
    return load_season("s1")


def _played(n_days: int) -> dict:
    """A season state with the nominal calendar's first ``n_days`` played."""

    rows = season_clock.nominal_calendar(_season())[:n_days]
    return {"id": "s1", "played": [{**row, "flex": 0, "event_id": f"e{row['season_day']}"} for row in rows], "flags": {}}


def _pos(state: dict):
    return position(_season(), state, today=date(2026, 11, 18))  # a Wednesday: no flex


def _user(db, email: str) -> User:
    return db.scalar(select(User).where(User.email == email))


def _journeys(db, user_id) -> list[DailyJourney]:
    rows = db.scalars(select(DailyJourney).where(DailyJourney.user_id == user_id).order_by(DailyJourney.local_date)).all()
    for row in rows:
        db.refresh(row)
    return list(rows)


def _marker(db, journey_id: str) -> dict:
    row = db.get(DailyJourney, uuid.UUID(journey_id))
    db.refresh(row)
    return dict((row.plan_selection or {}).get("generation_fallback") or {})


def _jumped_driver(assembled_client, db_session, *, day: int, cefr: str = "A2.1", flags: dict | None = None):
    from app.services.season.admin import jump_to_day

    email = f"wp124b-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr=cefr), db=db_session)
    user = _user(db_session, email)
    jump_to_day(db_session, user, day=day, flags=flags)
    db_session.commit()
    return d, user


def _day(d, clock, answer="Je reste encore un peu.") -> dict:
    d.create()
    assert d.journey["status"] == "active", d.journey
    journey = dict(d.journey)
    d.play(answer=answer)
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    return journey


# ---------------------------------------------------------------------------
# The policy
# ---------------------------------------------------------------------------


def test_the_policy_rereads_once_then_moves_on_only_through_prerequisites():
    season = _season()
    # g5 holds no required moment: its prerequisites hold from its first day.
    g5 = _played(G5_DAY1 - 1)
    pos = _pos(g5)
    assert pos.key == "g5.1" and prerequisites_hold(season, g5, "g5")
    first = decide(season, g5, pos, failures_before=0, bridge_gaps=set())
    assert (first.kind, first.reason, first.failure) == ("reprise", "first_lost_day", 1)
    second = decide(season, g5, pos, failures_before=RECOVER_AT_FAILURE - 1, bridge_gaps=set())
    assert second.kind == "tentpole" and second.position.key == "t6.a" and second.gap == "g5"
    # g1 owes three moments: never a blind jump to T2.
    g1 = _played(G1_DAY1 - 1)
    pos = _pos(g1)
    assert missing_required(season, g1, "g1") == ["romy_enquete", "la_meme_chose", "le_billet"]
    safe = decide(season, g1, pos, failures_before=1, bridge_gaps=set())
    assert (safe.kind, safe.reason) == ("reprise", "no_bridge_for_missing_moments")
    bridged = decide(season, g1, pos, failures_before=1, bridge_gaps={"g1"})
    assert bridged.kind == "bridge" and bridged.missing == ("romy_enquete", "la_meme_chose", "le_billet")
    assert bridged.position.key == "g1.1", "the bridge stands in for today's gap day"
    # Only what is still owed is bridged; once nothing is, the tentpole is next.
    g1["premises"] = [{"gap": "g1", "premise": "romy_enquete"}, {"gap": "g1", "premise": "le_billet"}]
    assert decide(season, g1, pos, failures_before=1, bridge_gaps={"g1"}).missing == ("la_meme_chose",)
    g1["premises"].append({"gap": "g1", "premise": "la_meme_chose"})
    jump = decide(season, g1, pos, failures_before=5, bridge_gaps=set())
    assert jump.kind == "tentpole" and jump.position.key == "t2.a"
    assert MAX_CONSECUTIVE_REPRISES == RECOVER_AT_FAILURE - 1 == 1


def test_off_a_gap_and_after_the_finale_a_lost_day_is_a_reprise_and_moves_nothing():
    season = _season()
    on_tentpole = _played(G1_DAY1 + 4)  # g1 played to its end: T2 A is next
    assert _pos(on_tentpole).key == "t2.a"
    assert decide(season, on_tentpole, _pos(on_tentpole), failures_before=9).kind == "reprise"
    finished = _played(season.total_days)
    pos = _pos(finished)
    assert pos.finished
    for before in (0, 1, 7):
        decision = decide(season, finished, pos, failures_before=before, bridge_gaps={"g1", "g2", "g3", "g4"})
        assert (decision.kind, decision.reason, decision.position) == ("reprise", "season_finished", None)


def test_a_shortened_gap_ends_at_once_and_takes_no_weekend_flex():
    season = _season()
    state = _played(G1_DAY1)  # g1.1 played
    state[SHORTENED_KEY] = [{"gap": "g1", "via": "bridge"}]
    friday = date(2026, 11, 20)
    assert friday.weekday() == 4
    for today in (friday, date(2026, 11, 21), None):
        pos = position(season, state, today=today)
        assert pos.key == "t2.a" and pos.flex == 0, (today, pos)
    assert shortened_gaps(state) == {"g1": {"gap": "g1", "via": "bridge"}}
    # A gap the learner has already left is not affected.
    state["played"].append({"segment": "t2", "kind": "tentpole", "day_in_segment": 1, "key": "t2.a", "event_id": "x"})
    assert position(season, state, today=friday).key == "t2.b"


# ---------------------------------------------------------------------------
# Settling a recovered day (synthetic, no proposal needed)
# ---------------------------------------------------------------------------


def _bridge_ctx(moments: list[dict], *, gap="g1", day=1) -> dict:
    return {
        "season": {
            "id": "s1",
            "kind": "tentpole",
            "position": {"segment": gap, "day_in_segment": day, "season_day": G1_DAY1},
            "page": {"movements": []},
            "turns": [],
            "seed": "u",
            "recovery": {"kind": "bridge", "gap": gap, "reason": "missing_moments"},
            "bridge": {"gap": gap, "moments": moments},
        }
    }


G1_MOMENTS = [
    {"premise": "romy_enquete", "turns": ["g1.romy.turn"], "fixed": {}},
    {"premise": "la_meme_chose", "turns": ["g1.order"], "fixed": {}},
    {"premise": "le_billet", "turns": ["g1.billet.turn"], "fixed": {"user.return_ticket": "mercredi 2 décembre"}},
]


def test_a_bridge_stages_only_what_was_answered_and_closes_the_gap_only_then():
    live = {"season_script": _played(G1_DAY1 - 1)}
    routed = [{"turn_id": "g1.romy.turn", "reply_id": "open"}, {"turn_id": "g1.billet.turn", "reply_id": "honest"}]
    after = season_runtime.settle(
        deepcopy(live), story_context=_bridge_ctx(G1_MOMENTS), details={"season_turns": routed}, event_id="b1", date_iso="2026-11-13", day_index=3
    )
    state = after["season_script"]
    staged = {(row["gap"], row["premise"]) for row in state["premises"]}
    assert staged == {("g1", "romy_enquete"), ("g1", "le_billet")}, "the order was never asked: still owed"
    assert state["flags"]["user.return_ticket"] == "mercredi 2 décembre"
    assert "user.usual_order" not in state["flags"], "nothing decides the learner's order for them"
    assert SHORTENED_KEY not in state, "a moment is still owed: the gap stays open"
    assert state["played"][-1]["key"] == "g1.1" and state["played"][-1]["bridge"] is True
    # Replaying the same event settles nothing twice.
    again = season_runtime.settle(
        deepcopy(after), story_context=_bridge_ctx(G1_MOMENTS), details={"season_turns": routed}, event_id="b1", date_iso="2026-11-13", day_index=3
    )
    assert again == after
    # The next bridge stages the last moment: the gap closes, honestly recorded.
    done = season_runtime.settle(
        deepcopy(after),
        story_context=_bridge_ctx([G1_MOMENTS[1]], day=2),
        details={"season_turns": [{"turn_id": "g1.order", "reply_id": "the"}]},
        event_id="b2",
        date_iso="2026-11-14",
        day_index=4,
    )
    closed = done["season_script"][SHORTENED_KEY]
    assert closed == [
        {
            "gap": "g1",
            "played_days": 2,
            "nominal_days": 5,
            "via": "bridge",
            "moments_bridged": ["la_meme_chose"],
            "reason": "missing_moments",
            "date": "2026-11-14",
            "event_id": "b2",
        }
    ]
    assert position(_season(), done["season_script"], today=date(2026, 11, 20)).key == "t2.a"


def test_a_recovered_tentpole_records_the_gap_it_cut_short():
    live = {"season_script": _played(G5_DAY1)}  # g5.1 played
    ctx = {
        "season": {
            "id": "s1",
            "kind": "tentpole",
            "position": {"segment": "t6", "day_in_segment": 1, "season_day": G5_DAY1 + 1},
            "page": {"movements": []},
            "turns": [],
            "seed": "u",
            "recovery": {"kind": "tentpole", "gap": "g5", "reason": "prerequisites_hold"},
        }
    }
    after = season_runtime.settle(deepcopy(live), story_context=ctx, details={"season_turns": []}, event_id="t", date_iso="2026-12-16", day_index=36)
    state = after["season_script"]
    assert state[SHORTENED_KEY][0] == {
        "gap": "g5", "played_days": 1, "nominal_days": 7, "via": "tentpole", "moments_bridged": [],
        "reason": "prerequisites_hold", "date": "2026-12-16", "event_id": "t",
    }
    assert state["played"][-1]["key"] == "t6.a" and state["played"][-1]["recovery"] == "tentpole"
    assert _pos(state).key == "t6.b"


# ---------------------------------------------------------------------------
# The bridge rules (synthetic bridges: no story text needed)
# ---------------------------------------------------------------------------


def _say(text: str) -> dict:
    return {"a2": text, "native": {"en": text, "de": text}}


def _turn(tid: str, *, to="romy_tremblay", replies=None, gate=None, sets=None) -> dict:
    row = {
        "kind": "turn",
        "id": tid,
        "to": to,
        "panel": {"kind": "panel", "id": f"{tid}.p", "lines": [{"who": to, "say": _say("Et toi ?")}]},
        "task": {"en": "Answer.", "de": "Antworte.", "fr": "Réponds."},
        "listens_for": "Anything.",
        "replies": replies or [{"id": "a", "label": "A", "means": "Anything.", "examples": ["Oui."]}],
        "fallback": (replies or [{"id": "a"}])[-1]["id"],
    }
    if gate:
        row["gate"] = gate
    if sets:
        row["sets"] = sets
    return row


def _bridge(gap: str, moments: list[dict], hook="À suivre…") -> Bridge:
    return Bridge.model_validate(
        {
            "gap": gap,
            "title_fr": "Test",
            "story_date_fr": "nov.",
            "location_id": "le_mistral",
            "moments": moments,
            "hook": {"kind": "hook", "id": f"{gap}.hook", "role": "a_suivre", "panel": {"kind": "panel", "id": f"{gap}.hook.p", "lines": [{"who": "caption", "say": _say(hook)}]}},
        }
    )


def test_the_bridge_rules_refuse_a_fabricated_choice_a_foreign_flag_and_a_spoiler():
    season = _season()
    all_three = [
        {"premise": "romy_enquete", "movements": [_turn("r")]},
        {"premise": "la_meme_chose", "movements": [_turn("o", to="margaux_barman", replies=[{"id": "c", "label": "C", "means": "Coffee.", "examples": ["Un café."], "sets": {"user.usual_order": "un café"}}])]},
        {"premise": "le_billet", "movements": [_turn("b", to="clerk")], "fixed": [{"flag": "user.return_ticket", "value": "mercredi 2 décembre", "because": "The return ticket has moved to 2 December (user.return_ticket)."}]},
    ]
    assert validate_bridges(season, [_bridge("g1", all_three)]) == []
    # The page decides the order whatever is said: a fabricated learner choice.
    fabricated = deepcopy(all_three)
    fabricated[1]["movements"] = [_turn("o", to="margaux_barman", sets={"user.usual_order": "un café"})]
    assert any("fabricated choice" in p for p in validate_bridges(season, [_bridge("g1", fabricated)]))
    # A reply setting a flag its moment does not own.
    foreign = deepcopy(all_three)
    foreign[0]["movements"] = [_turn("r", replies=[{"id": "a", "label": "A", "means": "x", "examples": ["Oui."], "sets": {"user.usual_order": "un thé"}}])]
    assert any("not the moment's own flags" in p for p in validate_bridges(season, [_bridge("g1", foreign)]))
    # A fixed fact must quote the gap's own establish line.
    loose = deepcopy(all_three)
    loose[2]["fixed"][0]["because"] = "because"
    assert any("establish line" in p for p in validate_bridges(season, [_bridge("g1", loose)]))
    # Every required moment, and nothing else.
    assert any("does not stage required" in p for p in validate_bridges(season, [_bridge("g1", all_three[:2])]))
    stray = all_three + [{"premise": "le_diner_rate", "movements": [_turn("d")]}]
    assert any("not a required moment" in p for p in validate_bridges(season, [_bridge("g1", stray)]))
    # The gap's forbidden reveals, at any level.
    spoiler = deepcopy(all_three)
    spoiler[0]["movements"][0]["panel"]["lines"][0]["say"] = {"a2": "Lila part à Berlin.", "native": {}}
    assert any("forbidden reveal berlin" in p for p in validate_bridges(season, [_bridge("g1", spoiler)]))
    # A gate moment needs the gate, with both paths and a neutral fallback.
    no_gate = [{"premise": "le_diner_rate", "movements": [_turn("d", to="lila_bonnet")]}]
    assert any("has no turn carrying the gate" in p for p in validate_bridges(season, [_bridge("g2", no_gate)]))
    leaning = [{"premise": "le_diner_rate", "movements": [_turn("d", to="lila_bonnet", gate=2, replies=[
        {"id": "t", "label": "T", "means": "x", "examples": ["a"], "path": "romance"},
        {"id": "f", "label": "F", "means": "x", "examples": ["b"], "path": "friendship"},
    ])]}]
    problems = validate_bridges(season, [_bridge("g2", leaning)])
    assert any("needs a romance, a friendship and a neutral reply" in p for p in problems)
    assert any("fallback leans" in p for p in problems)
    assert any("«À suivre…»" in p for p in validate_bridges(season, [_bridge("g1", all_three, hook="Fin.")]))


def test_without_a_bridges_file_there_is_no_bridge(tmp_path):
    folder = tmp_path / "s1"
    folder.mkdir()
    for name in ("season.json", "gaps.json", *[f"t{n}.json" for n in range(1, 9)]):
        (folder / name).write_bytes((SEASON_ROOT / "s1" / name).read_bytes())
    assert load_bridges("s1", root=tmp_path) == {}
    (folder / "bridges.json").write_text(json.dumps({"bridges": [{"gap": "g1"}]}), encoding="utf-8")
    load_bridges.cache_clear()
    assert load_bridges("s1", root=tmp_path) == {}, "a broken file costs the bridge, never the day"


# ---------------------------------------------------------------------------
# End to end (the scripted provider; the director fails on demand)
# ---------------------------------------------------------------------------


def test_two_lost_days_in_a_gap_whose_moments_happened_play_the_next_tentpole(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """g5 holds no required moment. Lost day 1 re-reads T5 B; lost day 2 is T6 A,
    authored, bound and settled; g5 is recorded as cut short; T6 B follows."""

    d, user = _jumped_driver(assembled_client, db_session, day=G5_DAY1)
    flags_before = dict(_season_state(db_session, user.id).get("flags") or {})
    _director_fails(season_on, monkeypatch)
    first = _day(d, clock)
    assert first["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t5.b"
    marker = _marker(db_session, first["id"])
    assert (marker["kind"], marker["gap"], marker["failure"]) == (REPRISE_FALLBACK_KIND, "g5", 1)
    second = _day(d, clock)
    marker = _marker(db_session, second["id"])
    assert marker["kind"] == RECOVERY_FALLBACK_KIND and marker["recovery"] == "tentpole"
    assert marker["page_key"] == "t6.a" and marker["season_day"] is True and marker["failure"] == 2
    state = _season_state(db_session, user.id)
    assert state["played"][-1]["key"] == "t6.a" and state["played"][-1]["recovery"] == "tentpole"
    assert state[SHORTENED_KEY][0]["gap"] == "g5" and state[SHORTENED_KEY][0]["via"] == "tentpole"
    assert state[SHORTENED_KEY][0]["played_days"] == 0, "no g5 day was played: the archive has none to show"
    for key, value in flags_before.items():
        assert state["flags"].get(key) == value, f"{key} was rewritten by the recovery"
    third = _day(d, clock)
    assert not third["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX)
    assert _season_state(db_session, user.id)["played"][-1]["key"] == "t6.b"
    assert not _marker(db_session, third["id"]), "a tentpole day needs no recovery"


def test_without_bridges_a_gap_that_owes_moments_keeps_the_reprise(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """g1 owes Romy, the order and the ticket; with no bridge, two (and three) lost
    days re-read T1 B and the season does not move — never a jump to T2."""

    from app.services.season import bridges as bridges_module

    monkeypatch.setattr(bridges_module, "load_bridges", lambda season_id, **_: {})
    d, user = _jumped_driver(assembled_client, db_session, day=G1_DAY1)
    before = _season_state(db_session, user.id)
    _director_fails(season_on, monkeypatch)
    for failure in (1, 2, 3):
        journey = _day(d, clock)
        assert journey["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
        marker = _marker(db_session, journey["id"])
        assert marker["failure"] == failure and marker["gap"] == "g1"
        assert marker["recovery"] == ("first_lost_day" if failure == 1 else "no_bridge_for_missing_moments")
    assert _season_state(db_session, user.id) == before


def test_a_written_day_resets_the_run(assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch):  # noqa: F811
    """Lost, written, lost: the second lost day starts a new run (a reprise again)."""

    d, user = _jumped_driver(assembled_client, db_session, day=G5_DAY1)
    with monkeypatch.context() as failing:
        _director_fails(season_on, failing)
        first = _day(d, clock)
    written = _day(d, clock)
    assert not written["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX)
    with monkeypatch.context() as failing:
        _director_fails(season_on, failing)
        third = _day(d, clock)
    assert _marker(db_session, first["id"])["failure"] == 1
    assert not _marker(db_session, written["id"])
    assert third["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX)
    assert _marker(db_session, third["id"])["failure"] == 1
    assert [row["key"] for row in _season_state(db_session, user.id)["played"]][-1] == "g5.1"


def test_mixed_outages_never_reread_twice_in_a_row_and_the_season_only_moves_forward(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """A schedule of outages over g5 and beyond: no two reprises in a row, the
    played log only grows, and the season keeps advancing."""

    d, user = _jumped_driver(assembled_client, db_session, day=G5_DAY1)
    schedule = [True, False, True, True, False, True, True, True, False, True]
    kinds: list[str] = []
    played: list[int] = []
    for down in schedule:
        with monkeypatch.context() as failing:
            if down:
                _director_fails(season_on, failing)
            journey = _day(d, clock)
        marker = _marker(db_session, journey["id"])
        kinds.append(marker.get("kind") or "written")
        played.append(len(_season_state(db_session, user.id)["played"]))
    assert all(not (a == b == REPRISE_FALLBACK_KIND) for a, b in zip(kinds, kinds[1:], strict=False)), kinds
    assert played == sorted(played) and played[-1] - played[0] >= schedule.count(False) + 2, played
    assert kinds.count(REPRISE_FALLBACK_KIND) <= schedule.count(True)


def test_a_recovered_day_is_chosen_once_across_reloads_and_settles_once(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    d, user = _jumped_driver(assembled_client, db_session, day=G5_DAY1)
    _director_fails(season_on, monkeypatch)
    _day(d, clock)  # the reprise
    first = d.create()
    again = d.create()
    assert again["id"] == first["id"] and again["scenario"] == first["scenario"]
    assert (d.today().get("journey") or {}).get("id") == first["id"]
    assert _marker(db_session, first["id"])["recovery"] == "tentpole"
    revision = engine.story_revision(db_session, user)
    d.play(answer="Je reste encore un peu.")
    assert d.finish("complete").status_code == 200
    replay = d.finish("complete")
    assert replay.status_code in (200, 409), replay.text
    state = _season_state(db_session, user.id)
    assert [row["key"] for row in state["played"]].count("t6.a") == 1
    assert len(state[SHORTENED_KEY]) == 1
    # Any prefetched scene was keyed on the story revision the recovery has now moved.
    assert engine.story_revision(db_session, user) != revision


# ---------------------------------------------------------------------------
# With the bridge proposal applied
# ---------------------------------------------------------------------------


@needs_bridges
def test_the_shipped_bridges_hold_and_cover_every_gap_that_holds_a_moment():
    from scripts.season_check import check_bridges

    bridges = load_bridges("s1")
    season = _season()
    assert set(bridges) == {gap.id for gap in season.gaps.values() if gap.required} == {"g1", "g2", "g3", "g4"}
    problems, note = check_bridges("s1")
    assert problems == [] and "deviation recorded" in note


@needs_bridges
def test_the_first_gap_after_t1_bridges_its_moments_with_the_learners_own_choice_then_t2(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    email = f"wp124b-g1-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A1.1"), db=db_session)
    user = _user(db_session, email)
    for _ in range(2):  # T1 A and B, as written
        _day(d, clock, answer="Odile, c'est ma grand-mère.")
    _director_fails(season_on, monkeypatch)
    reprise = _day(d, clock)
    assert reprise["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
    chooser = _chooser(["the"], free="Oui, Odile est ma grand-mère.")
    d.create()
    bridge_day = dict(d.journey)
    assert bridge_day["scenario"]["title_fr"] == "La première semaine"
    d.play(answer=chooser)
    assert d.finish("complete").status_code == 200
    clock.advance(days=1)
    assert ("creme,noisette,the,chocolat", "the") in chooser.seen, "the order is the learner's card"
    marker = _marker(db_session, bridge_day["id"])
    assert marker["recovery"] == "bridge" and marker["moments"] == ["romy_enquete", "la_meme_chose", "le_billet"]
    state = _season_state(db_session, user.id)
    assert {row["premise"] for row in state["premises"] if row["gap"] == "g1"} == {"romy_enquete", "la_meme_chose", "le_billet"}
    assert state["flags"]["user.usual_order"] == "un thé"
    assert state["flags"]["user.return_ticket"] == "mercredi 2 décembre"
    assert state[SHORTENED_KEY] == [state[SHORTENED_KEY][0]] and state[SHORTENED_KEY][0]["via"] == "bridge"
    assert state[SHORTENED_KEY][0]["played_days"] == 1 and state[SHORTENED_KEY][0]["nominal_days"] == 5
    before = len(season_on.director_contexts())
    t2 = _day(d, clock)
    assert len(season_on.director_contexts()) == before, "T2 A is authored: no model"
    assert _season_state(db_session, user.id)["played"][-1]["key"] == "t2.a"
    assert not t2["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX)


@needs_bridges
@pytest.mark.parametrize(
    ("answer", "reply", "signal"),
    [
        ("C'est le meilleur dîner raté de ma vie.", "tendresse", "romance"),
        ("On dit à Marin que c'était exprès.", "complice", "friendship"),
        ("Oups.", "neutre", "none"),
    ],
)
def test_a_gate_bridge_records_what_the_learner_expressed(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch, answer, reply, signal  # noqa: F811
):
    """Gate 2 is read from what the learner says on the bridge (the classifier's
    reading, as on any day), never assumed: a neutral line records «none»."""

    season_on.routes[answer] = reply
    season_on.signal = signal
    d, user = _jumped_driver(assembled_client, db_session, day=G2_DAY1)
    _director_fails(season_on, monkeypatch)
    _day(d, clock)  # the reprise of T2 B
    bridge = _day(d, clock, answer=answer)
    assert _marker(db_session, bridge["id"])["moments"] == ["le_diner_rate"]
    state = _season_state(db_session, user.id)
    gate2 = [row for row in state.get("signals") or [] if row.get("gate") == 2]
    assert [row["signal"] for row in gate2] == [signal]
    assert ("g2", "le_diner_rate") in {(row["gap"], row["premise"]) for row in state["premises"]}
    assert _pos(state).key == "t3.a"


def _all_down_life(assembled_client, db_session, provider, clock, monkeypatch, *, cefr: str, picks: list[str], argument: str):
    email = f"wp124b-down-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr=cefr), db=db_session)
    user = _user(db_session, email)
    provider.routes[argument] = "lands"
    chooser = _chooser(picks, argument=argument)
    _director_fails(provider, monkeypatch)
    days: list[str] = []
    for _ in range(80):
        d.create()
        assert d.journey["status"] == "active", d.journey
        key = d.journey["scenario"]["scenario_key"]
        marker = _marker(db_session, d.journey["id"])
        d.play(answer=chooser)
        assert d.finish("complete").status_code == 200
        clock.advance(days=1)
        state = _season_state(db_session, user.id)
        days.append(marker.get("kind") or (state["played"][-1]["key"] if state.get("played") else key))
        if position(_season(), state, today=None).finished:
            break
    state = _season_state(db_session, user.id)
    return days, state, effective_flags(_season(), state, seed=str(user.id)), chooser


@needs_bridges
@pytest.mark.parametrize("cefr", ["A1.1", "A2.1", "B1.1", "C1.1"])
def test_an_all_down_season_reaches_its_ending_with_prerequisites_and_choices_intact(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch, cefr  # noqa: F811
):
    """Every generated day lost, from T1 to T8: each gap is one re-read and one
    bridge (or straight to its tentpole), and the keeper's choices reach «Garder»."""

    days, state, flags, chooser = _all_down_life(
        assembled_client, db_session, season_on, clock, monkeypatch, cefr=cefr,
        picks=["margaux", "double", "the", "margaux", "marchand_only", "keep_lease", "keep_kept", "keep"],
        argument="Odile voulait ça : \"oui, si Margaux reste\".",
    )
    reprises = [i for i, kind in enumerate(days) if kind == REPRISE_FALLBACK_KIND]
    assert all(b - a > 1 for a, b in zip(reprises, reprises[1:], strict=False)), days
    assert len(reprises) == 7, "one re-read per gap"
    assert days.count(RECOVERY_FALLBACK_KIND) == 7, "one recovery per gap: 4 bridges, 3 tentpole jumps"
    tentpoles = [row["key"] for row in state["played"] if row["kind"] == "tentpole"]
    assert tentpoles == [f"t{n}.{x}" for n in range(1, 9) for x in ("a", "b")]
    assert len(days) == 16 + 7 + 4, f"{len(days)} days to the finale"
    for gap in _season().gaps.values():
        assert missing_required(_season(), state, gap.id) == [], f"{gap.id} skipped a required moment"
    assert {row["gap"] for row in state[SHORTENED_KEY]} == {f"g{n}" for n in range(1, 8)}
    assert {row["gap"]: row["via"] for row in state[SHORTENED_KEY]} == {
        "g1": "bridge", "g2": "bridge", "g3": "bridge", "g4": "bridge", "g5": "tentpole", "g6": "tentpole", "g7": "tentpole",
    }
    assert {row.get("gate") for row in state.get("signals") or []} >= {1, 2, 3, 4, 5}
    assert flags["s1.letter_trusted_to"] == "margaux" and flags["user.usual_order"] == "un thé"
    assert flags["s1.margaux_persuaded"] is True and flags["s1.ending"] == "garder"
    print(f"\nWP-124b all-down {cefr}: {len(days)} days to the finale — {days}")


# ---------------------------------------------------------------------------
# The walk checks fire on a stalled season, and only then
# ---------------------------------------------------------------------------


def _life(days: list[tuple[str, dict | None]]) -> dict:
    return {
        "persona": "x",
        "quality": "average",
        "days": [
            {"day": n, "journey": {"scenario": {"scenario_key": key}}, **({"season": cursor} if cursor else {})}
            for n, (key, cursor) in enumerate(days, start=1)
        ],
    }


def _cursor(played: int, last: str, shortened=()) -> dict:
    return {"id": "s1", "played": played, "last": last, "shortened": list(shortened)}


def test_the_walk_checks_fire_on_a_stalled_season():
    from tests.walk_checks_wp124b import check_life_wp124b, check_reprise_runs, check_season_cursor

    stalled = _life([("story_a", _cursor(2, "t1.b")), ("season_reprise:t1.b", _cursor(2, "t1.b")), ("season_reprise:t1.b", _cursor(2, "t1.b"))])
    assert len(check_reprise_runs(stalled)) == 1 and "2 reprises in a row" in check_reprise_runs(stalled)[0]
    backwards = _life([("story_a", _cursor(5, "g1.3", ["g1"])), ("story_b", _cursor(4, "g1.2"))])
    problems = check_season_cursor(backwards)
    assert any("shrank" in p for p in problems) and any("moved back" in p for p in problems)
    assert any("no longer recorded" in p for p in problems)
    assert check_life_wp124b(stalled) and check_life_wp124b(backwards)


def test_the_walk_checks_are_quiet_on_a_season_that_recovers():
    from tests.walk_checks_wp124b import check_life_wp124b

    healthy = _life(
        [
            ("story_t1a", _cursor(1, "t1.a")),
            ("story_t1b", _cursor(2, "t1.b")),
            ("season_reprise:t1.b", _cursor(2, "t1.b")),
            ("story_bridge", _cursor(3, "g1.1", ["g1"])),
            ("story_t2a", _cursor(4, "t2.a", ["g1"])),
            ("season_reprise:t2.b", _cursor(6, "g2.6", ["g1"])),  # a flexed gap day keeps its place
            ("story_t3a", _cursor(7, "t3.a", ["g1", "g2"])),
            ("season_reprise:t8.b", None),
            ("season_reprise:t8.b", None),  # after the finale: the epilogue's day
        ]
    )
    assert check_life_wp124b(healthy) == []


def test_a_forced_outage_schedule_is_deterministic():
    from tests.experience_walk import outage_days

    assert outage_days("a1-de-fresh", "average", 30, 0) == set()
    assert outage_days("a1-de-fresh", "average", 30, 1) == set(range(1, 31))
    some = outage_days("a1-de-fresh", "average", 30, 0.21)
    assert some == outage_days("a1-de-fresh", "average", 30, 0.21) and 0 < len(some) < 30
