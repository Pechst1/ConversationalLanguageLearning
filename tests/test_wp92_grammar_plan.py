"""WP-92 «La règle dans l'histoire» and WP-93 «Mots à placer» — the story-engine half.

Fake providers only, never a paid call. What these tests pin:

* the director receives ``grammar_plan`` {introduce, weave, allowed, avoid} chosen before
  it writes (the unit the Règle step will pick), without the detectors' regexes; the actor
  never receives it, and the stored context keeps its provenance only;
* the validator counts the new form in the cast's lines (≥ 2) and asks for a question that
  invites it; one hinted retry, then the scene is ACCEPTED with ``woven: false``;
* a 14-day run with a director that sometimes forgets: ≥ 80 % of introduction days carry
  the form ≥ 2 times and an inviting question;
* «Rayons X» marks per line, with offsets into ``text_fr``; ``grammar_focus`` on the scene;
* five «mots à placer» from the band's lemma list, and ``placed_lemmas`` /
  ``recycled_lemmas`` stored, the reuse counted on the scene's cost row.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import concept_life
from app.services import living_story as engine
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.grammar_units import detector_spans
from app.services.journey_contracts import InputMode, ScenarioBrief
from tests import test_living_story as story

assembled_client = story.assembled_client
journey_enabled = story.journey_enabled
clock = story.clock
one_exchange = story.one_exchange

DAY0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def weave(value: dict, source: dict) -> dict:
    """A compliant director: the new form said twice, asked for, the words placed."""

    value = deepcopy(value)
    plan = source.get("grammar_plan") or {}
    introduce = plan.get("introduce") or {}
    examples = [str(item) for item in introduce.get("examples") or []]
    speaker = value["character_id"]
    cast = {member.get("id") for member in (source.get("world") or {}).get("cast") or []}
    coach = introduce.get("coach_id")
    two_hander = (source.get("chapter_shape") or {}).get("shape") == "two_hander"
    other = coach if coach in cast and coach != speaker and not two_hander else speaker
    if examples:
        first, second = examples[0], examples[1 % len(examples)]
        value["panels"][2]["dialogue"] = [
            {"character_id": other, "text_fr": first, "mood": "happy", "text_native": "[en] 1"}
        ]
        value["panels"][3]["dialogue"] = [
            {"character_id": speaker, "text_fr": second, "mood": "neutral", "text_native": "[en] 2"}
        ]
        value["suggested_response_fr"] = examples[-1]
    mots = list(source.get("mots_a_placer") or [])
    if mots:
        value["panels"][1]["dialogue"].append(
            {
                "character_id": speaker,
                "text_fr": f"Tu veux {mots[0]} ?",
                "mood": "neutral",
                "text_native": "[en] 3",
            }
        )
    return value


class WeavingProvider(story.FakeProvider):
    """``story.FakeProvider`` whose director obeys the grammar plan — except on the
    attempts listed in ``forget`` (0-based SceneDraft call numbers)."""

    def __init__(self):
        super().__init__()
        self.forget: set[int] = set()
        self.scene_calls = 0

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] == "SceneDraft":
            number = self.scene_calls
            self.scene_calls += 1
            if number not in self.forget:
                source = data["data"]
                previous = self.transform
                self.transform = lambda schema, output: previous(
                    schema, weave(output, source) if schema == "SceneDraft" else output
                )
                try:
                    return super().generate_chat_completion(messages, **kwargs)
                finally:
                    self.transform = previous
        return super().generate_chat_completion(messages, **kwargs)


@pytest.fixture
def plan_on(monkeypatch, db_session):
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_STORY_GRAMMAR_PLAN_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


@pytest.fixture
def weaver(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    fake = WeavingProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def _learner(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp92-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
        cefr_estimate="A1.1",
        daily_goal_minutes=10,
    )
    db.add(user)
    db.commit()
    return user


def _scene_sources(provider) -> list[dict]:
    return [source for schema, source in provider.calls if schema == "SceneDraft"]


# ---------------------------------------------------------------------------
# The plan, and who sees it
# ---------------------------------------------------------------------------


def test_the_director_gets_the_plan_before_writing_and_never_the_regex(db_session, plan_on, weaver):
    user = _learner(db_session)
    expected = concept_life.introduction_for_today(db_session, user, now=DAY0)
    brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT, now=DAY0)
    assert isinstance(brief, ScenarioBrief)

    source = _scene_sources(weaver)[0]
    plan = source["grammar_plan"]
    assert plan["introduce"]["title_fr"] == expected["title_fr"]
    assert plan["introduce"]["examples"], "the director is shown the form"
    assert set(plan) == {"introduce", "weave", "allowed", "avoid"}
    assert "A2" not in json.dumps(plan["allowed"])
    assert plan["avoid"], "above-band structures are named"
    assert "detectors" not in json.dumps(plan), "the regexes stay server-side"
    assert len(source["mots_a_placer"]) == engine.MOTS_COUNT

    stored = brief.story_context["source"]["grammar_plan"]
    assert stored == {
        "introduce": str(expected["concept_id"]),
        "weave": [],
        "allowed": 0,
        "avoid": len(plan["avoid"]),
    }, "the stored context keeps provenance, never the plan"
    focus = brief.story_context["grammar"]["focus"]
    assert focus == {
        "unit_id": str(expected["concept_id"]),
        "title_fr": expected["title_fr"],
        "title_native": expected["title_native"],
        "woven": True,
    }


def test_the_actor_never_sees_the_plan(
    assembled_client, db_session, journey_enabled, clock, plan_on, weaver
):
    d = story.driver(assembled_client, db_session)
    d.create()
    d.play(answer="Je peux apporter les affiches samedi.")
    assert any("grammar_plan" in source for source in _scene_sources(weaver))
    turns = [source for schema, source in weaver.calls if schema != "SceneDraft"]
    assert turns
    assert all("grammar_plan" not in json.dumps(source) for source in turns)
    assert all("mots_a_placer" not in json.dumps(source) for source in turns)


def test_flag_off_means_no_plan(db_session, plan_on, weaver, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_GRAMMAR_PLAN_ENABLED", False)
    user = _learner(db_session)
    brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT, now=DAY0)
    assert isinstance(brief, ScenarioBrief)
    assert "grammar_plan" not in _scene_sources(weaver)[0]
    assert brief.story_context["grammar"] is None


# ---------------------------------------------------------------------------
# The validator: count, invite, one retry, then accept
# ---------------------------------------------------------------------------


def test_a_forgotten_form_is_retried_once_with_a_named_hint(db_session, plan_on, weaver):
    weaver.forget = {0}
    user = _learner(db_session)
    brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT, now=DAY0)
    assert isinstance(brief, ScenarioBrief)
    sources = _scene_sources(weaver)
    assert len(sources) == 2
    hint = " ".join(sources[1]["previous_rejections"])
    assert "grammar_not_woven" in hint and "grammar_plan.introduce" in hint
    assert "opening_line_fr" in hint
    assert brief.story_context["grammar"]["focus"]["woven"] is True


def test_a_scene_that_never_weaves_is_accepted_and_flagged(db_session, plan_on, weaver):
    weaver.forget = {0, 1, 2}
    user = _learner(db_session)
    brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT, now=DAY0)
    assert isinstance(brief, ScenarioBrief), "a grammar plan never costs the day"
    assert len(_scene_sources(weaver)) == 2, "one retry, then accept"
    grammar = brief.story_context["grammar"]
    assert grammar["focus"]["woven"] is False
    assert grammar["uses"] < engine.GRAMMAR_MIN_USES


def test_a_unit_without_a_regex_is_not_measured():
    draft = engine.SceneDraft.model_validate(story.draft(story._scene_context(), 0))
    plan = {
        "introduce": {"unit_id": "77", "title_fr": "X", "title_native": "X", "detectors": [], "examples": []},
        "weave": [],
        "allowed": [],
        "avoid": [],
    }
    assert engine.grammar_weave_gap(draft, {"grammar_plan": plan}) is None
    outcome = engine.grammar_outcome(draft, plan)
    assert outcome["focus"]["woven"] is None
    assert outcome["marks"] == {}


def test_the_fourteen_day_run_weaves_the_new_form(db_session, plan_on, weaver):
    """Done-when: ≥ 80 % of introduction days carry the form ≥ 2 times and a question
    that invites it — with a director that forgets on every third day's first draft."""

    user = _learner(db_session)
    introductions: list[dict] = []
    forgotten_days = 0
    for day in range(14):
        now = DAY0 + timedelta(days=day)
        if day % 3 == 0:
            weaver.forget.add(weaver.scene_calls)
            forgotten_days += 1
        brief = engine.generate_scene(db_session, user=user, input_mode=InputMode.TEXT, now=now)
        assert isinstance(brief, ScenarioBrief), (day, brief)
        grammar = brief.story_context["grammar"] or {}
        focus = grammar.get("focus")
        if focus:
            introductions.append(grammar)
            # The learner reads the Règle: the unit is introduced that day.
            concept_life.mark_introduced(db_session, user=user, concept_id=int(focus["unit_id"]), now=now)
            db_session.commit()
    assert len(introductions) >= 4, "Régulier introduces two units a week"
    woven = [
        g for g in introductions
        if g["focus"]["woven"] and g["uses"] >= engine.GRAMMAR_MIN_USES and g["invited"]
    ]
    assert len(woven) / len(introductions) >= 0.8
    assert forgotten_days and any(
        "grammar_not_woven" in " ".join(source.get("previous_rejections") or [])
        for source in _scene_sources(weaver)
    ), "the forgetful days were retried"
    later = [source["grammar_plan"] for source in _scene_sources(weaver)[-3:]]
    assert any(plan.get("allowed") for plan in later), "met units become allowed"


