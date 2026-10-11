"""WP-132B «Après la finale»: every finale branch reaches an authored ending, then an
honest continuation that carries the season — never strangers, never the Berlin
season, never a reset (content program D8; EXPERIENCE-REVIEW 2026-10-04 §6).

Three tiers:

* **always** — the routing module on its own: the archive day is bible text only,
  the carried state names the actual ending, a malformed epilogue is refused whole;
* **hooks** — the few lines in ``format.load_season``, ``runtime`` and
  ``living_story.generate_scene`` that call ``season/epilogue.py`` (the WP-132B
  report's patch). Skipped until they are applied;
* **proposal** — the authored epilogue week (``app/data/season/s1/epilogue.json``,
  owner approval, ``WP-132B-EPILOGUE-PROPOSAL.md``). Skipped while it is absent.
  With it present the hooks are required: a shipped epilogue that nothing serves
  must fail here, not pass silently.

Learners are put on the finale with ``season.admin.jump_to_day`` (day 58 = T8 A) and
play the days through the real journey with the season suite's scripted provider.
"""

from __future__ import annotations

import inspect
import json
import uuid
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.user import User
from app.services import living_story as engine
from app.services.season import epilogue as ep
from app.services.season import runtime as season_runtime
from app.services.season.clock import SEASON_KEY, nominal_calendar
from app.services.season.fidelity import fold
from app.services.season.flags import effective_flags
from app.services.season.format import SEASON_ROOT, Season, SeasonFormatError, load_season
from app.services.season.levels import iter_says, level_key, read_levels, read_tasks
from app.services.season.page import hook_caption, resolve_day
from app.services.season.reprise import REPRISE_SCENARIO_PREFIX
from tests import test_journey_end_to_end as support
from tests.test_season_one import _latest_scene, _thread, season_on  # noqa: F401 - fixture
from tests.walk_checks_wp132b import check_no_old_serial_season

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

S1 = SEASON_ROOT / "s1"
HAS_EPILOGUE = (S1 / ep.EPILOGUE_FILE).is_file()
GENERIC_KEYS = {"order_at_cafe", "arrange_meeting", "explain_delay"}
#: The flags that lead T7 B's decision to each ending (bible 00 §6, «What T7 B offers»).
ENDING_FLAGS = {
    "garder": {"s1.flat_decision": "keep", "s1.evidence_shared": "marchand_only", "s1.margaux_persuaded": True},
    "partager": {"s1.flat_decision": "coop", "s1.evidence_shared": "public", "s1.gus_persuaded": True},
    "laisser_partir": {"s1.flat_decision": "sell"},
}
FINALE_DAY = 58


def _hooks_wired() -> bool:
    from app.services.season import format as season_format

    return all(
        marker in inspect.getsource(fn)
        for fn, marker in (
            (season_format.load_season, "attach_epilogue"),
            (season_runtime.settle, "after_settle"),
            (season_runtime.context_block, "context_extra"),
            (season_runtime.today_for, "position_for"),
            (season_runtime.season_script_finished, "season_finished"),
            (engine.generate_scene, "season_end_brief"),
        )
    )


HOOKS = _hooks_wired()
needs_hooks = pytest.mark.skipif(not HOOKS, reason="WP-132B hooks not applied (see the WP-132B report's patch)")
needs_epilogue = pytest.mark.skipif(not HAS_EPILOGUE, reason="the WP-132B epilogue proposal is not applied")


@pytest.fixture
def no_epilogue(monkeypatch):
    """The season as it ends without an authored epilogue, whatever is on disk."""

    monkeypatch.setattr(ep, "read_epilogue", lambda folder, **_: None)
    load_season.cache_clear()
    yield
    load_season.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_season_cache():
    load_season.cache_clear()
    yield
    load_season.cache_clear()


def _bare_season() -> Season:
    """season.json alone: no tentpoles, no epilogue."""

    return Season.model_validate(json.loads((S1 / "season.json").read_text(encoding="utf-8")))


