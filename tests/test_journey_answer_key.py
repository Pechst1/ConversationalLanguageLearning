"""WP-76 — the hashed answer key that lets a pick be coloured on the device.

The key must (1) agree with the server's own checker for every pickable
format, (2) never print the answer, (3) differ per step, and (4) reach the
public snapshot additively without breaking the frozen contract.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourneyStep
from app.schemas.daily_journey import RecallPrompt
from app.services.journey_answer_key import (
    TILE_JOINER,
    answer_digest,
    answer_key_for,
    answer_key_salt,
    answer_matches_key,
    answer_material,
    normalize_key_part,
)
from tests.test_daily_journey_api import (  # noqa: F401 — pytest fixtures
    assert_no_private_material,
    create_journey,
    journey_client,
    journey_enabled,
    login,
)

SECRET = b"test-secret"

CHOICE_TASK = {
    "task_type": "choice",
    "options": [{"id": "opt-a", "text_fr": "un café"}, {"id": "opt-b", "text_fr": "une table"}],
    "correct_option_id": "opt-b",
}
TILES_TASK = {
    "task_type": "word_bank",
    "options": [
        {"id": "t1", "text_fr": "l'addition"},
        {"id": "t2", "text_fr": "maintenant"},
        {"id": "x1", "text_fr": "café"},
    ],
    "correct_tile_order": ["t1", "t2"],
}


def test_a_choice_key_matches_the_right_pick_and_only_it() -> None:
    key = answer_key_for("step-1", CHOICE_TASK, secret=SECRET)
    assert key is not None and key["version"] == 1
    assert answer_matches_key(key, "choice", option_id="opt-b") is True
    assert answer_matches_key(key, "choice", option_id="opt-a") is False
    assert answer_matches_key(key, "choice", option_id=None) is False


def test_a_tile_key_is_the_exact_order_like_the_grader() -> None:
    key = answer_key_for("step-2", TILES_TASK, secret=SECRET)
    assert key is not None
    assert answer_matches_key(key, "word_bank", tile_ids=["t1", "t2"]) is True
    # The server compares the exact id sequence: order and extra chips matter.
    assert answer_matches_key(key, "word_bank", tile_ids=["t2", "t1"]) is False
    assert answer_matches_key(key, "word_bank", tile_ids=["t1", "t2", "x1"]) is False
    assert answer_matches_key(key, "word_bank", tile_ids=["t1"]) is False


def test_the_key_never_prints_the_answer() -> None:
    for task in (CHOICE_TASK, TILES_TASK):
        key = answer_key_for("step-3", task, secret=SECRET)
        blob = str(key)
        for option in task["options"]:
            assert option["id"] not in blob
            assert option["text_fr"] not in blob


def test_the_salt_is_per_step_and_secret_bound() -> None:
    a = answer_key_for("step-a", CHOICE_TASK, secret=SECRET)
    b = answer_key_for("step-b", CHOICE_TASK, secret=SECRET)
    c = answer_key_for("step-a", CHOICE_TASK, secret=b"other")
    assert a["salt"] != b["salt"] and a["digests"] != b["digests"]
    assert a["salt"] != c["salt"]
    assert len(a["salt"]) == 32


def test_the_digest_recipe_is_the_one_the_client_mirrors() -> None:
    """`lib/answer-key.ts` hashes `salt + ":" + material` with SHA-256 hex."""

    salt = answer_key_salt("s", secret=SECRET)
    material = answer_material("tiles", tile_ids=["a", "b"])
    assert material == f"a{TILE_JOINER}b"
    assert answer_digest(salt, material) == hashlib.sha256(f"{salt}:a\u001fb".encode()).hexdigest()
    # A pinned vector, repeated verbatim in the frontend test.
    assert answer_digest("0123456789abcdef0123456789abcdef", "opt-b") == hashlib.sha256(
        b"0123456789abcdef0123456789abcdef:opt-b"
    ).hexdigest()


def test_normalisation_folds_smart_quotes_like_the_text_checker() -> None:
    assert normalize_key_part("l\u2019addition") == "l'addition"
    assert normalize_key_part("  a \u00a0 b ") == "a b"


def test_written_formats_and_malformed_tasks_get_no_key() -> None:
    assert answer_key_for("s", {"task_type": "short_answer", "accepted_answers": ["x"]}) is None
    assert answer_key_for("s", {"task_type": "transform"}) is None
    assert answer_key_for("s", {"task_type": "choice"}) is None
    assert answer_key_for("s", {"task_type": "tiles", "correct_tile_order": []}) is None
    assert answer_key_for("s", None) is None
    assert answer_key_for("", CHOICE_TASK) is None


def test_the_public_prompt_accepts_the_key_additively() -> None:
    base = {
        "task_type": "choice",
        "instruction_native": "Pick",
        "options": [{"id": "a", "text_fr": "a"}],
        "target": {"kind": "vocabulary", "id": "1", "label_fr": "a"},
        "optional": False,
    }
    assert RecallPrompt.model_validate(base).answer_key is None
    keyed = RecallPrompt.model_validate(
        {**base, "answer_key": answer_key_for("s", CHOICE_TASK, secret=SECRET)}
    )
    assert keyed.answer_key is not None and len(keyed.answer_key.digests) == 1


def test_the_snapshot_carries_a_key_that_agrees_with_the_grader(
    journey_client, journey_enabled: None, db_session: Session  # noqa: F811
) -> None:
    headers = login(journey_client, f"answer-key-{uuid.uuid4().hex[:8]}@example.com")
    journey = create_journey(journey_client, headers)
    assert_no_private_material(journey)

    recalls = [step for step in journey["steps"] if step["kind"] == "recall"]
    keyed = [step for step in recalls if step["prompt"].get("answer_key")]
    for step in recalls:
        task: dict[str, Any] = dict(
            db_session.get(DailyJourneyStep, uuid.UUID(step["id"])).private_task or {}
        ).get("recall_task", {})
        key = step["prompt"].get("answer_key")
        if task.get("task_type") in {"choice", "classify"} and task.get("correct_option_id"):
            assert key, "a pickable recall carries a key"
            assert answer_matches_key(key, task["task_type"], option_id=task["correct_option_id"])
            for option in task["options"]:
                if option["id"] != task["correct_option_id"]:
                    assert not answer_matches_key(key, task["task_type"], option_id=option["id"])
        elif task.get("task_type") in {"tiles", "word_bank"} and task.get("correct_tile_order"):
            assert key
            assert answer_matches_key(key, task["task_type"], tile_ids=task["correct_tile_order"])
        else:
            assert key is None, "a written recall never carries a key"
    # The stub plan deals at least one pickable recall; otherwise this proves nothing.
    assert recalls and keyed
