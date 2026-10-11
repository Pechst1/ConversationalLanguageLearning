"""WP-94 «Numéro spécial» and WP-95 «Le Carnet» — the story-engine half.

Fake providers only, never a paid call. What these tests pin (the contract the services
agent reads):

* every engine scene stores ``script_payload["can_do_id"]``: one can-do of the learner's
  current sub-band, chosen by the director from a list ordered unstamped-first; an id
  not on the list is dropped (``None``), never a lost day; a missing
  ``app.services.can_do`` module reads as "nothing stamped";
* on ``checkpoint_ready`` — and only then — the scene is a special edition:
  ``special = "epreuve"``, ``epreuve = {band, can_do_ids (2–3), attempt, pass_line_fr,
  fail_line_fr, …}``, the whole cast in the page;
* a retried épreuve is staged in a new situation (another place, another premise).
"""
from __future__ import annotations

import json
import sys
import types
import uuid
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services import level_checkpoint
from app.services import living_story as engine
from app.services.journey_contracts import InputMode, ScenarioBrief
from tests import test_living_story as story

assembled_client = story.assembled_client
journey_enabled = story.journey_enabled
clock = story.clock
one_exchange = story.one_exchange

DAY0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
A11_IDS = [item["id"] for item in level_checkpoint.band_can_dos("A1.1")]
CAST_IDS = ["marin_leveque", "lila_bonnet", "augustin_de_roncourt", "romy_tremblay", "margaux_barman"]


def view(*, ready: bool, band: str = "A1.1", attempts: int = 0, state: str | None = None) -> dict:
    return {
        "band": band,
        "state": state or ("ready" if ready else "locked"),
        "checkpoint_ready": ready,
        "attempts": attempts,
        "can_dos": level_checkpoint.band_can_dos(band),
    }


class Director(story.FakeProvider):
    """``story.FakeProvider`` whose director can pick a can-do and play the épreuve."""

    def __init__(self):
        super().__init__()
        self.pick = "prefer"  # "prefer" | "none" | an explicit id
        self.full_cast = False
        self.lines = False
        self.location: str | None = None
        self.premise: str | None = None

    def edit(self, value: dict, source: dict) -> dict:
        value = deepcopy(value)
        menu = source.get("can_dos") or {}
        if self.pick == "prefer":
            value["can_do_id"] = (menu.get("prefer") or [None])[0]
        elif self.pick != "none":
            value["can_do_id"] = self.pick
        epreuve = source.get("epreuve")
        if self.location:
            value["location_id"] = self.location
        if self.premise:
            value["premise_fr"] = self.premise
        if epreuve and self.full_cast:
            lines = [
                {"character_id": member["id"], "text_fr": "Bonsoir !", "text_native": "[en] Good evening!"}
                for member in epreuve["cast"]
            ]
            value["panels"][2]["dialogue"] = lines[:3]
            value["panels"][3]["dialogue"] = lines[3:6]
        if epreuve and self.lines:
            value["epreuve_pass_line_fr"] = "Bravo, on est fiers de vous !"
            value["epreuve_fail_line_fr"] = "On se revoit la semaine prochaine ?"
        return value

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] == "SceneDraft":
            source = data["data"]
            previous = self.transform
            self.transform = lambda schema, output: previous(
                schema, self.edit(output, source) if schema == "SceneDraft" else output
            )
            try:
                return super().generate_chat_completion(messages, **kwargs)
            finally:
                self.transform = previous
        return super().generate_chat_completion(messages, **kwargs)


