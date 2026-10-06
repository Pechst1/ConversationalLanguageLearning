"""WP-127 (basic) — a short, top-down vocabulary check with honest credit.

Review 2026-10-04 F-3: after placement every sub-band below was checked from the
bottom up (192 items for a C1 learner). Now:

* the ladder starts at the highest eligible sub-band below the learner's own; a
  pass stops it, a miss steps down;
* a visit is at most two 24-item checks (48 items), with stop and resume;
* the sampled, right words are *sampled recognition*; the rest of a passed band
  and every lower band are *inferred* — a separate provenance — and inference
  never overwrites a weakness;
* the answer key is the attempt's (reload, midnight, retry change nothing) and a
  replayed submit credits nothing twice;
* every attempt records the policy, the sampled items and the misses.
"""
from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.db.models.pilot_event import PilotEvent
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services import band_check
from app.services.core_lexicon import CORE_DECK, ensure_core_lexicon

NOW = datetime(2026, 10, 4, 9, 0, tzinfo=UTC)
DOC = Path(__file__).resolve().parents[1] / "docs" / "implementation" / "atelier-v2" / "WP-127-THRESHOLD.md"


@pytest.fixture(autouse=True)
def _drop_core_rows(db_session):
    yield
    db_session.rollback()
    core_ids = select(VocabularyWord.id).where(VocabularyWord.deck_name == CORE_DECK)
    db_session.execute(delete(WordInteraction).where(WordInteraction.word_id.in_(core_ids)))
    db_session.execute(delete(UserVocabularyProgress).where(UserVocabularyProgress.word_id.in_(core_ids)))
    db_session.execute(delete(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK))
    db_session.commit()


