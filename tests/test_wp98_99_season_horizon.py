"""WP-98 «La saison suivante» and WP-99 «Le facteur et les dépêches» — the engine half.

* Season 3 is authored and loads like seasons 1–2; after it, the life is never in an
  unbounded interlude: either a season is written (behind the flag, fake director
  here), or the interlude is NAMED with a return date, and on that date a reprise
  season built from the learner's own material begins.
* Every resolution writes a teaser that names a real open row, never repeated within
  fourteen days.
* The director hears the gap; a returning learner is greeted, not reproached; and
  «Entre-temps» is read from the cast's `meanwhile` rows.

No model is called: the provider is the scripted fake from the longitudinal suite.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.services import living_story as engine
from app.services import season_writer
from app.services.serial import AUTHORED_SEASON_PATHS, SerialThreadService
from app.services.serial_arc_planner import INTERLUDE_BEATS
from tests import test_living_story_longitudinal as longitudinal
from tests.test_living_story_longitudinal import (
    CAST,
    SceneScript,
    TurnScript,
    driver,
    live_state,
    play_day,
    scenes_of,
    thread_of,
)

# The longitudinal suite's fixtures: the assembled API, its clock and the scripted model.
assembled_client = longitudinal.assembled_client
clock = longitudinal.clock
journey_enabled = longitudinal.journey_enabled
provider = longitudinal.provider
one_exchange = longitudinal.one_exchange

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _world_for(season: int) -> dict:
    """The world a life is in during ``season``: season one, with each authored
    season merged over it exactly as a rollover does."""

    world = SerialThreadService._load_world_bible()
    for number in range(2, season + 1):
        world = SerialThreadService.merge_season_world_bible(
            world, SerialThreadService.authored_season_world_bible(number), next_season=number
        )
    return world


def _location_ids(world: dict) -> dict[str, dict]:
    return {place["id"]: place for place in engine._locations(world)}


_INCLUSIVE = re.compile(r"[A-Za-zÀ-ÿ]·[A-Za-zÀ-ÿ]")


# ---------------------------------------------------------------------------
# 1. Season files: 2 and 3 validate with the same checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("season", [2, 3])
def test_every_authored_season_validates_like_the_others(season):
    raw = SerialThreadService.authored_season_world_bible(season)
    assert raw, f"season {season} is authored ({AUTHORED_SEASON_PATHS[season]})"
    world = _world_for(season)
    assert world["season_number"] == season
    cast_ids = {member["id"] for member in world["cast"]}
    assert {"marin_leveque", "lila_bonnet", "augustin_de_roncourt", "romy_tremblay", "margaux_barman"} <= cast_ids

    # The situation is this season's own, with French threads for the page.
    situation = engine.season_situation(world)
    assert situation == raw[f"season_{season_writer.ORDINALS[season]}_situation"]
    threads = engine.season_threads(world)
    assert [row["key"] for row in threads] == [f"s{season}:{n}" for n in range(len(threads))]
    assert len(threads) == 5 and all(row["text"] and row["text_fr"] for row in threads)

    # Arcs: well formed, cast from the world, a tentpole at the end, flags set.
    arcs = world["season_arcs"]
    assert len(arcs) == 5 and sum(len(arc["stages"]) for arc in arcs) == 15
    assert len({arc["id"] for arc in arcs}) == len(arcs)
    for arc in arcs:
        assert arc["title"] and 2 <= int(arc["min_episodes_between_stages"]) <= 4
        assert set(arc["characters"]) <= cast_ids | {"user"}, arc["id"]
        stage_ids = [stage["id"] for stage in arc["stages"]]
        assert len(set(stage_ids)) == len(stage_ids)
        assert all(stage["summary"] and stage["sets"] for stage in arc["stages"])
        assert arc["stages"][-1].get("tentpole") is True
    assert engine.season_completion(arcs, {}) == 0.0

    # Agendas: every cast member has a private plan; witnesses are others in the cast.
    agendas = engine.character_agendas(world)
    assert set(agendas) == cast_ids
    for character_id, steps in agendas.items():
        assert 4 <= len(steps) <= 6
        for step in steps:
            assert step["id"] and step["summary"] and step["meanwhile_fr"]
            assert step["witnesses"] and character_id not in step["witnesses"]
            assert set(step["witnesses"]) <= cast_ids

    # Premiere copy, and learner-facing French that passes the A1/A2 guards.
    premiere = engine.season_premiere_of(world)
    assert premiere["number"] == season and premiere["title_fr"] and premiere["logline_fr"]
    french = [
        premiere["title_fr"], premiere["logline_fr"], *situation["open_threads_fr"],
        *[step["meanwhile_fr"] for steps in agendas.values() for step in steps],
    ]
    for line in french:
        assert engine._without_vulgar(line) == line, line
        assert not _INCLUSIVE.search(line), line

    # Places: every one has a French name.
    for place in _location_ids(world).values():
        assert engine.location_display_name(place), place["id"]


def test_season_three_carries_the_cast_adds_one_face_and_its_own_interludes():
    s2 = _world_for(2)
    s3 = _world_for(3)
    before = {member["id"]: member for member in s2["cast"]}
    after = {member["id"]: member for member in s3["cast"]}
    added = set(after) - set(before)
    assert added == {"tiago_moreira"}, "at most one new character"
    tiago = after["tiago_moreira"]
    assert tiago["portrait"] is None and tiago["portrait_missing"] is True
    assert "tiago_moreira" not in (s3.get("visual_design") or {}).get("characters", {}), (
        "no portrait asset: faces fall back to initials"
    )
    # The five carried characters keep their names and origins; their season secrets move on.
    for cid, member in before.items():
        assert after[cid]["name"] == member["name"] and after[cid].get("origin") == member.get("origin")
        assert after[cid]["secret"] != member.get("secret"), cid
    # The merge directives are applied, never copied into the world.
    for key in ("cast_updates", "cast_additions", "locations_fr"):
        assert key not in s3
    # Six authored interludes of its own, then the shared deck (now eight).
    beats = engine.interlude_beats(s3)
    own = s3["interlude_beats"]
    assert len(own) >= 5 and len(INTERLUDE_BEATS) >= 5
    places = _location_ids(s3)
    for beat in own:
        assert beat["location_id"] in places and beat["summary"] and beat["seed"]
    assert [beat["id"] for beat in beats[: len(own)]] == [beat["id"] for beat in own]
    # Continuity with season two's ending: its questions become this season's premise.
    assert "Margaux" in s3["season_three_situation"]["open_threads_fr"][0]
    assert any("clés" in step["meanwhile_fr"] for step in s2["character_agendas"]["margaux_barman"])


def test_the_loader_serves_three_and_nothing_after_it():
    service = SerialThreadService(None)
    world = _world_for(2)
    third = service._load_next_season_world_bible(current_world=world, next_season=3)
    assert third["season_number"] == 3 and third["world_bible_version"] == "paris-s3"
    assert service._load_next_season_world_bible(current_world=third, next_season=4) == {}
    # The world it was merged over is not mutated.
    assert world["season_number"] == 2 and "tiago_moreira" not in {m["id"] for m in world["cast"]}


# ---------------------------------------------------------------------------
# 2. Rollover 2 → 3 → named interlude → reprise
# ---------------------------------------------------------------------------


def _material_live(season: int) -> dict:
    return {
        "season_index": season,
        "arc_progress": {},
        "planted": [
            {"id": "e1:plant", "text_fr": "La vieille clé bleue du compteur.", "status": "open",
             "character_id": "margaux_barman", "chapter_index": 1, "day": 4},
        ],
        "consequences": [
            {"id": "e2:branch:0", "kind": "branch", "text_fr": "Vous avez promis d'aider Lila au vernissage.",
             "character_id": "lila_bonnet", "weight": 3, "day": 20, "last_referenced": None},
        ],
        "commitments": [
            {"id": "e3:commitment:0", "text_fr": "Apporter du pain dimanche chez Marin.", "status": "open",
             "witnesses": ["marin_leveque"], "day": 30},
        ],
        "secrets": {"margaux_barman": "revealed", "lila_bonnet": "hinted"},
        "chronicle": [{"id": "c1", "season": 1, "day": 4}],
    }


def test_two_rolls_into_three_then_a_named_interlude_then_the_reprise(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", False)
    thread = SimpleNamespace(id="thread-s3", world_bible=_world_for(2))
    live = _material_live(2)

    assert engine.roll_over_season(None, thread, live, day=150, today="2026-10-01") is True
    assert live["season_index"] == 3 and thread.world_bible["season_number"] == 3
    assert live["season_premiere"] == {
        "number": 3,
        "title_fr": "Les clés du Mistral",
        "logline_fr": thread.world_bible["season_logline_fr"],
        "source": "authored",
        "pending": True,
        "day": 150,
    }
    # Secrets whose text changed start unknown; the old state is archived, not lost.
    assert live["secrets"] == {} and live["secrets_archive"] == {
        "s2:margaux_barman": "revealed",
        "s2:lila_bonnet": "hinted",
    }
    assert "interlude" not in live and live["season_stage"] == "running"

    # Season three ends; nothing is authored after it and the writer is off.
    archive_before = len(live["threads_archive"])
    assert engine.roll_over_season(None, thread, live, day=260, today="2026-11-01") is False
    assert live["season_stage"] == "interlude"
    assert live["interlude"] == {
        "since": "2026-11-01",
        "returns_on": "2026-11-15",
        "reason_fr": "Entre deux saisons : l'histoire reprend le 15 novembre.",
    }
    archived = len(live["threads_archive"])
    assert archived == archive_before + 5

    # Asked again before the date: still the same named interlude, nothing re-archived.
    assert engine.roll_over_season(None, thread, live, day=264, today="2026-11-10") is False
    assert live["interlude"]["returns_on"] == "2026-11-15"
    assert len(live["threads_archive"]) == archived

    # On the promised day the story resumes — from this life's own open rows.
    assert engine.roll_over_season(None, thread, live, day=270, today="2026-11-15") is True
    world = thread.world_bible
    assert world["season_number"] == 4 and world["season_source"] == "reprise"
    assert live["season_index"] == 4 and "interlude" not in live
    assert live["interludes"][-1]["ended_on"] == "2026-11-15"
    grounded = {arc["grounded_in"] for arc in world["season_arcs"]}
    assert {"e1:plant", "e2:branch:0", "e3:commitment:0"} <= grounded
    threads_fr = engine.season_situation(world)["open_threads_fr"]
    assert any("La vieille clé bleue du compteur." in line for line in threads_fr)
    assert [row["key"] for row in engine.season_threads(world)][0] == "s4:0"
    assert live["season_premiere"]["source"] == "reprise" and live["season_premiere"]["number"] == 4
    assert engine.season_completion(world["season_arcs"], {}) == 0.0


def test_the_reprise_is_deterministic_and_never_empty():
    world = _world_for(3)
    empty = {"season_index": 3}
    first = season_writer.reprise_season(live=empty, world=world, next_season=4, seed="a")
    assert first == season_writer.reprise_season(live=empty, world=world, next_season=4, seed="a")
    assert len(first["season_arcs"]) >= 3, "a life with nothing open still gets a season"
    assert season_writer.french_date("2026-12-01") == "1er décembre"


class _FakeDirector:
    """The season writer's director and critic, scripted."""

    def __init__(self, *, ground: bool = True, accept: bool = True) -> None:
        self.ground = ground
        self.accept = accept
        self.calls: list[str] = []

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        self.calls.append(schema)
        if schema == "SeasonDraft":
            refs = [row["id"] for row in source["material"]]
            ref = (lambda i: refs[i % len(refs)]) if self.ground else (lambda i: "invented:row")
            value = {
                "title_fr": "Le pain du dimanche",
                "logline": "The promises of last season come due.",
                "logline_fr": "Les promesses de la saison dernière reviennent.",
                "your_arc": "Keep what you promised, with the people you promised it to.",
                "first_episode_seed": "Sunday morning, bread under your arm, Marin's door ajar.",
                "arcs": [
                    {
                        "id": f"written_arc_{i}",
                        "title_fr": f"Arc écrit {i}",
                        "characters": ["marin_leveque", "user"],
                        "grounded_in": ref(i),
                        "min_episodes_between_stages": 3,
                        "stages": [
                            {"id": "spark", "summary": "A promise comes back to the table.", "sets": {"marin.x": "a"}},
                            {"id": "pressure", "summary": "Keeping it costs something real.", "sets": {"marin.x": "b"}},
                            {"id": "tentpole", "summary": "It is kept in front of everyone.", "sets": {"marin.x": True}},
                        ],
                    }
                    for i in range(3)
                ],
                "open_threads": [
                    {"text": "Will the bread arrive?", "text_fr": "Le pain arrivera-t-il ?", "grounded_in": ref(i)}
                    for i in range(3)
                ],
            }
        else:
            value = {"accepted": self.accept, "issues": [] if self.accept else ["too far from the material"]}
        return SimpleNamespace(
            content=json.dumps(value, ensure_ascii=False), model="fake-season", provider="test",
            total_tokens=10, cost=0.0,
        )