@pytest.fixture
def director(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    fake = Director()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


@pytest.fixture
def checkpoint(monkeypatch):
    """The checkpoint the engine reads, set per test (default: A1.1, not ready)."""

    state = {"view": view(ready=False)}
    monkeypatch.setattr(level_checkpoint, "current_checkpoint", lambda db, user: dict(state["view"]))
    return state


@pytest.fixture
def stamped(monkeypatch):
    """A stand-in for the services agent's ``app.services.can_do``."""

    ids: set[str] = set()
    module = types.ModuleType("app.services.can_do")
    module.stamped_can_do_ids = lambda db, user_id: set(ids)
    monkeypatch.setitem(sys.modules, "app.services.can_do", module)
    return ids


def _learner(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp94-{uuid.uuid4().hex}@example.com",
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


def _sources(provider) -> list[dict]:
    return [source for schema, source in provider.calls if schema == "SceneDraft"]


def _generate(db, user) -> ScenarioBrief:
    brief = engine.generate_scene(db, user=user, input_mode=InputMode.TEXT, now=DAY0)
    assert isinstance(brief, ScenarioBrief), brief
    return brief


# ---------------------------------------------------------------------------
# WP-95 — can_do_id
# ---------------------------------------------------------------------------


def test_the_director_chooses_the_can_do_from_the_band_preferring_unstamped(
    db_session, director, checkpoint, stamped
):
    stamped.update({A11_IDS[0], A11_IDS[1]})
    user = _learner(db_session)
    brief = _generate(db_session, user)
    menu = _sources(director)[-1]["can_dos"]
    assert menu["band"] == "A1.1"
    ids = [option["id"] for option in menu["options"]]
    assert sorted(ids) == sorted(A11_IDS)
    # Unstamped first, stamped last, and `prefer` names only the unstamped ones.
    assert ids[-2:] == [A11_IDS[0], A11_IDS[1]]
    assert menu["prefer"] == ids[:-2]
    assert all(option["title"] and option["title_fr"] for option in menu["options"])
    assert brief.story_context["draft"]["can_do_id"] == menu["prefer"][0]
    assert "epreuve" not in _sources(director)[-1]


def test_an_id_not_on_the_list_is_dropped_not_fatal(db_session, director, checkpoint, stamped):
    director.pick = "CD_B21_DEBATE_NOT_THIS_BAND"
    brief = _generate(db_session, _learner(db_session))
    assert brief.story_context["draft"]["can_do_id"] is None


def test_without_the_can_do_module_nothing_reads_as_stamped(
    db_session, director, checkpoint, monkeypatch
):
    # ``None`` in sys.modules makes the import raise ImportError.
    monkeypatch.setitem(sys.modules, "app.services.can_do", None)
    assert engine.stamped_can_dos(db_session, _learner(db_session)) == set()
    brief = _generate(db_session, _learner(db_session))
    menu = _sources(director)[-1]["can_dos"]
    assert sorted(menu["prefer"]) == sorted(A11_IDS)
    assert brief.story_context["draft"]["can_do_id"] in A11_IDS


def test_already_exercised_can_dos_move_back(db_session, director, checkpoint, stamped):
    user = _learner(db_session)
    first = _generate(db_session, user)
    chosen = first.story_context["draft"]["can_do_id"]
    db_session.add(
        GraphicNovelScene(
            user_id=user.id,
            title="x",
            brief="x",
            status="available",
            cadence="daily",
            prompt_version=engine.VERSION,
            script_payload={"can_do_id": chosen},
            source_snapshot={},
            cache_key="x",
            image_model="existing-setting-art",
            image_quality="reference",
        )
    )
    db_session.flush()
    menu = engine.can_do_menu(db_session, user, band="A1.1", control_language="en")
    assert menu["options"][-1]["id"] == chosen


# ---------------------------------------------------------------------------
# WP-94 — the épreuve
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current",
    [
        view(ready=False),
        view(ready=False, state="failed", attempts=1),  # inside its week of consolidation
        view(ready=False, state="passed", attempts=1),
    ],
)
def test_no_epreuve_unless_the_checkpoint_is_ready(db_session, director, checkpoint, current):
    checkpoint["view"] = current
    brief = _generate(db_session, _learner(db_session))
    assert "epreuve" not in _sources(director)[-1]
    draft = brief.story_context["draft"]
    assert draft["epreuve_pass_line_fr"] is None and draft["epreuve_fail_line_fr"] is None


def test_a_ready_checkpoint_stages_the_special_edition(db_session, director, checkpoint, stamped):
    stamped.add(A11_IDS[0])
    checkpoint["view"] = view(ready=True)
    director.full_cast, director.lines = True, True
    brief = _generate(db_session, _learner(db_session))
    plan = _sources(director)[-1]["epreuve"]
    assert plan["band"] == "A1.1" and plan["attempt"] == 1
    assert 2 <= len(plan["can_do_ids"]) <= 3
    assert A11_IDS[0] not in plan["can_do_ids"], "least evidenced first"
    assert set(plan["can_do_ids"]) <= set(A11_IDS)
    assert sorted(member["id"] for member in plan["cast"]) == sorted(CAST_IDS)
    assert plan["suggested_location"] == "le_mistral"
    assert plan["avoid"] is None
    draft = brief.story_context["draft"]
    assert draft["can_do_id"] in plan["can_do_ids"]
    assert draft["epreuve_pass_line_fr"] == "Bravo, on est fiers de vous !"
    assert draft["epreuve_fail_line_fr"] == "On se revoit la semaine prochaine ?"
    # The director's prompt tells it what a special edition is.
    assert "NUMÉRO SPÉCIAL" in engine.DIRECTOR


def test_a_director_that_forgets_the_cast_is_hinted_once_then_completed(
    db_session, director, checkpoint
):
    checkpoint["view"] = view(ready=True)
    brief = _generate(db_session, _learner(db_session))
    sources = _sources(director)
    assert len(sources) == 2, "one hinted retry"
    assert any("everyone comes" in item for item in sources[-1]["previous_rejections"])
    draft = engine.SceneDraft.model_validate(brief.story_context["draft"])
    plan = brief.story_context["source"]["epreuve"]
    assert engine.epreuve_absent_cast(draft, plan) == []
    assert "arrivent aussi" in draft.panels[0].narration_fr
    assert draft.epreuve_pass_line_fr and draft.epreuve_fail_line_fr
    assert "semaine prochaine" in draft.epreuve_fail_line_fr
    assert "·" not in draft.epreuve_fail_line_fr + draft.epreuve_pass_line_fr


def test_the_bound_epreuve_carries_the_contract(
    assembled_client, db_session, journey_enabled, clock, director, checkpoint
):
    checkpoint["view"] = view(ready=True)
    director.lines = True
    d = story.driver(assembled_client, db_session)
    d.create()
    db_session.expire_all()
    scene = db_session.scalar(select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id))
    payload = scene.script_payload
    assert payload["special"] == "epreuve"
    epreuve = payload["epreuve"]
    assert epreuve["band"] == "A1.1" and epreuve["attempt"] == 1
    assert 2 <= len(epreuve["can_do_ids"]) <= 3
    assert payload["can_do_id"] in epreuve["can_do_ids"]
    assert epreuve["pass_line_fr"] == "Bravo, on est fiers de vous !"
    assert epreuve["fail_line_fr"] == "On se revoit la semaine prochaine ?"
    assert sorted(epreuve["cast_ids"]) == sorted(CAST_IDS)
    # Everyone is in the page: a line, or a name in the narration.
    page = " ".join(
        [panel.overlay_payload["narration_fr"] for panel in scene.panels]
        + [line["character_id"] for panel in scene.panels for line in panel.overlay_payload["dialogue"]]
    )
    for member in ("Marin", "Lila", "Augustin", "romy_tremblay", "Margaux"):
        assert member in page or member.casefold() in page.casefold(), member
    thread = db_session.scalar(select(SerialThread).where(SerialThread.user_id == d.user_id))
    staged = thread.state["living_story"]["epreuves"]
    assert staged[-1]["band"] == "A1.1" and staged[-1]["location_id"] == scene.script_payload["location_id"]


