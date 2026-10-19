"""The learner's avatar (``/avatar``) and the items achievements unlock.

The editor's config is stored as-is on ``users.avatar`` once its shape checks
out; an item a reward unlocks (``REWARD_SLOTS``) is refused until its
achievement is earned. The ``helps`` measure behind the three «entraide»
achievements counts missions done plus story replies done.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.mission import RealWorldMission
from app.db.models.user import User
from app.main import create_app
from app.services.achievement import CATALOGUE, MEASURES, REWARD_SLOTS

TEST_PASSWORD = "securepass123"
AVATAR = "/api/v1/avatar"


def register_and_login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> str:
    payload = {
        "email": email,
        "password": password,
        "target_language": "fr",
        "native_language": "en",
    }
    client.post("/api/v1/auth/register", json=payload)
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login_response.json()["access_token"]


def _headers(client: TestClient, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {register_and_login(client, email)}"}


def _user(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def _missions(db: Session, user: User, count: int, *, status: str = "completed") -> None:
    for _ in range(count):
        db.add(RealWorldMission(user_id=user.id, status=status, title="Une lettre", brief="Répondre."))
    db.commit()


def _journey(db: Session, user: User, on: date, steps: list[tuple[str, str]]) -> None:
    journey = DailyJourney(user_id=user.id, local_date=on, status="completed", scenario_snapshot={})
    db.add(journey)
    db.flush()
    for ordinal, (kind, status) in enumerate(steps):
        db.add(DailyJourneyStep(journey_id=journey.id, ordinal=ordinal, kind=kind, status=status))
    db.commit()


REWARDED = [item for item in CATALOGUE if item.reward]


# ---------------------------------------------------------------------------
# The catalogue's rewards
# ---------------------------------------------------------------------------


def test_every_reward_is_one_item_in_one_slot() -> None:
    rewards = [item.reward for item in REWARDED]
    assert len(rewards) == len(set(rewards)), "no item is the reward of two achievements"
    assert set(rewards) <= set(REWARD_SLOTS), "every reward item has a slot"
    for item in REWARD_SLOTS:
        owners = [defn.key for defn in CATALOGUE if defn.reward == item]
        assert len(owners) == 1, f"{item} belongs to exactly one achievement, not {owners}"
    assert {defn.key: defn.reward for defn in REWARDED} == {
        "first_scene": "pins_atelier",
        "scenes_10": "badge_presse",
        "session_streak_3": "montre",
        "session_streak_7": "soleil",
        "session_streak_30": "canotier",
        "first_letter": "crayon",
        "helps_10": "foulard",
        "helps_50": "bracelet",
        "helps_100": "boucles_or",
        "words_kept_50": "mariniere",
        "first_chapter": "collier_cle",
    }


def test_the_entraide_achievements_follow_the_first_letter() -> None:
    keys = [item.key for item in CATALOGUE]
    at = keys.index("first_letter")
    assert keys[at + 1 : at + 4] == ["helps_10", "helps_50", "helps_100"]
    by_key = {item.key: item for item in CATALOGUE}
    assert [(by_key[k].tier, by_key[k].target) for k in ("helps_10", "helps_50", "helps_100")] == [
        ("bronze", 10),
        ("silver", 50),
        ("gold", 100),
    ]
    for key in ("helps_10", "helps_50", "helps_100"):
        assert (by_key[key].category, by_key[key].measure) == ("entraide", "helps")


def test_the_avatar_routes_are_free_for_everyone() -> None:
    routes = [
        route
        for route in create_app().routes
        if isinstance(route, APIRoute) and route.path == AVATAR
    ]
    assert {method for route in routes for method in route.methods} == {"GET", "PUT"}
    assert all(not route.dependencies for route in routes), "no paid-route guard on /avatar"


# ---------------------------------------------------------------------------
# GET / PUT
# ---------------------------------------------------------------------------


def test_a_new_learner_has_no_avatar_and_every_reward_locked(client: TestClient) -> None:
    response = client.get(AVATAR, headers=_headers(client, "avatar-new@example.com"))

    assert response.status_code == 200
    body = response.json()
    assert body["avatar"] is None
    assert body["unlocked"] == []
    assert [r["item"] for r in body["rewards"]] == [item.reward for item in REWARDED]
    by_item = {item.reward: item for item in REWARDED}
    for reward in body["rewards"]:
        defn = by_item[reward["item"]]
        assert reward["slot"] == REWARD_SLOTS[reward["item"]]
        assert reward["achievement_key"] == defn.key
        assert reward["name"] == defn.name
        assert reward["tier"] == defn.tier
        assert (reward["current"], reward["target"]) == (0, defn.target)
        assert reward["unlocked"] is False
        assert reward["unlocked_at"] is None


def test_the_avatar_needs_a_signed_in_learner(client: TestClient) -> None:
    assert client.get(AVATAR).status_code == 401
    assert client.put(AVATAR, json={"avatar": {"v": 1}}).status_code == 401


def test_a_valid_avatar_round_trips(client: TestClient, db_session: Session) -> None:
    email = "avatar-save@example.com"
    headers = _headers(client, email)
    config = {
        "v": 1,
        "face": "round",
        "hair": "short_02",
        "hairColor": "c3",
        "skin": 4,
        "freckles": True,
        "hat": "beret",
    }

    saved = client.put(AVATAR, json={"avatar": config}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["avatar"] == config
    assert client.get(AVATAR, headers=headers).json()["avatar"] == config
    assert _user(db_session, email).avatar == config

    # A PUT replaces the whole config; nothing is merged in.
    smaller = {"v": 1, "face": "oval"}
    assert client.put(AVATAR, json={"avatar": smaller}, headers=headers).json()["avatar"] == smaller
    assert client.get(AVATAR, headers=headers).json()["avatar"] == smaller


def test_a_locked_item_is_refused_until_its_achievement_is_earned(
    client: TestClient, db_session: Session
) -> None:
    email = "avatar-locked@example.com"
    headers = _headers(client, email)
    config = {"v": 1, "face": "round", "ears": "crayon"}

    refused = client.put(AVATAR, json={"avatar": config}, headers=headers)
    assert refused.status_code == 403
    assert refused.json()["detail"] == {"code": "avatar_item_locked", "item": "crayon"}
    assert _user(db_session, email).avatar is None, "nothing was stored"

    # first_letter (an answered Courrier letter) unlocks the crayon.
    _missions(db_session, _user(db_session, email), 1)
    saved = client.put(AVATAR, json={"avatar": config}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["avatar"] == config

    state = client.get(AVATAR, headers=headers).json()
    assert state["unlocked"] == ["crayon"]
    crayon = next(r for r in state["rewards"] if r["item"] == "crayon")
    assert crayon["unlocked"] is True
    assert crayon["unlocked_at"] is not None
    assert (crayon["current"], crayon["target"]) == (1, 1)
    # helps counts the same letter: 1 of 10, still locked.
    foulard = next(r for r in state["rewards"] if r["item"] == "foulard")
    assert (foulard["current"], foulard["target"], foulard["unlocked"]) == (1, 10, False)

    # Another locked item in another slot is still refused, by name.
    other = client.put(AVATAR, json={"avatar": {**config, "neck": "foulard"}}, headers=headers)
    assert other.status_code == 403
    assert other.json()["detail"] == {"code": "avatar_item_locked", "item": "foulard"}
    assert _user(db_session, email).avatar == config


def test_an_unlocked_item_only_counts_in_its_own_slot(client: TestClient) -> None:
    headers = _headers(client, "avatar-slot@example.com")
    # A reward id outside its slot is just another string: not an item worn.
    response = client.put(AVATAR, json={"avatar": {"v": 1, "hat": "crayon"}}, headers=headers)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "avatar",
    [
        pytest.param({"face": "round"}, id="missing-v"),
        pytest.param({"v": 2}, id="wrong-version"),
        pytest.param({"v": True}, id="version-true-is-not-1"),
        pytest.param({"v": "1"}, id="version-as-text"),
        pytest.param({"v": 1, "hat": ["beret"]}, id="list-value"),
        pytest.param({"v": 1, "hat": {"id": "beret"}}, id="object-value"),
        pytest.param({"v": 1, "hat": None}, id="null-value"),
        pytest.param({"v": 1, "size": 1.5}, id="float-value"),
        pytest.param({"v": 1, "size": 1001}, id="number-too-large"),
        pytest.param({"v": 1, "size": -1}, id="negative-number"),
        pytest.param({"v": 1, "hat": "b" * 41}, id="string-too-long"),
        pytest.param({"v": 1, "hat": ""}, id="empty-string"),
        pytest.param({"v": 1, "hat": "Beret"}, id="uppercase-string"),
        pytest.param({"v": 1, "hat": "beret\n"}, id="string-trailing-newline"),
        pytest.param({"v": 1, "hat": "bé"}, id="accented-string"),
        pytest.param({"v": 1, "1hat": "beret"}, id="key-starts-with-digit"),
        pytest.param({"v": 1, "hat_color": "red"}, id="key-with-underscore"),
        pytest.param({"v": 1, "h" * 33: "x"}, id="key-too-long"),
        pytest.param({"v": 1, **{f"k{i}": i for i in range(32)}}, id="too-many-keys"),
        pytest.param(["v", 1], id="not-an-object"),
        pytest.param("v1", id="a-string"),
        pytest.param(None, id="null"),
    ],
)
def test_a_malformed_avatar_is_refused_with_a_clear_detail(client: TestClient, avatar) -> None:
    headers = _headers(client, f"avatar-bad-{uuid.uuid4().hex[:8]}@example.com")
    response = client.put(AVATAR, json={"avatar": avatar}, headers=headers)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, str) and "avatar" in detail
    assert client.get(AVATAR, headers=headers).json()["avatar"] is None


def test_the_limits_themselves_are_accepted(client: TestClient) -> None:
    headers = _headers(client, "avatar-limits@example.com")
    config = {"v": 1, "h" * 32: "b" * 40, "zero": 0, "max": 1000, "off": False}
    config.update({f"k{i}": i for i in range(32 - len(config))})
    assert len(config) == 32
    response = client.put(AVATAR, json={"avatar": config}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["avatar"] == config


def test_a_body_without_an_avatar_is_refused(client: TestClient) -> None:
    headers = _headers(client, "avatar-nobody@example.com")
    assert client.put(AVATAR, json={}, headers=headers).status_code == 422


# ---------------------------------------------------------------------------
# The helps measure
# ---------------------------------------------------------------------------


def test_helps_counts_missions_done_and_story_replies_done(
    client: TestClient, db_session: Session
) -> None:
    _headers(client, "avatar-helps@example.com")
    _headers(client, "avatar-helps-other@example.com")
    learner = _user(db_session, "avatar-helps@example.com")
    other = _user(db_session, "avatar-helps-other@example.com")

    _missions(db_session, learner, 2)
    _missions(db_session, learner, 1, status="active")
    _journey(
        db_session,
        learner,
        date(2026, 3, 1),
        [
            ("scene", "completed"),
            ("recall", "completed"),
            ("respond", "completed"),
            ("resolution", "completed"),
        ],
    )
    _journey(db_session, learner, date(2026, 3, 2), [("respond", "completed")])
    _journey(db_session, learner, date(2026, 3, 3), [("respond", "active"), ("respond", "skipped")])
    # Somebody else's help is theirs.
    _missions(db_session, other, 3)
    _journey(db_session, other, date(2026, 3, 1), [("respond", "completed")])

    assert MEASURES["helps"](db_session, learner) == 2 + 2
    assert MEASURES["helps"](db_session, other) == 3 + 1


def test_ten_helps_unlock_the_foulard(client: TestClient, db_session: Session) -> None:
    email = "avatar-foulard@example.com"
    headers = _headers(client, email)
    learner = _user(db_session, email)
    _missions(db_session, learner, 6)
    for day in range(1, 4):
        _journey(db_session, learner, date(2026, 4, day), [("respond", "completed")])
    config = {"v": 1, "neck": "foulard"}
    assert client.put(AVATAR, json={"avatar": config}, headers=headers).status_code == 403, "nine is not ten"

    _journey(db_session, learner, date(2026, 4, 4), [("respond", "completed")])
    saved = client.put(AVATAR, json={"avatar": config}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert "foulard" in saved.json()["unlocked"]
    # The missions also earned first_letter, and the finished days first_scene.
    assert client.get(AVATAR, headers=headers).json()["unlocked"] == ["pins_atelier", "crayon", "foulard"]


# ---------------------------------------------------------------------------
# The achievements API names the reward; the export carries the avatar
# ---------------------------------------------------------------------------


def test_the_achievements_api_names_each_reward(client: TestClient, db_session: Session) -> None:
    email = "avatar-ach@example.com"
    headers = _headers(client, email)
    rewards = {item.key: item.reward for item in CATALOGUE}

    listed = client.get("/api/v1/achievements", headers=headers).json()
    assert {a["achievement_key"]: a["reward_item"] for a in listed} == rewards

    mine = client.get("/api/v1/achievements/my", params={"include_locked": True}, headers=headers).json()
    assert {a["achievement_key"]: a["reward_item"] for a in mine} == rewards

    _missions(db_session, _user(db_session, email), 1)
    checked = client.post("/api/v1/achievements/check", headers=headers).json()
    assert [(a["achievement_key"], a["reward_item"]) for a in checked["newly_unlocked"]] == [
        ("first_letter", "crayon")
    ]


def test_the_data_export_carries_the_avatar(client: TestClient) -> None:
    headers = _headers(client, "avatar-export@example.com")
    assert client.get("/api/v1/users/me/export", headers=headers).json()["user"]["avatar"] is None

    config = {"v": 1, "face": "round", "skin": 2}
    assert client.put(AVATAR, json={"avatar": config}, headers=headers).status_code == 200
    exported = client.get("/api/v1/users/me/export", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["user"]["avatar"] == config