def _user(db, level: str) -> User:
    user = User(id=uuid.uuid4(), email=f"wp127-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                target_language="fr", native_language="en", cefr_estimate=level)
    db.add(user)
    db.commit()
    return user


def _answers(db, user, sub_band, *, wrong: int = 0) -> tuple[dict[str, int | None], str]:
    attempt = band_check.next_attempt(db, user, sub_band)
    items = band_check._items(user, sub_band, attempt=attempt)
    answers = {item["id"]: item["answer"] for item in items}
    for item in items[:wrong]:
        answers[item["id"]] = None
    return answers, band_check.attempt_id(user, sub_band, attempt)


def _check(db, user, sub_band, *, wrong=0, now=NOW):
    answers, attempt = _answers(db, user, sub_band, wrong=wrong)
    result = band_check.submit(db, user, sub_band, answers, attempt=attempt, now=now)
    db.commit()
    return result


def _rows(db, user, provenance):
    return db.scalars(
        select(UserVocabularyProgress).where(
            UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.provenance == provenance
        )
    ).all()


# ---------------------------------------------------------------------------
# The ladder: top-down, a pass stops it, a miss descends
# ---------------------------------------------------------------------------


def test_the_ladder_starts_at_the_highest_band_below_the_learner(db_session):
    user = _user(db_session, "C1.1")
    state = band_check.ladder(db_session, user, now=NOW)
    assert state["status"] == "open" and state["next"] == "B2.2"
    assert [row["sub_band"] for row in state["bands"]][0] == "B2.2"
    assert state["policy_version"] == band_check.POLICY_VERSION
    assert state["max_checks_per_visit"] * state["items_per_check"] == 48
    assert band_check.ladder(db_session, _user(db_session, "A1.1"), now=NOW)["status"] == "none"


def test_the_common_strong_c1_path_is_one_check_and_infers_every_band_below(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "C1.1")
    result = _check(db_session, user, "B2.2", wrong=1)
    assert result["passed"] and result["total"] == 24
    assert result["ladder_status"] == "done" and result["next"] is None
    assert result["inferred_bands"] == ["B2.1", "B1.2", "B1.1", "A2.2", "A2.1", "A1.2", "A1.1"]
    sampled = _rows(db_session, user, band_check.PROVENANCE)
    inferred = _rows(db_session, user, band_check.INFERRED_PROVENANCE)
    assert result["credited_sampled"] == len(sampled) == 23
    assert {row.provenance_ref for row in sampled} == {"B2.2"}
    assert result["credited_inferred"] == len(inferred) > 1000
    kinds = band_check.credit_kinds(db_session, user)
    assert kinds["B2.2"] == "sampled" and kinds["A1.1"] == "inferred"
    # One check — 24 items — was the whole visit.
    assert sum(row["total"] for row in band_check.attempts(db_session, user)) == 24


def test_a_miss_steps_down_and_a_visit_never_exceeds_48_items(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "C1.1")
    first = _check(db_session, user, "B2.2", wrong=6)
    assert not first["passed"] and first["next"] == "B2.1" and first["ladder_status"] == "open"
    second = _check(db_session, user, "B2.1", wrong=6)
    assert not second["passed"] and second["ladder_status"] == "paused" and second["resume_band"] == "B1.2"
    # The visit is spent: a third check can neither open nor be graded.
    with pytest.raises(band_check.VisitFull):
        band_check.start(db_session, user, "B1.2", now=NOW)
    with pytest.raises(band_check.VisitFull):
        band_check.submit(db_session, user, "B1.2", {}, now=NOW)
    seen = sum(row["total"] for row in band_check.attempts(db_session, user))
    assert seen == 48
    # Useful partial result: nothing credited, two bands on record as not yet.
    state = band_check.ladder(db_session, user, now=NOW)
    assert {row["sub_band"] for row in state["bands"] if row["missed"]} == {"B2.2", "B2.1"}
    assert not _rows(db_session, user, band_check.PROVENANCE)
    # The next visit resumes where it stopped.
    later = NOW + timedelta(hours=band_check.VISIT_HOURS + 1)
    resumed = band_check.ladder(db_session, user, now=later)
    assert resumed["status"] == "open" and resumed["next"] == "B1.2"


def test_a_pass_after_a_miss_stops_and_never_credits_the_missed_band(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "C1.1")
    _check(db_session, user, "B2.2", wrong=8)
    result = _check(db_session, user, "B2.1", wrong=0)
    assert result["passed"] and result["ladder_status"] == "done"
    kinds = band_check.credit_kinds(db_session, user)
    assert "B2.2" not in kinds and kinds["B2.1"] == "sampled" and kinds["B1.1"] == "inferred"


# ---------------------------------------------------------------------------
# Inferred credit never overwrites a weakness
# ---------------------------------------------------------------------------


def test_inferred_credit_never_touches_an_existing_card_or_a_missed_word(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "B2.1")
    # A lower-band word the learner is struggling with: a card with lapses.
    lemma = band_check._pool("A1.1")[0][0]
    word = db_session.scalar(select(VocabularyWord).where(VocabularyWord.deck_name == CORE_DECK,
                                                           VocabularyWord.normalized_word == lemma))
    weak = UserVocabularyProgress(user_id=user.id, word_id=word.id, state="relearning", lapses=3,
                                  stability=0.5, provenance=None)
    db_session.add(weak)
    db_session.commit()
    # A first check of B1.2 misses; its missed words are weaknesses on record.
    first = _check(db_session, user, "B1.2", wrong=5)
    assert not first["passed"]
    missed_before = set(first["missed"])
    result = _check(db_session, user, "B1.1", wrong=1)
    assert result["passed"]
    db_session.refresh(weak)
    assert (weak.state, weak.lapses, weak.provenance) == ("relearning", 3, None)
    credited = {
        row[0]
        for row in db_session.execute(
            select(VocabularyWord.normalized_word)
            .join(UserVocabularyProgress, UserVocabularyProgress.word_id == VocabularyWord.id)
            .where(UserVocabularyProgress.user_id == user.id,
                   UserVocabularyProgress.provenance.in_(band_check.CHECK_PROVENANCES))
        )
    }
    assert not credited & missed_before
    assert not credited & set(result["missed"])
    # The missed band above is never inferred from a pass below it.
    assert "B1.2" not in band_check.credit_kinds(db_session, user)


def test_a_lower_band_missed_on_record_is_never_inferred(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "B2.1")
    _check(db_session, user, "A2.2", wrong=8)  # a manual check of a lower band, missed
    result = _check(db_session, user, "B1.2", wrong=0, now=NOW + timedelta(days=1))
    assert result["passed"]
    assert "A2.2" not in result["inferred_bands"] and "A2.1" in result["inferred_bands"]
    assert "A2.2" not in band_check.credit_kinds(db_session, user)


def test_the_light_check_schedule_is_kept_for_inferred_credit(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "C1.1")
    _check(db_session, user, "B2.2", wrong=0)
    lowest = [row for row in _rows(db_session, user, band_check.INFERRED_PROVENANCE) if row.provenance_ref == "A1.1"]
    assert lowest
    first, last = band_check.credit_schedule(8)[1]
    for row in lowest:
        due = row.due_at if row.due_at.tzinfo else row.due_at.replace(tzinfo=UTC)
        assert first <= (due - NOW).days <= last


# ---------------------------------------------------------------------------
# Persistent assessment identity; the record the pilot reads
# ---------------------------------------------------------------------------


def test_reload_and_midnight_do_not_change_the_answer_key(db_session):
    user = _user(db_session, "B1.1")
    before = band_check.start(db_session, user, "A2.2", now=NOW)
    after_midnight = band_check.start(db_session, user, "A2.2", now=NOW + timedelta(hours=16))
    assert before == after_midnight
    assert band_check._items(user, "A2.2", attempt=0, now=NOW) == band_check._items(
        user, "A2.2", attempt=0, now=NOW + timedelta(days=3)
    )


def test_a_replayed_submit_returns_the_stored_result_and_credits_nothing_twice(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "B1.1")
    answers, attempt = _answers(db_session, user, "A2.2", wrong=1)
    first = band_check.submit(db_session, user, "A2.2", answers, attempt=attempt, now=NOW)
    db_session.commit()
    count = db_session.scalar(select(func.count()).select_from(UserVocabularyProgress)
                              .where(UserVocabularyProgress.user_id == user.id))
    again = band_check.submit(db_session, user, "A2.2", answers, attempt=attempt, now=NOW + timedelta(hours=1))
    db_session.commit()
    assert again["replayed"] is True
    assert {k: again[k] for k in ("correct", "passed", "credited_words", "attempt_id")} == {
        k: first[k] for k in ("correct", "passed", "credited_words", "attempt_id")
    }
    assert db_session.scalar(select(func.count()).select_from(UserVocabularyProgress)
                             .where(UserVocabularyProgress.user_id == user.id)) == count
    assert len(band_check.attempts(db_session, user)) == 1
    # A next attempt at the same band is a new identity with a new sample.
    assert band_check.attempt_id(user, "A2.2", 1) != attempt
    with pytest.raises(band_check.StaleAttempt):
        band_check.submit(db_session, user, "A2.2", answers, attempt="A2.2:7:feedfacefeedface", now=NOW)


def test_every_attempt_records_policy_sample_and_misses_for_the_pilot(db_session):
    ensure_core_lexicon(db_session)
    user = _user(db_session, "B1.1")
    result = _check(db_session, user, "A2.2", wrong=3)
    row = db_session.scalar(select(PilotEvent).where(PilotEvent.user_id == user.id,
                                                     PilotEvent.event_type == band_check.ATTEMPT_EVENT))
    payload = row.payload
    assert row.entity_id == result["attempt_id"]
    assert payload["policy_version"] == band_check.POLICY_VERSION
    assert len(payload["sampled"]) == 24 and len(payload["missed"]) == 3
    assert payload["pass_correct"] == 21 and payload["correct"] == 21 and payload["passed"] is True
    assert set(payload["dont_know"]) == set(payload["missed"])


# ---------------------------------------------------------------------------
# The candidate threshold and its documented trade-off
# ---------------------------------------------------------------------------


def _binomial_at_most(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))


