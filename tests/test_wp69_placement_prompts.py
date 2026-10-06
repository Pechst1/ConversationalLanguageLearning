"""WP-69 (L3) — placement never asks the same question twice in a session.

On 2026-09-22 a learner held at A2.1 on middle scores and read «Racontez… le
week-end dernier» three times in a row: the bank had one prompt per band.
"""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from app.db.models.user import User
from app.services.placement import (
    MAX_TURNS,
    PLACEMENT_BANDS,
    PROMPT_VARIANTS,
    PROMPTS_BY_ID,
    PlacementService,
    prompt_for_session,
)


class _MiddlingGrader:
    """Every answer scores 2.0: the ladder holds the band on every turn."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def generate_error_detection(self, messages, **kwargs):
        self.payloads.append(json.loads(messages[0]["content"]))
        return SimpleNamespace(
            content=json.dumps(
                {
                    "score_0_4": 2.0,
                    "demonstrated_band": None,
                    "dimensions": {"range": 2.0, "accuracy": 2.0, "coherence": 2.0, "task": 2.0},
                    "evidence_fr": "phrases simples",
                    "off_task": False,
                }
            ),
            model="test-model",
            provider="test",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            cost=0.0,
        )


def _user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp69-placement-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="beginner",
    )
    db.add(user)
    db.commit()
    return user


def test_every_band_has_enough_distinct_prompts_for_a_whole_session() -> None:
    assert set(PROMPT_VARIANTS) == set(PLACEMENT_BANDS)
    for band, variants in PROMPT_VARIANTS.items():
        assert len(variants) >= MAX_TURNS, band
        assert len({p.prompt_id for p in variants}) == len(variants)
        assert len({p.prompt_fr for p in variants}) == len(variants)
        assert all(p.band == band and p.intent and p.hint_fr for p in variants)
    assert len(PROMPTS_BY_ID) == sum(len(v) for v in PROMPT_VARIANTS.values())


def test_a_held_band_never_repeats_a_prompt(db_session) -> None:
    grader = _MiddlingGrader()
    service = PlacementService(db_session, llm_service=grader)
    session = service.start(_user(db_session))
    shown: list[str] = []
    while session.status == "in_progress":
        shown.append(PlacementService.current_prompt(session).prompt_fr)
        session = service.respond(session, answer="Je suis allé au marché.", turn_index=len(session.turns or []))
    turns = list(session.turns)
    assert len(turns) >= 4
    assert len({t["band"] for t in turns}) == 1, "middle scores must hold the band"
    assert len(set(shown)) == len(shown)
    assert [t["prompt_fr"] for t in turns] == shown
    ids = [t["prompt_id"] for t in turns]
    assert len(set(ids)) == len(ids)
    # The grader was told each chosen prompt's own text and intent.
    for turn, payload in zip(turns, grader.payloads, strict=True):
        prompt = PROMPTS_BY_ID[turn["prompt_id"]]
        assert payload["prompt_fr"] == prompt.prompt_fr
        assert payload["prompt_intent"] == prompt.intent


def test_the_choice_is_deterministic_per_session_and_fresh_after_every_turn() -> None:
    first = prompt_for_session("A2.1", session_key="s-1")
    assert prompt_for_session("A2.1", session_key="s-1") == first
    turns: list[dict] = []
    seen = set()
    for _ in range(MAX_TURNS):
        prompt = prompt_for_session("A2.1", session_key="s-1", turns=turns)
        assert prompt.prompt_id not in seen
        seen.add(prompt.prompt_id)
        turns.append({"band": "A2.1", "prompt_id": prompt.prompt_id, "prompt_fr": prompt.prompt_fr})
    orders = {prompt_for_session("A2.1", session_key=f"s-{i}").prompt_id for i in range(20)}
    assert len(orders) > 1, "different sessions should not all open on the same prompt"


def test_legacy_turns_without_an_id_still_count_as_shown() -> None:
    legacy = PROMPT_VARIANTS["A2.1"][0]
    for key in (f"k{i}" for i in range(10)):
        chosen = prompt_for_session("A2.1", session_key=key, turns=[{"band": "A2.1", "prompt_fr": legacy.prompt_fr}])
        assert chosen.prompt_id != legacy.prompt_id
