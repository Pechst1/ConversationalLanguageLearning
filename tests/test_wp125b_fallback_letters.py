"""WP-125B — credible fallback letters.

Provider-off (``_safe_llm`` returns ``None``: what every learner reads whenever the
model fails, and what the life walk plays), the Courrier used to reprint the same
canned letters — «Plus de pain blanc» six times in a month to a B1 learner, the
same A1 bread question to a C1 learner. These tests hold the three rules that now
decide whether a fallback letter is sent at all (level, recency, story), the
follow-up that must name the earlier exchange, the day with no letter rather than
a repeat, the letter's own time estimate, and the neutral feedback when nothing
could assess the reply. No provider is called.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

import app.services.missions as missions_module
from app.config import settings
from app.db.models.mission import RealWorldMission
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import story_correspondence as courrier
from app.services.living_story import STATE_KEY
from app.services.missions import (
    CANNED_REUSE_DAYS,
    LETTER_FIT_KEY,
    REAL_WORLD_MISSION_DOMAINS,
    MissionCorrectionService,
    MissionGenerator,
    MissionScheduler,
    NoCredibleLetter,
    _unassessed_acknowledgement,
    letter_band_index,
    letter_reach,
    serialize_mission,
)

CANNED = {item["domain"]: item for item in REAL_WORLD_MISSION_DOMAINS}


@pytest.fixture(autouse=True)
def provider_off(monkeypatch):
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")


@pytest.fixture
def beginner_catalogue(monkeypatch):
    """Only the A1/A2 canned letters and the A2 story frame — the catalogue as it
    shipped before any B1+ letter text (an owner-approval item) exists. The tests
    that prove «none rather than below band» hold on it whatever is added later."""

    monkeypatch.setattr(
        missions_module,
        "REAL_WORLD_MISSION_DOMAINS",
        tuple(item for item in REAL_WORLD_MISSION_DOMAINS if letter_band_index(item["level"]) <= 1),
    )
    monkeypatch.setattr(
        missions_module,
        "STORY_FRAMES",
        {key: value for key, value in missions_module.STORY_FRAMES.items() if letter_band_index(key) <= 1},
    )


def _user(db_session, level: str) -> User:
    user = User(
        id=uuid4(),
        email=f"wp125b-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
        proficiency_level=level,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _letter(db_session, user: User, **kwargs) -> RealWorldMission:
    return asyncio.run(
        MissionScheduler(db_session).create(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            withhold_if_not_credible=True,
            **kwargs,
        )
    )


def _complete(db_session, mission: RealWorldMission, *, days_ago: float = 0) -> None:
    mission.status = "completed"
    mission.completed_at = datetime.now(UTC) - timedelta(days=days_ago)
    db_session.add(mission)
    db_session.commit()


def _fit(mission: RealWorldMission) -> dict:
    return (mission.prompt_payload or {})[LETTER_FIT_KEY]


def _season_thread(db_session, user: User) -> SerialThread:
    thread = SerialThread(
        id=uuid4(),
        user_id=user.id,
        status="active",
        world_bible={"cast": [{"id": "romy_tremblay", "name": "Romy"}, {"id": "lila_bonnet", "name": "Lila"}]},
        state={STATE_KEY: {"events": [], "commitments": [], "moods": {}, "season_script": {"id": "s1"}}},
        news_seed={},
        current_episode_index=0,
    )
    db_session.add(thread)
    db_session.commit()
    return thread


# ---------------------------------------------------------------------------
# Level
# ---------------------------------------------------------------------------


def test_every_canned_letter_has_a_level_and_the_reach_rule_is_two_bands_for_open_letters():
    assert all(item.get("level") in {"A1", "A2", "B1", "B2", "C1"} for item in REAL_WORLD_MISSION_DOMAINS)
    assert letter_reach("A1") == "A2"
    assert letter_reach("A2") == "B1"
    assert letter_reach("A2", open_ended=True) == "B2"
    assert letter_reach("B1", open_ended=True) == "C1"
    assert letter_band_index("C2") == letter_band_index("C1")


@pytest.mark.parametrize("level", ["A1", "A2", "B1"])
def test_a_fallback_letter_is_never_beyond_its_reach(db_session, level):
    user = _user(db_session, level)
    for _ in range(4):
        try:
            mission = _letter(db_session, user)
        except NoCredibleLetter:
            break
        fit = _fit(mission)
        assert fit["source"] == "canned"
        assert letter_band_index(level) <= letter_band_index(fit["reach"]), fit
        _complete(db_session, mission)


@pytest.mark.parametrize("level", ["B2", "C1"])
def test_a_b2_or_c1_learner_gets_no_canned_beginner_letter(beginner_catalogue, db_session, level):
    """The bread question to a C1 learner: no canned letter reaches B2 or C1 yet."""

    user = _user(db_session, level)
    with pytest.raises(NoCredibleLetter) as raised:
        _letter(db_session, user)
    assert raised.value.reason == "below_band"
    assert db_session.query(RealWorldMission).filter_by(user_id=user.id).count() == 0


def test_the_week_has_no_letter_rather_than_one_below_the_learner(beginner_catalogue, db_session):
    user = _user(db_session, "C1")
    scheduler = MissionScheduler(db_session)
    # Not the first letter (that one is the cast's, authored for the band).
    _complete(db_session, asyncio.run(scheduler.ensure_weekly(user)))
    db_session.query(RealWorldMission).filter_by(user_id=user.id).update({"iso_week": None, "iso_year": None})
    db_session.commit()

    assert asyncio.run(scheduler.ensure_weekly(user)) is None
    # The Courrier still opens, with nothing new on it.
    today = asyncio.run(scheduler.today(user))
    assert today["weekly_mission"] is None


def test_the_c1_first_letter_is_romys_open_interview_not_a_story_frame_below_band(beginner_catalogue, db_session):
    """A story frame (A2, open: reach B2) is withheld at C1; the authored B1 interview is not."""

    user = _user(db_session, "C1")
    thread = _season_thread(db_session, user)
    state = dict(thread.state)
    live = dict(state[STATE_KEY])
    live["events"] = [
        {
            "id": "scene:1",
            "scene_id": str(uuid4()),
            "witnesses": ["romy_tremblay"],
            "summary_fr": "Romy vous a posé trois questions au Mistral.",
            "at": datetime.now(UTC).isoformat(),
        }
    ]
    state[STATE_KEY] = live
    thread.state = state
    db_session.add(thread)
    db_session.commit()

    today = asyncio.run(MissionScheduler(db_session).today(user))

    letter = today["weekly_mission"] or today["active_mission"]
    assert letter["title"] == "Trois questions de Romy"
    assert letter["letter_fit"]["source"] == "authored"
    assert letter["letter_fit"]["reach"] == "C1"


# ---------------------------------------------------------------------------
# Recency: no repeat, and none rather than a repeat
# ---------------------------------------------------------------------------


def test_no_canned_letter_is_reprinted_and_the_courrier_runs_out_rather_than_repeat(db_session):
    user = _user(db_session, "A2")
    seen: list[str] = []
    with pytest.raises(NoCredibleLetter) as raised:
        for _ in range(len(REAL_WORLD_MISSION_DOMAINS) + 1):
            mission = _letter(db_session, user)
            seen.append(_fit(mission)["request_key"])
            _complete(db_session, mission)
    assert len(seen) == len(set(seen)), seen
    assert seen, "an A2 learner has credible canned letters"
    assert raised.value.reason != "follow_up_unwritten"


def test_a_canned_letter_comes_back_only_after_the_reprint_window(db_session):
    user = _user(db_session, "A1")
    first = _letter(db_session, user)
    key = _fit(first)["request_key"]
    _complete(db_session, first)
    # Exhaust the rest.
    while True:
        try:
            _complete(db_session, _letter(db_session, user))
        except NoCredibleLetter:
            break
    # A month later, the first one may come round again (and only then).
    rows = db_session.query(RealWorldMission).filter_by(user_id=user.id).all()
    for row in rows:
        payload = dict(row.prompt_payload)
        fit = dict(payload[LETTER_FIT_KEY])
        fit["served_at"] = (datetime.now(UTC) - timedelta(days=CANNED_REUSE_DAYS + 1)).isoformat()
        payload[LETTER_FIT_KEY] = fit
        row.prompt_payload = payload
        row.completed_at = datetime.now(UTC) - timedelta(days=CANNED_REUSE_DAYS + 1)
    db_session.commit()
    again = _letter(db_session, user)
    assert _fit(again)["request_key"] in {_fit(row)["request_key"] for row in rows}
    assert key  # the first letter had a request key to come back to


def test_a_request_completed_this_week_is_not_asked_again(db_session):
    user = _user(db_session, "A2")
    scheduler = MissionScheduler(db_session)
    rotation = scheduler._letter_rotation(user)
    assert rotation["completed_recent"] == set()

    mission = _letter(db_session, user)
    _complete(db_session, mission, days_ago=2)
    rotation = scheduler._letter_rotation(user)
    assert _fit(mission)["request_key"] in rotation["completed_recent"]

    mission.completed_at = datetime.now(UTC) - timedelta(days=8)
    db_session.commit()
    assert _fit(mission)["request_key"] not in scheduler._letter_rotation(user)["completed_recent"]


def test_a_withheld_week_is_not_retried_the_same_day(beginner_catalogue, db_session, monkeypatch):
    user = _user(db_session, "C1")
    _season_thread(db_session, user)
    scheduler = MissionScheduler(db_session)
    _complete(db_session, asyncio.run(scheduler.ensure_weekly(user)))
    db_session.query(RealWorldMission).filter_by(user_id=user.id).update({"iso_week": None, "iso_year": None})
    db_session.commit()
    assert asyncio.run(scheduler.ensure_weekly(user)) is None

    calls: list[int] = []
    monkeypatch.setattr(scheduler, "create", lambda **_kw: calls.append(1))
    assert asyncio.run(scheduler.ensure_weekly(user)) is None
    assert calls == []


# ---------------------------------------------------------------------------
# Follow-ups name the earlier exchange
# ---------------------------------------------------------------------------


def _chain_from(letter: RealWorldMission, *, source: str = "canned") -> dict:
    return {
        "chain_id": f"chain:test:{letter.id}",
        "index": 2,
        "total": 2,
        "correspondent": courrier.correspondent_of(letter),
        "domain": _fit(letter)["request_key"],
        "after_outcome": "kept",
        "after_summary_fr": courrier.summarise_letter(letter),
        "after_mission_id": str(letter.id),
        "after_source": source,
        "stakes_level": 2,
        "queued_at": datetime.now(UTC).isoformat(),
    }


def test_a_canned_letter_without_an_authored_follow_up_opens_no_affair(db_session, monkeypatch):
    monkeypatch.setattr(courrier, "CHAIN_OPEN_PROBABILITY", 1.0)
    user = _user(db_session, "A2")
    mission = _letter(db_session, user)
    assert mission.chain_id is None


def test_a_reprint_is_not_a_follow_up(db_session):
    user = _user(db_session, "A2")
    first = _letter(db_session, user)
    _complete(db_session, first)
    chain = _chain_from(first)
    generator = MissionGenerator(db_session)
    with pytest.raises(NoCredibleLetter) as raised:
        asyncio.run(
            generator.build_payload(
                user=user,
                mission_type="message",
                cadence="ad_hoc",
                use_news=False,
                chain=chain,
                rotation=MissionScheduler(db_session)._letter_rotation(user),
                withhold=True,
            )
        )
    assert raised.value.reason == "follow_up_unwritten"
    assert raised.value.chain_id == chain["chain_id"]


def test_an_affair_that_cannot_go_on_ends_and_frees_the_courrier(db_session):
    user = _user(db_session, "A2")
    thread = _season_thread(db_session, user)
    first = _letter(db_session, user)
    _complete(db_session, first)
    chain = _chain_from(first)
    state = dict(thread.state)
    state[courrier.CORRESPONDENCE_KEY] = {"chains": {chain["chain_id"]: chain}}
    thread.state = state
    db_session.add(thread)
    db_session.commit()
    assert courrier.pending_chain_step(db_session, user=user) is not None

    with pytest.raises(NoCredibleLetter):
        _letter(db_session, user)
    assert courrier.pending_chain_step(db_session, user=user) is None


def test_an_authored_follow_up_names_the_earlier_exchange(db_session, monkeypatch):
    user = _user(db_session, "A2")
    first = _letter(db_session, user)
    _complete(db_session, first)
    domain = _fit(first)["request_key"]
    follow_up = "Merci pour votre réponse d'hier. Il reste une seule question."
    patched = tuple(
        {**item, "follow_ups": [{"opening_message": follow_up, "brief": "Répondez à sa dernière question."}]}
        if item["domain"] == domain
        else item
        for item in REAL_WORLD_MISSION_DOMAINS
    )
    monkeypatch.setattr(missions_module, "REAL_WORLD_MISSION_DOMAINS", patched)

    payload = asyncio.run(
        MissionGenerator(db_session).build_payload(
            user=user,
            mission_type="message",
            cadence="ad_hoc",
            use_news=False,
            chain=_chain_from(first),
            rotation=MissionScheduler(db_session)._letter_rotation(user),
            withhold=True,
        )
    )

    messenger = payload["prompt_payload"]["messenger"]
    assert messenger["opening_message"] == follow_up
    assert messenger["opening_message"] != (first.prompt_payload or {})["messenger"]["opening_message"]
    assert "suite de" in messenger["chain_note"]
    assert payload["prompt_payload"][LETTER_FIT_KEY]["follow_up_of"] == str(first.id)
    assert payload["brief"] == "Répondez à sa dernière question."
    assert "follow_up_brief" not in payload["prompt_payload"][LETTER_FIT_KEY]


# ---------------------------------------------------------------------------
# Story: the season's cast and registers stand
# ---------------------------------------------------------------------------


def test_a_season_learner_never_gets_a_premise_the_season_contradicts(db_session):
    user = _user(db_session, "A1")
    _season_thread(db_session, user)
    assert MissionScheduler(db_session)._season_active(user)
    unsafe = {domain for domain, item in CANNED.items() if item.get("season_safe") is False}
    assert {"work", "everyday_warmth", "social_plans"} <= unsafe
    seen: list[str] = []
    while True:
        try:
            mission = _letter(db_session, user)
        except NoCredibleLetter:
            break
        seen.append(_fit(mission)["request_key"])
        _complete(db_session, mission)
    assert seen and not set(seen) & unsafe, seen
    # And none of what was sent has a stranger say «tu».
    assert all("tu /" not in str(CANNED[key].get("register")) for key in seen)


def test_without_a_season_the_whole_catalogue_is_open(db_session):
    user = _user(db_session, "A1")
    assert not MissionScheduler(db_session)._season_active(user)


# ---------------------------------------------------------------------------
# The letter's own time estimate
# ---------------------------------------------------------------------------


def test_every_letter_carries_its_own_time_estimate(db_session):
    estimates = {}
    for level in ("A1", "B1"):
        user = _user(db_session, level)
        mission = _letter(db_session, user)
        body = serialize_mission(mission)
        assert isinstance(body["estimated_seconds"], int)
        assert 60 <= body["estimated_seconds"] <= 15 * 60, body["estimated_seconds"]
        assert body["letter_fit"]["level"] and body["letter_fit"]["reach"]
        estimates[level] = body["estimated_seconds"]
    # The first letter (authored) carries one too.
    user = _user(db_session, "C1")
    first = asyncio.run(MissionScheduler(db_session).ensure_weekly(user))
    assert serialize_mission(first)["estimated_seconds"] > 0


def test_an_older_letter_without_a_fit_serializes_without_an_estimate(db_session):
    user = _user(db_session, "A1")
    mission = _letter(db_session, user)
    payload = dict(mission.prompt_payload)
    payload.pop(LETTER_FIT_KEY)
    mission.prompt_payload = payload
    db_session.commit()
    body = serialize_mission(mission)
    assert body["estimated_seconds"] is None and body["letter_fit"] is None


# ---------------------------------------------------------------------------
# Neutral feedback when nothing assessed the reply
# ---------------------------------------------------------------------------


def test_an_unassessed_reply_claims_nothing_missing(db_session):
    user = _user(db_session, "B1")
    first = asyncio.run(MissionScheduler(db_session).ensure_weekly(user))
    first.objectives = [
        *list(first.objectives or []),
        {"id": "concept_1", "label": "Placer une fois : le subjonctif", "kind": "grammar", "target_count": 1},
    ]
    db_session.commit()
    text = "Merci pour ta lettre. Depuis que je suis arrivé, je découvre le quartier et les gens."

    correction = MissionCorrectionService(db_session)._fallback_correction(
        mission=first, text=text, language="de"
    )

    assert correction["verdict"] == "unassessed"
    assert correction["score_0_4"] is None
    assert correction["missing_targets"] == []
    assert all(item["assessed"] is False and item["met"] is False for item in correction["objective_progress"])
    assert "manque" not in _unassessed_acknowledgement(first)


def test_a_one_off_letter_is_never_reprinted(db_session):
    from app.services.missions import canned_letter_problem

    item = {**CANNED["transport"], "once": True}
    rotation = {"band": "A1", "completed_recent": set(), "canned_recent": set(), "canned_ever": {"transport"}}
    assert canned_letter_problem(item, rotation) == "sent_once"
    assert canned_letter_problem(CANNED["transport"], rotation) is None


def test_a_letter_is_not_written_more_than_one_band_above_the_learner():
    from app.services.missions import canned_letter_problem

    rotation = {"band": "A1", "completed_recent": set(), "canned_recent": set()}
    assert canned_letter_problem({"domain": "x", "level": "A2"}, rotation) is None
    assert canned_letter_problem({"domain": "x", "level": "B1"}, rotation) == "above_band"


def _scene(db_session, thread: SerialThread, event_id: str, summary: str, witness: str = "romy_tremblay") -> None:
    state = dict(thread.state)
    live = dict(state[STATE_KEY])
    live["events"] = [
        *list(live.get("events") or []),
        {
            "id": event_id,
            "scene_id": str(uuid4()),
            "witnesses": [witness],
            "summary_fr": summary,
            "at": datetime.now(UTC).isoformat(),
        },
    ]
    state[STATE_KEY] = live
    thread.state = state
    db_session.add(thread)


def test_two_scenes_with_the_same_summary_make_one_letter_a_week(db_session, monkeypatch):
    monkeypatch.setattr(courrier, "STORY_LETTER_PROBABILITY", 1.0)
    user = _user(db_session, "A2")
    thread = _season_thread(db_session, user)
    _scene(db_session, thread, "scene:a", "Vous avez répondu à Romy.")
    db_session.commit()
    first = courrier.story_letter_candidate(db_session, user=user)
    assert first and first["event_id"] == "scene:a"
    courrier.note_story_letter(db_session, user=user, candidate=first, mission_id=uuid4())
    db_session.commit()

    _scene(db_session, thread, "scene:b", "Vous avez répondu à Romy.")
    db_session.commit()
    assert courrier.story_letter_candidate(db_session, user=user) is None

    # A week later the same words may make a letter again.
    state = dict(thread.state)
    ledger = [dict(item) for item in state[courrier.CORRESPONDENCE_KEY]["story_born"]]
    for item in ledger:
        item["at"] = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        item["week"] = "2000-W01"
    state[courrier.CORRESPONDENCE_KEY] = {**state[courrier.CORRESPONDENCE_KEY], "story_born": ledger}
    thread.state = state
    db_session.commit()
    again = courrier.story_letter_candidate(db_session, user=user)
    assert again and again["event_id"] == "scene:b"


def test_a_story_letter_answered_this_week_is_not_written_again(db_session):
    user = _user(db_session, "A2")
    _season_thread(db_session, user)
    candidate = {
        "event_id": "scene:x",
        "character_id": "romy_tremblay",
        "character_name": "Romy",
        "register": "vous",
        "summary_fr": "Vous avez répondu à Romy.",
        "source_quotes": [],
        "week": courrier.iso_week_key(),
    }
    first = _letter(db_session, user, story_letter=candidate)
    assert _fit(first)["source"] == "story_frame"
    _complete(db_session, first)
    with pytest.raises(NoCredibleLetter) as raised:
        _letter(db_session, user, story_letter={**candidate, "event_id": "scene:y"})
    assert raised.value.reason == "completed_recently"
