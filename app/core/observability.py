"""WP-73 — see production: structured logs, request ids, error tracking, worker liveness.

Everything here is configured from the process environment (Render sets it), not
from ``app.config.settings``, so the API, the Celery worker and one-off scripts
share one switchboard:

``LOG_FORMAT``          ``json`` (one JSON object per line, ``extra`` included) or
                        ``text``. Default: ``json`` when ``APP_ENV=production``.
``LOG_LEVEL``           default ``INFO``.
``SENTRY_DSN``          unset → Sentry is never initialised (tests, local dev).
``SENTRY_ENVIRONMENT``  default ``APP_ENV``.
``SENTRY_RELEASE``      default ``RENDER_GIT_COMMIT`` (Render sets it on every deploy).
``SENTRY_TRACES_SAMPLE_RATE``  default ``0`` (errors only; performance costs quota).
``WORKER_HEARTBEAT_STALE_SECONDS``  default ``300``.

PII: learner French text reaches the API in request bodies, so Sentry never sees
a body (``max_request_body_size="never"``), never sees local variables, cookies,
query strings or headers beyond a small allow-list, and knows a user by id only.
"""
from __future__ import annotations

import contextvars
import inspect
import json
import logging
import os
import re
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from loguru import logger

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")

#: The request (or task) this code runs for. Read by the loguru patcher, the
#: Sentry ``before_send`` hook and Celery's publish signal.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def app_env() -> str:
    return _env("APP_ENV", "development").lower()


# ---------------------------------------------------------------------------
# Request ids
# ---------------------------------------------------------------------------


def new_request_id() -> str:
    return uuid.uuid4().hex


def accept_request_id(candidate: str | None) -> str:
    """A caller's id when it is a sane token, a fresh one otherwise."""

    if candidate and _REQUEST_ID_RE.match(candidate.strip()):
        return candidate.strip()
    return new_request_id()


def current_request_id() -> str | None:
    return request_id_var.get()


class RequestIdMiddleware:
    """Pure ASGI: accept/create ``X-Request-ID``, bind it, echo it on the response."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        incoming = None
        for key, value in scope.get("headers") or []:
            if key == b"x-request-id":
                incoming = value.decode("latin-1", "replace")
                break
        request_id = accept_request_id(incoming)
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        _sentry_tag("request_id", request_id)

        async def send_with_id(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers") or [] if k.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_handler_id: int | None = None
_default_removed = False


def log_format() -> str:
    explicit = _env("LOG_FORMAT").lower()
    if explicit in ("json", "text"):
        return explicit
    return "json" if app_env() == "production" else "text"


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def format_json_record(record: Mapping[str, Any]) -> str:
    """One log line: time, level, message, where, request id, extras, exception."""

    extra = {k: _json_safe(v) for k, v in (record.get("extra") or {}).items()}
    payload: dict[str, Any] = {
        "time": record["time"].astimezone(UTC).isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "logger": record.get("name"),
        "function": record.get("function"),
        "line": record.get("line"),
    }
    request_id = extra.pop("request_id", None)
    if request_id:
        payload["request_id"] = request_id
    if extra:
        payload["extra"] = extra
    exception = record.get("exception")
    if exception is not None and exception.type is not None:
        import traceback

        payload["exception"] = {
            "type": exception.type.__name__,
            "value": str(exception.value),
            "traceback": "".join(traceback.format_exception(exception.type, exception.value, exception.traceback)),
        }
    return json.dumps(payload, ensure_ascii=False)


def _json_sink(stream: Any) -> Callable[[Any], None]:
    def sink(message: Any) -> None:
        stream.write(format_json_record(message.record) + "\n")
        stream.flush()

    return sink


def _patch_request_id(record: dict) -> None:
    request_id = request_id_var.get()
    if request_id and "request_id" not in record["extra"]:
        record["extra"]["request_id"] = request_id


def _text_format(record: dict) -> str:
    extra = {k: v for k, v in record["extra"].items() if k != "request_id"}
    record["extra"]["_rendered_extra"] = (" " + " ".join(f"{k}={v!r}" for k, v in extra.items())) if extra else ""
    rid = record["extra"].get("request_id")
    record["extra"]["_rid"] = f" [{rid[:8]}]" if rid else ""
    return (
        "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level>{extra[_rid]} | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>{extra[_rendered_extra]}\n{exception}"
    )


class InterceptHandler(logging.Handler):
    """Route stdlib logging (uvicorn, sqlalchemy, celery, our own modules) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(*, fmt: str | None = None, stream: Any = None, level: str | None = None) -> int:
    """Install our single stderr sink. Idempotent: replaces only its own handler.

    Handlers other code (tests) added to loguru are left alone; so are root
    logging handlers — the intercept is appended, never forced.
    """

    global _handler_id, _default_removed
    fmt = (fmt or log_format()).lower()
    level = (level or _env("LOG_LEVEL", "INFO")).upper()
    stream = stream or sys.stderr
    if not _default_removed:
        try:
            logger.remove(0)
        except ValueError:
            pass
        _default_removed = True
    if _handler_id is not None:
        try:
            logger.remove(_handler_id)
        except ValueError:
            pass
    logger.configure(patcher=_patch_request_id)
    if fmt == "json":
        _handler_id = logger.add(_json_sink(stream), level=level, format="{message}", backtrace=False, diagnose=False)
    else:
        _handler_id = logger.add(stream, level=level, format=_text_format, backtrace=False, diagnose=False)

    root = logging.getLogger()
    if not any(isinstance(h, InterceptHandler) for h in root.handlers):
        root.addHandler(InterceptHandler())
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "sqlalchemy"):
        std = logging.getLogger(name)
        std.handlers = [h for h in std.handlers if isinstance(h, InterceptHandler)]
        std.propagate = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    return _handler_id


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------