def _finished_state(season: Season, ending: str, *, upto: str = "t8") -> dict:
    played = []
    for row in nominal_calendar(season):
        played.append({**row, "flex": 0, "date": None, "event_id": f"x:{row['key']}"})
        if row["segment"] == upto and row["day_in_segment"] == 2:
            break
    return {"id": season.id, "played": played, "flags": dict(ENDING_FLAGS[ending]), "signals": []}


def _season_strings() -> str:
    """Every French string the season's own files carry, folded (bible + level variants)."""

    blobs: list[str] = []
    for path in sorted(S1.glob("t[0-9].json")) + [S1 / "season.json"]:
        blobs.append(json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False))
    levels = read_levels(S1)
    blobs.append(json.dumps(levels, ensure_ascii=False))
    return fold("\n".join(blobs).replace("\\n", " "))


# ---------------------------------------------------------------------------
# Always: the routing module on its own
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ending", list(ENDING_FLAGS))
def test_the_archive_day_is_the_learners_own_season_in_bible_lines(ending, no_epilogue):
    """Without an epilogue the season ends on one archive day: the eight «À suivre» of
    the learner's own branches, the season's question, and the finale's last caption
    as its ending. Every French line on it is already in the season files."""

    season = load_season("s1")
    state = _finished_state(season, ending)
    flags = effective_flags(season, state, seed="x")
    assert flags["s1.ending"] == ending
    page_model = ep.archive_page(season, flags, band="A2")
    assert page_model is not None
    joined = season.model_copy(update={"tentpoles": {**season.tentpoles, "end": page_model}})
    page = resolve_day(joined, "end", "b", flags=flags, band="A2", language="de")
    finale_b = resolve_day(season, "t8", "b", flags=flags, band="A2", language="de")
    assert hook_caption(page)["text_fr"] == hook_caption(finale_b)["text_fr"], "it ends on the finale's own caption"
    assert finale_b["variant"] == ending
    blob = _season_strings()
    said = [
        line["text_fr"]
        for movement in page["movements"]
        for panel in [movement.get("panel") or movement]
        for line in panel.get("lines") or []
    ]
    assert len(said) >= 8
    assert all(fold(text) in blob for text in said), [text for text in said if fold(text) not in blob]
    turns = [row for row in page["movements"] if row["kind"] == "turn"]
    assert len(turns) == 1 and turns[0]["task_native"] == ep.SEASON_END_TASK["de"]
    assert all(fold(example) in blob for reply in turns[0]["replies"] for example in reply["examples"])
    assert all(not reply["sets"] for reply in turns[0]["replies"]), "the archive day sets nothing"


@pytest.mark.parametrize("ending", list(ENDING_FLAGS))
def test_the_continuation_is_told_the_ending_this_life_chose(ending, no_epilogue):
    season = load_season("s1")
    state = _finished_state(season, ending)
    flags = effective_flags(season, state, seed="x")
    carried = ep.carried(season, state, flags, band="B1", language="fr")
    assert carried["ending"] == ending
    assert carried["painting"] == {"garder": "with_you", "partager": "with_gus", "laisser_partir": "lost"}[ending]
    assert carried["facts"][: len(ep.ENDING_FACTS[ending])] == list(ep.ENDING_FACTS[ending])
    assert any("Berlin" in rule and "second season" in rule for rule in carried["rules"])
    assert any("stranger" in rule for rule in carried["rules"])
    assert carried["closed_locations"] == (["le_mistral"] if ending == "laisser_partir" else [])
    finale_b = resolve_day(season, "t8", "b", flags=flags, band="B1", language="fr")
    assert carried["last_page"]["text_fr"] == hook_caption(finale_b)["text_fr"]
    assert carried["last_page"]["key"] == "t8.b"


