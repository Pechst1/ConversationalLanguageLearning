"""WP-96 «Les Cahiers du feuilleton» + WP-97 «Les suites» — services and API.

* Every day is in the story (W14): the authored first day is a planche with the
  learner's own lines, next to the engine's days.
* «Précédemment» and the margin notes ride on the scene step; the recap carries
  the margin notes, «Fin du chapitre» and «Tome N».
* The trombinoscope: trust (which falls), what they know, the «tu» with its date
  and its Seal «Le tu de Romy» in the Relevé, pressed once.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models.atelier import AtelierCollectible
from app.db.models.graphic_novel import GraphicNovelScene
from app.services import living_story as engine
from app.services import story_archive
from tests import test_living_story_longitudinal as story
from tests.test_journey_end_to_end import (  # noqa: F401 - fixtures
    assembled_client,
    clock,
    journey_enabled,
)
from tests.test_living_story_longitudinal import provider  # noqa: F401 - fixture


@pytest.fixture(autouse=True)
def one_exchange(monkeypatch):
    monkeypatch.setattr(engine, "keeps_talking", lambda *a, **k: False)


@pytest.fixture
def first_day_authored(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_FIRST_DAY_AUTHORED_ENABLED", True)


@pytest.fixture
def serial_world(monkeypatch):
    """The cast route lives under /serial, which answers 403 while the flag is off.

    The flag defaults off; these tests passed only where a developer .env turned it on
    (CI has no .env, nor has a fresh worktree).
    """

    monkeypatch.setattr(settings, "SERIAL_WORLD_ENABLED", True)


def _archive(client, d, **params) -> dict:
    response = client.get("/api/v1/story-engine/archive", headers=d.headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _days(archive: dict) -> list[dict]:
    return [
        day
        for season in archive["seasons"]
        for chapter in season["chapters"]
        for day in chapter["days"]
    ]


def _scene_of(db, journey_id: str) -> GraphicNovelScene | None:
    for scene in db.scalars(select(GraphicNovelScene)):
        if (scene.source_snapshot or {}).get("journey_id") == journey_id:
            return scene
    return None


def _write_payload(db, scene: GraphicNovelScene, **fields) -> None:
    scene.script_payload = {**(scene.script_payload or {}), **fields}
    db.add(scene)
    db.commit()


def test_three_walked_days_are_three_planches_with_the_learners_own_lines(
    assembled_client, db_session, journey_enabled, clock, provider, first_day_authored
):
    """WP-96 done-when, and W14: day one is authored and still in the story."""

    d = story.driver(assembled_client, db_session, cefr="A1.1")
    answers = ["Bonjour, un café s'il vous plaît.", "Oui, je viens samedi.", "Merci, à demain."]
    journey_ids = []
    for answer in answers:
        journey_ids.append(story.play_day(d, provider, answer=answer))
        clock.advance(days=1)

    archive = _archive(assembled_client, d)
    days = _days(archive)
    assert [day["journey_id"] for day in sorted(days, key=lambda row: row["date"])] == journey_ids
    first = next(day for day in days if day["journey_id"] == journey_ids[0])
    assert first["authored"] is True and first["scene_id"] is None
    assert first["title_fr"]
    assert first["learner_lines"] and first["learner_lines"][0] == answers[0]
    for day, answer in zip(sorted(days, key=lambda row: row["date"]), answers, strict=True):
        assert answer in day["learner_lines"], day
        assert day["edition_no"] is not None
    engine_days = [day for day in days if not day["authored"]]
    assert engine_days and all(day["scene_id"] for day in engine_days)

    # Newest chapter first; days oldest first inside a chapter; the authored day
    # opens the life as its prologue.
    season = archive["seasons"][0]
    assert season["loaded"] is True and season["day_count"] == 3
    chapters = season["chapters"]
    assert chapters[-1]["prologue"] is True and chapters[-1]["title_fr"] == "Prologue"
    assert chapters[-1]["closed"] is True
    for chapter in chapters:
        dates = [day["date"] for day in chapter["days"]]
        assert dates == sorted(dates)
    assert archive["current"]["season"] == season["number"]
    assert archive["current"]["chapter"] == chapters[0]["index"]


def test_the_archive_is_private_and_needs_a_session(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = story.driver(assembled_client, db_session, cefr="A1.1")
    story.play_day(d, provider, answer="Bonjour, je suis là.")
    other = story.driver(assembled_client, db_session, cefr="A1.1")
    assert _days(_archive(assembled_client, other)) == []
    assert assembled_client.get("/api/v1/story-engine/archive").status_code == 401
    # An unknown season falls back to the newest one rather than failing.
    assert _archive(assembled_client, d, season=9)["seasons"][0]["loaded"] is True


def test_precedemment_and_margin_notes_ride_on_the_scene_and_the_recap(
    assembled_client, db_session, journey_enabled, clock, provider
):
    d = story.driver(assembled_client, db_session, cefr="A2.2")
    first = story.play_day(d, provider, answer="Je m'en occupe demain.")
    clock.advance(days=1)
    cause = _scene_of(db_session, first)

    provider.scene = story.SceneScript()
    provider.turn = story.TurnScript()
    d.create()
    scene = _scene_of(db_session, d.journey["id"])
    assert scene is not None
    _write_payload(
        db_session,
        scene,
        previously_fr=["Romy a perdu sa clé.", "Vous avez promis d'aider.", "Marin attend.", "trop"],
        margin_notes=[
            {
                "text_fr": "Parce que vous avez dit à Romy « je m'en occupe »",
                "cause_scene_id": str(cause.id),
                "cause_date": "2026-03-10T09:00:00+00:00",
                "character_id": "romy",
                "panel_index": 0,
            },
            {"text_fr": "", "cause_scene_id": None},
            "garbage",
        ],
    )

    snapshot = assembled_client.get(
        f"/api/v1/daily-journeys/{d.journey['id']}", headers=d.headers
    ).json()
    prompt = next(step for step in snapshot["steps"] if step["kind"] == "scene")["prompt"]
    assert prompt["previously_fr"] == ["Romy a perdu sa clé.", "Vous avez promis d'aider.", "Marin attend."]
    assert len(prompt["margin_notes"]) == 1
    note = prompt["margin_notes"][0]
    assert note["cause_scene_id"] == str(cause.id)
    assert note["cause_date"] == "2026-03-10"
    assert note["cause_edition_no"] == 1
    first_panel = min(scene.panels, key=lambda panel: panel.panel_index)
    assert note["panel_index"] == 0 and note["panel_id"] == str(first_panel.id)

    d.journey = snapshot
    d.play(answer="D'accord, je viens.")
    # The story lane settles the chapter block when the reply is resolved; the
    # recap (at finish) reads what it left. Here: this page closed the finale.
    db_session.refresh(scene)
    _write_payload(
        db_session,
        scene,
        chapter={"index": 1, "title_fr": "La clé", "closes": True, "digest_fr": "La clé est retrouvée.", "season": 1},
    )
    scene.source_snapshot = {
        **(scene.source_snapshot or {}),
        "chapter": {**((scene.source_snapshot or {}).get("chapter") or {}), "finale": True},
    }
    db_session.add(scene)
    db_session.commit()
    response = d.finish()
    assert response.status_code == 200, response.text
    recap = response.json()["recap"]
    assert recap["margin_notes"][0]["text_fr"].startswith("Parce que vous avez dit")
    assert recap["chapter_closed"] == {
        "index": 1,
        "title_fr": "La clé",
        "digest_fr": "La clé est retrouvée.",
    }
    assert recap["season_finished"]["number"] == 1
    assert recap["season_finished"]["title_fr"]

    day = next(row for row in _days(_archive(assembled_client, d)) if row["journey_id"] == d.journey["id"])
    assert day["margin_notes"][0]["cause_edition_no"] == 1
    assert day["margin_notes"][0]["panel_id"] == str(first_panel.id)
    chapter = next(
        c for c in _archive(assembled_client, d)["seasons"][0]["chapters"] if any(x["journey_id"] == d.journey["id"] for x in c["days"])
    )
    assert chapter["closed"] is True and chapter["digest_fr"] == "La clé est retrouvée."
    assert _archive(assembled_client, d)["seasons"][0]["finished"] is True


def test_an_authored_day_has_no_precedemment_and_no_recap_chapter(
    assembled_client, db_session, journey_enabled, clock, provider, first_day_authored
):
    d = story.driver(assembled_client, db_session, cefr="A1.1")
    d.create()
    prompt = next(step for step in d.journey["steps"] if step["kind"] == "scene")["prompt"]
    assert prompt["previously_fr"] is None and prompt["margin_notes"] is None
    d.play(answer="Bonjour, un café.")
    recap = d.finish().json()["recap"]
    assert recap["margin_notes"] == []
    assert recap["chapter_closed"] is None and recap["season_finished"] is None


def _cast_row(client, d, character_id: str) -> dict:
    response = client.get("/api/v1/serial/threads/current/cast", headers=d.headers)
    assert response.status_code == 200, response.text
    return next(row for row in response.json()["cast"] if row["id"] == character_id)


def test_the_tu_is_a_scene_a_date_and_one_seal_in_the_releve(
    assembled_client, db_session, journey_enabled, clock, provider, serial_world
):
    d = story.driver(assembled_client, db_session, cefr="A2.2")
    story.play_day(d, provider, answer="Bonjour Romy.")
    clock.advance(days=1)
    romy = story.CAST["romy"]
    before = _cast_row(assembled_client, d, romy)
    assert before["register"] == "vous" and before["tu_since"] is None
    assert before["relationship"]["closeness_deprecated"] is True

    tu_journeys = []
    for _ in range(2):
        provider.scene = story.SceneScript()
        provider.turn = story.TurnScript()
        d.create()
        scene = _scene_of(db_session, d.journey["id"])
        tu_journeys.append((d.journey["id"], d.journey["local_date"], str(scene.id)))
        d.play(answer="Oui, on se tutoie !")
        # The story lane writes `tutoiement` when it settles the reply.
        db_session.refresh(scene)
        _write_payload(db_session, scene, tutoiement={"character_id": romy, "state": "accepted"})
        assert d.finish().status_code == 200
        clock.advance(days=1)

    after = _cast_row(assembled_client, d, romy)
    assert after["register"] == "tu"
    assert after["tu_since"] == {"date": tu_journeys[0][1], "scene_id": tu_journeys[0][2]}

    seals = list(
        db_session.scalars(
            select(AtelierCollectible).where(
                AtelierCollectible.user_id == d.user_id,
                AtelierCollectible.source_kind == story_archive.TUTOIEMENT_SOURCE_KIND,
            )
        )
    )
    assert len(seals) == 1, "one «tu» Seal per character, however often it is accepted"
    assert seals[0].kind == "story_seal"
    assert seals[0].metadata_payload["name"].startswith("Le tu de ")
    almanac = assembled_client.get("/api/v1/atelier/almanac", headers=d.headers).json()
    assert any(
        (item.get("metadata") or {}).get("source") == "tutoiement"
        for item in almanac["collectibles"]["story_seal"]
    )


def test_trust_is_the_one_meter_and_it_can_fall(
    assembled_client, db_session, journey_enabled, clock, provider, serial_world
):
    d = story.driver(assembled_client, db_session, cefr="A2.2")
    romy = story.CAST["romy"]
    assert _cast_row(assembled_client, d, romy)["trust"] is None  # not met yet
    story.play_day(
        d, provider, answer="Avec plaisir !",
        turn=story.TurnScript(extra={"feeling_shift": "warmer"}),
    )
    clock.advance(days=1)
    warm = _cast_row(assembled_client, d, romy)["trust"]
    assert warm is not None and 0 <= warm <= 5
    story.play_day(
        d, provider, answer="Non, je n'ai pas le temps.",
        turn=story.TurnScript(extra={"feeling_shift": "colder"}),
    )
    colder = _cast_row(assembled_client, d, romy)
    assert colder["trust"] < warm
    # What she knows about the learner: dated, and pointing at the scene.
    for item in colder["known_about_you"]:
        assert item["text_fr"]
        assert item["date"] is None or len(item["date"]) == 10


def test_known_about_you_reads_only_what_the_character_witnessed(monkeypatch):
    # The fallback path, as on a build whose story lane has no helper yet.
    monkeypatch.setattr(story_archive, "_living_helper", lambda name: None)
    live = {
        "events": [
            {"id": "journey:j1:story", "scene_id": "s1", "witnesses": ["romy"], "at": "2026-03-10T09:00:00+00:00"},
            {"id": "journey:j2:story", "scene_id": "s2", "witnesses": ["marin"]},
        ],
        "consequences": [
            {"text_fr": "Vous avez aidé Romy.", "event_id": "journey:j1:story", "character_id": "romy"},
            {"text_fr": "Vous avez vu Marin.", "event_id": "journey:j2:story", "character_id": "marin"},
        ],
        "moods": {"romy": {"trust": 7}},
    }
    known = story_archive._known_about_you(live, "romy", journey_dates={"j1": "2026-03-09"})
    assert known == [{"text_fr": "Vous avez aidé Romy.", "date": "2026-03-09", "scene_id": "s1"}]
    assert story_archive._trust(live, "romy") == 5
    assert story_archive._trust(live, "lila") is None


def test_contract_readers_are_defensive():
    assert story_archive.margin_notes_of(None) == []
    assert story_archive.margin_notes_of({"margin_notes": "x"}) == []
    assert story_archive.previously_of({"previously_fr": [1, "", "  Un.  "]}) == ["Un."]
    assert story_archive.chapter_of({"chapter": "x"}) is None
    assert story_archive.chapter_of({"chapter": {"index": "2", "closes": 1}})["index"] == 2
    assert story_archive.tutoiement_of({"tutoiement": {"character_id": "romy"}}) is None


def test_known_about_you_and_trust_prefer_the_story_lanes_helpers(monkeypatch):
    monkeypatch.setattr(
        story_archive,
        "_living_helper",
        lambda name: {
            "known_about_learner": lambda live, cid: [
                {"text_fr": "Ancien.", "date": "2026-03-01", "scene_id": "a"},
                {"text_fr": "Récent.", "date": "2026-03-09", "scene_id": "b"},
            ],
            "trust_of": lambda live, cid: 1,
        }[name],
    )
    known = story_archive._known_about_you({}, "romy", journey_dates={})
    assert [item["text_fr"] for item in known] == ["Récent.", "Ancien."]  # newest first
    assert story_archive._trust({}, "romy") == 1
