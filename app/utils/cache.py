"""Caching utilities with optional Redis backing."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import threading
import time
from dataclasses import dataclass
from typing import Any

from app.config import settings


def _json_default(value: Any) -> Any:
    """Serialize values not supported by ``json`` out of the box."""

    if hasattr(value, "isoformat"):
        return value.isoformat()  # datetime and date objects
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "hex") and callable(getattr(value, "hex")):
        return value.hex()
    if hasattr(value, "__str__"):
        return str(value)
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


def build_cache_key(**components: Any) -> str:
    """Return a stable hash for the provided components."""

    def normalize_value(val: Any) -> Any:
        if isinstance(val, dict):
            return {k: normalize_value(v) for k, v in sorted(val.items())}
        if isinstance(val, (list, tuple)):
            return [normalize_value(item) for item in val]
        return val

    normalized = normalize_value(components)
    payload = json.dumps(normalized, sort_keys=True, default=_json_default)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


_redis_module = None
if importlib.util.find_spec("redis") is not None:
    _redis_module = importlib.import_module("redis")


@dataclass
class _CacheEntry:
    expires_at: float | None
    payload: str


class CacheBackend:
    """Simple cache backend writing to Redis when available."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._lock = threading.Lock()
        self._local: dict[str, _CacheEntry] = {}
        self._redis = None
        if redis_url and _redis_module is not None:
            self._redis = _redis_module.Redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _compose(namespace: str, key: str) -> str:
        return f"{namespace}:{key}"

    def get(self, namespace: str, key: str) -> Any | None:
        namespaced = self._compose(namespace, key)
        if self._redis is not None:
            try:
                value = self._redis.get(namespaced)
            except Exception:
                self._redis = None
            else:
                if value is not None:
                    return json.loads(value)
        with self._lock:
            entry = self._local.get(namespaced)
            if not entry:
                return None
            if entry.expires_at is not None and entry.expires_at < time.time():
                self._local.pop(namespaced, None)
                return None
            return json.loads(entry.payload)

    def set(self, namespace: str, key: str, value: Any, ttl_seconds: int) -> None:
        namespaced = self._compose(namespace, key)
        payload = json.dumps(value, default=_json_default)
        if self._redis is not None:
            try:
                self._redis.set(namespaced, payload, ex=ttl_seconds)
            except Exception:
                self._redis = None
        with self._lock:
            expires_at = time.time() + ttl_seconds if ttl_seconds else None
            self._local[namespaced] = _CacheEntry(expires_at=expires_at, payload=payload)

    def invalidate(self, namespace: str, *, key: str | None = None, prefix: str | None = None) -> None:
        if key is not None:
            namespaced = self._compose(namespace, key)
            if self._redis is not None:
                try:
                    self._redis.delete(namespaced)
                except Exception:
                    self._redis = None
            with self._lock:
                self._local.pop(namespaced, None)
            return

        if prefix is None:
            return

        pattern = self._compose(namespace, prefix)
        if self._redis is not None:
            try:
                for cache_key in self._redis.scan_iter(f"{pattern}*"):
                    self._redis.delete(cache_key)
            except Exception:
                self._redis = None
        with self._lock:
            for cache_key in list(self._local.keys()):
                if cache_key.startswith(pattern):
                    self._local.pop(cache_key, None)

    def clear(self, *, include_redis: bool = False) -> None:
        """Reset the in-memory cache (and optionally Redis) for test environments."""

        with self._lock:
            self._local.clear()
        if include_redis and self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception:
                self._redis = None


cache_backend = CacheBackend(str(settings.REDIS_URL) if settings.REDIS_URL else None)


__all__ = ["cache_backend", "CacheBackend", "build_cache_key"]