# ---------------------------------------------------------------------------
# «Rayons X» marks, grammar_focus, words — on the bound scene
# ---------------------------------------------------------------------------


def test_the_bound_scene_carries_marks_focus_and_words(
    assembled_client, db_session, journey_enabled, clock, plan_on, weaver, monkeypatch
):
    monkeypatch.setattr(
        engine,
        "_director_vocabulary",
        lambda db, user: {
            "kept_words": [{"word": "affiche", "gloss": "poster", "example_fr": ""}],
            "lexicon_history": ["pluie", "parapluie"],
            "drilled_words": [],
        },
    )
    d = story.driver(assembled_client, db_session)
    d.create()
    db_session.expire_all()
    scene = db_session.scalar(select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id))
    focus = scene.script_payload["grammar_focus"]
    assert focus["woven"] is True and focus["unit_id"] and focus["title_fr"]

    plan = _scene_sources(weaver)[-1]["grammar_plan"]
    unit = concept_life.concept_brief(
        db_session,
        db_session.get(concept_life.GrammarConcept, int(focus["unit_id"])),
        control_language="en",
    )
    assert plan["introduce"]["title_fr"] == unit["title_fr"]
    marked = 0
    for panel in scene.panels:
        for line in panel.overlay_payload["dialogue"]:
            assert "grammar_marks" in line
            expected = detector_spans(unit["detectors"], line["text_fr"])
            got = [(m["start"], m["end"]) for m in line["grammar_marks"] if m["unit_id"] == focus["unit_id"]]
            assert got == expected
            for mark in line["grammar_marks"]:
                assert 0 <= mark["start"] < mark["end"] <= len(line["text_fr"])
                assert line["text_fr"][mark["start"]:mark["end"]].strip()
            marked += len(got)
    assert marked >= engine.GRAMMAR_MIN_USES

    mots = _scene_sources(weaver)[-1]["mots_a_placer"]
    assert scene.script_payload["placed_lemmas"] == [mots[0]]
    assert scene.script_payload["recycled_lemmas"] == ["affiche", "pluie"]
    cost = db_session.scalar(
        select(PilotEvent).where(
            PilotEvent.user_id == d.user_id, PilotEvent.event_type == "journey_story_scene_cost"
        )
    )
    assert cost.payload["word_reuse"] == {"offered": 5, "placed": 1, "recycled": 2, "pool": 3}
    assert cost.payload["grammar"]["woven"] is True
    assert cost.payload["grammar"]["uses"] >= 2

    # The reader's API passes the lines through as they are stored.
    episode = assembled_client.get(
        f"/api/v1/story-engine/episodes/{scene.id}", headers=d.headers
    ).json()
    assert any(line.get("grammar_marks") for panel in episode["panels"] for line in panel["dialogue"])


def test_detector_spans_are_offsets_into_the_line():
    patterns = [r"\b(?:un|une|des)\s+[a-zàâçéèêëîïôûùüÿœ]{2,}"]
    text = "Tiens, une table et des chaises — un peu tard !"
    spans = detector_spans(patterns, text)
    assert [text[a:b] for a, b in spans] == ["une table", "des chaises"], "«un peu» is skipped"
    folded = "J’ai une idée."
    assert [folded[a:b] for a, b in detector_spans(patterns, folded)] == ["une idée"]


def test_mots_a_placer_skip_what_the_learner_met_and_rotate(db_session, monkeypatch):
    user = _learner(db_session)
    first = engine.mots_a_placer(db_session, user, {"level": "A1"})
    assert len(first) == engine.MOTS_COUNT
    assert all(" " not in word for word in first)
    again = engine.mots_a_placer(
        db_session, user, {"level": "A1", "lexicon_history": first[:2], "drilled_words": [first[2]]}
    )
    assert not set(first[:3]) & set(again)