@pytest.mark.parametrize(
    ("ground", "accept", "written"),
    [(True, True, True), (False, True, False), (True, False, False)],
)
def test_the_writer_drafts_season_four_from_this_life_or_names_the_interlude(
    monkeypatch, ground, accept, written
):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", True)
    fake = _FakeDirector(ground=ground, accept=accept)
    monkeypatch.setattr(engine, "_client", lambda: fake)
    thread = SimpleNamespace(id="thread-w", world_bible=_world_for(3))
    live = _material_live(3)

    rolled = engine.roll_over_season(None, thread, live, day=300, today="2027-01-10")
    assert rolled is written
    if written:
        assert fake.calls == ["SeasonDraft", "SeasonReview"], "one director call, one critic call"
        world = thread.world_bible
        assert world["season_number"] == 4 and world["season_source"] == "written"
        assert {arc["id"] for arc in world["season_arcs"]} == {f"written_arc_{i}" for i in range(3)}
        assert all(arc["stages"][-1]["tentpole"] for arc in world["season_arcs"])
        assert live["season_premiere"]["title_fr"] == "Le pain du dimanche"
        assert live["season_premiere"]["source"] == "written"
        assert engine.season_situation(world)["open_threads_fr"] == ["Le pain arrivera-t-il ?"] * 3
    else:
        # An invented premise is refused before the critic; a refused one is not used.
        assert fake.calls == (["SeasonDraft"] if not ground else ["SeasonDraft", "SeasonReview"])
        assert live["interlude"]["returns_on"] == "2027-01-24"
        assert thread.world_bible["season_number"] == 3


