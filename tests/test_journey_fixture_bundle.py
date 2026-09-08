"""WP-00: structural guards on the frozen daily-journey fixture bundle.

These run today, without WP-02's schemas. WP-02 adds the executable validation of
each payload against the real Pydantic response models in its own test module.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from app.services.journey_contracts import (
    CONTRACT_VERSION,
    DEFAULT_BUDGET_SECONDS,
    MAX_PLANNED_STEPS,
    MAX_RECALL_STEPS,
    JourneyStatus,
    StepKind,
    StepStatus,
)

BUNDLE = pathlib.Path(__file__).resolve().parent / "fixtures" / "daily_journey_v1"
PUBLIC = BUNDLE / "public"
PRIVATE = BUNDLE / "private"

# CONTRACTS §11 requires exactly these scenarios to exist.
REQUIRED_SCENARIOS = {
    "first_day", "returning_due", "empty_queue", "active_legacy", "voice_unavailable",
    "preparing", "generation_unavailable", "wrong_then_supported", "unassisted_success",
    "completed", "ended_early", "stale_revision", "duplicate_submit", "midnight_resume",
    "content_superseded", "unknown_legacy_assistance",
}

# Private evaluator vocabulary that must never reach a client.
ANSWER_KEY_FIELDS = re.compile(
    r'"(rubric|rubric_native|accepted_answers|correct_option_id|correct_tile_order'
    r"|solution_fr|target_answer|allowed_outcomes|required_intents|optional_intents"
    r'|is_correct|suggested_response_fr)"'
)


def _manifest() -> dict:
    return json.loads((BUNDLE / "manifest.json").read_text(encoding="utf-8"))


def _public_payloads() -> list[tuple[str, dict]]:
    return [
        (path.stem, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(PUBLIC.glob("*.json"))
    ]


def _snapshots(response: dict) -> list[dict]:
    """Every JourneySnapshot reachable from one fixture response."""

    found: list[dict] = []
    if isinstance(response, dict):
        if "steps" in response and "budget_seconds" in response:
            found.append(response)
        nested = response.get("journey")
        if isinstance(nested, dict) and "steps" in nested:
            found.append(nested)
    return found


def test_manifest_lists_exactly_the_public_fixtures() -> None:
    listed = {entry["fixture"] for entry in _manifest()["fixtures"]}
    on_disk = {path.stem for path in PUBLIC.glob("*.json")}
    assert listed == on_disk


def test_every_contracts_section_11_scenario_exists() -> None:
    on_disk = {path.stem for path in PUBLIC.glob("*.json")}
    assert REQUIRED_SCENARIOS <= on_disk


def test_private_pairs_are_declared_and_present() -> None:
    declared = {
        entry["fixture"] for entry in _manifest()["fixtures"] if entry["has_private_pair"]
    }
    assert declared == {path.stem for path in PRIVATE.glob("*.json")}


@pytest.mark.parametrize("name,payload", _public_payloads())
def test_public_fixture_never_leaks_answer_key_material(name: str, payload: dict) -> None:
    """A renderer payload may not carry the evaluator's answers."""

    serialized = json.dumps(payload, ensure_ascii=False)
    leak = ANSWER_KEY_FIELDS.search(serialized)
    assert leak is None, f"{name} leaks private field {leak.group(1) if leak else ''}"


@pytest.mark.parametrize("name,payload", _public_payloads())
def test_public_fixture_declares_the_frozen_contract_version(name: str, payload: dict) -> None:
    response = payload["response"]
    if payload["http_status"] >= 400:
        assert "detail" in response, f"{name} error fixture must use the detail envelope"
        assert "code" in response["detail"]
        return
    if "contract_version" in response:
        assert response["contract_version"] == CONTRACT_VERSION


@pytest.mark.parametrize("name,payload", _public_payloads())
def test_planned_steps_respect_the_five_minute_envelope(name: str, payload: dict) -> None:
    for snapshot in _snapshots(payload["response"]):
        steps = snapshot["steps"]
        if not steps:
            # preparing / unavailable legitimately carry no plan yet
            assert snapshot["status"] in {
                JourneyStatus.PREPARING, JourneyStatus.UNAVAILABLE
            }, f"{name}: only preparing/unavailable may have an empty plan"
            continue

        assert len(steps) <= MAX_PLANNED_STEPS, f"{name}: too many steps"
        assert [s["ordinal"] for s in steps] == list(range(len(steps))), f"{name}: ordinals"

        kinds = [s["kind"] for s in steps]
        assert kinds[0] == StepKind.SCENE, f"{name}: must open with the scene"
        assert kinds[-1] == StepKind.RESOLUTION, f"{name}: must end with the resolution"
        assert kinds.count(StepKind.RESPOND) == 1, f"{name}: exactly one respond step"
        assert kinds.count(StepKind.RECALL) <= MAX_RECALL_STEPS, f"{name}: recall cap"

        total = sum(s["estimated_seconds"] for s in steps)
        assert snapshot["budget_seconds"] == DEFAULT_BUDGET_SECONDS
        assert total <= snapshot["budget_seconds"], f"{name}: {total}s exceeds the budget"

        active = [s for s in steps if s["status"] == StepStatus.ACTIVE]
        assert len(active) <= 1, f"{name}: only one step may be active"
        if snapshot["status"] in {JourneyStatus.COMPLETED, JourneyStatus.ENDED_EARLY}:
            assert not active, f"{name}: a terminal journey has no active step"
            assert snapshot["current_step_id"] is None


