"""S2.1 · the shadow gate: the learner walk with the stored day plan on, mismatches counted.

Plays the long learner walk (30 days × 5 personas, ``tests/test_learner_walk.py``'s
production configuration) with ``DAY_PLAN_STORED`` on and reads the day the way Home
does at each checkpoint: before the scene, after it, after a Forge séance, after the
words. Every read compares the stored plan with today's recomputed view
(:func:`app.services.day_plan.shadow_compare`); this counts the mismatches by field.
The stored plan becomes the source (S2.2) only once every count is zero.

Opt-in, never in CI's default run (it is the long walk)::

    DAY_PLAN_SHADOW_WALK=1 DAY_PLAN_SHADOW_OUT=/tmp/shadow.json \\
        pytest -q -s -m walk tests/test_day_plan_shadow_walk.py

The day's own shape rotates so every event is met: most days the scene is finished,
every fifth one is left early; La Forge is finished three days in four (a finished
séance row, flushed through the same listener a real one is). The day deck is dealt
and half of it answered every day; two days in three the rest too, and one day in
three the client then posts «words done» (the other emptied decks are never marked,
as when the review page is closed before its end). Days 10 and 20 change the pace
after the scene.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from collections import Counter, defaultdict
from typing import Any

import pytest

from app.config import settings
from app.services import day_plan
from tests import learner_walk as walk
from tests import test_journey_end_to_end as support
from tests.test_learner_walk import (  # noqa: F401 - fixtures
    assembled_client,
    clock,
    journey_enabled,
    production_day,
)
from tests.test_season_one import season_on  # noqa: F401 - fixture

DAYS = int(os.environ.get("DAY_PLAN_SHADOW_DAYS") or 30)


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "event", None) == day_plan.MISMATCH_EVENT:
            self.records.append(record)


def _finished_seance(db, user_id: uuid.UUID) -> None:
    from app.db.models.atelier import AtelierSession
    from app.services import daily_journey as service

    row = AtelierSession(
        user_id=user_id, selected_concept_ids=[], quote_payload={"forge": {"walk": True}}, recap_payload={}
    )
    db.add(row)
    db.commit()
    row.status = "completed"
    row.completed_at = service._utcnow()
    db.commit()


#: Days the learner switches pace after the scene (the Tempo sheet).
PACE_CHANGES = {10: "schnell", 20: "normal"}
#: The day deck as ``pages/vocabulary/review.tsx?day=1`` asks for it.
DAY_QUEUE = {
    "limit": 100, "due_limit": 100, "fragile_limit": 0, "new_limit": 50, "topic_limit": 0, "linked_limit": 0,
    "drill": "session",
}


def _deal_day_deck(client, headers) -> list[dict[str, Any]]:
    response = client.get("/api/v1/vocabulary/due-context", headers=headers, params=DAY_QUEUE)
    if response.status_code != 200:
        return []
    deck = response.json()
    seen: set[int] = set()
    cards: list[dict[str, Any]] = []
    for bucket in ("due_words", "fragile_words", "linked_words", "topic_compatible_words", "new_words"):
        for item in deck.get(bucket) or []:
            if item["word_id"] not in seen:
                seen.add(item["word_id"])
                cards.append(item)
    return cards


def _answer(client, db, headers, cards: list[dict[str, Any]]) -> None:
    from app.db.models.vocabulary import VocabularyWord
    from app.services.vocab_fsrs import card_french

    for item in cards:
        word = db.get(VocabularyWord, item["word_id"])
        french = (card_french(word) or [item.get("word")])[0] if word is not None else item.get("word")
        is_new = bool(item.get("is_new")) or item.get("bucket") == "new"
        client.post(
            "/api/v1/anki/review",
            headers=headers,
            json={
                "word_id": item["word_id"],
                "rating": 2,
                "format": "flashcard" if is_new else "typed",
                "answer_text": None if is_new else french,
            },
        )


def _play_early(client, db, headers) -> None:
    driver = support.Driver(client, headers, db=db)
    journey = driver.create()
    if journey.get("status") == "active":
        driver.finish("early")


@pytest.mark.walk
@pytest.mark.parametrize("persona", walk.PERSONAS, ids=lambda p: p.key)
def test_shadow_mismatches_over_a_month(
    persona, assembled_client, db_session, journey_enabled, clock, production_day, monkeypatch  # noqa: F811
):
    if os.environ.get("DAY_PLAN_SHADOW_WALK") != "1":
        pytest.skip("the shadow walk runs with DAY_PLAN_SHADOW_WALK=1")
    monkeypatch.setattr(settings, "DAY_PLAN_STORED", True)

    compared: Counter[str] = Counter()
    original = day_plan.shadow_compare

    def counting(journey: Any, view: dict[str, Any]):
        result = original(journey, view)
        compared["reads"] += 1
        if journey is not None and result is None:
            compared["reads_without_plan"] += 1
        elif result is not None:
            compared["reads_compared"] += 1
        return result

    monkeypatch.setattr(day_plan, "shadow_compare", counting)
    collector = _Collector()
    logging.getLogger("app.services.day_plan").addHandler(collector)
    checkpoint = {"name": ""}
    by_field: Counter[str] = Counter()
    by_checkpoint: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def read(name: str, call) -> None:
        checkpoint["name"] = name
        before = len(collector.records)
        call()
        for record in collector.records[before:]:
            for field, diff in record.day_plan_mismatch.items():
                by_field[field] += 1
                by_checkpoint[name][field] += 1
                if len(examples[field]) < 3:
                    examples[field].append({"day": day, "checkpoint": name, **diff})

    headers, email = walk.register(assembled_client, persona)
    user_id = support.learner_id(db_session, email)
    today = lambda: assembled_client.get("/api/v1/daily-journeys/today", headers=headers)  # noqa: E731
    try:
        for day in range(1, DAYS + 1):
            quality = walk.QUALITIES[(day - 1) % len(walk.QUALITIES)]
            read("home_before_scene", today)
            if day % 5 == 0:
                _play_early(assembled_client, db_session, headers)
            else:
                walk.play_day(
                    assembled_client, db_session, headers,
                    persona=persona, quality=quality, day=day, provider=production_day,
                )
            read("after_scene", today)
            if day % 4 != 0:
                _finished_seance(db_session, user_id)
                read("after_forge", today)
            if day in PACE_CHANGES:
                # The learner picks another pace on the Tempo sheet mid-day.
                read(
                    "pace_changed",
                    lambda pace=PACE_CHANGES[day]: assembled_client.put(
                        "/api/v1/daily-journeys/session/pace", json={"pace": pace}, headers=headers
                    ),
                )
                read("after_pace_change", today)
            cards = _deal_day_deck(assembled_client, headers)
            half = cards[: len(cards) // 2]
            _answer(assembled_client, db_session, headers, half)
            read("words_half_answered", today)
            if day % 3 != 0:
                _answer(assembled_client, db_session, headers, cards[len(half) :])
                read("words_deck_answered", today)
            if day % 3 == 1:
                read(
                    "words_done",
                    lambda: assembled_client.post("/api/v1/daily-journeys/session/words-done", headers=headers),
                )
            read("end_of_day", today)
            clock.advance(days=1)
    finally:
        logging.getLogger("app.services.day_plan").removeHandler(collector)

    summary = {
        "persona": persona.key,
        "days": DAYS,
        **compared,
        "mismatched_reads": len(collector.records),
        "by_field": dict(sorted(by_field.items())),
        "by_checkpoint": {name: dict(counts) for name, counts in by_checkpoint.items()},
        "examples": examples,
    }
    print("\nDAY_PLAN_SHADOW " + json.dumps(summary, ensure_ascii=False))
    out = os.environ.get("DAY_PLAN_SHADOW_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, ensure_ascii=False) + "\n")
