"""WP-90 «La planche» — the story-engine half. Fake providers only, never a paid call.

What these tests pin:

* faces act: every line carries a ``mood`` (an unknown word is ``neutral``, never a
  refused draft) and reaches the reader through the episode API;
* understanding at A1: an A1/A2 learner who is not French gets ``text_native`` on every
  line, a B1 learner and a French speaker do not; every panel carries ``alt_native``;
* a missing translation costs at most one retry with a hint and never the scene;
* art ready before the tap: a prefetched draft's panels are drawn at prefetch time,
  attached at bind with no second drawing, inside the art allowance of the day they are
  drawn; a drawing still in flight at bind is waited for, not drawn twice; a discarded
  prefetch draws nothing more.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services import journey_latency, panel_art
from app.services import living_story as engine
from app.services.journey_contracts import InputMode
from app.services.spend_guard import PANEL_ART_EVENT_TYPE
from tests import test_journey_end_to_end as support
from tests.test_living_story import (
    FakeProvider,
    _draft,
    _scene_context,
    draft,
    with_reading_aids,
)
from tests.test_panel_art import _png

assembled_client = support.assembled_client
journey_enabled = support.journey_enabled
clock = support.clock


@pytest.fixture(autouse=True)
def one_exchange(monkeypatch):
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)


class AidProvider(FakeProvider):
    """The scripted director, with the reading aids switched per call."""

    def __init__(self):
        super().__init__()
        #: One entry per SceneDraft call: True = a compliant draft, False = no aids.
        #: Past the end of the list every draft is compliant.
        self.aids: list[bool] = []
        self.hard_fail_after: int | None = None

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] != "SceneDraft":
            return super().generate_chat_completion(messages, **kwargs)
        source = data["data"]
        index = self.scenes
        self.calls.append(("SceneDraft", source))
        self.scenes += 1
        if self.hard_fail_after is not None and index >= self.hard_fail_after:
            value = {"not": "a draft"}
        else:
            compliant = self.aids[index] if index < len(self.aids) else True
            value = with_reading_aids(_draft(source, 0), source) if compliant else _draft(source, 0)
            if compliant:
                moods = ["happy", "cross", "furious", "moved"]
                for n, line in enumerate(line for p in value["panels"] for line in p["dialogue"]):
                    line["mood"] = moods[n % len(moods)]
        return SimpleNamespace(
            content=json.dumps(value), model="fake-wp90", provider="test", total_tokens=30, cost=0.0
        )


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    fake = AidProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


def _driver(client, db, *, cefr="A1.1", native="en"):
    email = f"wp90-{__import__('uuid').uuid4()}@example.com"
    headers = support.register(client, email, cefr=cefr)
    d = support.Driver(client, headers, db=db)
    d.user_id = support.learner_id(db, email)
    if native != "en":
        user = db.get(User, UUID(str(d.user_id)))
        user.native_language = native
        db.commit()
    return d


def _episode(client, d) -> dict:
    listed = client.get("/api/v1/story-engine/episodes", headers=d.headers).json()["episodes"]
    assert len(listed) == 1
    return listed[0]


def _scene(db, d) -> GraphicNovelScene:
    db.expire_all()
    return db.scalars(
        select(GraphicNovelScene).where(GraphicNovelScene.user_id == UUID(str(d.user_id)))
    ).one()


def _director_calls(provider) -> list[dict]:
    return [source for schema, source in provider.calls if schema == "SceneDraft"]


# ---------------------------------------------------------------------------
# The schema is lenient where it may be
# ---------------------------------------------------------------------------


def test_mood_and_aids_are_lenient_fields():
    line = engine.Dialogue.model_validate(
        {"character_id": "romy_tremblay", "text_fr": "Salut.", "mood": "Furious", "text_native": "   "}
    )
    assert line.mood == "neutral", "an unknown mood is neutral, never a refused draft"
    assert line.text_native is None
    assert engine.Dialogue.model_validate(
        {"character_id": "romy_tremblay", "text_fr": "Salut.", "mood": " Moved "}
    ).mood == "moved"
    long = engine.Dialogue.model_validate(
        {"character_id": "romy_tremblay", "text_fr": "Salut.", "text_native": "word " * 200}
    ).text_native
    assert long is not None and len(long) <= engine.LINE_NATIVE_CHARS
    panel = engine.Panel.model_validate(
        {"visual_direction": "Wide shot.", "alt_native": "Romy at the counter " * 20}
    )
    assert len(panel.alt_native) <= engine.PANEL_ALT_CHARS
    # A draft stored before WP-90 still binds.
    assert engine.Dialogue.model_validate({"character_id": "x", "text_fr": "Oui."}).mood == "neutral"


@pytest.mark.parametrize(
    ("level", "language", "expected"),
    [("A1", "en", "en"), ("A2", "de", "de"), ("A1", "fr", None), ("B1", "en", None), ("C1", "de", None)],
)
def test_who_gets_line_translations(level, language, expected):
    assert engine.line_translation_language({"level": level, "control_language": language}) == expected


def test_translations_are_required_at_a1_and_dropped_at_b1():
    a1 = _scene_context(control_language="en")
    bare = engine.SceneDraft.model_validate(_draft(a1, 0))
    with pytest.raises(engine.SoftRejection) as refused:
        engine._validate_scene(bare, a1)
    assert "text_native" in refused.value.hint and "alt_native" in refused.value.hint
    engine._validate_scene(engine.SceneDraft.model_validate(draft(a1, 0)), a1)

    b1 = _scene_context(control_language="en", level="B1")
    translated = engine.SceneDraft.model_validate(with_reading_aids(_draft(b1, 0), a1))
    engine._validate_scene(translated, b1)
    assert all(line.text_native is None for p in translated.panels for line in p.dialogue), (
        "a B1 learner reads the French"
    )


# ---------------------------------------------------------------------------
# One hint, then the scene — never a lost day
# ---------------------------------------------------------------------------


def _approve(context):
    sink = SimpleNamespace(add=lambda row: None)
    return engine._approved(
        engine.DIRECTOR,
        {**context, engine.LINE_TRANSLATION_KEY: engine.line_translation_language(context)},
        engine.SceneDraft,
        lambda proposal: engine._validate_scene(proposal, context),
        db=sink,
        user=SimpleNamespace(id=None),
    )


def test_a_missing_translation_gets_one_retry_with_the_hint(provider):
    provider.aids = [False, True]
    scene, _ = _approve(_scene_context(control_language="de"))
    calls = _director_calls(provider)
    assert len(calls) == 2
    assert any("text_native" in note for note in calls[1]["previous_rejections"])
    assert all(line.text_native for p in scene.panels for line in p.dialogue)


def test_a_second_miss_is_accepted_with_empty_aids(provider):
    provider.aids = [False, False, False]
    scene, _ = _approve(_scene_context(control_language="en"))
    assert len(_director_calls(provider)) == 2, "one retry, then the scene"
    assert all(line.text_native is None for p in scene.panels for line in p.dialogue)
    assert all(p.alt_native is None for p in scene.panels)


def test_a_missing_translation_never_fails_the_scene(provider):
    # The first draft is only missing its aids; every later attempt is unusable.
    provider.aids = [False]
    provider.hard_fail_after = 1
    scene, _ = _approve(_scene_context(control_language="en"))
    assert scene.title_fr, "the kept draft is served rather than the day lost"
    assert len(_director_calls(provider)) >= 2


# ---------------------------------------------------------------------------
# The fields reach the reader
# ---------------------------------------------------------------------------


def test_an_a1_learner_reads_moods_translations_and_alt_text(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = _driver(assembled_client, db_session)
    d.create()
    director = _director_calls(provider)[0]
    assert director[engine.LINE_TRANSLATION_KEY] == "en"
    episode = _episode(assembled_client, d)
    lines = [line for panel in episode["panels"] for line in panel["dialogue"]]
    assert lines
    for line in lines:
        assert line["mood"] in engine.LINE_MOODS
        assert line["text_native"].startswith("[en] ")
    assert {line["mood"] for line in lines} <= {"happy", "cross", "neutral", "moved"}
    scene = _scene(db_session, d)
    for panel in scene.panels:
        assert panel.overlay_payload["alt_native"], "alt text is stored with the panel"


@pytest.mark.parametrize(("cefr", "native"), [("B1.1", "en"), ("A1.1", "fr")])
def test_b1_and_french_learners_get_no_translations(
    assembled_client, db_session, journey_enabled, clock, provider, cefr, native
):
    d = _driver(assembled_client, db_session, cefr=cefr, native=native)
    d.create()
    assert _director_calls(provider)[0][engine.LINE_TRANSLATION_KEY] is None
    lines = [line for panel in _episode(assembled_client, d)["panels"] for line in panel["dialogue"]]
    assert lines and all(line["text_native"] is None for line in lines)
    assert len(_director_calls(provider)) == 1, "no retry for an aid nobody asked for"


# ---------------------------------------------------------------------------
# Art ready before the tap
# ---------------------------------------------------------------------------


@pytest.fixture
def art(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", True)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "local")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_BANDS", "A1,A2")
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_COST_USD_PER_PANEL", 0.05)
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD", 10.0)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PREFETCH_ENABLED", True)
    queued: list = []
    monkeypatch.setattr(panel_art, "dispatcher", queued.append)
    drawn: list = []
    failing: set[int] = set()

    def fake_draw(job):
        drawn.append(job)
        if job.panel_index in failing:
            raise RuntimeError("scripted failure")
        return _png()

    monkeypatch.setattr(panel_art, "draw", fake_draw)
    return SimpleNamespace(queued=queued, drawn=drawn, failing=failing)


def _prefetch(db, d) -> PilotEvent:
    user = db.get(User, UUID(str(d.user_id)))
    assert journey_latency.prefetch_scene_for(db, user, input_mode=InputMode.TEXT) == "prefetched"
    return db.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == user.id, PilotEvent.event_type == journey_latency.PREFETCH_EVENT
        )
    ).one()


def _jobs(art, kind):
    return [job for job in art.queued if isinstance(job, kind)]


def _art_rows(db, d) -> list[PilotEvent]:
    db.expire_all()
    return list(
        db.scalars(
            select(PilotEvent).where(
                PilotEvent.user_id == UUID(str(d.user_id)), PilotEvent.event_type == PANEL_ART_EVENT_TYPE
            )
        ).all()
    )


def test_a_prefetched_draft_is_drawn_ahead_and_attached_at_bind(
    assembled_client, db_session, journey_enabled, clock, provider, art
):
    d = _driver(assembled_client, db_session)
    row = _prefetch(db_session, d)
    [job] = _jobs(art, panel_art.PrefetchArtJob)
    assert job.prefetch_id == str(row.id)
    assert panel_art.render_prefetch_art(job) == "done"
    panels = len(row.payload["brief"]["story_context"]["draft"]["panels"])
    assert len(art.drawn) == panels
    rows = _art_rows(db_session, d)
    assert len(rows) == panels and all(r.entity_id == str(row.id) for r in rows)
    assert all(r.cost_usd == pytest.approx(0.05) for r in rows)

    art.queued.clear()
    d.create()
    assert _director_calls(provider) and len(_director_calls(provider)) == 1, "served warm"
    assert art.queued == [], "nothing left to draw or wait for"
    episode = _episode(assembled_client, d)
    assert [p["image_status"] for p in episode["panels"]] == ["panel_art"] * panels
    assert all(p["image_url"].startswith("/media/graphic-novel/scenes/prefetch-") for p in episode["panels"])
    assert len(art.drawn) == panels, "no second drawing"
    assert len(_art_rows(db_session, d)) == panels, "no second bill"
    scene = _scene(db_session, d)
    assert scene.source_snapshot["prefetch_id"] == str(row.id)


def test_the_allowance_is_respected_at_prefetch(
    assembled_client, db_session, journey_enabled, clock, provider, art, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_DAILY_ALLOWANCE_USD", 0.10)
    d = _driver(assembled_client, db_session)
    _prefetch(db_session, d)
    [job] = _jobs(art, panel_art.PrefetchArtJob)
    panel_art.render_prefetch_art(job)
    assert len(art.drawn) == 2, "two panels fit today's allowance"
    art.queued.clear()
    d.create()
    assert _jobs(art, panel_art.SceneArtJob) == [], "the spent allowance draws nothing more"
    statuses = [p["image_status"] for p in _episode(assembled_client, d)["panels"]]
    assert statuses[:2] == ["panel_art", "panel_art"]
    assert set(statuses[2:]) == {"setting_reference"}
    assert sum(r.cost_usd for r in _art_rows(db_session, d)) == pytest.approx(0.10)


def test_a_failed_prefetch_panel_is_the_only_one_drawn_at_bind(
    assembled_client, db_session, journey_enabled, clock, provider, art
):
    art.failing.add(1)
    d = _driver(assembled_client, db_session)
    row = _prefetch(db_session, d)
    panel_art.render_prefetch_art(_jobs(art, panel_art.PrefetchArtJob)[0])
    panels = len(row.payload["brief"]["story_context"]["draft"]["panels"])
    art.queued.clear()
    art.failing.clear()
    d.create()
    [scene_job] = _jobs(art, panel_art.SceneArtJob)
    assert scene_job.indices == (1,)
    assert panel_art.render_scene_art(scene_job) == "done"
    assert [job.panel_index for job in art.drawn].count(1) == 2
    assert len(art.drawn) == panels + 1
    assert {p["image_status"] for p in _episode(assembled_client, d)["panels"]} == {"panel_art"}


def test_a_drawing_in_flight_at_bind_is_waited_for_not_drawn_twice(
    assembled_client, db_session, journey_enabled, clock, provider, art
):
    d = _driver(assembled_client, db_session)
    row = _prefetch(db_session, d)
    [prefetch_job] = _jobs(art, panel_art.PrefetchArtJob)
    art.queued.clear()
    d.create()  # bound before the prefetch's drawings are done
    [adopt] = _jobs(art, panel_art.AdoptArtJob)
    assert _jobs(art, panel_art.SceneArtJob) == []
    assert {p["image_status"] for p in _episode(assembled_client, d)["panels"]} == {"rendering"}

    assert panel_art.render_prefetch_art(prefetch_job) == "done"
    assert panel_art.adopt_prefetched_art(adopt, wait_seconds=0) == "adopted"
    panels = len(row.payload["brief"]["story_context"]["draft"]["panels"])
    assert len(art.drawn) == panels
    assert {p["image_status"] for p in _episode(assembled_client, d)["panels"]} == {"panel_art"}


def test_a_drawing_that_never_comes_is_drawn_by_the_scene(
    assembled_client, db_session, journey_enabled, clock, provider, art
):
    d = _driver(assembled_client, db_session)
    row = _prefetch(db_session, d)
    art.queued.clear()
    d.create()
    [adopt] = _jobs(art, panel_art.AdoptArtJob)
    assert panel_art.adopt_prefetched_art(adopt, wait_seconds=0) == "drew_missing"
    panels = len(row.payload["brief"]["story_context"]["draft"]["panels"])
    assert len(art.drawn) == panels
    assert {p["image_status"] for p in _episode(assembled_client, d)["panels"]} == {"panel_art"}
    # The late prefetch drawing now finds every panel taken and draws nothing.
    assert panel_art.render_prefetch_art(panel_art.PrefetchArtJob(str(row.id), db_session.get_bind()))
    assert len(art.drawn) == panels


def test_a_discarded_prefetch_draws_nothing(
    assembled_client, db_session, journey_enabled, clock, provider, art
):
    d = _driver(assembled_client, db_session)
    row = _prefetch(db_session, d)
    journey_latency._mark(db_session, row, journey_latency.PREFETCH_DISCARDED_EVENT, reason="test")
    db_session.commit()
    assert panel_art.render_prefetch_art(_jobs(art, panel_art.PrefetchArtJob)[0]) == "discarded"
    assert art.drawn == []


def test_prefetch_art_is_off_with_the_flag(
    assembled_client, db_session, journey_enabled, clock, provider, art, monkeypatch
):
    monkeypatch.setattr(settings, "ATELIER_PANEL_ART_ENABLED", False)
    d = _driver(assembled_client, db_session)
    row = _prefetch(db_session, d)
    assert art.queued == []
    assert panel_art.prefetch_ledger(db_session, str(row.id)).requested == set()
