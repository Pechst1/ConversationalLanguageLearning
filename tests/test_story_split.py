"""Story plan, Phase 2: a season's generated day written ahead of time is planned, then
written, then given its reading aids (``app/services/story_split.py``)."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.services import living_story as engine
from app.services import story_split
from app.services.journey_contracts import InputMode
from tests import test_journey_end_to_end as support
from tests.test_season_one import SeasonProvider, season_on  # noqa: F401 - fixture

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


class SplitProvider(SeasonProvider):
    """The season fake, answering the planner, the author and the aids."""

    def __init__(self) -> None:
        super().__init__()
        self.plans: list[dict] = []
        self.stranger_once = False
        self.text_misses_once = False

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        source = data["data"]
        if schema not in ("PagePlan", "PageText", "PageAids"):
            return super().generate_chat_completion(messages, **kwargs)
        self.calls.append((schema, deepcopy(source)))
        value = {"PagePlan": self._plan, "PageText": self._text, "PageAids": self._aids}[schema](source)
        return SimpleNamespace(content=json.dumps(value, ensure_ascii=False), model="fake-split", provider="test", total_tokens=30, cost=0.0)

    def _plan(self, source: dict) -> dict:
        today = source["brief"]["today"]
        premise = today.get("required_premise") or (today.get("premises") or [{}])[0]
        lead = "lila_bonnet"
        if (source.get("avoid") or {}).get("character_id") == lead:
            lead = "marin_leveque"
        cast = [lead, "marin_leveque" if lead != "marin_leveque" else "lila_bonnet"]
        if source["brief"].get("shape") == "two_hander":
            cast = [lead]
        if self.stranger_once:
            self.stranger_once = False
            cast = [lead, "odile"]
        n = len(self.plans)
        plan = {
            "premise_id": premise.get("id"),
            "location_id": "user_apartment",
            "cast": cast,
            "lead_id": lead,
            "beats": ["Lila opens the box.", "Marin finds his own Polaroid.", "Lila puts it aside."],
            "change": {"before": "The box is closed.", "after": "The box is open."},
            "question": "Who do you think this caption is about?",
            "task": "Lila wants to know who the caption is about.",
            "replies": [{"gist": "a name", "intent": "other", "then": "Lila laughs"}],
            "hook": "Marin wants to ask something.",
            "chapter": {"question": "What does the box hold?", "developments": ["Photos.", "Letters."]}
            if source["brief"]["chapter"]["open_new"]
            else None,
            "threads": ["The Polaroid box"],
            "small_moment_id": None,
            "complication": None,
            "callback_id": None,
            "learner_agency": None,
            "novelty_key": f"la-boite-{n}",
            "problem_key": "polaroid_box",
        }
        self.plans.append(plan)
        return plan

    def _text(self, source: dict) -> dict:
        lead = source["plan"]["lead_id"]
        if self.text_misses_once:
            # Measured run 2026-10-16: a page that ended after its panels.
            self.text_misses_once = False
            return {"title_fr": "La boîte", "premise_fr": "Une boîte.", "panels": [
                {"visual_direction": "A box.", "narration_fr": "Une boîte.", "dialogue": []},
                {"visual_direction": "A hand.", "narration_fr": "Une main.", "dialogue": []},
            ]}
        return {
            "title_fr": "La boîte",
            "premise_fr": "Une boîte de photos sous le lit d'Odile.",
            "panels": [
                {"visual_direction": "A box under a bed.", "narration_fr": "Sous le lit, une boîte.", "dialogue": []},
                {"visual_direction": "Lila opens the box.", "narration_fr": "", "dialogue": [{"character_id": lead, "text_fr": "Soixante photos. Au moins.", "mood": "happy"}]},
                {"visual_direction": "Marin holds a Polaroid.", "narration_fr": "Marin se tait.", "dialogue": []},
                {"visual_direction": "Lila turns to Toi.", "narration_fr": "", "dialogue": [{"character_id": lead, "text_fr": "Regarde celle-là.", "mood": "neutral"}]},
            ],
            "opening_line_fr": "C'est qui, à ton avis ?",
            "suggested_response_fr": "C'est Marin.",
            "hook_fr": "Marin veut te demander quelque chose.",
            "chapter_title_fr": "La boîte" if source["plan"]["chapter"] else None,
            "chapter_question_fr": "Qu'est-ce qu'il y a dans la boîte ?" if source["plan"]["chapter"] else None,
        }

    def _aids(self, source: dict) -> dict:
        panels = source["page"]["panels"]
        return {
            "setup_native": "A box of photos under Odile's bed.",
            "translation_native": "Who is it, do you think?",
            "hint_native": "Say who you think it is.",
            "alt_native": ["A box under a bed."] * len(panels),
            "lines_native": [["A line."] * len(panel["dialogue"]) for panel in panels],
            "lexicon": [],
            "can_do_id": None,
        }


@pytest.fixture
def split_on(season_on, monkeypatch):  # noqa: F811 - the fixture above
    fake = SplitProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", True)
    return fake


def _learner_on_gap_day(assembled_client, db_session, day: int = 14):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"split-{uuid.uuid4()}@example.com"
    support.register(assembled_client, email, cefr="A2.1")
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=day)
    db_session.commit()
    return user


def _schemas(provider) -> list[str]:
    return [schema for schema, _ in provider.calls]


def test_a_page_written_ahead_of_time_is_planned_then_written_then_aided(assembled_client, db_session, journey_enabled, clock, split_on):
    split_on.critic_refusals_left = 0
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(brief, engine.ContentUnavailable), brief
    schemas = _schemas(split_on)
    assert schemas[:3] == ["PagePlan", "PageText", "PageAids"]
    assert "SceneDraft" not in schemas, "the one-call director is not asked"
    assert brief.objective_native == "Lila wants to know who the caption is about."
    season = brief.story_context.get("season") or {}
    assert (season.get("position") or {}).get("key") == "g2.5"


def test_a_page_the_story_critic_refuses_buys_a_new_plan(assembled_client, db_session, journey_enabled, clock, split_on):
    assert split_on.critic_refusals_left == 1, "the fake critic refuses the first page"
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(brief, engine.ContentUnavailable), brief
    schemas = [schema for schema in _schemas(split_on) if schema != "StoryReview"]
    assert schemas == ["PagePlan", "PageText", "PageAids"] * 2
    second = [payload for schema, payload in split_on.calls if schema == "PagePlan"][1]
    assert "Nothing changes by the end of the day." in second["previous_rejections"]


def test_the_author_never_reads_a_secret_or_the_gap_s_forbidden_list(assembled_client, db_session, journey_enabled, clock, split_on):
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    planner = next(payload for schema, payload in split_on.calls if schema == "PagePlan")
    author = next(payload for schema, payload in split_on.calls if schema == "PageText")
    assert any(card.get("secret") for card in planner["cast"]), "the planner knows the secrets"
    assert planner["brief"]["gap"]["must_not"], "the planner knows what is kept for later"
    text = json.dumps(author, ensure_ascii=False)
    assert "Berlin" not in text and "must_not" not in text and '"secret"' not in text
    assert {card["id"] for card in author["cast"]} == set(author["plan"]["cast"])


def test_a_plan_with_someone_who_cannot_speak_costs_only_a_new_plan(assembled_client, db_session, journey_enabled, clock, split_on):
    split_on.stranger_once = True
    split_on.critic_refusals_left = 0
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(brief, engine.ContentUnavailable), brief
    schemas = _schemas(split_on)
    assert schemas[:4] == ["PagePlan", "PagePlan", "PageText", "PageAids"], "no French was paid for the bad plan"
    second = [payload for schema, payload in split_on.calls if schema == "PagePlan"][1]
    assert any("odile" in hint for hint in second["previous_rejections"])


def test_a_page_text_that_misses_a_field_is_asked_again_on_the_same_plan(assembled_client, db_session, journey_enabled, clock, split_on):
    split_on.text_misses_once = True
    split_on.critic_refusals_left = 0
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert not isinstance(brief, engine.ContentUnavailable), brief
    assert _schemas(split_on)[:4] == ["PagePlan", "PageText", "PageText", "PageAids"], "one plan, two pages"
    second = [payload for schema, payload in split_on.calls if schema == "PageText"][1]
    assert any("opening_line_fr" in hint for hint in second["previous_rejections"])


def test_a_live_page_keeps_the_one_call_director(assembled_client, db_session, journey_enabled, clock, split_on):
    user = _learner_on_gap_day(assembled_client, db_session)
    engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    schemas = _schemas(split_on)
    assert "SceneDraft" in schemas and "PagePlan" not in schemas


def test_with_the_setting_off_the_overnight_page_keeps_the_one_call_director(assembled_client, db_session, journey_enabled, clock, split_on, monkeypatch):
    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", False)
    user = _learner_on_gap_day(assembled_client, db_session)
    with engine.written_ahead_of_time():
        engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT)
    assert "PagePlan" not in _schemas(split_on)


# -- the plan's guards and the assembly, without a model -----------------------------


def _context(**brief_today) -> dict:
    return {
        "level": "A2",
        "control_language": "en",
        "world": {
            "cast": [{"id": "lila_bonnet", "name": "Lila Bonnet"}, {"id": "marin_leveque", "name": "Marin Lévêque"}],
            "locations": [{"id": "le_mistral", "name": "Le Mistral"}, {"id": "user_apartment", "name": "L'appartement"}],
        },
        "season_script": {
            "brief": {
                "gap": {"id": "g2"},
                "today": {"required_premise": None, **brief_today},
                "page_rules": {"voices": {"speakers": ["lila_bonnet", "marin_leveque"]}, "chapter": {"open_new": False}},
            }
        },
        "chapter": {"title_fr": "La boîte", "dramatic_question": "Qu'y a-t-il dedans ?", "possible_developments": ["a", "b"]},
        "recent_situations": [{"objective_native": "Marin asks if he may use Odile's plan.", "character_id": "marin_leveque", "location_id": "le_mistral"}],
        "variety": {"must_change": {"character_id": "marin_leveque", "location_id": "le_mistral"}},
    }


def _plan(**changes) -> story_split.PagePlan:
    return story_split.PagePlan.model_validate(
        {
            "premise_id": None,
            "location_id": "user_apartment",
            "cast": ["lila_bonnet"],
            "lead_id": "lila_bonnet",
            "beats": ["One.", "Two."],
            "change": {"before": "Closed.", "after": "Open."},
            "question": "Who is it?",
            "task": "Lila wants to know who it is.",
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes, context_today, words",
    [
        ({"cast": ["lila_bonnet", "odile"]}, {}, "odile"),
        ({"location_id": "berlin"}, {}, "berlin"),
        ({}, {"required_premise": {"id": "la_boite", "title_fr": "La boîte"}}, "La boîte"),
        ({"task": "Lila wants to know who it is and why and when and where today."}, {}, "12"),
        ({"lead_id": "marin_leveque", "cast": ["marin_leveque"], "location_id": "le_mistral"}, {}, "carried the last days"),
        ({"task": "Marin asks if he may use Odile's plan."}, {}, "already asked"),
    ],
)
def test_a_plan_that_breaks_a_rule_is_refused_with_the_reason(changes, context_today, words):
    issue = story_split.plan_issue(_plan(**changes), _context(**context_today))
    assert issue and words in issue


def test_a_two_hander_plan_leaves_everyone_but_the_lead_off_the_page():
    """Measured run 2026-10-16: g2.2 was lost to two_hander_crowded after the plan put two
    people on a two-hander's page."""

    context = {**_context(), "chapter": {**_context()["chapter"], "shape": "two_hander"}}
    crowded = _plan(cast=["lila_bonnet", "marin_leveque"])
    issue = story_split.plan_issue(crowded, context)
    assert issue and "two-hander" in issue and "marin_leveque" in issue
    assert story_split.plan_issue(_plan(), context) is None
    assert story_split.plan_issue(crowded, _context()) is None, "a standard chapter may hold two"
    assert story_split.planner_payload(context, [])["brief"]["shape"] == "two_hander"


