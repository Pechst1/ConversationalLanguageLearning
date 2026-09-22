"""WP-70 — keep blocking work off the server's event loop.

Uvicorn runs every ``async def`` handler *on* the event loop. Most of this
app's handlers were declared ``async`` but then called synchronous I/O — the
sync SQLAlchemy session, the sync ``httpx`` OpenAI wrapper, 60-second TTS
retries — so one slow provider call froze ``/ready`` and every other learner's
request on that worker until it returned.

Two tools, in order of preference:

* **A plain ``def`` handler.** FastAPI runs it in its thread pool. This is the
  right answer whenever the handler awaits nothing real.
* :func:`off_event_loop`, for the handlers that *do* await — an upload's
  ``file.read()``, or a service coroutine that mixes real ``httpx.AsyncClient``
  calls (news, images) with sync database and LLM calls. The decorator keeps
  the handler a coroutine function (so FastAPI, and the tests that drive the
  handler directly with ``asyncio.run``, see no difference) but runs its whole
  body on a worker thread, inside a private event loop. Whatever that body
  blocks on, it blocks a pool thread, never the server's loop.

The database session is used by exactly one thread at a time either way, which
is the same guarantee FastAPI's own threadpool gives a ``def`` handler.
"""
from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from starlette.concurrency import run_in_threadpool

P = ParamSpec("P")
T = TypeVar("T")

#: Marker read by the WP-70 audit test: a coroutine route either carries it or
#: is on the short, reviewed list of handlers that are genuinely asynchronous.
OFFLOADED_ATTRIBUTE = "__wp70_off_event_loop__"


def _drive(
    fn: Callable[..., Awaitable[T]], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> T:
    """Run one coroutine to completion on this (worker) thread's own loop."""

    return asyncio.run(fn(*args, **kwargs))  # type: ignore[arg-type]


async def run_coroutine_off_loop(
    fn: Callable[P, Awaitable[T]], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Await ``fn(*args, **kwargs)`` without letting it block the caller's loop."""

    return await run_in_threadpool(_drive, fn, args, kwargs)


def off_event_loop(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """Decorate an ``async def`` route so its body runs on a worker thread.

    Place it *under* the ``@router.<method>`` decorator. FastAPI reads the
    handler's signature to build its dependencies; the evaluated signature of
    the original function is attached here, because a module written with
    ``from __future__ import annotations`` stores string annotations that
    FastAPI would otherwise try to resolve in *this* module's namespace.
    """

    if not inspect.iscoroutinefunction(fn):
        raise TypeError("off_event_loop only wraps coroutine functions; use a plain def handler")

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return await run_coroutine_off_loop(fn, *args, **kwargs)

    try:
        wrapper.__signature__ = inspect.signature(fn, eval_str=True)  # type: ignore[attr-defined]
    except NameError:  # pragma: no cover - a forward reference FastAPI resolves later
        wrapper.__signature__ = inspect.signature(fn)  # type: ignore[attr-defined]
    setattr(wrapper, OFFLOADED_ATTRIBUTE, True)
    return wrapper


__all__ = ["OFFLOADED_ATTRIBUTE", "off_event_loop", "run_coroutine_off_loop"]
