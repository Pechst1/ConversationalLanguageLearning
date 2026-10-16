"""gpt-5-mini retires on 2026-12-11; its replacement (gpt-6-luna) is a reasoning model too.

Three callers set ``reasoning_effort`` only for names starting with ``gpt-5``: on a
gpt-6 model they sent none, and the model reasoned at its default, slower and dearer.
"""

from __future__ import annotations

import pytest

from app.services.llm_service import openai_reasoning_effort, takes_reasoning_effort


@pytest.mark.parametrize(
    "model, expected",
    [("gpt-5-mini", True), ("gpt-6-luna", True), ("gpt-6.1-sol", True), ("gpt-4o", False), ("claude-haiku-5-5", False), (None, False)],
)
def test_the_reasoning_models_are_the_gpt_5_and_gpt_6_families(model, expected):
    assert takes_reasoning_effort(model) is expected


def test_minimal_effort_on_gpt_6_is_sent_as_none():
    assert openai_reasoning_effort("gpt-6-luna", "minimal") == "none"
    assert openai_reasoning_effort("gpt-5-mini", "minimal") == "minimal"


def test_no_caller_tests_the_gpt_5_prefix_by_hand():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if 'startswith("gpt-5")' in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"use llm_service.takes_reasoning_effort: {offenders}"