def test_a_plan_that_keeps_the_rules_passes():
    assert story_split.plan_issue(_plan(), _context()) is None


def test_the_page_is_assembled_into_the_director_s_draft_and_keeps_the_open_chapter():
    context = _context()
    text = story_split.PageText.model_validate(
        {
            "title_fr": "La boîte",
            "premise_fr": "Une boîte.",
            "panels": [
                {"visual_direction": "A box.", "dialogue": []},
                {"visual_direction": "Lila.", "dialogue": [{"character_id": "lila_bonnet", "text_fr": "Regarde."}]},
            ],
            "opening_line_fr": "C'est qui ?",
            "suggested_response_fr": "C'est Marin.",
            "hook_fr": "Demain, Marin.",
        }
    )
    aids = story_split.PageAids(alt_native=["A box.", "Lila."], lines_native=[[], ["Look."]], hint_native="Say a name.")
    draft = engine.SceneDraft.model_validate(story_split.assemble(context, _plan(premise_id="la_boite"), text, aids))
    assert draft.chapter.dramatic_question == "Qu'y a-t-il dedans ?", "the open chapter goes on verbatim"
    assert draft.objective_native == "Lila wants to know who it is."
    assert draft.panels[1].dialogue[0].text_native == "Look."
    assert draft.season_checklist.premise_id == "la_boite"
    assert draft.season_checklist.hook_fr == "Demain, Marin."
    assert draft.hint_native == "Say a name."