def test_relationships_and_open_threads_are_carried(no_epilogue):
    season = load_season("s1")
    state = _finished_state(season, "garder")
    state["flags"].update({"marchand.sundays": True, "s1.lila_has_key": True, "romy.footage": "kept"})
    state["signals"] = [{"gate": 1, "signal": "romance"}, {"gate": 4, "signal": "romance"}]
    flags = effective_flags(season, state, seed="x")
    carried = ep.carried(season, state, flags, band="A2", language="en")
    assert carried["lila_path"] == "romance" and carried["lila_key"] == "kept_by_lila"
    assert carried["marchand_sundays"] is True and carried["camille"]["register"] == "vous"
    assert any("46 bus" in fact for fact in carried["facts"])
    assert any("memory card" in fact for fact in carried["facts"])
    assert carried["open_question"].startswith("Who is «L.»")


def test_carrying_the_ending_seeds_the_written_and_the_reprise_seasons(no_epilogue):
    """The continuation's material is the learner's own ending: ``world_flags`` and
    an open thread in the words of the last page (D8: «a real arc»)."""

    from app.services import season_writer
    from app.services.season.world import season_world_bible

    season = load_season("s1")
    live = {SEASON_KEY: _finished_state(season, "partager")}
    carried = ep.carry_into_live(live, season=season)
    assert carried["world_flags"]["s1.ending"] == "partager"
    assert carried["world_flags"]["s1.painting"] == "with_gus"
    row = next(item for item in carried["threads_archive"] if item["key"] == "s1.open_question")
    assert row["state"] == "open" and "À suivre" not in row["text_fr"] and "Gus" in row["text_fr"]
    assert ep.carry_into_live(carried, season=season) == carried, "once per season"
    world = season_world_bible("s1")
    material = season_writer.season_material(carried, world)
    assert any(item["id"] == "thread:s1.open_question" for item in material)
    reprise = season_writer.reprise_season(live=carried, world=world, next_season=2, seed="x")
    assert any(arc["grounded_in"] == "thread:s1.open_question" for arc in reprise["season_arcs"]), reprise["season_arcs"]


def test_a_season_not_yet_finished_carries_nothing(no_epilogue):
    season = load_season("s1")
    state = _finished_state(season, "garder", upto="t7")
    live = {SEASON_KEY: state}
    assert ep.carry_into_live(live, season=season) == live
    assert ep.phase(season, state) == "season"


def test_phases_after_the_finale(no_epilogue):
    season = load_season("s1")
    state = _finished_state(season, "garder")
    assert ep.phase(season, state) == "season_end"
    assert ep.season_finished(season, state)
    state[ep.END_KEY] = {"on": "2026-01-09", "event_id": "x", "via": "season_end"}
    assert ep.phase(season, state) == "continuation"


def test_a_season_closed_before_an_epilogue_shipped_stays_closed():
    """A learner already in the continuation is never pulled back to the morning after
    the train when an epilogue ships later."""

    season = load_season("s1")
    if not ep.has_epilogue(season):
        epilogue = ep.EpilogueFile.model_validate(_minimal_epilogue())
        season = ep.with_epilogue(season, epilogue)
    state = _finished_state(season, "garder")
    assert ep.position_for(season, state, today=None).segment.id == ep.epilogue_ids(season)[0]
    state[ep.END_KEY] = {"on": "2026-01-09", "event_id": "x", "via": "season_end"}
    assert ep.position_for(season, state, today=None).finished
    assert ep.phase(season, state) == "continuation"


def _minimal_epilogue(endings=("garder", "partager", "laisser_partir")) -> dict:
    """A structurally whole one-page epilogue (test text, never served)."""

    def day(letter, ending):
        return {
            "day": letter,
            "variant": ending,
            "when": {"s1.ending": ending},
            "story_date_fr": "samedi 9 janvier",
            "location_id": "le_mistral",
            "movements": [
                {
                    "kind": "turn",
                    "id": f"x.{letter}.{ending}",
                    "to": "margaux_barman",
                    "panel": {"kind": "panel", "id": f"x.{letter}.{ending}.p", "lines": [{"who": "margaux_barman", "say": {"a2": "La même chose ?"}}]},
                    "task": {"en": "x", "de": "x", "fr": "x"},
                    "listens_for": "x",
                    "replies": [{"id": "a", "label": "x", "means": "x"}],
                    "fallback": "a",
                },
                {"kind": "hook", "id": f"x.{letter}.{ending}.h", "role": "midpoint", "panel": {"kind": "panel", "id": f"x.{letter}.{ending}.hp"}},
            ],
        }

    return {
        "id": "test",
        "title_fr": "Test",
        "segments": [{"id": "e1", "kind": "tentpole", "days": 2}],
        "pages": [{"id": "e1", "number": 9, "title_fr": "Test", "days": [day(letter, ending) for ending in endings for letter in ("a", "b")]}],
    }


