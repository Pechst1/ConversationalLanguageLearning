"""The season walk's fast-forward client (scripts/walk_fast_forward.py, #802).

The walk's access tokens live one minute (WP-107) and its rate limit can ask the client to
wait most of that minute. A request that is rate limited, waits, and then finds its token
expired must sign in again and go on, not hand the learner's day a 401.
"""

from __future__ import annotations

import json

import httpx
import pytest

TOKEN_SECONDS = 60.0


class FakeWalkApi:
    """The walk API as the fast-forward meets it: one-minute tokens on a clock that only
    moves when the client waits, and a rate limit that answers the first attempt with a
    long wait."""

    def __init__(self) -> None:
        self.now = 0.0
        self.tokens: dict[str, float] = {}
        self.attempts = 0
        self.log: list[tuple[str, int]] = []

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def handle(self, request: httpx.Request) -> httpx.Response:
        response = self._answer(request)
        self.log.append((request.url.path, response.status_code))
        return response

    def _answer(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            token = f"t{len(self.tokens) + 1}"
            self.tokens[token] = self.now
            return httpx.Response(200, json={"access_token": token})
        bearer = request.headers.get("Authorization", "").removeprefix("Bearer ")
        issued = self.tokens.get(bearer)
        if issued is None or self.now - issued > TOKEN_SECONDS:
            return httpx.Response(401, json={"detail": "Could not validate credentials"})
        self.attempts += 1
        if self.attempts == 1:
            return httpx.Response(
                429, json={"detail": {"retry_after_seconds": 50}}, headers={"Retry-After": "50"}
            )
        return httpx.Response(200, json={"ok": True})


@pytest.fixture()
def api(monkeypatch: pytest.MonkeyPatch) -> FakeWalkApi:
    from scripts import walk_fast_forward as ff

    fake = FakeWalkApi()
    monkeypatch.setattr(
        httpx.HTTPTransport, "handle_request", lambda _self, request: fake.handle(request)
    )
    monkeypatch.setattr(ff.time, "sleep", fake.sleep)
    return fake


def test_wait_outlives_token(api: FakeWalkApi) -> None:
    """A rate-limit wait that outlives the token signs in again (the CI failure of #802)."""
    from scripts import walk_fast_forward as ff

    client = ff.WalkClient("http://walk.test", "learner@example.com", "pw")
    try:
        api.now = 15.0  # the token is already a few seconds old when the day reaches the attempt
        response = client.post(
            "/api/v1/daily-journeys/j/steps/s/attempts",
            headers=client.headers_,
            json={"mode": "text", "text": "Oui"},
        )
    finally:
        client.close()

    assert response.status_code == 200, (
        "after waiting out the rate limit the token had expired, and the fast-forward "
        f"returned {response.status_code} {response.text} instead of signing in again; "
        f"requests: {json.dumps(api.log)}"
    )
    assert api.log[-1] == ("/api/v1/daily-journeys/j/steps/s/attempts", 200)


def test_expired_then_limited(api: FakeWalkApi) -> None:
    """The other order: the token has expired, the fresh one meets the rate limit."""
    from scripts import walk_fast_forward as ff

    client = ff.WalkClient("http://walk.test", "learner@example.com", "pw")
    try:
        api.now = 61.0
        response = client.post(
            "/api/v1/daily-journeys/j/steps/s/attempts",
            headers=client.headers_,
            json={"mode": "text", "text": "Oui"},
        )
    finally:
        client.close()

    assert response.status_code == 200, json.dumps(api.log)
