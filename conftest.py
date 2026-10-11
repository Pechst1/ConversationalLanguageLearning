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

# WP-108: the same for the job queue. The owner's `.env` points Celery at the real
# local Redis, so every test that reached `.delay()` / `.apply_async()` queued a real
# job there: 1,499 of them (1,443 notifications, 56 next-day warm-ups) sat waiting for a
# worker, and a worker started on them would have made paid calls. Set (not setdefault)
# before `app.config` reads `.env`: an environment variable outranks the dotenv file.
# `tests/test_wp108_no_real_broker.py` fails the suite if this ever regresses.
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "false"

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_task_reaches_a_real_broker(monkeypatch):
    """Fail the test that sends a Celery task to anything but the in-memory broker."""

    from celery.app.task import Task

    real_apply_async = Task.apply_async

    def guarded(self, *args, **kwargs):
        broker = str(self.app.conf.broker_url or "")
        if not (broker.startswith("memory:") or self.app.conf.task_always_eager):
            raise AssertionError(
                f"WP-108: {self.name} was sent to a real broker ({broker!r}) during a test. "
                "Patch the task's .delay/.apply_async or keep CELERY_BROKER_URL=memory://."
            )
        return real_apply_async(self, *args, **kwargs)

    monkeypatch.setattr(Task, "apply_async", guarded)


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


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Fold pytest-randomly's per-test seed into 32 bits for its entry-point seeders.

    pytest-randomly reseeds every test phase with ``randomly_seed + crc32(nodeid)``,
    which can reach 2**33. It folds that into numpy's range itself but hands it
    unfolded to each ``pytest_randomly.random_seeder`` entry point, and spaCy's
    ``thinc`` registers one (``thinc.api:fix_random_seed``) that passes it straight
    to ``numpy.random.seed`` → «Seed must be between 0 and 2**32 - 1». Whenever the
    sum overflowed, a test errored in setup and teardown with nothing wrong in it:
    with the plugin's default random seed about half the tests of a file
    (tests/test_wp73_observability.py showed 18-28 errors), with a fixed seed a
    scattered handful across the suite.
    """

    try:
        import pytest_randomly
    except ImportError:  # pragma: no cover - plugin not installed
        return
    from importlib.metadata import entry_points

    def folded(reseed):
        def _reseed(seed: int) -> None:
            reseed(seed % 2**32)

        return _reseed

    pytest_randomly.entrypoint_reseeds = [
        folded(ep.load()) for ep in entry_points(group="pytest_randomly.random_seeder")
    ]
