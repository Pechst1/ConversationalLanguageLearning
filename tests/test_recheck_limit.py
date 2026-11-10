"""Package V stage 1: «Check again» is limited per learner and day, and the learner is told.

The Courrier and Journal re-check routes had no limit at all (and were not on the paid-route
list, so the daily spend cap skipped them): a provider outage made every tap a model call.
One counter covers both surfaces, in UTC-day windows; past it the route answers 429 with
``detail.code = recheck_limit_reached``, which ``lib/app-errors.ts`` says in en, de and fr.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest

from app.config import settings
from app.core.rate_limit import (
    DAY_SECONDS,
    PAID_ROUTES,
    RECHECK_LIMIT_CODE,
    MemoryRateLimitBackend,
    limiter,
)
from tests import test_journal_api as _journal

# The journal API's fixtures, by name (assigned, not imported, so a test's parameter reads as one).
fake_checker = _journal.fake_checker
journal_client = _journal.journal_client
journal_table = _journal.journal_table
login = _journal.login
_email = _journal._email
_seed_scene = _journal._seed_scene


@pytest.fixture(autouse=True)
def _memory_limiter() -> Generator[None, None, None]:
    limiter.use_backend(MemoryRateLimitBackend())
    yield
    limiter.use_backend(None)


def test_the_ask_again_routes_are_paid_routes():
    assert {
        ("POST", "/missions/{mission_id}/turns/{turn_id}/correction"),
        ("POST", "/missions/{mission_id}/turns/{turn_id}/reply"),
        ("POST", "/journal/{entry_id}/retry"),
    } <= PAID_ROUTES


def test_check_again_stops_after_the_daily_limit_on_both_surfaces(
    journal_client, db_session, fake_checker, monkeypatch
):
    monkeypatch.setattr(settings, "VERDICT_RECHECK_DAILY_LIMIT", 3)
    email = _email()
    headers = login(journal_client, email)
    _seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]
    journal_client.post(
        f"/api/v1/journal/{entry_id}/write", headers=headers, json={"text": "J’ai rapporté la livre à Romy."}
    )

    journal = f"/api/v1/journal/{entry_id}/retry"
    courrier = f"/api/v1/missions/{uuid.uuid4()}/turns/{uuid.uuid4()}/correction"
    assert journal_client.post(journal, headers=headers).status_code == 200
    assert journal_client.post(courrier, headers=headers).status_code == 404  # counted all the same
    assert journal_client.post(journal, headers=headers).status_code == 200

    for refused in (journal_client.post(journal, headers=headers), journal_client.post(courrier, headers=headers)):
        assert refused.status_code == 429, refused.text
        detail = refused.json()["detail"]
        assert detail["code"] == RECHECK_LIMIT_CODE
        assert 1 <= int(refused.headers["Retry-After"]) <= DAY_SECONDS

    # Another learner has their own day.
    other = login(journal_client, _email())
    assert journal_client.post(courrier, headers=other).status_code == 404


def test_a_limit_of_zero_lifts_it(journal_client, monkeypatch):
    monkeypatch.setattr(settings, "VERDICT_RECHECK_DAILY_LIMIT", 0)
    headers = login(journal_client, _email())
    courrier = f"/api/v1/missions/{uuid.uuid4()}/turns/{uuid.uuid4()}/correction"
    assert {journal_client.post(courrier, headers=headers).status_code for _ in range(12)} == {404}
