"""The season walk's fast-forward hands its learner over with the paid budget free.

Season shard b plays days 1-5 through the API (scripts/walk_fast_forward.py) in about
22 s, then the browser takes the learner over on day 6. The learner's paid routes allow
RATE_LIMIT_PAID_MAX_REQUESTS a RATE_LIMIT_PAID_WINDOW_SECONDS window, and the
fast-forward had spent most of it: the browser's first answers on day 6 were refused
with ``429 rate_limited`` and the day never finished (PR 885's run 44219352111, «refused:
429 POST /api/v1/daily-journeys/…/attempts ×2»). The fast-forward now waits until a
window that started after its last request, before it prints its days.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fast_forward():
    spec = importlib.util.spec_from_file_location("walk_fast_forward", ROOT / "scripts" / "walk_fast_forward.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("walk_fast_forward", module)
    spec.loader.exec_module(module)
    return module


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _client(fast_forward, handler):
    """A WalkClient on a mock transport (no network): sign-in answers a token."""

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"access_token": "t"})
        return handler(request)

    client = fast_forward.WalkClient.__new__(fast_forward.WalkClient)
    httpx.Client.__init__(client, base_url="http://walk.test", transport=httpx.MockTransport(route))
    client.email, client.password = "e", "p"
    client.headers_ = {"Authorization": ""}
    client.last_request_at = None
    client.sign_in()
    return client


def test_the_hand_over_waits_out_the_window_of_the_last_request(fast_forward):
    client = _client(fast_forward, lambda request: httpx.Response(200, json={}))
    client.post("/api/v1/daily-journeys")
    clock = _Clock(client.last_request_at + 7.0)
    waited = client.leave_budget_free(60, clock=clock, sleep=clock.sleep)
    assert waited == pytest.approx(54.0)
    assert clock.now - client.last_request_at > 60, "the browser's first request would share the fast-forward's window"


def test_nothing_to_wait_for_once_the_window_is_over(fast_forward):
    client = _client(fast_forward, lambda request: httpx.Response(200, json={}))
    client.post("/api/v1/daily-journeys")
    clock = _Clock(client.last_request_at + 120.0)
    assert client.leave_budget_free(60, clock=clock, sleep=clock.sleep) == pytest.approx(1.0)


def test_a_refused_request_is_waited_out_and_counts_when_it_went_through(fast_forward, monkeypatch):
    answers = iter([
        httpx.Response(429, json={"detail": {"code": "rate_limited", "retry_after_seconds": 3}}),
        httpx.Response(200, json={}),
    ])
    slept: list[float] = []
    monkeypatch.setattr(fast_forward.time, "sleep", slept.append)
    client = _client(fast_forward, lambda request: next(answers))
    response = client.post("/api/v1/daily-journeys")
    assert response.status_code == 200
    assert slept == [3.5]
    assert client.last_request_at is not None


def test_main_leaves_the_budget_free_before_it_prints(fast_forward):
    source = (ROOT / "scripts" / "walk_fast_forward.py").read_text(encoding="utf-8")
    body = source.split("def main(", 1)[1]
    assert body.index("leave_budget_free(") < body.index('print(json.dumps({"days": rows}'), (
        "the walk takes the learner over as soon as the days are printed"
    )
