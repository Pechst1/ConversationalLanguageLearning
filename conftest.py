"""Repository-root pytest guard: the test suite may never reach a paid provider.

Loaded before ``tests/conftest.py`` and therefore before ``app.config`` reads the
real ``.env``. This exists because of a real incident on 2026-09-05: a package's
test fixture set ``settings.ATELIER_LLM_ENABLED = True`` globally, and since
``app/config.py`` loads the repository ``.env`` — which holds a live
``OPENAI_API_KEY`` — several test runs made billable API calls.

``tests/conftest.py`` only calls ``os.environ.setdefault(...)`` on the feature
flags, which does not help: a test that flips a flag at runtime re-enables the
provider with a real key still in place. So the keys themselves are neutralised
here. A test that genuinely needs provider behaviour must patch the client
object (e.g. ``journey_content.LLMService``, ``journey_conversation._conversation_llm``),
never rely on a real credential.
"""
from __future__ import annotations

import os

# Obviously-fake, clearly-labelled credentials. Set (not setdefault) so a real key
# inherited from the developer's shell or .env cannot survive into a test run.
_NEUTRALISED = "test-key-not-a-real-credential"

for _variable in (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "PERPLEXITY_API_KEY",
    "ELEVENLABS_API_KEY",
):
    os.environ[_variable] = _NEUTRALISED

# Deliberately NOT done here: forcing the cost-bearing feature flags off.
# An earlier version of this guard also set ATELIER_CORRECTION_LLM_ENABLED and
# friends to "false". That broke 7 tests in tests/test_atelier.py which depend on
# the real default (True) to exercise the AI-review and critic paths against a
# fake llm_service. Neutralising the credentials above is what actually prevents
# spend — a request with a fake key is rejected, not billed — so flag defaults are
# left exactly as the application and tests/conftest.py define them.


def pytest_report_header() -> str:
    """Make the guard visible in every run, so a regression is noticed."""

    return "provider guard: API keys neutralised; no test may reach a paid provider"
