"""Owner request, 2 Nov 2026 — more new words a day, more gold, and why.

«Zudem solltest du die Möglichkeit geben, noch mehr Wörter pro Tag zu lernen,
das sollte auch mehr XP geben. Gleichzeitig auch dem Lerner sagen, dass man so
schneller an sein Sprachziel kommt.»

Before, «Noch 10 Wörter» after the day sent ``extra=10`` to the deck, which
then ignored the day's cap altogether: the client sized the words past the
dose, nothing on the server remembered them (a reload dealt ten more), and no
other read of the day knew they had been granted. Now:

* the cap is one function, ``vocabulary_pace.effective_new_word_cap``: the
  learner's own number plus the extras they asked for today, stored on the
  day's batch row by ``POST /vocabulary/new-words/more``; every room reads it;
* an extra word answered right earns its gold through the ledger's one path
  (``gold_ledger._mint_and_write``), so the day's earned gold counts it;
* ``goal_estimate.days_sooner`` is the one figure for «… etwa 3 Wochen früher»,
  and there is no figure without a goal.
"""
from __future__ import annotations

import ast
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.gold import GoldLedgerEntry
from app.services import goal_estimate, gold_ledger, vocabulary_pace
from app.services.daily_session import WORD_RETENTION
from tests.test_wp154_drill_reload import (
    _deck,
    _forget_test_words,  # noqa: F401 - autouse fixture: the suite shares one database
    _ids,
    _login,
    _supply,
)

ROOT = Path(__file__).resolve().parents[1]

#: review.tsx's continuation after the day deck («Noch 5 neue Wörter»).
MORE = {"limit": 35, "due_limit": 30, "fragile_limit": 0, "new_limit": 5, "topic_limit": 0, "linked_limit": 0,
        "drill": "more"}
#: The Lexique's own session deck.
SESSION = {"limit": 50, "due_limit": 30, "fragile_limit": 12, "new_limit": 8, "topic_limit": 8, "linked_limit": 8,
           "drill": "session"}


@pytest.fixture(autouse=True)
def gold_in_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


