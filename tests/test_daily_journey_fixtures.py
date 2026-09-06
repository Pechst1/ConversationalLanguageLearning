"""Executable validation of the WP-00 fixture bundle against the real schemas.

Every ``tests/fixtures/daily_journey_v1/public/*.json`` payload is validated
with the actual Pydantic response model for its manifest ``endpoint`` +
``http_status``. The bundle is frozen: if a fixture cannot validate, this test
fails loudly rather than the fixture being quietly rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.schemas.daily_journey import (
    AttemptResult,
    CapabilityProgress,
    HelpResult,
    JourneyErrorBody,
    JourneySnapshot,
    TodayEnvelope,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "daily_journey_v1"
PUBLIC_DIR = FIXTURE_ROOT / "public"
PRIVATE_DIR = FIXTURE_ROOT / "private"
MANIFEST = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))

#: Evaluator material that must never appear anywhere in a public payload.
PRIVATE_KEYS = (
    "rubric",
    "rubric_native",
    "accepted_answers",
    "correct_option_id",
    "correct_tile_order",
    "solution_fr",
    "target_answer",
    "allowed_outcomes",
    "private_task",
)


def _model_for(endpoint: str, http_status: int) -> type[BaseModel]:
    if http_status >= 400 or http_status == 202 and endpoint.endswith("/attempts"):
        return JourneyErrorBody
    if endpoint.endswith("/today"):
        return TodayEnvelope
    if endpoint.endswith("/capabilities/progress"):
        return CapabilityProgress
    if endpoint.endswith("/attempts"):
        return AttemptResult
    if endpoint.endswith("/help"):
        return HelpResult
    return JourneySnapshot


def _load(name: str) -> dict[str, Any]:
    return json.loads((PUBLIC_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _walk_keys(node: Any):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _walk_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_keys(item)


@pytest.mark.parametrize("entry", MANIFEST["fixtures"], ids=lambda e: e["fixture"])
def test_public_fixture_validates_against_real_schema(entry: dict[str, Any]) -> None:
    payload = _load(entry["fixture"])

    assert payload["contract_version"] == 1
    assert payload["http_status"] == entry["http_status"]
    assert payload["endpoint"] == entry["endpoint"]

    model = _model_for(entry["endpoint"], entry["http_status"])
    model.model_validate(payload["response"])


@pytest.mark.parametrize("entry", MANIFEST["fixtures"], ids=lambda e: e["fixture"])
def test_public_fixture_carries_no_evaluator_material(entry: dict[str, Any]) -> None:
    payload = _load(entry["fixture"])
    leaked = sorted({key for key in _walk_keys(payload["response"]) if key in PRIVATE_KEYS})
    assert leaked == [], f"{entry['fixture']} leaks private keys: {leaked}"


@pytest.mark.parametrize("entry", MANIFEST["fixtures"], ids=lambda e: e["fixture"])
def test_manifest_private_pairs_exist_and_stay_out_of_public(
    entry: dict[str, Any],
) -> None:
    private_path = PRIVATE_DIR / f"{entry['fixture']}.json"
    assert private_path.exists() is bool(entry["has_private_pair"])


def test_round_trip_public_fixture_reserializes_identically() -> None:
    """Validation must not silently drop or rename a contract field."""

    payload = _load("cafe_journey_created")["response"]
    model = JourneySnapshot.model_validate(payload)
    assert model.model_dump(mode="json") == payload


def test_every_private_fixture_stays_out_of_the_public_directory() -> None:
    private_names = {path.stem for path in PRIVATE_DIR.glob("*.json")}
    for name in private_names:
        public = _load(name)
        leaked = sorted(
            {key for key in _walk_keys(public["response"]) if key in PRIVATE_KEYS}
        )
        assert leaked == []
