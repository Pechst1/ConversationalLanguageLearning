"""Pytest fixtures placeholder following roadmap guidance."""

import pytest


@pytest.fixture(scope="session")
def event_loop():  # pragma: no cover - placeholder for async tests
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
