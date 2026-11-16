"""Red-thread design, slice 5: a contract day's page is shared between learners.

With ``STORY_SHARED_PAGES`` the page of a contract day is written without the life of
the learner it is written for, kept, and served to the next learner whose day gives
the writer the same input: no model call, their own words in its slots, and every
guard run on it in their own life. A page a guard refuses for them is not served to
them. Off, every page is written for its learner, as before.

Fake models only: nothing is spent.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.story_pool import StoryPoolPage
from app.services import living_story as engine
from app.services.season import clock as season_clock
from app.services.season import page_pool
from app.services.season.format import load_season
from tests import test_journey_end_to_end as support
from tests.test_day_contract_ending import (  # noqa: F401 - fixture
    _canape_season_day,
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


@pytest.fixture
def shared_on(monkeypatch, contract_on):  # noqa: F811
    monkeypatch.setattr(settings, "STORY_SHARED_PAGES", True, raising=False)


@pytest.fixture
def provider(season_on):  # noqa: F811
    # The scripted critic accepts: only a page the critic accepted is kept for others.
    season_on.critic_refusals_left = 0
    season_on.spoil_once = False
    return season_on


def _learner(assembled_client, db_session, *, cefr: str = "A1.2", camille: str = "f"):
    """A learner on the canapé day (g3.5), the four planned days before it played, and
    Camille as they chose in T1 (a life that has not chosen is dealt one by its seed)."""

    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"s1-pool-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr=cefr), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=_canape_season_day())
    thread = _thread(db_session, user.id)
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    season = dict(live.get(season_clock.SEASON_KEY) or {})
    staged = [beat.premise for beat in load_season("s1").gaps["g3"].days if beat.day < 5]
    season["premises"] = [*(season.get("premises") or []), *[{"gap": "g3", "premise": premise} for premise in staged]]
    season["flags"] = {**(season.get("flags") or {}), "s1.camille_gender": camille}
    thread.state = {**state, engine.STATE_KEY: {**live, season_clock.SEASON_KEY: season}}
    db_session.commit()
    return d, user


def _pages(db_session) -> list[StoryPoolPage]:
    db_session.expire_all()
    return list(db_session.scalars(select(StoryPoolPage).order_by(StoryPoolPage.created_at, StoryPoolPage.id)))


def _printed(assembled_client, d, journey) -> str:
    episodes = assembled_client.get(f"/api/v1/story-engine/episodes?journey_id={journey['id']}", headers=d.headers)
    return json.dumps(episodes.json(), ensure_ascii=False)


# --- the day without the life ------------------------------------------------------


def _context(**extra) -> dict:
    return {
        "control_language": "de",
        "level": "A1",
        "learner": {"address": "neutral"},
        "season": {"number": 1, "phase": "running", "chapters": 4, "completion": 0.3},
        "season_script": {
            "id": "s1",
            "position": {"segment": "g3"},
            "brief": {
                "today": {
                    "required_premise": {"id": "les_canapes"},
                    "contract": {"lead": {"id": "marin_leveque"}},
                    "callback": {"id": "evt-1", "text_fr": "Tu as cassé un verre."},
                },
                "page_rules": {
                    "checked": "…",
                    "chapter": {"open_new": True, "beat": "setup", "rule": "…", "retired_questions": ["Qui a cassé le verre ?"]},
                    "voices": {"speakers": ["marin_leveque"]},
                },
            },
        },
        "world": {"cast": [], "locations": [], "arcs": [{"id": "a"}], "suggested_arc": "a", "complication_card": "rain"},
        "relationships": {"marin_leveque": {"register": "tu", "closeness": 3}},
        "chapter": None,
        "chapter_shape": {"shape": "standard"},
        "recent_situations": [{"title_fr": "Le verre cassé"}],
        "events": [{"id": "evt-1", "summary_fr": "Tu as cassé un verre."}],
        "memory": {"learned": [{"text": "plays the cello"}]},
        "story_words": [{"lemma": "verre"}],
        "grammar_plan": {"units": ["passe_compose"]},
        "thread_id": "t-1",
        "revision": "r-1",
        "secrets": {"next": "marin_leveque"},
        **extra,
    }


def test_off_by_default_and_never_without_the_contract(monkeypatch):
    assert not page_pool.applies(_context())
    monkeypatch.setattr(settings, "STORY_SHARED_PAGES", True, raising=False)
    assert not page_pool.applies(_context())  # the contract flag is off


def test_a_shared_page_is_written_without_the_life(shared_on):
    context = _context()
    assert page_pool.applies(context)
    shared = page_pool.shareable(context)
    told = json.dumps(shared, ensure_ascii=False, default=str)
    for private in ("cassé", "cello", "passe_compose", "t-1", "r-1", "rain", "closeness"):
        assert private not in told, private
    assert shared["relationships"] == {"marin_leveque": {"register": "tu"}}
    assert shared["recent_situations"] == [] and shared["events"] == [] and shared["secrets"] == {}
    assert "memory" not in shared and "story_words" not in shared and "grammar_plan" not in shared
    # The learner's own context is untouched by the copy.
    assert context["world"]["complication_card"] == "rain" and context["recent_situations"]


def test_two_lives_on_the_same_day_share_a_frame_and_a_level_does_not(shared_on):
    one = _context()
    other = _context(
        thread_id="t-2",
        revision="r-2",
        events=[],
        recent_situations=[],
        memory=None,
        secrets={"next": "lila_bonnet"},
        relationships={"marin_leveque": {"register": "tu", "closeness": 0}},
    )
    key = page_pool.key_for(one, page_pool.shareable(one))
    assert key == page_pool.key_for(other, page_pool.shareable(other))
    assert key.day_key == "g3:les_canapes" and key.band == "A1" and key.language == "de"
    for change in ({"level": "B1"}, {"control_language": "en"}, {"relationships": {"marin_leveque": {"register": "vous"}}}):
        different = _context(**change)
        assert page_pool.key_for(different, page_pool.shareable(different)).frame_hash != key.frame_hash, change


@pytest.mark.parametrize("extra", [{"absence": {"days": 9}}, {"epreuve": {"can_do_ids": ["x"]}}, {"a_new_personal_input": [1]}])
def test_a_day_this_module_does_not_know_is_written_for_its_learner(shared_on, extra):
    assert not page_pool.applies(_context(**extra))


def test_the_engine_gives_no_key_the_pool_does_not_know(assembled_client, db_session, journey_enabled, clock, monkeypatch, shared_on):
    """Every key of a real generation context is classified: a new one is a decision."""

    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_SEASON_SCRIPT", "s1")
    _d, user = _learner(assembled_client, db_session)
    context = engine.story_context(db_session, user)
    engine.on_built_stage(context, keep=[])
    engine._add_director_context(db_session, user, context)
    assert page_pool.applies(context)


def test_a_kept_page_claims_nothing_about_a_life():
    kept = page_pool.sanitized({"title_fr": "Le menu", "callback_fr": "Tu as cassé un verre.", "callback_ref": "evt-1", "arc_id": "a", "secret_shift": "hinted"})
    assert kept["title_fr"] == "Le menu"
    assert kept["callback_fr"] == "" and kept["callback_ref"] is None and kept["arc_id"] is None and kept["secret_shift"] is None


# --- whole days ----------------------------------------------------------------------


@LANES
def test_the_second_learner_reads_the_page_the_first_one_paid_for(
    assembled_client, db_session, journey_enabled, clock, provider, shared_on, monkeypatch
):
    _reads(provider, monkeypatch, route=None, mark=None)
    first, _user = _learner(assembled_client, db_session)
    one = _play(first, provider, clock, "C'est quoi, un canapé ?")
    written = len(provider.director_contexts())
    assert written >= 1
    pages = _pages(db_session)
    assert [(page.day_key, page.band, page.served) for page in pages] == [("g3:les_canapes", "A1", 0)]

    second, user = _learner(assembled_client, db_session)
    two = _play(second, provider, clock, "Le petit bateau.")
    # No page was written for the second learner.
    assert len(provider.director_contexts()) == written
    assert [page.served for page in _pages(db_session)] == [1]
    scene = _latest_scene(db_session, user.id)
    assert (scene.script_payload or {}).get("season", {}).get("key") == "g3.5"
    assert one["id"] != two["id"]
    title = pages[0].draft["title_fr"]
    assert title in _printed(assembled_client, first, one) and title in _printed(assembled_client, second, two)


@LANES
def test_with_the_pool_off_every_page_is_written_for_its_learner(
    assembled_client, db_session, journey_enabled, clock, provider, contract_on, monkeypatch  # noqa: F811
):
    first, _ = _learner(assembled_client, db_session)
    _play(first, provider, clock, "Le petit bateau.")
    written = len(provider.director_contexts())
    second, _ = _learner(assembled_client, db_session)
    _play(second, provider, clock, "Le petit bateau.")
    assert len(provider.director_contexts()) > written
    assert _pages(db_session) == []


@LANES
@pytest.mark.parametrize("other", [{"cefr": "B1.1"}, {"camille": "m"}], ids=["level", "story-variant"])
def test_another_level_or_another_state_of_the_story_gets_its_own_page(
    assembled_client, db_session, journey_enabled, clock, provider, shared_on, monkeypatch, other
):
    first, _ = _learner(assembled_client, db_session)
    _play(first, provider, clock, "Le petit bateau.")
    written = len(provider.director_contexts())
    second, _ = _learner(assembled_client, db_session, **other)
    _play(second, provider, clock, "Le petit bateau.")
    assert len(provider.director_contexts()) > written
    pages = _pages(db_session)
    assert len(pages) == 2 and len({page.frame_hash for page in pages}) == 2
    assert sorted(page.band for page in pages) == (["A1", "B1"] if "cefr" in other else ["A1", "A1"])


@LANES
def test_a_page_a_guard_refuses_in_this_life_is_not_served_and_a_retired_one_never(
    assembled_client, db_session, journey_enabled, clock, provider, shared_on, monkeypatch
):
    first, _ = _learner(assembled_client, db_session)
    _play(first, provider, clock, "Le petit bateau.")
    page = _pages(db_session)[0]
    # The kept page names someone this world does not have: the guards refuse it.
    page.draft = {**page.draft, "character_id": "nobody"}
    db_session.commit()
    written = len(provider.director_contexts())
    second, _ = _learner(assembled_client, db_session)
    _play(second, provider, clock, "Le petit bateau.")
    assert len(provider.director_contexts()) > written
    pages = _pages(db_session)
    assert len(pages) == 2 and [row.served for row in pages] == [0, 0]

    assert page_pool.retire(db_session, pages[1].id, reason="owner: weak page")
    assert page_pool.retire(db_session, pages[0].id, reason="broken")
    db_session.commit()
    written = len(provider.director_contexts())
    third, _ = _learner(assembled_client, db_session)
    _play(third, provider, clock, "Le petit bateau.")
    assert len(provider.director_contexts()) > written
    assert len(_pages(db_session)) == 3


@LANES
def test_each_learner_reads_their_own_words_on_the_shared_page(
    assembled_client, db_session, journey_enabled, clock, provider, shared_on, monkeypatch
):
    """The eve of the party brings the canapé's name back. One page, two names."""

    read = provider.generate_chat_completion

    def writes_the_slot(messages, **kwargs):
        response = read(messages, **kwargs)
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] != "SceneDraft":
            return response
        today = ((data["data"].get("season_script") or {}).get("brief") or {}).get("today") or {}
        back = (today.get("contract") or {}).get("brings_back") or []
        if not back:
            return response
        value = json.loads(response.content)
        value["panels"][0]["narration_fr"] = f"Sur le menu : « {back[0]['slot']} »."
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", writes_the_slot)
    printed = {}
    for name in ("Le petit bateau", "La tour Eiffel"):
        seen = _reads(provider, monkeypatch, route="named", mark=name)
        d, user = _learner(assembled_client, db_session)
        _play(d, provider, clock, f"{name}.")
        _play(d, provider, clock, "Celle-là.")
        eve = _play(d, provider, clock, "Ça va, Margaux ?")
        assert (_latest_scene(db_session, user.id).script_payload or {}).get("season", {}).get("key") == "g3.7"
        printed[name] = _printed(assembled_client, d, eve)
        assert seen
        # The next learner starts on the same weekday: the gap has the same days left.
        clock.advance(days=4)
    assert "Sur le menu : « Le petit bateau »." in printed["Le petit bateau"]
    assert "Sur le menu : « La tour Eiffel »." in printed["La tour Eiffel"]
    assert "bateau" not in printed["La tour Eiffel"]
    eve_pages = [page for page in _pages(db_session) if page.day_key == "g3:tout_va_bien"]
    assert len(eve_pages) == 1 and eve_pages[0].served == 1
    # The pool keeps the slot, never a learner's words.
    assert "{g3.canape_name}" in json.dumps(eve_pages[0].draft, ensure_ascii=False)
    assert "bateau" not in json.dumps(eve_pages[0].draft, ensure_ascii=False)