_SAFE_HEADERS = {"user-agent", "content-type", "content-length", "x-request-id", "accept", "origin"}
_sentry_ready = False


def sentry_enabled() -> bool:
    return _sentry_ready


def _sentry_tag(key: str, value: str) -> None:
    if not _sentry_ready:
        return
    import sentry_sdk

    sentry_sdk.get_isolation_scope().set_tag(key, value)


def scrub_event(event: dict, hint: dict | None = None) -> dict:
    """``before_send``: strip anything that could carry learner text or credentials."""

    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        request.pop("query_string", None)
        request.pop("env", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {k: v for k, v in headers.items() if k.lower() in _SAFE_HEADERS}
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if user.get("id") else {}
    for crumb in (event.get("breadcrumbs") or {}).get("values", []) if isinstance(event.get("breadcrumbs"), dict) else []:
        if isinstance(crumb, dict):
            crumb.pop("data", None)
    for exc in ((event.get("exception") or {}).get("values") or []):
        for frame in ((exc.get("stacktrace") or {}).get("frames") or []):
            frame.pop("vars", None)
    tags = event.setdefault("tags", {})
    request_id = request_id_var.get()
    if request_id and isinstance(tags, dict) and not tags.get("request_id"):
        tags["request_id"] = request_id
    return event


def init_sentry(component: str, *, transport: Any = None, dsn: str | None = None) -> bool:
    """Initialise Sentry for ``api`` or ``worker``. No DSN → strict no-op."""

    global _sentry_ready
    dsn = dsn if dsn is not None else _env("SENTRY_DSN")
    if not dsn:
        return False
    import sentry_sdk

    integrations: list[Any] = []
    if component == "worker":
        from sentry_sdk.integrations.celery import CeleryIntegration

        integrations.append(CeleryIntegration(monitor_beat_tasks=False, propagate_traces=False))
    else:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations += [StarletteIntegration(), FastApiIntegration()]
    try:
        traces = float(_env("SENTRY_TRACES_SAMPLE_RATE", "0") or 0)
    except ValueError:
        traces = 0.0
    kwargs: dict[str, Any] = {
        "dsn": dsn,
        "environment": _env("SENTRY_ENVIRONMENT") or app_env(),
        "release": _env("SENTRY_RELEASE") or _env("RENDER_GIT_COMMIT") or None,
        "send_default_pii": False,
        "max_request_body_size": "never",
        "include_local_variables": False,
        "traces_sample_rate": traces,
        "before_send": scrub_event,
        "integrations": integrations,
    }
    if transport is not None:
        kwargs["transport"] = transport
    sentry_sdk.init(**kwargs)
    sentry_sdk.set_tag("component", component)
    _sentry_ready = True
    return True


def set_sentry_user(user_id: Any) -> None:
    """Identify the learner by id only — never email or name."""

    if not _sentry_ready or not user_id:
        return
    import sentry_sdk

    sentry_sdk.set_user({"id": str(user_id)})


# ---------------------------------------------------------------------------
# Worker liveness
# ---------------------------------------------------------------------------

HEARTBEAT_KEY = "wp73:worker:heartbeat"


def _redis_client() -> Any:
    import redis

    from app.config import settings

    return redis.Redis.from_url(str(settings.REDIS_URL), socket_timeout=1.0, socket_connect_timeout=1.0)


def write_heartbeat(client: Any = None, *, now: float | None = None) -> float:
    stamp = float(now if now is not None else time.time())
    (client or _redis_client()).set(HEARTBEAT_KEY, repr(stamp), ex=24 * 3600)
    return stamp


def worker_health(client: Any = None, *, now: float | None = None) -> dict[str, Any]:
    """``status``: ``ok`` | ``stale`` | ``missing`` | ``unreachable``."""

    stale_after = int(_env("WORKER_HEARTBEAT_STALE_SECONDS", "300") or 300)
    now = float(now if now is not None else time.time())
    try:
        raw = (client or _redis_client()).get(HEARTBEAT_KEY)
    except Exception as exc:  # noqa: BLE001 — any Redis failure is "can't tell"
        logger.warning("Worker health: Redis unreachable", error=type(exc).__name__)
        return {"status": "unreachable", "stale_after_seconds": stale_after}
    if raw is None:
        return {"status": "missing", "stale_after_seconds": stale_after}
    last = float(raw.decode() if isinstance(raw, bytes) else raw)
    age = max(0.0, now - last)
    return {
        "status": "ok" if age <= stale_after else "stale",
        "age_seconds": round(age, 1),
        "last_heartbeat": datetime.fromtimestamp(last, tz=UTC).isoformat(),
        "stale_after_seconds": stale_after,
    }


def install_api_observability(app: Any) -> None:
    """One call from ``create_app``: logs, Sentry, request ids, ``/health/worker``."""

    from fastapi.responses import JSONResponse

    configure_logging()
    init_sentry("api")
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health/worker", include_in_schema=False)
    def health_worker() -> JSONResponse:
        """Celery liveness, separate from ``/ready`` so a dead worker never takes the API down."""

        body = worker_health()
        return JSONResponse(body, status_code=200 if body["status"] == "ok" else 503)