def test_an_epilogue_that_leaves_an_ending_without_a_day_is_refused_whole(tmp_path, caplog):
    season = _bare_season()
    whole = ep.EpilogueFile.model_validate(_minimal_epilogue())
    assert ep.epilogue_problems(season, whole) == []
    partial = ep.EpilogueFile.model_validate(_minimal_epilogue(endings=("garder", "partager")))
    problems = ep.epilogue_problems(season, partial)
    assert any("no day for ending laisser_partir" in problem for problem in problems)
    folder = tmp_path / "s1"
    folder.mkdir()
    (folder / ep.EPILOGUE_FILE).write_text(json.dumps(_minimal_epilogue(endings=("garder",))), encoding="utf-8")
    assert ep.attach_epilogue(season, folder, levels={}, tasks={}) is season
    (folder / ep.EPILOGUE_FILE).write_text("{ not json", encoding="utf-8")
    with pytest.raises(SeasonFormatError):
        ep.read_epilogue(folder, levels={}, tasks={})
    assert ep.attach_epilogue(season, folder, levels={}, tasks={}) is season
    (folder / ep.EPILOGUE_FILE).write_text(json.dumps(_minimal_epilogue()), encoding="utf-8")
    attached = ep.attach_epilogue(season, folder, levels={}, tasks={})
    assert [segment.id for segment in attached.segments][-1] == "e1" and "e1" in attached.tentpoles
    assert attached.total_days == season.total_days + 2