@pytest.fixture(autouse=True)
def ledger_never_swallows(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    caplog.set_level(logging.WARNING, logger=gold_ledger.__name__)
    yield
    swallowed = [record.getMessage() for record in caplog.get_records("call") if record.name == gold_ledger.__name__]
    assert not swallowed, f"a gold writer failed inside its savepoint: {swallowed}"


def _dose_of(db: Session, user, monkeypatch: pytest.MonkeyPatch, words: int) -> None:
    """The learner's own number, no throttle, the scene planned with no new words."""

    user.daily_pace = None
    user.new_words_per_day = words
    db.commit()
    monkeypatch.setattr(vocabulary_pace, "intake_throttle_factor", lambda *_a, **_k: 1.0)
    monkeypatch.setattr(vocabulary_pace, "journey_reservation", lambda *_a, **_k: (True, set()))


def _answer(client: TestClient, headers: dict, word_ids: list[int], *, rating: int = 3) -> None:
    for word_id in word_ids:
        reviewed = client.post(
            "/api/v1/anki/review", headers=headers, json={"word_id": word_id, "rating": rating, "format": "flashcard"}
        )
        assert reviewed.status_code == 200, reviewed.text


def _extra_entries(db: Session, user) -> list[GoldLedgerEntry]:
    db.expire_all()
    return (
        db.query(GoldLedgerEntry)
        .filter(GoldLedgerEntry.user_id == user.id, GoldLedgerEntry.source_kind == gold_ledger.SOURCE_EXTRA_WORD)
        .all()
    )


# ---------------------------------------------------------------------------
# One cap
# ---------------------------------------------------------------------------


def test_the_cap_is_the_learners_number_plus_todays_extras(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _headers, user = _login(client, db_session)
    _dose_of(db_session, user, monkeypatch, 20)
    assert vocabulary_pace.effective_new_word_cap(db_session, user) == 20

    assert vocabulary_pace.grant_extra_new_words(db_session, user) == 5
    db_session.commit()
    assert vocabulary_pace.extra_new_words_today(db_session, user) == 5
    assert vocabulary_pace.effective_new_word_cap(db_session, user) == 25
    # The extras are a choice the throttle never halves; the dose still is.
    assert vocabulary_pace.effective_new_word_cap(db_session, user, factor=0.5) == 10 + 5
    # The day deck counts the dose, not the extras.
    assert vocabulary_pace.daily_quota(db_session, user) == 20

    for _ in range(20):
        vocabulary_pace.grant_extra_new_words(db_session, user)
    assert vocabulary_pace.extra_new_words_today(db_session, user) == vocabulary_pace.MAX_EXTRA_NEW_WORDS


def test_every_room_for_new_words_reads_the_one_cap(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard: the drill's and the journey's rooms take the cap from
    ``effective_new_word_cap`` and nowhere else."""

    _headers, user = _login(client, db_session)
    _dose_of(db_session, user, monkeypatch, 10)
    monkeypatch.setattr(vocabulary_pace, "effective_new_word_cap", lambda *_a, **_k: 37)
    room, _reserved = vocabulary_pace.drill_new_word_room(db_session, user)
    assert room == 37
    assert vocabulary_pace.journey_new_word_room(db_session, user) == 37


def test_nothing_else_adds_extras_or_computes_a_cap_of_its_own() -> None:
    """Guard, by source: only ``vocabulary_pace`` reads the stored extras, and the
    raw quota (``_quota``) is read only for the cap and the day's dose."""

    allowed_quota = {
        ("app/services/vocabulary_pace.py", "daily_quota"),
        ("app/services/vocabulary_pace.py", "planned_new_words"),
        ("app/services/vocabulary_pace.py", "effective_new_word_cap"),
        # The day's plan: the dose the day deck holds, never the extras.
        ("app/services/day_words.py", "make_plan"),
        ("app/services/day_words.py", "_dose"),
    }
    quota_calls: set[tuple[str, str]] = set()
    extras_reads: set[tuple[str, str]] = set()
    for path in (ROOT / "app").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in ast.walk(tree):
            if not isinstance(func, ast.FunctionDef):
                continue
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_quota":
                    quota_calls.add((rel, func.name))
                if isinstance(node, ast.Attribute) and node.attr == "extra_new_words":
                    extras_reads.add((rel, func.name))
    assert quota_calls <= allowed_quota, f"a cap computed outside effective_new_word_cap: {quota_calls - allowed_quota}"
    assert {rel for rel, _name in extras_reads} == {"app/services/vocabulary_pace.py"}, extras_reads


def test_the_client_never_sizes_the_words_past_the_dose(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before: ``extra=10`` dealt ten new words past the cap, and again on every
    reload. Now only a granted step makes room, and a reload deals nothing more."""

    headers, user = _login(client, db_session)
    supply = _supply(db_session, 30, "wmore")
    _dose_of(db_session, user, monkeypatch, 3)

    first = _ids(_deck(client, headers, SESSION))
    assert len(first) == 3
    _answer(client, headers, first)

    sneaky = _deck(client, headers, {**MORE, "new_limit": 10, "extra": 10})
    assert _ids(sneaky) == [], "the client asked for ten past the dose and got them"

    granted = client.post("/api/v1/vocabulary/new-words/more", headers=headers)
    assert granted.status_code == 200, granted.text
    assert (granted.json()["extra_today"], granted.json()["cap_today"]) == (5, 8)

    extra = _ids(_deck(client, headers, MORE))
    assert len(extra) == 5 and set(extra) <= set(supply)
    assert _ids(_deck(client, headers, MORE)) == extra, "a reload deals the same five, never five more"


def test_the_last_step_of_the_day_is_refused(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    _dose_of(db_session, user, monkeypatch, 10)
    for _ in range(vocabulary_pace.MAX_EXTRA_NEW_WORDS // vocabulary_pace.EXTRA_WORDS_STEP):
        assert client.post("/api/v1/vocabulary/new-words/more", headers=headers).status_code == 200
    assert client.post("/api/v1/vocabulary/new-words/more", headers=headers).status_code == 409
    body = client.get("/api/v1/vocabulary/new-words", headers=headers).json()
    assert body["can_add_more"] is False and body["extra_today"] == vocabulary_pace.MAX_EXTRA_NEW_WORDS


# ---------------------------------------------------------------------------
# More gold, through the ledger's one path
# ---------------------------------------------------------------------------


def test_an_extra_word_answered_right_earns_gold_through_the_ledger(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 30, "wgold")
    _dose_of(db_session, user, monkeypatch, 2)

    minted: list[str] = []
    shared = gold_ledger._mint_and_write

    def spy(*args, **kwargs):
        minted.append(kwargs["source_kind"])
        return shared(*args, **kwargs)

    monkeypatch.setattr(gold_ledger, "_mint_and_write", spy)

    dose = _ids(_deck(client, headers, SESSION))
    assert len(dose) == 2
    _answer(client, headers, dose)
    assert _extra_entries(db_session, user) == [], "the day's own dose earns no extra-word gold"
    before = gold_ledger.day_earned(db_session, user=user)

    assert client.post("/api/v1/vocabulary/new-words/more", headers=headers).status_code == 200
    extra = _ids(_deck(client, headers, MORE))
    assert len(extra) == 5
    _answer(client, headers, extra[:1], rating=0)  # a miss pays nothing
    assert _extra_entries(db_session, user) == []
    _answer(client, headers, extra[1:3])
    _answer(client, headers, extra[1:2])  # answered again: once per word

    entries = _extra_entries(db_session, user)
    assert sorted(int(entry.target["id"]) for entry in entries) == sorted(extra[1:3])
    assert all(entry.entry_kind == gold_ledger.ENTRY_EARN and entry.amount == 1 for entry in entries)
    assert minted.count(gold_ledger.SOURCE_EXTRA_WORD) == 2, "the extra words went around the shared mint"
    assert gold_ledger.day_earned(db_session, user=user) == before + 2, "the day's gold does not count them"


def test_no_extra_word_gold_without_extras(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    _supply(db_session, 10, "wnogold")
    _dose_of(db_session, user, monkeypatch, 3)
    _answer(client, headers, _ids(_deck(client, headers, SESSION)))
    assert _extra_entries(db_session, user) == []


# ---------------------------------------------------------------------------
# «… etwa 3 Wochen früher»: one function, honest
# ---------------------------------------------------------------------------


def test_days_sooner_for_a_known_case() -> None:
    # 870 words left, 87 % kept: 100 days at 10 a day, 50 at 20, 33⅓ at 30.
    assert WORD_RETENTION == 0.87
    assert goal_estimate.days_sooner(words_left=870, base_per_day=10, faster_per_day=20) == 50
    assert goal_estimate.days_sooner(words_left=870, base_per_day=20, faster_per_day=30) == 17
    assert goal_estimate.days_sooner(words_left=870, base_per_day=20, faster_per_day=25) == 10


def test_days_sooner_gives_no_figure_without_an_honest_one() -> None:
    assert goal_estimate.days_sooner(words_left=0, base_per_day=10, faster_per_day=20) is None
    assert goal_estimate.days_sooner(words_left=870, base_per_day=20, faster_per_day=20) is None
    assert goal_estimate.days_sooner(words_left=870, base_per_day=20, faster_per_day=10) is None
    assert goal_estimate.days_sooner(words_left=8, base_per_day=20, faster_per_day=25) is None  # under a day


def test_no_goal_no_figure(db_session: Session) -> None:
    learner = SimpleNamespace(id=None, cefr_target_level=None, cefr_estimate="A1.1")
    assert goal_estimate.learner_goal(db_session, learner) == (None, 0)
    passed = SimpleNamespace(id=None, cefr_target_level="A1.2", cefr_estimate="A2.1")
    assert goal_estimate.learner_goal(db_session, passed) == (None, 0)
    rows = goal_estimate.speedups(goal=None, words_left=870, base_per_day=10, options=goal_estimate.WORD_STEPS)
    assert [row["days_sooner"] for row in rows] == [None] * len(goal_estimate.WORD_STEPS)


def test_the_new_words_endpoint_says_what_the_next_step_brings(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user = _login(client, db_session)
    _dose_of(db_session, user, monkeypatch, 20)
    user.cefr_target_level = "A2.2"
    user.cefr_estimate = "A1.1"
    db_session.commit()
    monkeypatch.setattr(
        "app.services.daily_session.goal_gap", lambda *_a, **_k: ("A2.2", 870, 40)
    )
    body = client.get("/api/v1/vocabulary/new-words", headers=headers).json()
    assert (body["words_per_day"], body["extra_today"], body["cap_today"], body["step"]) == (20, 0, 20, 5)
    assert (body["goal"], body["words_left"]) == ("A2.2", 870)
    assert body["more"] == {"words": 25, "days_sooner": 10}
    assert [step["words"] for step in body["steps"]] == [10, 15, 20, 30, 40]
    assert [step["days_sooner"] for step in body["steps"]] == [None, None, None, 17, 25]

    user.cefr_target_level = None
    db_session.commit()
    body = client.get("/api/v1/vocabulary/new-words", headers=headers).json()
    assert body["goal"] is None and body["more"] == {"words": 25, "days_sooner": None}


def test_the_now_argument_is_honoured_for_a_new_day(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extras are today's: tomorrow starts at the learner's own number again."""

    _headers, user = _login(client, db_session)
    _dose_of(db_session, user, monkeypatch, 20)
    vocabulary_pace.grant_extra_new_words(db_session, user)
    db_session.commit()
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    assert vocabulary_pace.effective_new_word_cap(db_session, user, now=tomorrow) == 20