def test_the_threshold_is_a_documented_candidate():
    assert band_check.PASS_CORRECT == 21 and band_check.ITEMS == 24
    # The numbers the doc quotes (package doc §2 "Limits").
    assert round(100 * _binomial_at_most(21, 24, 0.92), 1) == 30.1  # 92 % learner fails 22/24
    assert round(100 * _binomial_at_most(20, 24, 0.92), 1) == 12.1  # … fails 21/24
    assert round(100 * (1 - _binomial_at_most(21, 24, 0.80)), 1) == 11.5  # 80 % learner passes 22/24
    assert round(100 * (1 - _binomial_at_most(20, 24, 0.80)), 1) == 26.4  # … passes 21/24
    text = DOC.read_text(encoding="utf-8")
    for needle in ("30.1", "12.1", "11.5", "26.4", "candidate", "WP-133b", band_check.POLICY_VERSION):
        assert needle in text, needle


# ---------------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------------


def test_the_api_serves_the_ladder_and_refuses_a_third_check(client, db_session):
    ensure_core_lexicon(db_session)
    address = f"wp127-api-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"email": address, "password": "securepass123",
                                               "starting_point": "confident"})
    token = client.post("/api/v1/auth/login", json={"email": address, "password": "securepass123"}).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    user = db_session.query(User).filter(User.email == address).one()

    ladder = client.get("/api/v1/vocabulary/band-check/ladder", headers=headers).json()
    assert ladder["status"] == "open" and ladder["next"] == "B1.2"
    for band in ("B1.2", "B1.1"):
        start = client.get(f"/api/v1/vocabulary/band-check/{band}", headers=headers).json()
        assert start["pass_correct"] == 21 and start["attempt_id"]
        assert start == client.get(f"/api/v1/vocabulary/band-check/{band}", headers=headers).json()
        key = {i["id"]: i["answer"] for i in band_check._items(user, band, attempt=0)}
        answers = {item["id"]: (key[item["id"]] + 1) % 4 for item in start["items"]}
        body = {"answers": answers, "attempt_id": start["attempt_id"]}
        result = client.post(f"/api/v1/vocabulary/band-check/{band}", headers=headers, json=body)
        assert result.status_code == 200 and result.json()["passed"] is False
        replay = client.post(f"/api/v1/vocabulary/band-check/{band}", headers=headers, json=body)
        assert replay.status_code == 200 and replay.json()["replayed"] is True
    assert client.get("/api/v1/vocabulary/band-check/A2.2", headers=headers).status_code == 409
    paused = client.get("/api/v1/vocabulary/band-check/ladder", headers=headers).json()
    assert paused["status"] == "paused" and paused["resume_band"] == "A2.2"
    # An older client without an attempt id is graded against the current attempt.
    assert client.get("/api/v1/vocabulary/band-check", headers=headers).status_code == 200
