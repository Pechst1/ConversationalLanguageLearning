"""WP-111 «La bible de saison»: season 1 «La clé d'Odile», runnable.

Three layers, cheapest first:

1. the season files are the owner-approved bible — every French line of every
   tentpole carried verbatim (``scripts/season_check.py``), every cross-reference
   resolved;
2. the pieces: the learner's own calendar with the weekend flex, the flags and
   Lila's path, a tentpole day resolved for a band, the gap's forbidden reveals;
3. a whole life through the real API with a scripted model: the fifty-nine days of
   the season, tentpoles on their days and served as written (no director call),
   generated days inside their gap's rules, the critic's one retry, and the flags
   the learner's replies set.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.services import living_story as engine
from app.services.season import clock as season_clock
from app.services.season import runtime as season_runtime
from app.services.season.director import forbidden_hits, gap_brief, required_schedule
from app.services.season.fidelity import missing_lines
from app.services.season.flags import effective_flags, holds, lila_path, promised_to
from app.services.season.format import SEASON_ROOT, load_season
from app.services.season.page import project, resolve_day
from app.services.season.turns import match_reply
from app.services.season.world import season_location_ids, season_world_bible
from tests import test_journey_end_to_end as support
from tests.test_living_story_longitudinal import (
    OBJECTIVES,
    PREMISES,
    ScriptedProvider,
    TurnScript,
    _fresh_question,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

BIBLES = {
    "t1": "01-le-mauvais-accueil.md",
    "t2": "02-la-haut.md",
    "t3": "03-deux-promesses.md",
    "t4": "04-la-photographie.md",
    "t5": "05-berlin.md",
    "t6": "06-lautre-cote.md",
    "t7": "07-le-dernier-soir.md",
    "t8": "08-ce-quon-garde.md",
}
REPO = SEASON_ROOT.parents[2]


# ---------------------------------------------------------------------------
# 1. The files are the bible
# ---------------------------------------------------------------------------


def test_season_one_loads_whole_and_holds_together():
    season = load_season("s1")
    assert season.total_days == 59
    assert sum(1 for seg in season.segments if seg.kind == "tentpole") == 8
    assert sum(seg.days for seg in season.segments if seg.kind == "gap") == 43
    assert set(season.tentpoles) == set(BIBLES)
    assert set(season.gaps) == {f"g{n}" for n in range(1, 8)}


@pytest.mark.parametrize("tentpole_id", sorted(BIBLES))
def test_every_french_line_of_the_bible_is_on_the_page(tentpole_id):
    bible = REPO / "docs" / "story" / "season-1" / BIBLES[tentpole_id]
    missing = missing_lines(bible, SEASON_ROOT / "s1" / f"{tentpole_id}.json")
    assert missing == [], f"{tentpole_id} drops or rewords bible lines: {missing[:5]}"


def test_every_place_and_speaker_resolves_in_the_season_world():
    season = load_season("s1")
    world = season_world_bible("s1")
    places = {place["id"] for place in world["setting"]["recurring_locations"]}
    assert season_location_ids("s1") <= places | {"le_mistral"}
    cast = {member["id"] for member in world["cast"]}
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            assert day.location_id in places, (tentpole.id, day.location_id)
    # Every turn is addressed to someone the world knows (the director reads the same cast).
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            for movement in day.movements:
                if getattr(movement, "kind", "") == "turn":
                    assert movement.to in cast, (tentpole.id, movement.id, movement.to)


def test_marin_and_lila_are_not_a_couple_in_the_world_the_director_reads():
    world = season_world_bible("s1")
    lila = next(member for member in world["cast"] if member["id"] == "lila_bonnet")
    assert "NOT a couple" in lila["role"]
    marin = next(member for member in world["cast"] if member["id"] == "marin_leveque")
    text = json.dumps(marin).casefold()
    assert not re.search(r"\bring\b|\bpropos", text), "S-2: the co-op plan replaces the ring proposal"


# ---------------------------------------------------------------------------
# 2a. The learner's own calendar (S-12)
# ---------------------------------------------------------------------------


def _play_calendar(start: date, *, skip_every: int = 0) -> list[dict]:
    """Walk the season day by day from ``start``; return the played log."""

    season = load_season("s1")
    state: dict = {"id": "s1"}
    today = start
    step = 0
    while True:
        step += 1
        if skip_every and step % skip_every == 0:
            today += timedelta(days=1)
            continue
        pos = season_clock.position(season, state, today=today)
        if pos.finished:
            break
        state = season_clock.record_played(state, pos, date_iso=today.isoformat(), event_id=f"e{step}")
        today += timedelta(days=1)
        assert step < 400
    return season_clock.played_log(state)


@pytest.mark.parametrize("start", [date(2026, 11, 11) + timedelta(days=n) for n in range(7)])
def test_the_season_is_59_days_give_or_take_a_weekend_and_tentpoles_are_two_days(start):
    log = _play_calendar(start)
    tentpole_days = [row for row in log if row["kind"] == "tentpole"]
    assert len(tentpole_days) == 16
    assert 59 - 7 <= len(log) <= 59 + 7
    for index, row in enumerate(log):
        if row["kind"] == "tentpole" and row["day_in_segment"] == 1:
            follow = log[index + 1]
            assert (follow["segment"], follow["day_in_segment"]) == (row["segment"], 2)
    season = load_season("s1")
    for segment in season.segments:
        if segment.kind == "gap":
            played = sum(1 for row in log if row["segment"] == segment.id)
            assert abs(played - segment.days) <= 1, (segment.id, played)


def test_a_tentpole_that_would_open_on_a_friday_opens_on_saturday():
    # T1 on Wed/Thu; gap 1 (5 days) Fri..Tue; T2 would open on Wed. Shift the start so
    # the nominal T2 Day A is a Friday: start T1 on a Friday → gap Sun..Thu → Fri.
    start = date(2026, 11, 13)  # a Friday
    assert start.weekday() == 4
    log = _play_calendar(start)
    t2 = next(row for row in log if row["segment"] == "t2" and row["day_in_segment"] == 1)
    assert date.fromisoformat(t2["date"]).weekday() == 5, "T2 Day A lands on the Saturday"
    assert sum(1 for row in log if row["segment"] == "g1") == 6


def test_a_gap_whose_last_day_is_a_weekend_day_ends_early():
    # Nominal T2 Day A on a Monday → the gap's last day falls on Sunday → start T2 then.
    start = date(2026, 11, 14)  # Saturday: T1 Sat/Sun, gap 1 Mon..Fri, T2 nominal Sat — pick another
    for offset in range(7):
        candidate = start + timedelta(days=offset)
        nominal_t2 = candidate + timedelta(days=2 + 5)
        if nominal_t2.weekday() == 0:  # Monday
            log = _play_calendar(candidate)
            t2 = next(row for row in log if row["segment"] == "t2" and row["day_in_segment"] == 1)
            assert date.fromisoformat(t2["date"]).weekday() == 6, "T2 opens on the Sunday"
            assert sum(1 for row in log if row["segment"] == "g1") == 4
            return
    pytest.fail("no start puts the nominal T2 on a Monday")


def test_a_skipped_real_day_is_not_a_story_day():
    log = _play_calendar(date(2026, 11, 11), skip_every=3)
    assert sum(1 for row in log if row["kind"] == "tentpole") == 16
    days = [row["season_day"] for row in log]
    assert days == list(range(1, len(days) + 1)), "the season counts the learner's days, not the calendar's"


# ---------------------------------------------------------------------------
# 2b. Flags and Lila's path (§6, §7)
# ---------------------------------------------------------------------------


def _signals(*values):
    return [{"gate": n, "signal": value, "source": f"s{n}"} for n, value in enumerate(values, 1)]


def test_lilas_path_moves_on_what_is_expressed_never_on_a_single_opening():
    assert lila_path([]) == "open"
    assert lila_path(_signals("romance")) == "open", "one romance-leaning expression leaves it open"
    assert lila_path(_signals("romance", "none", "romance")) == "romance"
    assert lila_path(_signals("romance", "romance", "friendship")) == "friendship", "naming friendship steers back"
    assert lila_path(_signals("romance", "romance", "none")) == "romance", "letting a moment pass loses nothing"
    assert lila_path(_signals("friendship", "romance", "romance")) == "romance"


def test_you_cannot_fully_promise_both():
    assert promised_to({"s1.promise_gus": "yes", "s1.promise_marin": "yes"}) == "both_half"
    assert promised_to({"s1.promise_gus": "yes", "s1.promise_marin": "no"}) == "gus"
    assert promised_to({"s1.promise_gus": "half", "s1.promise_marin": "no"}) == "gus"
    assert promised_to({"s1.promise_gus": "no", "s1.promise_marin": "yes"}) == "marin"
    assert promised_to({"s1.promise_gus": "no", "s1.promise_marin": "no"}) == "neither"


@pytest.mark.parametrize(
    ("stored", "ending"),
    [
        ({"s1.flat_decision": "keep", "s1.evidence_shared": "marchand_only"}, "garder"),
        ({"s1.flat_decision": "keep", "s1.evidence_shared": "kept"}, "laisser_partir"),
        ({"s1.flat_decision": "coop", "s1.evidence_shared": "public"}, "partager"),
        ({"s1.flat_decision": "sell", "s1.evidence_shared": "marchand_only"}, "laisser_partir"),
    ],
)
def test_the_flat_decides_the_ending(stored, ending):
    season = load_season("s1")
    flags = effective_flags(season, {"flags": stored})
    assert flags["s1.ending"] == ending
    assert flags["s1.painting"] == {"garder": "with_you", "partager": "with_gus", "laisser_partir": "lost"}[ending]


def test_camilles_gender_is_the_learners_and_stable_until_chosen():
    season = load_season("s1")
    one = effective_flags(season, {}, seed="learner-1")["s1.camille_gender"]
    assert one == effective_flags(season, {}, seed="learner-1")["s1.camille_gender"]
    chosen = effective_flags(season, {"flags": {"s1.camille_gender": "m"}}, seed="learner-1")
    assert chosen["s1.camille_gender"] == "m"


def test_conditions_read_flags_bands_and_paths():
    flags = {"s1.fire_photo": "wall", "s1.lila_path": "open", "s1.gus_persuaded": True}
    assert holds({"s1.fire_photo": "wall"}, flags)
    assert not holds({"s1.fire_photo": "margaux"}, flags)
    assert holds({"path": ["friendship", "open"]}, flags)
    assert holds({"band": "b1"}, flags, band="B1") and not holds({"band": "b1"}, flags, band="A2")
    assert holds({"all": [{"any": [{"s1.fire_photo": "wall"}, {"s1.evidence_shared": "public"}]}, {"s1.gus_persuaded": True}]}, flags)
    assert holds({"s1.kiss": {"set": False}}, flags)


# ---------------------------------------------------------------------------
# 2c. A tentpole day, resolved for this learner
# ---------------------------------------------------------------------------


def test_t1_day_a_at_a1_reads_the_a2_lines_with_translations_and_at_b1_the_b1_lines():
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    a1 = resolve_day(season, "t1", "a", flags=flags, band="A1", language="en")
    b1 = resolve_day(season, "t1", "a", flags=flags, band="B1", language="en")
    first_a1 = a1["movements"][0]["lines"][0]
    first_b1 = b1["movements"][0]["lines"][0]
    assert first_a1["text_fr"] == "Paris. Le 11 novembre. Il pleut. Tu as une valise, une lettre et une clé."
    assert first_a1["text_native"].startswith("Paris. 11 November")
    assert first_b1["text_fr"].startswith("Paris, un 11 novembre sous la pluie.")
    assert first_b1["text_native"] is None
    projection = project(a1)
    assert projection["turn"]["to"] == "augustin_de_roncourt"
    assert projection["scene_panels"][-1]["balloon"] is True, "the turn's own panel closes the scene"
    assert projection["ending"]["text_fr"] == "Deux clés pour la même porte. À suivre…"


def test_t5_is_told_or_discovered_by_what_happened_to_the_photograph():
    season = load_season("s1")
    for fire_photo, variant in (("wall", "elle_te_le_dit"), ("margaux", "tu_le_decouvres")):
        flags = effective_flags(season, {"flags": {"s1.fire_photo": fire_photo}}, seed="x")
        page = resolve_day(season, "t5", "a", flags=flags, band="A2", language="de")
        assert page["variant"].startswith(variant), (fire_photo, page["variant"])
    # B's place is Odile's flat with Lila's key, Marin and Lila's flat without it.
    places = {}
    for has_key in (True, False):
        flags = effective_flags(season, {"flags": {"s1.fire_photo": "margaux", "s1.lila_has_key": has_key}}, seed="x")
        places[has_key] = resolve_day(season, "t5", "a", flags=flags, band="A2", language="en")["location_id"]
    assert places == {True: "odile_flat", False: "marin_lila_flat"}


@pytest.mark.parametrize("ending", ["garder", "partager", "laisser_partir"])
def test_t8_plays_the_ending_the_flat_decided(ending):
    season = load_season("s1")
    decision = {"garder": "keep", "partager": "coop", "laisser_partir": "sell"}[ending]
    stored = {"s1.flat_decision": decision, "s1.evidence_shared": "marchand_only" if ending == "garder" else "public"}
    flags = effective_flags(season, {"flags": stored}, seed="x")
    for letter in ("a", "b"):
        page = resolve_day(season, "t8", letter, flags=flags, band="A2", language="en")
        assert page is not None and page["variant"] == ending


def test_a_clumsy_reply_routes_like_a_polished_one():
    season = load_season("s1")
    page = resolve_day(season, "t1", "a", flags=effective_flags(season, {}, seed="x"), band="A1", language="en")
    turn = project(page)["turn"]
    assert match_reply(turn, "Odile, c'est ma grand-mère.")[0] == "a"
    assert match_reply(turn, "Je viens pour vendre l'appartement.")[0] == "b"
    assert match_reply(turn, "Et vous, vous êtes qui ?")[0] == "d"
    assert match_reply(turn, "euh… bonjour")[0] == turn["fallback"]


# ---------------------------------------------------------------------------
# 2d. The gaps: forbidden reveals, scheduled moments
# ---------------------------------------------------------------------------


def test_a_generated_day_may_not_spoil_what_the_next_tentpole_owns():
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    assert forbidden_hits(season, "g1", ["Lila cache une lettre de Berlin."], flags=flags)
    assert forbidden_hits(season, "g1", ["Marin sort une vieille polaroïd."], flags=flags)
    assert forbidden_hits(season, "g2", ["Le feu a commencé chez Odile, en haut."], flags=flags)
    assert forbidden_hits(season, "g5", ["Margaux soupire : « Je suis fatiguée. »"], flags=flags)
    assert not forbidden_hits(season, "g1", ["Margaux essuie un verre déjà sec. Il pleut."], flags=flags)
    # «L.» is never named, in any gap.
    assert forbidden_hits(season, "g7", ["Marin lit derrière le tableau."], flags=flags)


def test_every_required_moment_is_scheduled_inside_its_window():
    season = load_season("s1")
    for gap in season.gaps.values():
        for seed in ("a", "b", "c", "d"):
            schedule = required_schedule(gap, seed=seed, length=gap_days(season, gap.id))
            assert sorted(schedule.values()) == sorted(need.premise for need in gap.required)
            for day, premise in schedule.items():
                need = next(row for row in gap.required if row.premise == premise)
                assert need.from_day <= day <= need.by_day


def gap_days(season, gap_id):
    return next(seg.days for seg in season.segments if seg.id == gap_id)


def test_the_gap_brief_names_todays_moment_and_the_next_tentpole():
    season = load_season("s1")
    state = {"id": "s1", "played": [{"segment": "t1", "day_in_segment": 1, "event_id": "1"}, {"segment": "t1", "day_in_segment": 2, "event_id": "2"}]}
    pos = season_clock.position(season, state, today=date(2026, 11, 13))
    assert pos.key == "g1.1"
    brief = gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x")
    assert brief["next_tentpole"]["id"] == "t2"
    assert any("Berlin" in text for text in brief["gap"]["must_not"])
    assert brief["rules"]["the_rule"].startswith("Episodes without meaningful change are refused")


# ---------------------------------------------------------------------------
# 3. A life through the real API
# ---------------------------------------------------------------------------

#: The fake's premises: the longitudinal set minus any that address the learner as
#: «vous» — its lines say «tu», and a scene never mixes the two.
TU_PREMISES = [p for p in PREMISES if not re.search(r"\b(vous|votre|vos)\b", p, re.IGNORECASE)]
SEASON_LOCATIONS = ["le_mistral", "boulangerie", "quai_de_valmy", "user_apartment", "marin_lila_flat", "ngo_office", "stairwell"]
SEASON_SPEAKERS = ["margaux_barman", "lila_bonnet", "marin_leveque", "augustin_de_roncourt", "romy_tremblay"]


class SeasonProvider(ScriptedProvider):
    """A compliant director and critic for a season, plus the reply classifier."""

    def __init__(self) -> None:
        super().__init__()
        self.spoil_once = True
        self.critic_refusals_left = 1
        self.routes: dict[str, str] = {}
        self.signal = "romance"
        self.reviews: list[dict] = []
        self.classified: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        if schema == "SceneDraft" and (source.get("season_script") or {}).get("brief"):
            self.calls.append((schema, deepcopy(source)))
            value = self._season_draft(source)
            self.drafts.append(deepcopy(value))
            self.scene_index += 1
        elif schema == "StoryReview":
            self.calls.append((schema, deepcopy(source)))
            refuse = self.critic_refusals_left > 0
            self.critic_refusals_left -= 1 if refuse else 0
            value = {
                "hook": True, "stakes": True, "value_turn": not refuse, "meaningful_change": not refuse,
                "advances_thread": True, "in_character": True, "spoils_next_tentpole": False,
                "change_summary": "avant → après", "issues": ["Nothing changes by the end of the day."] if refuse else [],
                "accepted": not refuse,
            }
            self.reviews.append(value)
        elif schema in ("TutorVerdict", "VoiceReply", "StoryTurn", "TurnReview"):
            self.calls.append((schema, deepcopy(source)))
            text = str(source.get("learner_text") or "")
            season_turn = ((source.get("story") or {}).get("season_turn")) or {}
            value = {
                "TutorVerdict": {"outcome": "met", "evidence_quotes": [text] if text.strip() else []},
                "VoiceReply": {"reply_fr": "D'accord.", "understood_intent": "The learner answered.", "needs_clarification": False},
                "StoryTurn": {
                    "resolution_fr": "La journée se termine.",
                    "summary_native": "The day ends.",
                    "callback_fr": "Vous avez parlé.",
                    "season_flags": [{"flag": "user.usual_order", "value": "un café crème"}]
                    if "user.usual_order" in (season_turn.get("may_set") or [])
                    else [],
                    "season_signal": self.signal if season_turn.get("gate") else None,
                },
                "TurnReview": {"accepted": True, "issues": [], "released_issues": []},
            }[schema]
        elif schema == "ReplyChoice":
            self.calls.append((schema, deepcopy(source)))
            replies = [row["id"] for row in source["replies"]]
            wanted = self.routes.get(source["learner_text"])
            value = {
                "reply_id": wanted if wanted in replies else source["fallback"],
                "expresses": self.signal if (source["scene"] or {}).get("gate") else "none",
                "value": "un café crème" if "crème" in source["learner_text"] else None,
                "confidence": 0.9,
            }
            self.classified.append({"turn": source["scene"], **value})
        else:
            return super().generate_chat_completion(messages, **kwargs)
        return SimpleNamespace(content=json.dumps(value, ensure_ascii=False), model="fake-season", provider="test", total_tokens=30, cost=0.0)

    def _season_draft(self, context: dict) -> dict:
        brief = context["season_script"]["brief"]
        today = brief["today"]
        premise = today.get("required_premise") or (today.get("premises") or [{}])[0]
        n = self.scene_index
        chapter = context.get("chapter") or {}
        keeps = bool(chapter) and not (chapter.get("resolved") or chapter.get("exhausted"))
        speaker = SEASON_SPEAKERS[n % len(SEASON_SPEAKERS)]
        location = SEASON_LOCATIONS[n % len(SEASON_LOCATIONS)]
        shape = str((context.get("chapter_shape") or {}).get("shape") or chapter.get("shape") or "")
        if shape == "bottle" and keeps and chapter.get("location_id"):
            location = str(chapter["location_id"])
        must_change = (context.get("variety") or {}).get("must_change") or {}
        if must_change.get("character_id") == speaker and must_change.get("location_id") == location:
            speaker = SEASON_SPEAKERS[(n + 1) % len(SEASON_SPEAKERS)]
        spoil = self.spoil_once
        self.spoil_once = False
        title = premise.get("title_fr") or f"Jour {n}"
        return {
            "title_fr": f"{title} ({n})",
            "premise_fr": TU_PREMISES[n % len(TU_PREMISES)],
            "setup_native": "A day between two tentpoles.",
            "objective_native": OBJECTIVES[n % len(OBJECTIVES)],
            "objective_semantics": "Any sincere answer.",
            "character_id": speaker,
            "location_id": location,
            "causal_reason": "Follows the gap's thread.",
            "source_event_ids": [],
            "novelty_key": f"season-{n}",
            "chapter": {k: chapter[k] for k in ("title_fr", "dramatic_question", "possible_developments")} if keeps else {
                "title_fr": f"Entre-deux {n}",
                "dramatic_question": _fresh_question(context, n),
                "possible_developments": ["Quelque chose change.", "Rien ne bouge encore."],
            },
            "panels": [
                {"narration_fr": "Il pleut sur le canal." + (" Lila cache une lettre de Berlin." if spoil else ""), "dialogue": [], "visual_direction": "Wide shot of the canal.", "alt_native": "The canal in the rain."},
                {"narration_fr": "", "dialogue": [{"character_id": speaker, "text_fr": "Tu as une minute ?", "text_native": "Got a minute?"}], "visual_direction": "Two friends at the zinc.", "alt_native": "Two friends at the zinc."},
                {"narration_fr": "Un silence.", "dialogue": [], "visual_direction": "Close-up of a glass.", "alt_native": "A glass."},
                {"narration_fr": "", "dialogue": [{"character_id": speaker, "text_fr": "Alors, on fait quoi ?", "text_native": "So, what do we do?"}], "visual_direction": "The friend turns to Toi.", "alt_native": "The friend turns to you."},
            ],
            "opening_line_fr": "Tu en penses quoi ?",
            "suggested_response_fr": "Je reste encore un peu.",
            "hint_native": "Say what you think.",
            "translation_native": "What do you think?",
            "capability_key": None,
            "season_checklist": {
                "premise_id": premise.get("id"),
                "threads": ["settling"],
                "change_before": "avant",
                "change_after": "après",
                "turn_want": "say it",
                "small_moment_id": ((today.get("small_moments") or [{}])[0]).get("id"),
                "hook_fr": "À suivre…",
                "forbidden_respected": True,
            },
        }

    def _turn(self, source: dict) -> dict:
        value = super()._turn(source)
        season_turn = (source.get("story") or {}).get("season_turn") or {}
        if "user.usual_order" in (season_turn.get("may_set") or []):
            value["season_flags"] = [{"flag": "user.usual_order", "value": "un café crème"}]
        if season_turn.get("gate"):
            value["season_signal"] = self.signal
        return value


@pytest.fixture
def season_on(monkeypatch, request):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    lanes_on = bool(getattr(request, "param", False))
    monkeypatch.setattr(settings, "ATELIER_STORY_TURN_LANES_ENABLED", lanes_on)
    if lanes_on:
        # WP-87's story lane, run inline (as tests/test_wp87_lanes.py does): nothing
        # is left in the background pool when the test ends.
        from app.services import story_lanes

        monkeypatch.setattr(story_lanes, "dispatcher", lambda job: story_lanes.run_story_job(job))
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    season_runtime._ROUTE_CACHE.clear()
    fake = SeasonProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def _thread(db, user_id) -> SerialThread:
    thread = db.scalar(select(SerialThread).where(SerialThread.user_id == user_id))
    db.refresh(thread)
    return thread


def _season_state(db, user_id) -> dict:
    return dict(((_thread(db, user_id).state or {}).get(engine.STATE_KEY) or {}).get(season_clock.SEASON_KEY) or {})


def _latest_scene(db, user_id) -> GraphicNovelScene:
    return db.scalars(
        select(GraphicNovelScene).where(GraphicNovelScene.user_id == user_id).order_by(GraphicNovelScene.created_at.desc())
    ).first()


def _play(d, provider, clock, answer: str, *, turn: TurnScript | None = None) -> dict:
    provider.turn = turn or TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
    d.create()
    assert d.journey["status"] == "active", d.journey
    d.play(answer=answer)
    response = d.finish("complete")
    assert response.status_code == 200, response.text
    clock.advance(days=1)
    return d.journey


@pytest.mark.parametrize("season_on", [False, True], ids=["one-actor", "lanes"], indirect=True)
def test_a_whole_season_plays_its_tentpoles_on_their_days(assembled_client, db_session, journey_enabled, clock, season_on):
    """Fifty-nine story days of one A2 learner: every tentpole day served as written
    on its day (no director call), every generated day inside its gap's rules."""

    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(assembled_client, support.register(assembled_client, f"s1-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session)
    user_id = None
    days: list[dict] = []
    for _day in range(80):
        before = len(provider.director_contexts())
        journey = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
        user_id = user_id or _user_id_of(db_session, journey)
        scene = _latest_scene(db_session, user_id)
        season = dict((scene.script_payload or {}).get("season") or {})
        days.append(
            {
                "key": season.get("key"),
                "kind": season.get("kind"),
                "director_calls": len(provider.director_contexts()) - before,
                "title": scene.title,
                "page": bool((scene.script_payload or {}).get("season_page")),
            }
        )
        if _season_state(db_session, user_id) and season_clock.position(
            load_season("s1"), _season_state(db_session, user_id), today=clock.moment.date()
        ).finished:
            break
    keys = [row["key"] for row in days]
    tentpoles = [row for row in days if row["kind"] == "tentpole"]
    assert len(tentpoles) == 16, " ".join(str(k) for k in keys)
    assert all(row["director_calls"] == 0 and row["page"] for row in tentpoles), "a tentpole is served as written"
    assert [row["key"] for row in tentpoles] == [f"t{n}.{d}" for n in range(1, 9) for d in ("a", "b")]
    gaps = [row for row in days if row["kind"] == "gap"]
    assert 43 - 7 <= len(gaps) <= 43 + 7
    assert all(row["director_calls"] >= 1 for row in gaps)
    assert days[0]["key"] == "t1.a" and days[0]["title"] == "Le mauvais accueil"
    # The gap's forbidden reveal was refused once and rewritten; the critic's one
    # refusal bought one retry.
    refused = [payload for schema, payload in provider.calls if schema == "SceneDraft" and payload.get("previous_rejections")]
    assert any("season_spoiler" in " ".join(row["previous_rejections"]) for row in refused)
    assert any(not review["accepted"] for review in provider.reviews)
    state = _season_state(db_session, user_id)
    flags = state.get("flags") or {}
    assert flags.get("user.usual_order") == "un café crème"
    assert flags.get("user.return_ticket") == "mercredi 18 novembre" or flags.get("user.return_ticket")
    assert flags.get("s1.estate_liable") is True, "T4's fixed facts are set for everybody"
    gates = {row.get("gate") for row in state.get("signals") or []}
    assert {1, 2, 3, 4, 5} <= gates, f"all five of Lila's gates were read: {sorted(g for g in gates if g)}"
    premises = {(row["gap"], row["premise"]) for row in state.get("premises") or []}
    for gap_id, premise in (("g1", "romy_enquete"), ("g1", "la_meme_chose"), ("g1", "le_billet"), ("g2", "le_diner_rate"), ("g3", "sur_le_toit"), ("g4", "la_dispute")):
        assert (gap_id, premise) in premises, f"{gap_id} never staged its required moment {premise}"


def _user_id_of(db, journey: dict):
    from app.db.models.daily_journey import DailyJourney

    return db.get(DailyJourney, uuid.UUID(journey["id"])).user_id


# ---------------------------------------------------------------------------
# The owner's read: the first days, written down
# ---------------------------------------------------------------------------

GAP_REPLIES = [
    "Je reste encore un peu. Je veux comprendre qui elle était.",
    "Un café crème, s'il te plaît. Comme elle.",
    "Merci pour la soupe. Oui, j'ai froid, mais ça va mieux.",
    "Je ne sais pas encore. Mais je ne pars pas demain.",
    "D'accord, je t'aide. On commence quand ?",
    "C'est gentil. Je suis un peu perdu ici.",
]


def _pinned_brief(db, journey_id: str) -> dict:
    from app.db.models.daily_journey import DailyJourneyStep

    for step in db.scalars(select(DailyJourneyStep).where(DailyJourneyStep.journey_id == uuid.UUID(journey_id))):
        brief = (step.private_task or {}).get("scenario_brief")
        if brief:
            return brief
    return {}


def _respond_turns(db, journey_id: str) -> list[dict]:
    from app.db.models.daily_journey import DailyJourneyStep

    for step in db.scalars(select(DailyJourneyStep).where(DailyJourneyStep.journey_id == uuid.UUID(journey_id))):
        if str(step.kind) == "respond":
            return list((step.private_task or {}).get("turns") or [])
    return []


@pytest.mark.skipif(not os.environ.get("SEASON_REPORT"), reason="writes the owner's transcript; set SEASON_REPORT=<path>")
def test_write_the_first_days_for_the_owner(assembled_client, db_session, journey_enabled, clock, season_on):
    from app.services.season.transcript import render_generated_day, render_tentpole_day

    provider = season_on
    provider.critic_refusals_left = 0
    provider.spoil_once = False
    days = int(os.environ.get("SEASON_REPORT_DAYS", "10"))
    band = os.environ.get("SEASON_REPORT_BAND", "A2.1")
    d = support.Driver(assembled_client, support.register(assembled_client, f"s1-report-{uuid.uuid4()}@example.com", cefr=band), db=db_session)
    lines = [
        "# Saison 1 · «La clé d'Odile» — les premiers jours d'une vie (fake provider)",
        "",
        f"*Joué par le harnais (`tests/test_season_one.py`), niveau {band}, langue de l'interface : anglais.*",
        "*Les jours de tentpole sont les pages de la bible, telles qu'un apprenant les rencontre. Les jours générés "
        "viennent ici d'un faux réalisateur (plomberie seulement, jamais la qualité) : leur vraie prose demande un "
        "passage payant avec l'accord du propriétaire.*",
        "",
    ]
    user_id = None
    for day in range(1, days + 1):
        provider.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
        d.create()
        journey_id = d.journey["id"]
        user_id = user_id or _user_id_of(db_session, d.journey)
        brief = _pinned_brief(db_session, journey_id)
        season_ctx = (brief.get("story_context") or {}).get("season") or {}
        turns = season_ctx.get("turns") or []
        answers: list[str] = []
        for index, turn in enumerate(turns):
            replies = [reply for reply in turn.get("replies") or [] if reply.get("examples")]
            pick = replies[(day + index) % len(replies)] if replies else None
            answers.append(pick["examples"][0] if pick else "Je ne sais pas.")
        count = 0
        for _ in range(120):
            step = d.current()
            if step is None:
                break
            if step["kind"] in ("scene", "resolution", "rule"):
                d.advance()
                continue
            if step["kind"] == "recall":
                d.attempt(d.recall_answer(step, correct=True))
                if d.journey.get("current_step_id") == step["id"]:
                    d.advance()
                continue
            text = answers[min(count, len(answers) - 1)] if answers else GAP_REPLIES[(day + count) % len(GAP_REPLIES)]
            if answers:
                provider.routes[text] = next(
                    (reply["id"] for turn in turns for reply in turn.get("replies") or [] if text in (reply.get("examples") or [])),
                    "",
                )
            count += 1
            body = d.attempt({"mode": "text", "text": text}).json()
            if body.get("next_turn"):
                continue
            if d.journey.get("current_step_id") == step["id"]:
                d.advance()
        assert d.finish("complete").status_code == 200
        scene = _latest_scene(db_session, user_id)
        payload = scene.script_payload or {}
        season = payload.get("season") or {}
        if payload.get("season_page"):
            page = payload["season_page"]
            lines.append(f"## Jour {day} — T{page['number']} · {page['tentpole_title_fr']} · jour {page['day'].upper()} · {page['story_date_fr']}")
            lines.append("")
            lines.extend(render_tentpole_day(page, payload.get("season_routing") or []))
        else:
            draft = (brief.get("story_context") or {}).get("draft") or {}
            resolution = next((step for step in d.journey["steps"] if step["kind"] == "resolution"), {})
            lines.append(f"## Jour {day} — {season.get('key', '?')} (jour généré) · {draft.get('title_fr')}")
            lines.append("")
            lines.extend(render_generated_day(draft, _respond_turns(db_session, journey_id), resolution.get("prompt") or {}))
        clock.advance(days=1)
    state = _season_state(db_session, user_id)
    lines += ["---", "", "**Drapeaux après ces jours** (jamais montrés à l'apprenant) :", "", "```json",
              json.dumps(state.get("flags") or {}, ensure_ascii=False, indent=1), "```", ""]
    from pathlib import Path

    Path(os.environ["SEASON_REPORT"]).write_text("\n".join(lines), encoding="utf-8")


def test_a_test_learner_can_be_put_on_any_season_day(assembled_client, db_session, journey_enabled, clock, season_on):
    """``scripts/season_jump.py``: the owner plays T2 on the test copy without living days 1–7."""

    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"s1-jump-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    summary = jump_to_day(db_session, user, day=8, flags={"s1.lila_has_key": True})
    db_session.commit()
    assert summary["next"]["key"] == "t2.a" and summary["played"] == 7
    journey = _play(d, season_on, clock, "Je ne sais pas. Je ne la connaissais pas bien.")
    scene = _latest_scene(db_session, _user_id_of(db_session, journey))
    assert (scene.script_payload or {}).get("season", {}).get("key") == "t2.a"
    assert scene.title == "Là-haut"
    flags = _season_state(db_session, user.id).get("flags") or {}
    assert flags.get("camille.met") is True and flags.get("s1.lila_has_key") is True


def test_a_director_that_skips_the_scheduled_moment_never_costs_the_day(assembled_client, db_session, journey_enabled, clock, season_on):
    """The dinner (gate 2) is owed until staged; a draft without it is asked once more,
    then served — the season never stalls on a missed moment."""

    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    provider = season_on
    original = provider._season_draft

    def stubborn(context):
        value = original(context)
        value["season_checklist"]["premise_id"] = None  # never the scheduled one
        return value

    provider._season_draft = stubborn
    email = f"s1-owed-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A2.1"), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=14)  # g2.5: the dinner's last scheduled day has come
    db_session.commit()
    journey = _play(d, provider, clock, "Je reste encore un peu.")
    scene = _latest_scene(db_session, _user_id_of(db_session, journey))
    assert (scene.script_payload or {}).get("season", {}).get("key") == "g2.5", "the day was served, not lost"
    hints = [" ".join(payload.get("previous_rejections") or []) for schema, payload in provider.calls if schema == "SceneDraft"]
    assert any("Le dîner raté" in hint for hint in hints), "the director was asked once more for the dinner"
    brief = gap_brief(
        load_season("s1"),
        season_clock.position(load_season("s1"), _season_state(db_session, user.id), today=clock.moment.date()),
        flags={},
        state=_season_state(db_session, user.id),
        seed=str(user.id),
    )
    assert (brief["today"]["required_premise"] or {}).get("id") == "le_diner_rate", "the dinner is still owed"