def test_the_writer_is_off_by_default():
    assert settings.model_fields["ATELIER_SEASON_WRITER_ENABLED"].default is False


# ---------------------------------------------------------------------------
# 3. Teasers
# ---------------------------------------------------------------------------


def test_a_teaser_names_a_real_open_row_and_is_not_repeated_within_fourteen_days():
    world = _world_for(3)
    live = _material_live(3)
    live["threads"] = {}
    candidates = engine.teaser_candidates(live, world)
    refs = {row["ref"] for row in candidates}
    assert {"e1:plant", "e3:commitment:0", "s3:0"} <= refs

    seen: list[dict] = []
    start = date(2026, 10, 1)
    for offset in range(40):
        today = (start + timedelta(days=offset)).isoformat()
        teaser = engine.next_teaser(
            live, world, character_id="marin_leveque", register="tu", date=today, seed="t"
        )
        if teaser is None:
            continue
        assert teaser["ref"] in refs and teaser["date"] == today
        assert engine.teaser_grounded(teaser["text_fr"], teaser["ref"], candidates)
        for earlier in seen:
            gap = (date.fromisoformat(today) - date.fromisoformat(earlier["date"])).days
            if gap < engine.TEASER_WINDOW_DAYS:
                assert earlier["ref"] != teaser["ref"] and earlier["text_fr"] != teaser["text_fr"]
        seen.append(teaser)
        live["teasers"] = engine.teasers_after(live, teaser)
    assert seen, "open rows exist, so teasers are written"
    # The witness of a promise raises it first.
    assert seen[0]["ref"] == "e3:commitment:0" and seen[0]["text_fr"].startswith("Dis, j'y repense")

    # Nothing open → nothing written; an invented line or an unknown id never passes.
    bare = {"threads": {key: {"state": "closed"} for key in [f"s3:{n}" for n in range(5)]}}
    assert engine.next_teaser(bare, world, character_id="romy_tremblay", register="vous",
                              date="2026-10-01", seed="t") is None
    assert not engine.teaser_grounded("Demain, un dragon arrive au canal.", "e1:plant", candidates)
    assert not engine.teaser_grounded("La vieille clé bleue du compteur.", "e9:plant", candidates)