@pytest.mark.parametrize("name,payload", _public_payloads())
def test_recall_options_never_mark_the_correct_choice(name: str, payload: dict) -> None:
    for snapshot in _snapshots(payload["response"]):
        for step in snapshot["steps"]:
            if step["kind"] != StepKind.RECALL:
                continue
            for option in step["prompt"]["options"]:
                assert set(option) == {"id", "text_fr"}, f"{name}: option carries extra keys"


@pytest.mark.parametrize("name,payload", _public_payloads())
def test_localized_strings_use_the_frozen_suffix_rule(name: str, payload: dict) -> None:
    """Every localized string is either `_fr` (content) or `_native` (controls)."""

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and key in {"title", "instruction", "summary",
                                                      "objective", "setup", "note"}:
                    pytest.fail(f"{name}: '{key}' must be suffixed _fr or _native")
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload["response"])


def test_early_finish_grants_no_objective_credit_and_no_keepsake() -> None:
    recap = json.loads((PUBLIC / "ended_early.json").read_text(encoding="utf-8"))
    recap = recap["response"]["recap"]
    assert recap["completion_kind"] == "early"
    assert recap["objective_outcome"] != "met"
    assert recap["collectible_ids"] == []
    assert all(
        target["evidence_kind"] != "produced_independent"
        for target in recap["practiced_targets"]
    )


def test_completed_recap_reports_real_evidence() -> None:
    recap = json.loads((PUBLIC / "completed.json").read_text(encoding="utf-8"))
    recap = recap["response"]["recap"]
    assert recap["completion_kind"] == "complete"
    assert recap["practiced_targets"], "a real completion names what was practiced"
    assert recap["active_seconds"] is None or recap["active_seconds"] > 0
    assert len(recap["collectible_ids"]) == 1


def test_supported_success_is_not_recorded_as_independent() -> None:
    attempt = json.loads((PUBLIC / "wrong_then_supported.json").read_text(encoding="utf-8"))
    body = attempt["response"]
    assert body["assistance_level"] != "none"
    assert body["task_outcome"] != "met" or body["assistance_level"] == "none"
    correction = body["correction"]
    assert correction["span_fr"] != correction["corrected_fr"], "no-op correction"


def test_disabled_flag_offers_no_journey_and_no_scenario() -> None:
    envelope = json.loads((PUBLIC / "flag_disabled.json").read_text(encoding="utf-8"))
    envelope = envelope["response"]
    assert envelope["enabled"] is False
    assert envelope["journey"] is None
    assert envelope["available"] is None


def test_midnight_resume_prefers_yesterdays_active_journey() -> None:
    envelope = json.loads((PUBLIC / "midnight_resume.json").read_text(encoding="utf-8"))
    envelope = envelope["response"]
    assert envelope["journey"] is not None
    assert envelope["journey"]["local_date"] < envelope["local_date"]
    assert envelope["journey"]["status"] == JourneyStatus.ACTIVE
    assert envelope["available"] is None, "no second journey is offered on top of it"


def test_control_language_fixtures_keep_french_content_french() -> None:
    for name in ("controls_de", "controls_fr"):
        envelope = json.loads((PUBLIC / f"{name}.json").read_text(encoding="utf-8"))
        envelope = envelope["response"]
        assert envelope["control_language"] == name.split("_")[1]
        assert envelope["available"]["title_fr"] == "Un café au Mistral"


def test_null_artwork_never_blocks_the_scene() -> None:
    payload = json.loads((PUBLIC / "null_art_fallback.json").read_text(encoding="utf-8"))
    snapshot = payload["response"]
    assert snapshot["scenario"]["image_url"] is None
    scene = next(s for s in snapshot["steps"] if s["kind"] == StepKind.SCENE)
    assert scene["prompt"]["image_url"] is None
    assert scene["prompt"]["setup_fr"], "the learner can still read the scene"


def test_a_character_reply_always_states_its_provenance() -> None:
    """CONTRACTS: an authored line must never be presented as a live model response."""

    for path in PUBLIC.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))["response"]
        if not isinstance(payload, dict) or not payload.get("character_reply_fr"):
            continue
        assert payload.get("reply_source") in {"model", "authored"}, (
            f"{path.stem} shows a character reply without saying where it came from"
        )


def test_no_recall_fixture_carries_its_own_answer() -> None:
    """WP-12 defect D-4: the prompt that asks the question must not contain the answer.

    The public target used to carry `label_fr` ("un café") while the options were
    built from the same labels, so the correct option text sat verbatim in the
    payload asking "Which French phrase means 'a coffee'?" — and reading it there
    bypassed the assistance ledger that a paid `solution` reveal records.
    """

    for path in PUBLIC.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))["response"]
        for snapshot in _snapshots(payload):
            for step in snapshot["steps"]:
                if step["kind"] != StepKind.RECALL:
                    continue
                target_label = (step["prompt"].get("target") or {}).get("label_fr")
                assert not target_label, (
                    f"{path.stem}: the recall target still ships label_fr "
                    f"({target_label!r}) alongside the options"
                )