def test_a_new_chapter_needs_the_author_s_title_and_question():
    context = _context()
    context["chapter"] = {}
    text = story_split.PageText.model_validate(
        {
            "title_fr": "T",
            "premise_fr": "P.",
            "panels": [{"visual_direction": "a"}, {"visual_direction": "b"}],
            "opening_line_fr": "Q ?",
            "suggested_response_fr": "R.",
        }
    )
    with pytest.raises(engine.StoryUnavailable) as caught:
        story_split.assemble(context, _plan(), text, None)
    assert str(caught.value) == "chapter_missing"


def test_the_planner_the_author_and_the_aids_are_the_writer_s_calls(monkeypatch):
    monkeypatch.setattr(settings, "STORY_WRITER_MODEL", "gpt-6-luna")
    monkeypatch.setattr(settings, "STORY_LIVE_MODEL", None)
    with engine.written_ahead_of_time():
        for schema in (story_split.PagePlan, story_split.PageText, story_split.PageAids):
            assert engine.story_route(schema)[0] == "gpt-6-luna"


def test_a_second_attempt_after_two_refused_drafts_asks_the_director_again(monkeypatch):
    """CI 2026-10-16: the dual-draft worker was also called ``draw`` and shadowed the
    Phase 2 draw, so the attempt after two refused drafts called the worker instead."""

    from pydantic import BaseModel

    class Page(BaseModel):
        n: int

    answers = iter([1, 2, 3])
    monkeypatch.setattr(engine, "_json_call", lambda *args, **kwargs: (Page(n=next(answers)), {}))
    monkeypatch.setattr(engine, "CRITIC_ENABLED", False)

    def validate(page):
        if page.n < 3:
            raise engine.StoryUnavailable("refused", hint="again")

    page, _ = engine._approved("system", {}, Page, validate, db=None, user=None, candidates=2)
    assert page.n == 3