# ---------------------------------------------------------------------------
# 4. Absence and «Entre-temps»
# ---------------------------------------------------------------------------


def test_the_greeting_fits_the_absence_and_never_reproaches():
    short = engine.absence_greeting(2, character_id="romy_tremblay", register="tu")
    week = engine.absence_greeting(6, character_id="margaux_barman", register="vous")
    long = engine.absence_greeting(40, character_id="lila_bonnet", register="tu")
    assert len({short, week, long}) == 3
    assert "vous" in week.casefold() and "te " in long
    for line in (short, week, long):
        assert not engine.guilt_tripping(line)
    assert engine.guilt_tripping("Où étiez-vous passé ?")
    assert engine.guilt_tripping("Tu nous as abandonnés !")
    assert engine.absence_context(1) is None and engine.absence_context(None) is None
    assert engine.absence_context(3)["days"] == 3


def test_meanwhile_since_reads_only_the_cast_offscreen_week_after_the_date():
    live = {
        "events": [
            {"id": "journey:1:story", "summary_fr": "Vous avez aidé Romy.", "date": "2026-10-02"},
            {"id": "meanwhile:marin_leveque:s3_train_ticket", "kind": "meanwhile",
             "character_id": "marin_leveque", "summary_fr": "Marin a imprimé les horaires.",
             "date": "2026-10-01"},
            {"id": "meanwhile:lila_bonnet:s3_studio_key", "kind": "meanwhile",
             "character_id": "lila_bonnet", "summary_fr": "Lila a la clé d'un atelier.",
             "date": "2026-10-05"},
            {"id": "meanwhile:romy_tremblay:s3_contract_offer", "kind": "meanwhile",
             "character_id": "romy_tremblay", "summary_fr": "La cheffe de Romy a proposé un contrat.",
             "at": "2026-10-04T09:00:00+00:00"},
        ]
    }
    rows = engine.meanwhile_since({engine.STATE_KEY: live}, "2026-10-01")
    assert rows == [
        {"text_fr": "La cheffe de Romy a proposé un contrat.", "date": "2026-10-04", "character_id": "romy_tremblay"},
        {"text_fr": "Lila a la clé d'un atelier.", "date": "2026-10-05", "character_id": "lila_bonnet"},
    ]
    assert engine.meanwhile_since(live, date(2026, 10, 5)) == []


