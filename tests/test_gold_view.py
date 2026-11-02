"""Package O-2 — l'or on screen, and the word deck that earns it.

The ledger's writers are pinned in ``tests/test_gold_ledger.py``. Here: a graded
word card mints (a self-rated one never does), more words a day pay more up to
the plafond, and ``GET /api/v1/gold`` and ``/gold/ledger`` show the ledger only
to whom ``ATELIER_GOLD_UI`` names.
"""
from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core import gold as core
from app.db.models.gold import GoldLedgerEntry
from app.db.models.progress import UserVocabularyProgress
from app.services import gold_ledger
from app.services.gold_view import build_gold_view, week_bounds
from tests.test_daily_words import _make_due_word
from tests.test_wp115a_vocabulary_memory import _login


@pytest.fixture(autouse=True)
def gold_for_the_owner(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")
    monkeypatch.setattr(settings, "ATELIER_GOLD_UI", "owner")


@pytest.fixture(autouse=True)
def ledger_never_swallows(caplog) -> Iterator[None]:
    caplog.set_level(logging.WARNING, logger=gold_ledger.__name__)
    yield
    swallowed = [r.getMessage() for r in caplog.get_records("call") if r.name == gold_ledger.__name__]
    assert not swallowed, f"a gold writer failed inside its savepoint: {swallowed}"


def _cards(db_session, user) -> list[GoldLedgerEntry]:
    db_session.expire_all()
    return (
        db_session.query(GoldLedgerEntry)
        .filter(GoldLedgerEntry.user_id == user.id, GoldLedgerEntry.source_kind == gold_ledger.SOURCE_WORD_CARD)
        .order_by(GoldLedgerEntry.created_at)
        .all()
    )


def _review(client: TestClient, headers: dict, word_id: int, **body):
    response = client.post("/api/v1/anki/review", headers=headers, json={"word_id": word_id, "rating": 3, **body})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# The word deck mints
# ---------------------------------------------------------------------------


def test_a_typed_card_answered_right_pays_its_recall_doubled_after_days_away(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=80)  # last seen five days ago
    db_session.commit()
    _review(client, headers, word.id, format="typed", answer_text="la clé")
    [entry] = _cards(db_session, user)
    assert (entry.amount, entry.state) == (4, core.STATE_SETTLED)
    assert entry.target == {"kind": "vocabulary", "id": str(word.id)}
    assert entry.breakdown["reason_fr"] == "Rappel écrit · rappel différé ×2"


def test_a_picked_card_pays_as_recognition(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la porte", rank=81)
    db_session.flush()
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    progress.last_review_date = datetime.now(UTC) - timedelta(hours=2)  # seen this morning: no ×2
    db_session.commit()
    _review(client, headers, word.id, format="choice", answer_text="la porte")
    [entry] = _cards(db_session, user)
    assert entry.amount == 1
    assert entry.breakdown["category"] == "recognised"


def test_a_self_rated_card_pays_nothing(client: TestClient, db_session):
    """Law 1: «Facile» is the learner's word, not evidence."""

    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "le zinc", rank=82)
    db_session.commit()
    _review(client, headers, word.id)  # a flashcard
    _review(client, headers, word.id, format="typed")  # no answer: read as a flashcard
    assert _cards(db_session, user) == []


def test_a_missed_card_pays_nothing_and_its_second_try_today_neither(client: TestClient, db_session):
    """R6 and R7: a miss pays nothing; the card coming back later the same day is a second try."""

    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=83)
    db_session.commit()
    assert _review(client, headers, word.id, format="typed", answer_text="la porte")["correct"] is False
    assert _review(client, headers, word.id, format="typed", answer_text="la clé")["correct"] is True
    assert _cards(db_session, user) == []


def test_a_word_answered_twice_in_a_day_pays_once(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=84)
    db_session.commit()
    _review(client, headers, word.id, format="typed", answer_text="la clé")
    _review(client, headers, word.id, format="typed", answer_text="la clé")
    assert [entry.amount for entry in _cards(db_session, user)] == [4]


def _write_cards(db_session, user, count: int, *, now: datetime) -> list[int]:
    """``count`` different words, each typed right once, seen last two days ago."""

    amounts = []
    for index in range(count):
        word = _make_due_word(db_session, user, f"mot{index}", rank=1000 + index)
        before = sum(e.amount for e in _cards(db_session, user))
        gold_ledger.record_word_card(
            db_session,
            user=user,
            word_id=word.id,
            review_format="typed",
            verdict=SimpleNamespace(correct=True, note=None),
            snapshot={"contact": now - timedelta(days=2), "drill": now - timedelta(days=2)},
            now=now + timedelta(seconds=index),
        )
        amounts.append(sum(e.amount for e in _cards(db_session, user)) - before)
    return amounts


def test_more_words_a_day_pay_more_until_the_plafond(client: TestClient, db_session):
    """Vincent, 2 Nov: more words a day should earn more. Each word pays, the plafond caps a binge."""

    _headers, user = _login(client, db_session)
    now = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    amounts = _write_cards(db_session, user, 45, now=now)
    totals = [sum(amounts[: n + 1]) for n in range(len(amounts))]
    assert totals[9] == 40, "ten words typed back after two days: 4 each"
    assert totals[29] == 105, "past 90 the plafond pays half"
    assert all(later >= earlier for earlier, later in zip(totals, totals[1:], strict=False))
    assert totals[-1] == core.DAY_CAP == 120, "a day never pays more than the plafond"