def test_season_check_reports_on_the_epilogue_like_a_tentpole():
    import importlib.util

    spec = importlib.util.spec_from_file_location("season_check", Path(__file__).resolve().parents[1] / "scripts" / "season_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problems = module.check_epilogue("s1")
    if HAS_EPILOGUE:
        assert problems == []
    else:
        assert problems and "does not exist" in problems[0]


# ---------------------------------------------------------------------------
# Hooks: the season ends without an epilogue
# ---------------------------------------------------------------------------


def _learner(client, db, *, cefr: str):
    email = f"wp132b-{uuid.uuid4()}@example.com"
    driver = support.Driver(client, support.register(client, email, cefr=cefr), db=db)
    return driver, db.scalar(select(User).where(User.email == email))


def _day(driver, provider, clock, answer: str = "Je ne sais pas.") -> dict:
    driver.create()
    journey = driver.journey
    assert journey["status"] == "active", journey
    driver.play(answer=answer)
    response = driver.finish("complete")
    assert response.status_code == 200, response.text
    clock.advance(days=1)
    return journey


def _live(db, user_id) -> dict:
    return deepcopy(dict((_thread(db, user_id).state or {}).get(engine.STATE_KEY) or {}))


def _season_payload(db, user_id) -> tuple[dict, dict]:
    scene = _latest_scene(db, user_id)
    payload = dict(scene.script_payload or {}) if scene else {}
    return dict(payload.get("season") or {}), dict(payload.get("season_page") or {})


def _assert_in_season_world(db, user_id, journey: dict) -> None:
    world = _thread(db, user_id).world_bible
    assert world.get("season_script") == "s1", "never the old serial's world"
    assert world.get("season_title_fr") not in {"Choisir Paris", "Les clés du Mistral"}
    assert not {arc.get("id") for arc in world.get("season_arcs") or []} & {"lila_berlin_opening", "romy_montreal_deadline"}
    assert (journey.get("scenario") or {}).get("scenario_key") not in GENERIC_KEYS


@needs_hooks
@pytest.mark.parametrize("ending", list(ENDING_FLAGS))
def test_without_an_epilogue_the_finale_is_followed_by_one_archive_day_then_the_continuation(
    ending, assembled_client, db_session, journey_enabled, clock, season_on, no_epilogue  # noqa: F811
):
    from app.services.season.admin import jump_to_day

    provider = season_on
    driver, user = _learner(assembled_client, db_session, cefr="A2.1")
    jump_to_day(db_session, user, day=FINALE_DAY, flags=ENDING_FLAGS[ending])
    db_session.commit()
    for key in ("t8.a", "t8.b"):
        _day(driver, provider, clock)
        assert _season_payload(db_session, user.id)[0]["key"] == key
    before = len(provider.director_contexts())
    journey = _day(driver, provider, clock, "Je garde le café dans mon cœur.")
    season, page = _season_payload(db_session, user.id)
    assert season["key"] == "end.b" and season["kind"] == "tentpole"
    assert len(provider.director_contexts()) == before, "the archive day needs no model"
    assert journey["scenario"]["title_fr"] == "La clé d'Odile"
    assert page["variant"] is None and len([row for row in page["movements"] if row["kind"] == "panel"]) == 7
    live = _live(db_session, user.id)
    state = live[SEASON_KEY]
    assert state[ep.END_KEY]["via"] == "season_end"
    assert [row["key"] for row in state["played"]][-1] == "t8.b", "the archive day is not a season day"
    assert live["world_flags"]["s1.ending"] == ending
    assert any(row["key"] == "s1.open_question" for row in live["threads_archive"])
    _assert_in_season_world(db_session, user.id, journey)
    # The next day is the continuation: generated, told the ending.
    journey = _day(driver, provider, clock)
    contexts = provider.director_contexts()
    assert len(contexts) > before
    carried = contexts[-1]["season_script"][ep.CARRIED_KEY]
    assert carried["ending"] == ending and carried["ended"]["via"] == "season_end"
    assert contexts[-1]["season_script"]["phase"] == "continuation"
    _assert_in_season_world(db_session, user.id, journey)
    # And it stays the continuation: no second archive day.
    journey = _day(driver, provider, clock)
    assert _season_payload(db_session, user.id)[0].get("key") != "end.b"
    _assert_in_season_world(db_session, user.id, journey)


def _director_fails(provider, monkeypatch) -> None:
    original = provider.generate_chat_completion

    def refused(messages, **kwargs):
        if json.loads(messages[0]["content"])["output_schema"]["title"] == "SceneDraft":
            raise engine.StoryUnavailable("provider down")
        return original(messages, **kwargs)

    monkeypatch.setattr(provider, "generate_chat_completion", refused)


@needs_hooks
def test_provider_off_after_the_season_ended_rereads_the_finale_never_strangers(
    assembled_client, db_session, journey_enabled, clock, season_on, no_epilogue, monkeypatch  # noqa: F811
):
    from app.services.season.admin import jump_to_day

    provider = season_on
    driver, user = _learner(assembled_client, db_session, cefr="A1.1")
    jump_to_day(db_session, user, day=FINALE_DAY, flags=ENDING_FLAGS["laisser_partir"])
    db_session.commit()
    for _ in range(3):  # T8 A, T8 B, the archive day
        _day(driver, provider, clock)
    before = _live(db_session, user.id)[SEASON_KEY]
    _director_fails(provider, monkeypatch)
    for _ in range(2):
        journey = _day(driver, provider, clock)
        assert journey["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}t8.b"
        _assert_in_season_world(db_session, user.id, journey)
    assert _live(db_session, user.id)[SEASON_KEY] == before, "nothing moved, nothing reset"


# ---------------------------------------------------------------------------
# Proposal: the epilogue week, every branch, three levels
# ---------------------------------------------------------------------------

EPILOGUE_KEYS = ["e1.a", "e1.b", "e2.a", "e2.b", "e3.a", "e3.b"]
BANDS = {"A1": "A1.1", "B1": "B1.1", "C1": "C1.1"}


def _variant(text_fr: str, band: str) -> str | None:
    """Which written level of the epilogue a served line is."""

    levels = read_levels(S1)["lines"]
    raw = json.loads((S1 / ep.EPILOGUE_FILE).read_text(encoding="utf-8"))
    for say in iter_says(raw):
        row = levels.get(level_key(say["a2"], say.get("b1"))) or {}
        for field in ("a1", "b2", "c1"):
            if fold(row.get(field) or "") == fold(text_fr):
                return field
        if fold(say["a2"]) == fold(text_fr):
            return "a2"
    return None


@needs_epilogue
def test_the_epilogue_file_holds_together_with_the_hooks():
    assert HOOKS, "an epilogue is on disk but nothing serves it: apply the WP-132B hooks"
    season = load_season("s1")
    assert ep.epilogue_ids(season) == ["e1", "e2", "e3"]
    assert [segment.id for segment in season.segments][-4:] == ["t8", "e1", "e2", "e3"]
    epilogue = ep.read_epilogue(S1, levels=read_levels(S1), tasks=read_tasks(S1))
    assert ep.epilogue_problems(_bare_season(), epilogue) == []


@needs_epilogue
@needs_hooks
@pytest.mark.parametrize("band", list(BANDS))
@pytest.mark.parametrize("ending", list(ENDING_FLAGS))
def test_each_finale_branch_plays_its_epilogue_week(
    ending, band, assembled_client, db_session, journey_enabled, clock, season_on  # noqa: F811
):
    """From T8 A, a learner of each ending plays the finale and the six epilogue days at
    their own level, then meets the continuation: generated, in s1's world, told the
    ending they chose."""

    from app.services.season.admin import jump_to_day

    provider = season_on
    provider.routes = {"Je reste à Paris.": "stay"}
    driver, user = _learner(assembled_client, db_session, cefr=BANDS[band])
    flags = {**ENDING_FLAGS[ending], **({"marchand.sundays": True} if ending == "garder" else {})}
    jump_to_day(db_session, user, day=FINALE_DAY, flags=flags)
    db_session.commit()
    for key in ("t8.a", "t8.b"):
        _day(driver, provider, clock)
        assert _season_payload(db_session, user.id)[0]["key"] == key
    before = len(provider.director_contexts())
    served: dict[str, dict] = {}
    for key in EPILOGUE_KEYS:
        answer = "Je reste à Paris." if key == "e3.b" else "Je ne sais pas."
        journey = _day(driver, provider, clock, answer)
        season, page = _season_payload(db_session, user.id)
        assert season["key"] == key and season["kind"] == "tentpole", (key, season)
        assert page["band"] == band
        served[key] = page
        _assert_in_season_world(db_session, user.id, journey)
        assert check_no_old_serial_season({"scenario": journey.get("scenario") or {}, "events": []}) == []
    assert len(provider.director_contexts()) == before, "the epilogue is authored: no model writes it"
    # Each ending reads its own branch where the epilogue branches.
    for key in ("e1.a", "e2.a"):
        assert served[key]["variant"] == ending
    lines = [
        line["text_fr"]
        for page in served.values()
        for movement in page["movements"]
        for panel in [movement.get("panel") or movement]
        for line in panel.get("lines") or []
    ]
    joined = " ".join(lines)
    if ending == "garder":
        assert "bus 46" in joined, "Marchand's Sundays carried"
    if ending == "partager":
        assert any(m.get("to") == "augustin_de_roncourt" for m in served["e1.a"]["movements"]), "Gus has the painting"
    if ending == "laisser_partir":
        assert any(line.get("who") == "dealer" for m in served["e2.a"]["movements"] for line in m.get("lines") or []), "the painting went to the dealer"
    # Lines are served at the learner's level.
    want = {"A1": "a1", "B1": "a2", "C1": "c1"}[band]
    levels = [_variant(text, band) for text in lines]
    assert levels.count(want) >= len(levels) // 3, (band, levels)
    if band == "A1":
        natives = [
            line.get("text_native")
            for page in served.values()
            for movement in page["movements"]
            for panel in [movement.get("panel") or movement]
            for line in panel.get("lines") or []
        ]
        assert all(natives), "A1: every epilogue line comes with its translation"
    live = _live(db_session, user.id)
    state = live[SEASON_KEY]
    assert state[ep.END_KEY]["via"] == "epilogue"
    assert state["flags"].get("user.stays") == "stays" and state["flags"].get("user.return_ticket") == "cancelled"
    assert live["world_flags"]["s1.ending"] == ending
    row = next(item for item in live["threads_archive"] if item["key"] == "s1.open_question")
    assert "Lancry" in row["text_fr"], "the open question is the epilogue's last page"
    # The continuation: generated, told the ending and the choices, never an archive day.
    journey = _day(driver, provider, clock)
    assert len(provider.director_contexts()) > before
    block = provider.director_contexts()[-1]["season_script"]
    assert block[ep.CARRIED_KEY]["ending"] == ending
    assert block[ep.CARRIED_KEY]["last_page"]["key"] == "e3.b"
    assert block["phase"] == "continuation"
    assert _season_payload(db_session, user.id)[0].get("key") != "end.b"
    _assert_in_season_world(db_session, user.id, journey)


@needs_epilogue
@needs_hooks
def test_provider_off_after_the_epilogue_rereads_its_last_page(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    from app.services.season.admin import jump_to_day

    provider = season_on
    driver, user = _learner(assembled_client, db_session, cefr="A1.1")
    jump_to_day(db_session, user, day=FINALE_DAY + 2, flags=ENDING_FLAGS["partager"])
    db_session.commit()
    for _ in EPILOGUE_KEYS:
        _day(driver, provider, clock)
    before = _live(db_session, user.id)[SEASON_KEY]
    assert before[ep.END_KEY]["via"] == "epilogue"
    _director_fails(provider, monkeypatch)
    journey = _day(driver, provider, clock)
    assert journey["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}e3.b"
    _assert_in_season_world(db_session, user.id, journey)
    assert _live(db_session, user.id)[SEASON_KEY] == before


@needs_epilogue
@needs_hooks
def test_a_lost_epilogue_day_rereads_the_previous_page_and_the_epilogue_resumes(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    """An epilogue page that cannot be served (a broken page, the provider down) is
    re-read from the last page; the epilogue does not move and resumes the next day."""

    from app.services.season.admin import jump_to_day

    provider = season_on
    driver, user = _learner(assembled_client, db_session, cefr="B1.1")
    jump_to_day(db_session, user, day=FINALE_DAY + 2, flags=ENDING_FLAGS["garder"])
    db_session.commit()
    _day(driver, provider, clock)  # e1.a
    with monkeypatch.context() as broken:
        broken.setattr(season_runtime, "tentpole_brief", lambda today, context: None)
        _director_fails(provider, broken)
        journey = _day(driver, provider, clock)
    assert journey["scenario"]["scenario_key"] == f"{REPRISE_SCENARIO_PREFIX}e1.a"
    _day(driver, provider, clock)
    assert _season_payload(db_session, user.id)[0]["key"] == "e1.b"



# ---------------------------------------------------------------------------
# The walk check
# ---------------------------------------------------------------------------


def _transcript(title: str, line: str) -> dict:
    return {
        "day": 61,
        "scenario": {"scenario_key": "story_x", "title_fr": title},
        "events": [{"step": {"kind": "scene", "prompt": {"panels": [{"narration_fr": "", "dialogue": [{"text_fr": line}]}]}}}],
    }


def test_the_walk_check_fires_on_the_old_serials_later_seasons_and_only_then():
    from tests.walk_checks_wp132b import old_season_markers

    assert "choisir paris" in old_season_markers()
    assert check_no_old_serial_season(_transcript("Choisir Paris", "Bonjour.")) != []
    tiago = next(marker for marker in old_season_markers() if marker == "tiago")
    assert check_no_old_serial_season(_transcript("Le quartier", f"{tiago.title()} arrive au café.")) != []
    good = _transcript("Le premier matin", "Berlin : il pleut. Comme à Paris. Et toi, ça va ?")
    assert check_no_old_serial_season(good) == []
