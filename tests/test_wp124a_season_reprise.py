"""WP-124a «La reprise»: a failed day never leaves the season.

EXPERIENCE-REVIEW 2026-10-04 §2.3 F-5 and owner decision 1(a)/(c). When the
director cannot write a gap day of a season life, the learner re-reads the last
completed season page — their own branch, at their level, A1 lines translated, with
an honest note — instead of a stranger's café scene. The re-read earns only the
learning its practice produces: it binds no scene, settles nothing, sets no flag
and is not a played season day. A life off the season keeps the generic stand-in.

The director's failure is forced deterministically: the season suite's scripted
provider (``tests/test_season_one.SeasonProvider``) raises on every draft.
"""

from __future__ import annotations

import json
import random
import uuid
from copy import deepcopy

from sqlalchemy import func, select

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.schemas.daily_journey import ScenePanelLine
from app.services import living_story as engine
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from app.services.season import runtime as season_runtime
from app.services.season.reprise import (
    REPRISE_FALLBACK_KIND,
    REPRISE_SCENARIO_PREFIX,
    is_reprise,
    pinned_turns,
    reprise_brief,
)
from tests import learner_walk as walk
from tests import test_journey_end_to_end as support
from tests import walk_checks
from tests.test_learner_walk import production_day  # noqa: F401 - fixture
from tests.test_season_one import _season_state, _thread, season_on  # noqa: F401 - fixture
from tests.walk_checks_wp124a import check_lost_day_stays_in_season

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

#: The scene step's public panel line carries ``text_native`` once the WP-124a schema
#: patch (``app/schemas/daily_journey.ScenePanelLine``) is applied; until then the
#: translation is in the private draft only and the walk check rightly reports it.
SCHEMA_CARRIES_TRANSLATIONS = "text_native" in ScenePanelLine.model_fields
A1_DE = walk.Persona("a1-de-reprise", "de", "A1.1", "A1 German learner, a lost day")
GENERIC_KEYS = {"order_at_cafe", "arrange_meeting", "explain_delay"}


class CardPicker(walk.Answerer):
    """Plays well, and taps the named card when «Le choix» is posed."""

    def __init__(self, card_id: str) -> None:
        super().__init__("good", random.Random(7))
        self.card_id = card_id

    def pick_card(self, cards, examples):
        card = next((row for row in cards if row.get("id") == self.card_id), cards[0])
        return str(card.get("label_fr"))