def test_a_card_and_the_journey_share_the_words_best_of_the_day(client: TestClient, db_session):
    """R1: a word the journey already paid as typed today pays nothing more in the deck."""

    _headers, user = _login(client, db_session)
    now = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    word = _make_due_word(db_session, user, "la clé", rank=85)
    day = gold_ledger._open_day(db_session, user, when=now, now=now)
    gold_ledger._mint_and_write(
        db_session, user_id=user.id, day=day,
        observation=core.GoldObservation(category=core.Category.TYPED, target=core.target_key("vocabulary", word.id)),
        source_kind=gold_ledger.SOURCE_JOURNEY_TARGET, source_key="gold:journey:x:y:vocabulary:1",
        target={"kind": "vocabulary", "id": str(word.id)}, evidence={}, now=now,
    )
    gold_ledger.record_word_card(
        db_session, user=user, word_id=word.id, review_format="typed",
        verdict=SimpleNamespace(correct=True, note=None), snapshot={}, now=now + timedelta(minutes=5),
    )
    assert _cards(db_session, user) == []


def test_an_accent_slip_pays_half(client: TestClient, db_session):
    _headers, user = _login(client, db_session)
    now = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    word = _make_due_word(db_session, user, "la clé", rank=86)
    gold_ledger.record_word_card(
        db_session, user=user, word_id=word.id, review_format="typed",
        verdict=SimpleNamespace(correct=True, note="accent"), snapshot={}, now=now,
    )
    [entry] = _cards(db_session, user)
    assert entry.amount == 1
    assert entry.breakdown["reason_fr"] == "Rappel écrit · accent oublié ×1/2"


def test_an_imported_cards_second_try_today_pays_nothing(client: TestClient, db_session):
    """R7 for an imported Anki card too: its SM-2 review log carries no source."""

    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=89)
    db_session.flush()
    progress = db_session.query(UserVocabularyProgress).filter_by(user_id=user.id, word_id=word.id).one()
    progress.scheduler = "anki"
    db_session.commit()
    assert _review(client, headers, word.id, format="typed", answer_text="la porte")["correct"] is False
    assert _review(client, headers, word.id, format="typed", answer_text="la clé")["correct"] is True
    assert _cards(db_session, user) == []


def test_the_deck_writes_nothing_with_the_ledger_off(client: TestClient, db_session, monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "off")
    headers, user = _login(client, db_session)
    word = _make_due_word(db_session, user, "la clé", rank=87)
    db_session.commit()
    _review(client, headers, word.id, format="typed", answer_text="la clé")
    assert _cards(db_session, user) == []


# ---------------------------------------------------------------------------
# Who sees it
# ---------------------------------------------------------------------------


def _owner(db_session, user):
    user.role = "admin"
    db_session.commit()
    return user


def test_a_learner_sees_nothing_while_the_owner_checks_the_numbers(client: TestClient, db_session):
    headers, _user = _login(client, db_session)
    assert client.get("/api/v1/gold", headers=headers).json() == {
        "visible": False, "mode": None, "balance": None, "today": None, "week": None, "entries": [],
    }
    assert client.get("/api/v1/gold/ledger", headers=headers).json()["visible"] is False


@pytest.mark.parametrize(
    ("mode", "ui", "admin", "visible"),
    [
        ("shadow", "owner", True, True),
        ("shadow", "owner", False, False),
        ("shadow", "all", False, True),
        ("shadow", "off", True, False),
        ("off", "all", True, False),
        ("live", "owner", True, True),
    ],
)
def test_who_sees_the_gold(monkeypatch, mode, ui, admin, visible):
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", mode)
    monkeypatch.setattr(settings, "ATELIER_GOLD_UI", ui)
    assert gold_ledger.gold_visible(SimpleNamespace(role="admin" if admin else "user")) is visible


def test_the_audience_setting_refuses_a_typo():
    from app.config import Settings

    with pytest.raises(ValueError):
        Settings.validate_atelier_gold_ui("everyone")
    assert Settings.validate_atelier_gold_ui(" OWNER ") == "owner"