def test_the_director_hears_the_gap_and_the_page_greets_the_learner_back(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = driver(assembled_client, db_session)
    for day in range(1, 3):
        play_day(d, provider, answer=f"Je viens samedi, jour {day}.")
        clock.advance(days=1)
    assert provider.director_contexts()[-1]["gap_days"] == 1
    assert "absence" not in provider.director_contexts()[-1]

    clock.advance(days=5)  # away six days in all
    play_day(d, provider, answer="Je suis de retour, bonjour !")
    context = provider.director_contexts()[-1]
    assert context["gap_days"] == 6
    assert context["absence"]["days"] == 6 and "No reproach" in context["absence"]["instruction"]
    scene = scenes_of(db_session, d)[-1]
    absence = scene.script_payload["absence"]
    assert absence["days"] == 6 and absence["greeting_fr"]
    assert not engine.guilt_tripping(absence["greeting_fr"])
    # Earlier pages carry no absence block.
    assert all("absence" not in (s.script_payload or {}) for s in scenes_of(db_session, d)[:-1])


# ---------------------------------------------------------------------------
# 5. Three hundred days: never an unbounded interlude, teasers always grounded
# ---------------------------------------------------------------------------

LIFE_DAYS = 300
# The first interlude chapter (at most CHAPTER_MAX_SCENES days) names the interlude;
# it then ends at the first interlude chapter that closes on or after its return date.
INTERLUDE_BOUND = season_writer.INTERLUDE_WAIT_DAYS + 2 * engine.CHAPTER_MAX_SCENES + 1


def test_three_hundred_days_never_sit_in_an_unbounded_interlude(
    assembled_client, db_session, journey_enabled, clock, provider, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", False)
    provider.long_memory = True
    provider.season_engine = True
    d = driver(assembled_client, db_session, cefr="A2.2")
    speakers = [CAST["romy"], CAST["margaux"], CAST["lila"]]
    phases: list[str] = []
    seasons: list[int] = []
    interludes: list[dict | None] = []
    teasers: list[dict | None] = []
    premieres: list[dict] = []
    dates: list[str] = []
    for day in range(1, LIFE_DAYS + 1):
        play_day(
            d,
            provider,
            answer=f"Je m'en occupe, jour {day}.",
            scene=SceneScript(character_id=speakers[(day // 2) % len(speakers)]),
            turn=TurnScript(
                callback_fr=f"Vous avez répondu le jour {day}.",
                summary_native=f"You answered on day {day}.",
                commitment_text=f"Passer au marché le jour {day + 3}." if day % 9 == 0 else None,
                resolve_open_commitments=day % 9 == 4,
                extra={"development_index": 1 + day % 2},
            ),
        )
        dates.append(clock.moment.date().isoformat())
        context = provider.director_contexts()[-1]
        phases.append(context["season"]["phase"])
        live = live_state(db_session, d)
        seasons.append(int(live.get("season_index") or 1))
        interludes.append(dict(live["interlude"]) if live.get("interlude") else None)
        teasers.append(dict(live["next_teaser"]) if live.get("next_teaser") else None)
        scene = scenes_of(db_session, d)[-1]
        if (scene.script_payload or {}).get("season_premiere"):
            premieres.append(scene.script_payload["season_premiere"])
        clock.advance(days=1)

    # The life went past the last authored season and kept going.
    assert max(seasons) >= 4, seasons[::20]
    assert [p["number"] for p in premieres] == sorted({p["number"] for p in premieres})
    assert {p["number"] for p in premieres} >= {2, 3, 4}
    assert next(p for p in premieres if p["number"] == 3)["title_fr"] == "Les clés du Mistral"

    # Every interlude past season three is named, and it ends by its promised date.
    run = 0
    for index, phase in enumerate(phases):
        run = run + 1 if phase == "interlude" else 0
        assert run <= INTERLUDE_BOUND, f"day {index + 1}: {run} days of interlude"
    named = [row for row in interludes if row]
    assert named, "season three has no successor authored: the interlude is named"
    for row in named:
        assert row["reason_fr"].startswith("Entre deux saisons : l'histoire reprend le")
        assert (date.fromisoformat(row["returns_on"]) - date.fromisoformat(row["since"])).days == 14
    last_named = max(index for index, row in enumerate(interludes) if row)
    assert last_named < LIFE_DAYS - 1 and seasons[last_named + 1] == seasons[last_named] + 1
    for index, row in enumerate(interludes):
        if row and (index + 1 == len(interludes) or not interludes[index + 1]):
            # The day the interlude closed is the day the next season began: on time.
            late = (date.fromisoformat(dates[index]) - date.fromisoformat(row["returns_on"])).days
            assert late <= engine.CHAPTER_MAX_SCENES, (row, dates[index])

    # Teasers: one per resolution when a row is open, grounded, never twice in 14 days.
    written = [row for row in teasers if row]
    assert len(written) >= LIFE_DAYS * 0.8
    for index, row in enumerate(written):
        assert row["ref"] and row["text_fr"] and row["character_id"]
        for earlier in written[max(0, index - 14): index]:
            gap = (date.fromisoformat(row["date"]) - date.fromisoformat(earlier["date"])).days
            if gap < engine.TEASER_WINDOW_DAYS:
                assert earlier["text_fr"] != row["text_fr"], (earlier, row)
                assert earlier["ref"] != row["ref"], (earlier, row)
    last = scenes_of(db_session, d)[-1]
    if teasers[-1]:
        assert last.script_payload["next_teaser_fr"] == teasers[-1]["text_fr"]
    thread = thread_of(db_session, d)
    assert int(thread.world_bible["season_number"]) == max(seasons)