def test_an_ordinary_scene_is_not_special(
    assembled_client, db_session, journey_enabled, clock, director, checkpoint
):
    d = story.driver(assembled_client, db_session)
    d.create()
    db_session.expire_all()
    scene = db_session.scalar(select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id))
    assert scene.script_payload["special"] is None
    assert "epreuve" not in scene.script_payload
    assert scene.script_payload["can_do_id"] in A11_IDS


def test_a_failed_epreuve_returns_in_a_new_situation(
    assembled_client, db_session, journey_enabled, clock, director, checkpoint, monkeypatch
):
    # The chapter's shape is dealt from the thread id; a «bottle» chapter keeps
    # every scene in one room, which is the other (tested) way the épreuve moves
    # on. Pin an open shape so this test is about the new place.
    monkeypatch.setattr(engine, "chapter_shape", lambda seed, index, previous=None: "standard")
    checkpoint["view"] = view(ready=True)
    director.location = "le_mistral"
    director.premise = "Tout le monde se retrouve au Mistral pour fêter l'anniversaire de Margaux."
    d = story.driver(assembled_client, db_session)
    d.create()
    d.play(answer="Bonsoir ! Je m'appelle Alex. Je voudrais un café.")
    d.finish("complete")
    # A week later the failed épreuve is ready again (retry_after passed): attempt 2.
    clock.advance(days=8)
    checkpoint["view"] = view(ready=True, attempts=1)
    # A director that stages the same evening again is refused, then moves on.
    calls_before = len(_sources(director))

    stubborn = {"left": 1}
    original = director.edit

    def edit(value, source):
        value = original(value, source)
        if stubborn["left"] <= 0:
            value["location_id"] = "buttes_chaumont"
            value["premise_fr"] = "Une fête surprise au parc pour le retour de Gus."
            value["novelty_key"] = "epreuve-park-party"
        stubborn["left"] -= 1
        return value

    director.edit = edit
    d.create()
    sources = _sources(director)[calls_before:]
    plan = sources[0]["epreuve"]
    assert plan["attempt"] == 2
    assert plan["avoid"]["location_id"] == "le_mistral"
    assert plan["suggested_location"] is None
    assert any("new situation" in item for item in sources[-1]["previous_rejections"])
    db_session.expire_all()
    payloads = [
        scene.script_payload
        for scene in db_session.scalars(
            select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id)
        )
    ]
    staged = {p["epreuve"]["attempt"]: p for p in payloads if p.get("special") == "epreuve"}
    assert sorted(staged) == [1, 2]
    assert staged[1]["location_id"] == "le_mistral"
    assert staged[2]["location_id"] == "buttes_chaumont"


def test_the_same_premise_elsewhere_is_still_the_same_situation():
    context = {
        "epreuve": {"avoid": {"location_id": "le_mistral", "premise_fr": "Tout le monde fête Margaux au café.", "novelty_key": "x"}},
        "chapter": {},
    }
    base = story.draft({"level": "A1", "world": {"cast": []}})
    base.update(premise_fr="Tout le monde fête Margaux au café.", location_id="newsroom")
    with pytest.raises(engine.StoryUnavailable, match="epreuve_same_situation"):
        engine._check_epreuve_situation(engine.SceneDraft.model_validate(base), context)
    base.update(premise_fr="Une fête surprise pour Gus.", novelty_key="y")
    engine._check_epreuve_situation(engine.SceneDraft.model_validate(base), context)


def test_the_cache_key_changes_on_the_epreuve_day(db_session, checkpoint):
    user = _learner(db_session)
    assert engine.epreuve_cache_key(db_session, user) is None
    checkpoint["view"] = view(ready=True, attempts=1)
    assert engine.epreuve_cache_key(db_session, user) == "A1.1:2"