def test_the_owner_sees_the_livret_the_day_and_where_it_came_from(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    _owner(db_session, user)
    word = _make_due_word(db_session, user, "la clé", rank=88)
    db_session.commit()
    _review(client, headers, word.id, format="typed", answer_text="la clé")

    body = client.get("/api/v1/gold", headers=headers).json()
    assert body["visible"] is True
    assert body["balance"] == 4
    today = body["today"]
    assert (today["settled"], today["pending"], today["plafond"]) == (4, 0, "open")
    assert today["mark"] == core.JOURNEE_PLEINE_MARK[today["rhythm"]]
    assert today["pleine"] is False
    assert body["week"]["settled"] == 4
    assert len(body["week"]["days"]) == 7
    [entry] = body["entries"]
    assert entry["subject"] == "la clé"
    assert entry["delayed_recall"] is True
    assert entry["reason_fr"] == "Rappel écrit · rappel différé ×2"

    ledger = client.get("/api/v1/gold/ledger", headers=headers).json()
    assert ledger["week_id"] == body["week"]["week_id"]
    assert [e["id"] for e in ledger["entries"]] == [entry["id"]]
    assert ledger["days"][0]["settled"] == 4


def test_a_full_day_reaches_its_mark(client: TestClient, db_session):
    _headers, user = _login(client, db_session)
    _owner(db_session, user)
    user.daily_goal_minutes = 10
    db_session.commit()
    now = datetime.now(UTC).replace(microsecond=0)
    view = build_gold_view(db_session, user=user, now=now)
    mark = view["today"]["mark"]
    _write_cards(db_session, user, mark // 4 + 1, now=now - timedelta(minutes=30))
    view = build_gold_view(db_session, user=user, now=now)
    assert view["today"]["pleine"] is True
    assert view["week"]["journees_pleines"] == 1
    assert view["entries"][0]["created_at"] >= view["entries"][-1]["created_at"], "newest first"


def test_past_ninety_the_day_says_the_plafond_pays_half(client: TestClient, db_session):
    _headers, user = _login(client, db_session)
    _owner(db_session, user)
    now = datetime.now(UTC).replace(microsecond=0)
    _write_cards(db_session, user, 25, now=now - timedelta(hours=1))
    today = build_gold_view(db_session, user=user, now=now)["today"]
    assert (today["earned_before_plafond"], today["settled"], today["plafond"]) == (100, 95, "half")


def test_the_week_is_the_ledgers_even_west_of_paris(client: TestClient, db_session):
    """Sunday evening in New York is already Monday in Paris: the new week counts only its own days."""

    _headers, user = _login(client, db_session)
    _owner(db_session, user)
    user.timezone = "America/New_York"
    user.daily_goal_minutes = 5  # léger: mark 10
    db_session.commit()
    friday = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
    _write_cards(db_session, user, 3, now=friday)  # a full Friday in W45
    sunday_night = datetime(2026, 11, 9, 3, 0, tzinfo=UTC)  # Sun 22:00 in New York, Mon 04:00 in Paris
    view = build_gold_view(db_session, user=user, now=sunday_night)
    assert view["week"]["week_id"] == "2026-W46"
    assert (view["week"]["settled"], view["week"]["journees_pleines"]) == (0, 0)
    gold_ledger.record_word_card(
        db_session, user=user, word_id=_make_due_word(db_session, user, "le soir", rank=2000).id,
        review_format="typed", verdict=SimpleNamespace(correct=True, note=None),
        snapshot={"contact": friday - timedelta(days=2)}, now=sunday_night - timedelta(minutes=5),
    )
    _write_cards(db_session, user, 3, now=sunday_night - timedelta(minutes=4))
    view = build_gold_view(db_session, user=user, now=sunday_night)
    assert view["today"]["local_date"] == "2026-11-08"
    assert view["week"]["journees_pleines"] == 1
    sunday = next(day for day in view["week"]["days"] if day["local_date"] == "2026-11-08")
    assert sunday["pleine"] is True
    assert view["week"]["settled"] == view["today"]["settled"] == 16


def test_the_weeks_totals_read_every_entry_however_many(client: TestClient, db_session):
    from app.services.gold_view import LEDGER_ENTRIES_SHOWN, build_gold_ledger

    _headers, user = _login(client, db_session)
    _owner(db_session, user)
    now = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)
    for index in range(LEDGER_ENTRIES_SHOWN + 1):
        db_session.add(GoldLedgerEntry(
            user_id=user.id, amount=1, entry_kind="earn", state="settled", source_kind="word_card",
            source_key=f"gold:test:{index}", evidence={}, breakdown={"earned": 1}, rule_version="gold-v1",
            local_date=now.date(), week_id="2026-W45", created_at=now + timedelta(seconds=index),
        ))
    db_session.flush()
    ledger = build_gold_ledger(db_session, user=user, week="2026-W45", now=now)
    assert ledger["settled"] == LEDGER_ENTRIES_SHOWN + 1
    assert ledger["entries_total"] == LEDGER_ENTRIES_SHOWN + 1
    assert len(ledger["entries"]) == LEDGER_ENTRIES_SHOWN
    assert ledger["days"][0]["settled"] == LEDGER_ENTRIES_SHOWN + 1


def test_a_malformed_week_is_refused(client: TestClient, db_session):
    headers, user = _login(client, db_session)
    _owner(db_session, user)
    assert client.get("/api/v1/gold/ledger?week=2026-45", headers=headers).status_code == 422
    assert client.get("/api/v1/gold/ledger?week=2026-W60", headers=headers).status_code == 422
    assert client.get("/api/v1/gold/ledger?week=2026-W44", headers=headers).json()["entries"] == []


def test_week_bounds():
    assert week_bounds("2026-W45") == (datetime(2026, 11, 2).date(), datetime(2026, 11, 8).date())
    assert week_bounds("nope") is None
