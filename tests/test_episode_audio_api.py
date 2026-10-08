"""WP-32 — the radio episode's four routes, driven the way the page drives them.

Behavioural: the real router, the real service, a fake synthesizer in place of
the paid one. What is pinned is what the page depends on — every route
authenticated, a scene the learner does not own is invisible rather than
forbidden-with-details, `disabled` arriving as data rather than as a 404, and
the clip route answering audio bytes and not JSON.

**No live TTS call is made anywhere in this file.**
"""
from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.user import User
from app.main import create_app
from app.services import episode_audio as module
from tests.test_episode_audio import FakeSynthesizer, make_scene

TEST_PASSWORD = "securepass123"


@pytest.fixture()
def radio_client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def fake_tts(monkeypatch: pytest.MonkeyPatch) -> FakeSynthesizer:
    """Every synthesis built inside a request gets this provider."""

    provider = FakeSynthesizer()
    monkeypatch.setattr(module, "_default_synthesizer", lambda: provider)
    return provider


@pytest.fixture()
def audio_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module.settings, "ATELIER_EPISODE_AUDIO_ENABLED", True)


def login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
            "target_language": "fr",
            "native_language": "en",
            "proficiency_level": "A2",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def signed_in(client: TestClient, db_session: Session) -> tuple[dict[str, str], User]:
    email = f"radio-api-{uuid.uuid4().hex[:8]}@example.com"
    headers = login(client, email)
    user = db_session.query(User).filter(User.email == email).one()
    return headers, user


def test_every_radio_route_needs_a_signed_in_learner(radio_client):
    scene_id = str(uuid.uuid4())
    clip_id = str(uuid.uuid4())
    assert radio_client.get(f"/api/v1/story-engine/episodes/{scene_id}/audio").status_code == 401
    assert radio_client.post(f"/api/v1/story-engine/episodes/{scene_id}/audio").status_code == 401
    assert (
        radio_client.get(f"/api/v1/story-engine/episodes/{scene_id}/audio/{clip_id}").status_code
        == 401
    )
    assert (
        radio_client.post(
            f"/api/v1/story-engine/episodes/{scene_id}/audio/prediction",
            json={"guess": "accord", "verdict": "confirmed"},
        ).status_code
        == 401
    )


def test_the_flag_being_off_arrives_as_data_not_as_an_error(
    radio_client, db_session, fake_tts
):
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    db_session.commit()

    read = radio_client.get(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    )
    assert read.status_code == 200
    assert read.json()["status"] == "disabled"

    made = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    )
    assert made.status_code == 200
    assert made.json() == {
        "status": "disabled",
        "revision": "",
        "clips": [],
        "truncated": False,
        "reason": "flag_off",
    }
    assert fake_tts.calls == []


def test_a_scene_belonging_to_someone_else_is_simply_not_found(
    radio_client, db_session, audio_on, fake_tts
):
    _, owner = signed_in(radio_client, db_session)
    scene = make_scene(db_session, owner)
    db_session.commit()

    intruder, _ = signed_in(radio_client, db_session)
    assert (
        radio_client.get(
            f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=intruder
        ).status_code
        == 404
    )
    assert (
        radio_client.post(
            f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=intruder
        ).status_code
        == 404
    )
    assert fake_tts.calls == []


def test_the_episode_is_spoken_once_and_then_served_from_the_cache(
    radio_client, db_session, audio_on, fake_tts
):
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    db_session.commit()

    first = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    ).json()
    assert first["status"] == "ready"
    assert len(first["clips"]) == 3
    assert first["revision"]
    spoken = len(fake_tts.calls)
    assert spoken == 3

    second = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    ).json()
    assert second["clips"] == first["clips"]
    assert len(fake_tts.calls) == spoken, "a replayed episode makes no paid call"

    listed = radio_client.get(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    ).json()
    assert listed["status"] == "ready"
    assert len(fake_tts.calls) == spoken


def test_a_clip_comes_back_as_audio_and_only_through_its_own_scene(
    radio_client, db_session, audio_on, fake_tts
):
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    other = make_scene(db_session, user)
    db_session.commit()

    manifest = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    ).json()
    clip_id = manifest["clips"][0]["id"]

    response = radio_client.get(
        f"/api/v1/story-engine/episodes/{scene.id}/audio/{clip_id}", headers=headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/")
    assert response.content.startswith(b"mp3:")

    # The clip is addressed through the scene that owns it; asking a different
    # scene for it is a 404, not a redirect to the bytes.
    assert (
        radio_client.get(
            f"/api/v1/story-engine/episodes/{other.id}/audio/{clip_id}", headers=headers
        ).status_code
        == 404
    )


def test_the_manifest_never_carries_the_bytes(radio_client, db_session, audio_on, fake_tts):
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    db_session.commit()

    manifest = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    ).json()
    for clip in manifest["clips"]:
        assert set(clip) == {
            "id",
            "line_key",
            "ordinal",
            "character_id",
            "voice",
            "content_type",
            "char_count",
            "text_fr",
        }


def test_a_provider_failure_is_an_honest_state_with_no_clips(
    radio_client, db_session, audio_on, monkeypatch
):
    monkeypatch.setattr(module, "_default_synthesizer", lambda: FakeSynthesizer(fail_on="tomates"))
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    db_session.commit()

    body = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio", headers=headers
    ).json()

    assert body["status"] == "failed"
    assert body["clips"] == []
    assert body["reason"] == "tts_failed"


def test_the_prediction_is_recorded_and_no_score_comes_back(
    radio_client, db_session, fake_tts
):
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    db_session.commit()

    response = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio/prediction",
        headers=headers,
        json={"guess": "accord", "verdict": "other", "supported": "resistance"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] == {
        "guess": "accord",
        "verdict": "other",
        "supported": "resistance",
    }
    assert "score" not in body and "correct" not in body

    db_session.refresh(scene)
    assert scene.source_snapshot["radio"]["prediction"]["verdict"] == "other"
    assert scene.source_snapshot["journey_id"], "the reading position's home is untouched"


def test_an_unknown_verdict_is_refused_rather_than_stored_as_something_else(
    radio_client, db_session
):
    headers, user = signed_in(radio_client, db_session)
    scene = make_scene(db_session, user)
    db_session.commit()

    response = radio_client.post(
        f"/api/v1/story-engine/episodes/{scene.id}/audio/prediction",
        headers=headers,
        json={"guess": "accord", "verdict": "brilliant"},
    )
    assert response.status_code == 422
