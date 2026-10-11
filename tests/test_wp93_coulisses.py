"""WP-93 «Coulisses» (app/services/coulisses.py) — fake provider only.

* requested inside the binding transaction, written only after its commit; a rollback
  queues nothing and leaves no «writing» marker;
* one director call; the page is 3–4 panels by cast members, stored as its own scene
  (``cadence="coulisses"``, ``source_snapshot.coulisses_for``), outside the day's
  episode list, with its cost on the ledger;
* a failed page is «unavailable», never an error; the flag off does nothing.
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
from app.services import coulisses
from app.services import living_story as engine
from tests import test_living_story as story

assembled_client = story.assembled_client
journey_enabled = story.journey_enabled
clock = story.clock
one_exchange = story.one_exchange


def _page(source: dict, panels: int = 3) -> dict:
    pov = source["pov_character_id"]
    return {
        "title_fr": "Le même soir, chez Marin",
        "pov_character_id": pov,
        "panels": [
            {
                "narration_fr": "Plus tard, la pluie continue.",
                "dialogue": [{"character_id": pov, "text_fr": "Quelle soirée !", "mood": "moved"}],
                "visual_direction": "Close-up at the window, rain outside.",
                "alt_native": "A character looks at the rain.",
            }
            for _ in range(panels)
        ],
    }


class CoulissesProvider(story.FakeProvider):
    def __init__(self):
        super().__init__()
        self.page_panels = 3
        self.pages: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] == "CoulissesDraft":
            self.pages.append(data["data"])
            self.calls.append(("CoulissesDraft", data["data"]))
            return SimpleNamespace(
                content=json.dumps(_page(data["data"], self.page_panels)),
                model="fake",
                provider="test",
                total_tokens=20,
                cost=0.003,
            )
        return super().generate_chat_completion(messages, **kwargs)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_STORY_ENGINE_ENABLED", True)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    fake = CoulissesProvider()
    monkeypatch.setattr(engine, "_client", lambda: fake)
    return fake


@pytest.fixture
def queued(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_COULISSES_ENABLED", True)
    jobs: list = []
    monkeypatch.setattr(coulisses, "dispatcher", jobs.append)
    return jobs


def _day(client, db, provider):
    d = story.driver(client, db)
    d.create()
    db.expire_all()
    scene = db.scalar(select(GraphicNovelScene).where(GraphicNovelScene.user_id == d.user_id))
    from app.db.models.user import User

    return d, scene, db.get(User, d.user_id)


def test_coulisses_are_written_after_the_commit_and_stored_as_their_own_page(
    assembled_client, db_session, journey_enabled, clock, provider, queued
):
    d, scene, user = _day(assembled_client, db_session, provider)
    journey_id = d.journey["id"]
    assert coulisses.coulisses_status(db_session, journey_id) == "unavailable"

    assert coulisses.request_coulisses(db_session, user=user, journey_id=journey_id, scene=scene)
    assert queued == [], "nothing runs before the commit"
    assert not [s for s, _ in provider.calls if s == "CoulissesDraft"]
    db_session.commit()
    assert len(queued) == 1
    assert coulisses.coulisses_status(db_session, journey_id) == "writing"
    # Asking twice is idempotent.
    assert coulisses.request_coulisses(db_session, user=user, journey_id=journey_id, scene=scene)
    db_session.commit()
    assert len(queued) == 1

    assert coulisses.write_coulisses(queued[0]) == "ready"
    db_session.expire_all()
    assert coulisses.coulisses_status(db_session, journey_id) == "ready"
    page = coulisses.coulisses_scene_for(db_session, journey_id)
    assert page is not None and page.id != scene.id
    assert page.source_snapshot["coulisses_for"] == str(scene.id)
    assert page.source_snapshot["journey_id"] == journey_id
    assert page.source_snapshot["story_engine"] == engine.VERSION
    assert page.cadence == "coulisses" and page.status == "available"
    assert 3 <= len(page.panels) <= 4
    assert all(p.image_url for p in page.panels), "the location plate on every panel"
    assert all(
        (p.generation_metadata or {}).get("image_source") == "setting_reference" for p in page.panels
    )

    request = provider.pages[0]
    speakers = [
        line["character_id"]
        for p in sorted(scene.panels, key=lambda p: p.panel_index)
        for line in p.overlay_payload["dialogue"]
    ]
    assert request["pov_character_id"] in {m["id"] for m in request["world"]["cast"]}
    if len(set(speakers)) > 1:
        assert request["pov_character_id"] != speakers[-1], "another cast member's eyes"
    assert request["scene"]["panels"], "the director retells the same page"
    assert request["word_limit"] <= engine._SCENE_WORD_LIMITS["A1"]
    assert all("secret" not in member for member in request["world"]["cast"]), "no plot material"

    cost = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.user_id == d.user_id,
            PilotEvent.event_type == "journey_story_scene_cost",
            PilotEvent.entity_type == "living_story_coulisses",
        )
    ).all()
    assert len(cost) == 1 and cost[0].cost_usd == pytest.approx(0.003)
    assert cost[0].entity_id == str(page.id)

    # Not the day's episode: the reader's list still shows one scene.
    listed = assembled_client.get("/api/v1/story-engine/episodes", headers=d.headers).json()
    assert [item["id"] for item in listed["episodes"]] == [str(scene.id)]
    # A second job for the same journey writes nothing more.
    assert coulisses.write_coulisses(queued[0]) == "exists"


def test_a_rolled_back_binding_queues_nothing_and_marks_nothing(
    assembled_client, db_session, journey_enabled, clock, provider, queued
):
    d, scene, user = _day(assembled_client, db_session, provider)
    journey_id = d.journey["id"]
    nested = db_session.begin_nested()
    assert coulisses.request_coulisses(db_session, user=user, journey_id=journey_id, scene=scene)
    nested.rollback()
    db_session.rollback()
    db_session.commit()
    assert queued == []
    assert coulisses.coulisses_status(db_session, journey_id) == "unavailable"


def test_a_failed_page_is_unavailable_never_an_error(
    assembled_client, db_session, journey_enabled, clock, provider, queued
):
    d, scene, user = _day(assembled_client, db_session, provider)
    journey_id = d.journey["id"]
    provider.page_panels = 2
    assert coulisses.request_coulisses(db_session, user=user, journey_id=journey_id, scene=scene)
    db_session.commit()
    assert coulisses.write_coulisses(queued[0]) == "unavailable"
    db_session.expire_all()
    assert coulisses.coulisses_scene_for(db_session, journey_id) is None
    assert coulisses.coulisses_status(db_session, journey_id) == "unavailable"
    failed = db_session.scalars(
        select(PilotEvent).where(
            PilotEvent.event_type == "journey_story_generation_failed",
            PilotEvent.entity_type == "living_story_coulisses",
            PilotEvent.entity_id == journey_id,
        )
    ).all()
    assert len(failed) == 1 and failed[0].cost_usd == pytest.approx(0.003), "spend is still spend"
    assert "too_few_panels" in failed[0].payload["reason"]


def test_flag_off_does_nothing(
    assembled_client, db_session, journey_enabled, clock, provider, queued, monkeypatch
):
    d, scene, user = _day(assembled_client, db_session, provider)
    monkeypatch.setattr(settings, "ATELIER_COULISSES_ENABLED", False)
    assert not coulisses.request_coulisses(db_session, user=user, journey_id=d.journey["id"], scene=scene)
    db_session.commit()
    assert queued == []
    assert not db_session.scalars(
        select(PilotEvent).where(PilotEvent.event_type == coulisses.REQUESTED_EVENT, PilotEvent.user_id == UUID(str(d.user_id)))
    ).all()


def test_a_long_page_is_cut_to_four_panels_and_strangers_are_refused():
    payload = {
        "level": "A1",
        "world": {"cast": [{"id": "romy_tremblay"}, {"id": "marin_leveque"}]},
        "pov_character_id": "marin_leveque",
        "word_limit": 200,
        "line_translation": None,
    }
    draft = coulisses.CoulissesDraft.model_validate(_page(payload, panels=6))
    kept = coulisses.validate_coulisses(draft, payload)
    assert len(kept.panels) == 4
    assert all(line.text_native is None for p in kept.panels for line in p.dialogue)
    stranger = _page(payload)
    stranger["panels"][0]["dialogue"][0]["character_id"] = "le_facteur"
    with pytest.raises(coulisses.CoulissesRefused):
        coulisses.validate_coulisses(coulisses.CoulissesDraft.model_validate(stranger), payload)
    tight = dict(payload, word_limit=5)
    with pytest.raises(coulisses.CoulissesRefused):
        coulisses.validate_coulisses(coulisses.CoulissesDraft.model_validate(_page(payload)), tight)
