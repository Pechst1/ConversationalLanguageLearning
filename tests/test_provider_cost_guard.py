"""The suite must never be able to spend money. See the root ``conftest.py``."""
from __future__ import annotations

import pytest

from app.config import get_settings

NEUTRALISED = "test-key-not-a-real-credential"


@pytest.mark.parametrize(
    "field",
    ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY", "ELEVENLABS_API_KEY"],
)
def test_no_real_provider_credential_is_visible_to_the_suite(field: str) -> None:
    value = getattr(get_settings(), field)
    assert value == NEUTRALISED, (
        f"{field} is not neutralised. The root conftest.py guard is not loading, so a "
        "test that enables an LLM flag would make billable calls with a real key."
    )


@pytest.mark.parametrize(
    "prefix", ["sk-", "sk-ant-", "pplx-"]
)
def test_no_credential_looks_like_a_live_key(prefix: str) -> None:
    settings = get_settings()
    for field in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY"):
        value = getattr(settings, field) or ""
        assert not value.startswith(prefix), f"{field} looks like a live credential"


def test_enabling_the_llm_flag_alone_cannot_reach_a_provider(monkeypatch) -> None:
    """The exact 2026-09-05 incident shape: flip the flag, keep the real client."""

    settings = get_settings()
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True, raising=False)
    # Even with the flag on, there is no usable credential to spend.
    assert settings.OPENAI_API_KEY == NEUTRALISED