def _director_fails(provider, monkeypatch) -> None:
    """Every draft is lost (the review's A1 day 3: a guard refused it)."""

    original = provider.generate_chat_completion

    def refused(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "SceneDraft":
            raise engine.StoryUnavailable("guard: gendered_agreement")
        return original(messages, **kwargs)

    monkeypatch.setattr(provider, "generate_chat_completion", refused)


def _user(db, email: str) -> User:
    return db.scalar(select(User).where(User.email == email))


def _journey(db, journey_id: str) -> DailyJourney:
    row = db.get(DailyJourney, uuid.UUID(journey_id))
    db.refresh(row)
    return row


def _live(db, user_id) -> dict:
    return deepcopy(dict((_thread(db, user_id).state or {}).get(engine.STATE_KEY) or {}))


def _scene_count(db, user_id) -> int:
    return int(db.scalar(select(func.count()).select_from(GraphicNovelScene).where(GraphicNovelScene.user_id == user_id)))


def _play(client, db, headers, persona, day, provider, answerer=None) -> dict:
    transcript = walk.play_day(
        client, db, headers, persona=persona, quality="good", day=day, provider=provider, answerer=answerer
    )
    assert transcript.get("error") is None, transcript.get("error")
    assert transcript["finish_status"] == 200, transcript
    return transcript


def _scene_prompt(transcript: dict) -> dict:
    return next(e["step"]["prompt"] for e in transcript["events"] if e["step"]["kind"] == "scene")


def _respond_prompts(transcript: dict) -> list[dict]:
    return [e["step"]["prompt"] for e in transcript["events"] if e["step"]["kind"] == "respond"]


# ---------------------------------------------------------------------------
# The reprise, end to end
# ---------------------------------------------------------------------------


def test_a_lost_gap_day_rereads_the_last_page_and_moves_nothing(
    assembled_client, db_session, journey_enabled, clock, production_day, monkeypatch  # noqa: F811
):
    """A1, German: T1 A and B played (the letter given to Gus); day 3 (g1.1) is lost.
    The day re-reads T1 B — the tentpole page is the last completed page — with the
    learner's own card, every line translated, the note in German; the season does
    not move and nothing is settled again."""

    provider = production_day
    headers, email = walk.register(assembled_client, A1_DE)
    user = _user(db_session, email)
    first = _play(assembled_client, db_session, headers, A1_DE, 1, provider)
    clock.advance(days=1)
    second = _play(assembled_client, db_session, headers, A1_DE, 2, provider, CardPicker("gus"))
    clock.advance(days=1)
    met_before = walk_checks.names_met(first) | walk_checks.names_met(second)
    before = _live(db_session, user.id)
    assert [row["key"] for row in before["season_script"]["played"]] == ["t1.a", "t1.b"]
    assert before["season_script"]["flags"].get("s1.letter_trusted_to") == "gus"
    scenes_before = _scene_count(db_session, user.id)

    with monkeypatch.context() as failing:
        _director_fails(provider, failing)
        transcript = _play(assembled_client, db_session, headers, A1_DE, 3, provider)

    assert transcript["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
    assert transcript["scenario"]["title_fr"] == "La lettre"
    scene = _scene_prompt(transcript)
    lines = [line for panel in scene["panels"] for line in panel["dialogue"]]
    assert lines, "the page is re-read in the scene step"
    journey = _journey(db_session, transcript["journey_id"])
    brief = DailyJourneyService(db_session, build_default_adapters())._pinned_brief(journey)
    drafted = [line for panel in brief.story_context["draft"]["panels"] for line in panel["dialogue"]]
    assert [line["text_fr"] for line in drafted] == [line["text_fr"] for line in lines]
    assert all(str(line.get("text_native") or "").strip() for line in drafted), "A1: every line translated"
    if SCHEMA_CARRIES_TRANSLATIONS:
        assert all(str(line.get("text_native") or "").strip() for line in lines), "A1: every line shown translated"
    respond = _respond_prompts(transcript)
    assert respond[0]["objective_native"].startswith("Heute lesen wir noch einmal."), respond[0]["objective_native"]
    # «Le choix» shows the card the learner actually tapped, and only that one.
    cards = [card for prompt in respond for card in prompt.get("choices") or []]
    cards += [card for e in transcript["events"] for card in ((e.get("result") or {}).get("next_turn") or {}).get("choices") or []]
    assert {card["id"] for card in cards} == {"gus"}, cards
    assert transcript["resolution"]["summary_native"].startswith("Noch einmal gelesen: «La lettre»")
    problems = check_lost_day_stays_in_season(transcript)
    if not SCHEMA_CARRIES_TRANSLATIONS:
        problems = [p for p in problems if "without its translation" not in p]
    assert problems == []
    # The day reads clean by every walk check the walk runs on any day (with the
    # names met on days 1–2, as a life walk carries them forward).
    transcript["names_met_before"] = sorted(met_before)
    assert walk_checks.run_all([transcript]) == []

    # Nothing moved: the season's day count, its flags and signals, the story.
    after = _live(db_session, user.id)
    assert after["season_script"] == before["season_script"]
    assert after.get("day_index") == before.get("day_index")
    assert after.get("events") == before.get("events")
    assert _scene_count(db_session, user.id) == scenes_before, "no scene was bound"
    marker = journey.plan_selection["generation_fallback"]
    assert marker["kind"] == REPRISE_FALLBACK_KIND and marker["season_day"] is False
    assert marker["page_key"] == "t1.b" and marker["page_source"] == "stored"
    assert journey.serial_episode_id is None


def test_a_reload_and_a_second_request_serve_the_same_reprise_and_settle_nothing(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """The reprise is chosen once, under the generation claim: a reload and a second
    create read the one stored plan; a repeated finish settles nothing twice."""

    email = f"reprise-reload-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = _user(db_session, email)
    for _ in range(2):  # T1 A and B, as written
        d.create()
        d.play(answer="Odile, c'est ma grand-mère.")
        assert d.finish("complete").status_code == 200
        clock.advance(days=1)
    before = _live(db_session, user.id)
    scenes_before = _scene_count(db_session, user.id)
    with monkeypatch.context() as failing:
        _director_fails(season_on, failing)

        first = d.create()
        assert first["status"] == "active"
        assert first["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
        again = d.create()
        assert again["id"] == first["id"] and again["scenario"] == first["scenario"]
        assert (d.today().get("journey") or {}).get("id") == first["id"]
        rows = db_session.scalars(select(DailyJourney).where(DailyJourney.user_id == user.id)).all()
        assert len([row for row in rows if str(row.local_date) == str(_journey(db_session, first["id"]).local_date)]) == 1
        d.play(answer="Oui. Je vends et je rentre.")
        assert d.finish("complete").status_code == 200
        replay = d.finish("complete")
        assert replay.status_code in (200, 409), replay.text
        # Settling the ending again (a concurrent finish) rewrites the same lines only.
        service = DailyJourneyService(db_session, build_default_adapters())
        journey = _journey(db_session, first["id"])
        brief = service._pinned_brief(journey)
        resolution = next(step for step in journey.steps if str(step.kind) == "resolution")
        shown = dict(resolution.public_prompt)
        service._settle_resolution(user, journey, brief, brief.response_task, proposal=None)
        service._settle_resolution(user, journey, brief, brief.response_task, proposal=None)
        assert resolution.public_prompt["summary_native"] == shown["summary_native"]
        db_session.flush()
        assert _live(db_session, user.id)["season_script"] == before["season_script"]
        assert _scene_count(db_session, user.id) == scenes_before

    # The director is back: the next day is the season's g1.1 — the reprise was a
    # learner day, not a season day.
    db_session.commit()
    clock.advance(days=1)
    d.create()
    assert d.journey["status"] == "active"
    assert not d.journey["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX)
    d.play(answer="Je reste encore un peu.")
    assert d.finish("complete").status_code == 200
    played = [row["key"] for row in _season_state(db_session, user.id)["played"]]
    assert played == ["t1.a", "t1.b", "g1.1"], played


def test_a_learner_whose_level_moved_rereads_the_page_at_their_level(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """T1 played at A2; the learner is B1 now: the same page and branch, in its B1 lines."""

    email = f"reprise-level-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = _user(db_session, email)
    for _ in range(2):
        d.create()
        d.play(answer="Odile, c'est ma grand-mère.")
        assert d.finish("complete").status_code == 200
        clock.advance(days=1)
    user.cefr_estimate = "B1.1"
    db_session.commit()
    _director_fails(season_on, monkeypatch)
    journey = d.create()
    assert journey["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
    assert journey["scenario"]["level_band"] == "B1"
    row = _journey(db_session, journey["id"])
    assert row.plan_selection["generation_fallback"]["page_source"] == "stored_relevelled"
    brief = DailyJourneyService(db_session, build_default_adapters())._pinned_brief(row)
    assert brief.story_context["season"]["page"]["band"] == "B1"


def test_a_life_without_a_stored_page_rereads_its_branch_from_the_bible(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """A life moved by ``jump_to_day`` (or stored before scenes kept their page) has no
    stored T1 B: the day is re-resolved from the bible at the learner's band, and the
    letter card is the one their flags say they chose."""

    from app.services.season.admin import jump_to_day

    email = f"reprise-bible-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = _user(db_session, email)
    jump_to_day(db_session, user, day=3, flags={"s1.letter_trusted_to": "marin"})
    db_session.commit()
    before = _live(db_session, user.id)["season_script"]
    _director_fails(season_on, monkeypatch)
    journey = d.create()
    assert journey["status"] == "active", journey
    assert journey["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
    row = _journey(db_session, journey["id"])
    assert row.plan_selection["generation_fallback"]["page_source"] == "bible"
    brief = DailyJourneyService(db_session, build_default_adapters())._pinned_brief(row)
    letter = next(turn for turn in brief.story_context["season"]["turns"] if turn.get("choice"))
    assert [reply["id"] for reply in letter["replies"]] == ["marin"]
    assert all("sets" not in reply for turn in brief.story_context["season"]["turns"] for reply in turn["replies"])
    d.play(answer="Je ne sais pas encore.")
    assert d.finish("complete").status_code == 200
    assert _live(db_session, user.id)["season_script"] == before


def test_with_no_page_to_reread_a_season_life_keeps_the_honest_dead_end(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """Day 1 cannot be served (a broken T1 page, the director down): there is no page
    to re-read, and a season life is still never sent to the café."""

    monkeypatch.setattr(season_runtime, "tentpole_brief", lambda today, context: None)
    _director_fails(season_on, monkeypatch)
    email = f"reprise-none-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A1.1"), db=db_session)
    journey = d.create()
    assert journey["status"] != "active", journey
    assert (journey.get("scenario") or {}).get("scenario_key") not in GENERIC_KEYS
    row = db_session.scalar(select(DailyJourney).where(DailyJourney.id == uuid.UUID(journey["id"])))
    assert "generation_fallback" not in (row.plan_selection or {})


def test_a_life_off_the_season_keeps_the_generic_stand_in(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """No season script: the director's failure is met by the WP-69 authored scene,
    exactly as before."""

    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "")
    _director_fails(season_on, monkeypatch)
    email = f"reprise-off-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    journey = d.create()
    assert journey["status"] == "active", journey
    assert journey["scenario"]["scenario_key"] in GENERIC_KEYS
    row = _journey(db_session, journey["id"])
    assert row.plan_selection["generation_fallback"]["kind"] == "authored"


def test_an_old_stand_in_journey_on_a_season_life_still_loads_and_finishes(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """A journey stored before WP-124a (the generic stand-in on a season life) is read
    back as it was planned, never re-written into a reprise, and can be finished."""

    email = f"reprise-old-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = _user(db_session, email)
    for _ in range(2):
        d.create()
        d.play(answer="Odile, c'est ma grand-mère.")
        assert d.finish("complete").status_code == 200
        clock.advance(days=1)
    _director_fails(season_on, monkeypatch)
    # The pre-WP-124a service: a season life was not recognised as one.
    with monkeypatch.context() as old:
        old.setattr(DailyJourneyService, "_starts_on_season", lambda self, user: False)
        stored = d.create()
    assert stored["scenario"]["scenario_key"] in GENERIC_KEYS
    before = _live(db_session, user.id)["season_script"]
    reloaded = d.today().get("journey") or {}
    assert reloaded["id"] == stored["id"]
    assert reloaded["scenario"]["scenario_key"] == stored["scenario"]["scenario_key"]
    d.play(answer="Un café, s'il vous plaît.")
    assert d.finish("complete").status_code == 200
    assert _live(db_session, user.id)["season_script"] == before


# ---------------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------------


def test_a_reprise_brief_is_never_settled_by_the_season():
    live = {"season_script": {"id": "s1", "played": [{"key": "t1.a", "event_id": "e1"}], "flags": {}}}
    context = {
        "season": {
            "id": "s1",
            "kind": "tentpole",
            "reprise": {"key": "t1.b"},
            "position": {"segment": "t1", "day_in_segment": 2, "season_day": 2},
            "page": {"movements": []},
        }
    }
    assert is_reprise(context) and season_runtime.is_tentpole(context)
    settled = season_runtime.settle(
        deepcopy(live), story_context=context, details={"season_turns": []}, event_id="e2", date_iso=None, day_index=3
    )
    assert settled == live


def test_pinned_turns_keep_the_route_taken_and_drop_every_consequence():
    turns = [
        {
            "id": "b.letter",
            "choice": True,
            "sets": {"x": 1},
            "replies": [
                {"id": "gus", "sets": {"s1.letter_trusted_to": "gus"}, "sets_if": [{"if": {}}]},
                {"id": "marin", "sets": {"s1.letter_trusted_to": "marin"}},
            ],
        },
        {"id": "b.turn1", "replies": [{"id": "a"}, {"id": "b"}]},
    ]
    routed = pinned_turns(turns, [{"turn_id": "b.letter", "reply_id": "gus"}], {})
    assert [reply["id"] for reply in routed[0]["replies"]] == ["gus"]
    assert "sets" not in routed[0] and all("sets" not in r and "sets_if" not in r for r in routed[0]["replies"])
    assert [reply["id"] for reply in routed[1]["replies"]] == ["a", "b"], "no evidence: every reply kept"
    by_flags = pinned_turns(turns, [], {"s1.letter_trusted_to": "marin"})
    assert [reply["id"] for reply in by_flags[0]["replies"]] == ["marin"]


def test_a_life_that_never_completed_a_page_has_no_reprise(db_session, season_on):  # noqa: F811
    from app.services.season.admin import jump_to_day

    email = f"reprise-unit-{uuid.uuid4()}@example.com"
    user = User(email=email, hashed_password="x", target_language="fr", native_language="en", cefr_estimate="A2.1")
    db_session.add(user)
    db_session.flush()
    jump_to_day(db_session, user, day=1)
    db_session.flush()
    assert reprise_brief(db_session, user) is None


# ---------------------------------------------------------------------------
# The walk check fires on a lost day that leaves the season, and only then
# ---------------------------------------------------------------------------


def _transcript(key: str, *, lines: list[dict], reply_lines: list[dict] | None = None, native: str = "de", cefr: str = "A1.1") -> dict:
    return {
        "persona": "x",
        "quality": "good",
        "day": 3,
        "native": native,
        "cefr": cefr,
        "scenario": {"scenario_key": key},
        "events": [
            {"step": {"kind": "scene", "prompt": {"panels": [{"narration_fr": "", "dialogue": lines}]}}},
            {
                "step": {"kind": "respond", "prompt": {"objective_native": "Heute lesen wir noch einmal."}},
                "result": {"character_lines": reply_lines or []},
            },
        ],
    }


def test_the_walk_check_fires_on_a_stranger_scene_a_wrong_vous_and_an_untranslated_line():
    stranger = _transcript(
        "order_at_cafe",
        lines=[{"character_id": "margaux_barman", "text_fr": "Tiens, bonjour ! Vous vous installez ou c'est à emporter ?", "text_native": ""}],
    )
    problems = check_lost_day_stays_in_season(stranger)
    assert any("generic scene" in p for p in problems) and any("generic stand-in line" in p for p in problems)
    bad = _transcript(
        f"{REPRISE_SCENARIO_PREFIX}t1.b",
        lines=[{"character_id": "lila_bonnet", "text_fr": "Lila voudrait vous voir demain.", "text_native": ""}],
        reply_lines=[{"speaker_id": "margaux_barman", "text_fr": "Vous restez pour dîner ?"}],
    )
    problems = check_lost_day_stays_in_season(bad)
    assert sum("«vous» here" in p for p in problems) == 2, problems
    assert any("without its translation" in p for p in problems)


def test_the_walk_check_is_quiet_on_an_honest_reprise():
    good = _transcript(
        f"{REPRISE_SCENARIO_PREFIX}t1.a",
        lines=[
            # The bible's own «vous» (Marin before the tutoiement) is the page re-read.
            {"character_id": "marin_leveque", "text_fr": "Asseyez-vous.", "text_native": "Setz dich."},
            {"character_id": "lila_bonnet", "text_fr": "Tu restes ?", "text_native": "Bleibst du?"},
            {"character_id": "augustin_de_roncourt", "text_fr": "Vous êtes qui ?", "text_native": "Wer sind Sie?"},
        ],
        reply_lines=[{"speaker_id": "lila_bonnet", "text_fr": "D'accord."}],
    )
    assert check_lost_day_stays_in_season(good) == []
    # A B1 reprise is not held to the A1 translation rule; a tentpole day is not a lost day.
    assert check_lost_day_stays_in_season(_transcript(f"{REPRISE_SCENARIO_PREFIX}t1.a", lines=[{"character_id": "lila_bonnet", "text_fr": "Tu restes ?"}], cefr="B1.1")) == []
    assert check_lost_day_stays_in_season(_transcript("story_x", lines=[{"character_id": "lila_bonnet", "text_fr": "Tu viens ?"}])) == []


def test_lost_days_keep_introducing_the_days_unit_so_the_plan_moves_on(
    assembled_client, db_session, journey_enabled, clock, production_day, monkeypatch  # noqa: F811
):
    """Integration finding, 2026-10-04: a reprise was treated as a tentpole page and
    introduced no unit, so the next day's grammar plan was the same one, and a
    director refused on that unit was refused again every day. The 15-life walk's
    A1 learners re-read T1 B for 28 days with no rule at all. A reprise is a practice
    day: it introduces the day's unit, and two lost days introduce two different ones."""

    from app.services.season import bridges as season_bridges

    # WP-124b: with the bridges applied, the second lost day of g1 is its bridge (an
    # authored season day); this test pins two reprises, so it runs without them.
    monkeypatch.setattr(season_bridges, "load_bridges", lambda season_id, **_: {})
    provider = production_day
    headers, email = walk.register(assembled_client, A1_DE)
    _play(assembled_client, db_session, headers, A1_DE, 1, provider)
    clock.advance(days=1)
    _play(assembled_client, db_session, headers, A1_DE, 2, provider, CardPicker("gus"))
    clock.advance(days=1)
    rules: list[str] = []
    with monkeypatch.context() as failing:
        _director_fails(provider, failing)
        for day in (3, 4):
            transcript = _play(assembled_client, db_session, headers, A1_DE, day, provider)
            assert transcript["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t1.b"
            rule = [e["step"] for e in transcript["events"] if e["step"]["kind"] == "rule"]
            assert rule, f"day {day}: the reprise introduces the day's unit"
            rules.append(json.dumps(rule[0].get("prompt") or {}, sort_keys=True, ensure_ascii=False))
            clock.advance(days=1)
    assert rules[0] != rules[1], "the second lost day introduces the next unit, not the same one"