@LANES
def test_a_page_served_over_the_critics_refusal_is_not_kept_for_others(
    assembled_client, db_session, journey_enabled, clock, season_on, shared_on, monkeypatch  # noqa: F811
):
    # The scripted critic refuses, the retry fails, and the day is served all the same
    # (the critic never costs a learner a day). Such a page stays that learner's own.
    season_on.critic_refusals_left = 5
    first, _ = _learner(assembled_client, db_session)
    _play(first, season_on, clock, "Le petit bateau.")
    assert _pages(db_session) == []


# --- the night's path: planned, then written (production) ------------------------------


def test_the_page_planned_and_written_at_night_is_shared_too(
    assembled_client, db_session, journey_enabled, clock, season_on, shared_on, monkeypatch  # noqa: F811
):
    from app.db.models.user import User
    from app.schemas.daily_journey import InputMode
    from app.services.season.admin import jump_to_day
    from tests.test_story_split import SplitProvider

    fake = SplitProvider()
    fake.critic_refusals_left = 0
    monkeypatch.setattr(engine, "_client", lambda: fake)
    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", True)

    def night_page():
        # g3.1, «Les petites cartes»: Lila asks, at the learner's flat.
        email = f"s1-pool-night-{uuid.uuid4()}@example.com"
        support.register(assembled_client, email, cefr="A2.1")
        user = db_session.scalar(select(User).where(User.email == email))
        jump_to_day(db_session, user, day=_canape_season_day() - 4)
        thread = _thread(db_session, user.id)
        state = dict(thread.state or {})
        live = dict(state.get(engine.STATE_KEY) or {})
        season = dict(live.get(season_clock.SEASON_KEY) or {})
        season["flags"] = {**(season.get("flags") or {}), "s1.camille_gender": "f"}
        thread.state = {**state, engine.STATE_KEY: {**live, season_clock.SEASON_KEY: season}}
        db_session.commit()
        with engine.written_ahead_of_time():
            brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
        db_session.commit()
        assert not isinstance(brief, engine.ContentUnavailable), brief
        return brief

    first = night_page()
    assert (first.story_context.get("season") or {}).get("position", {}).get("key") == "g3.1"
    schemas = [schema for schema, _ in fake.calls]
    assert schemas[:3] == ["PagePlan", "PageText", "PageAids"]
    planner = next(source for schema, source in fake.calls if schema == "PagePlan")
    # The planner plans the day without the life.
    assert "memory" not in planner and planner["recent_days"] == [] and planner["story_words"] is None
    assert planner["ledger"] == {"events": [], "commitments": [], "consequences": []}
    assert first.story_context["pool"]["served"] is False and first.story_context["pool"]["page"]

    calls = len(fake.calls)
    second = night_page()
    assert len(fake.calls) == calls, "nothing is planned or written for the second learner"
    assert second.story_context["pool"] == {"page": first.story_context["pool"]["page"], "served": True}
    assert second.story_context["draft"]["panels"] == first.story_context["draft"]["panels"]
    assert second.story_context["generation_usage"] == []
