"""Real-time session connection management backed by Redis."""
from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import WebSocket
from loguru import logger

from app.config import settings

try:  # pragma: no cover - optional dependency guard
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None  # type: ignore


class SessionConnectionManager:
    """Track active WebSocket connections for learning sessions."""

    def __init__(self, redis_url: str | None = None, namespace: str = "ws:sessions") -> None:
        self.redis_url = redis_url
        self.namespace = namespace
        self._redis: redis.Redis | None = None  # type: ignore[assignment]
        self._lock = asyncio.Lock()
        self._connections: Dict[uuid.UUID, Dict[uuid.UUID, WebSocket]] = defaultdict(dict)

    async def _get_redis(self) -> "redis.Redis | None":  # type: ignore[name-defined]
        if not self.redis_url or redis is None:  # type: ignore[name-defined]
            return None
        if self._redis is None:
            self._redis = redis.from_url(  # type: ignore[attr-defined]
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=1.5,
            )
        return self._redis

    def _session_key(self, session_id: uuid.UUID) -> str:
        return f"{self.namespace}:{session_id}"

    async def connect(self, *, websocket: WebSocket, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Register a WebSocket connection for a learner."""

        await websocket.accept()
        async with self._lock:
            self._connections[session_id][user_id] = websocket
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.hset(
                    self._session_key(session_id),
                    str(user_id),
                    datetime.now(timezone.utc).isoformat(),
                )
                await redis_client.expire(self._session_key(session_id), 3600)
            except Exception as exc:  # pragma: no cover - redis optional
                logger.warning("Failed to persist connection state in Redis", error=str(exc))
        logger.info(
            "WebSocket connected",
            session_id=str(session_id),
            user_id=str(user_id),
        )

    async def disconnect(self, *, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove a learner connection and clean up Redis state."""

        async with self._lock:
            session_connections = self._connections.get(session_id, {})
            session_connections.pop(user_id, None)
            if not session_connections and session_id in self._connections:
                self._connections.pop(session_id, None)
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.hdel(self._session_key(session_id), str(user_id))
            except Exception as exc:  # pragma: no cover - redis optional
                logger.warning("Failed to clean Redis connection state", error=str(exc))
        logger.info(
            "WebSocket disconnected",
            session_id=str(session_id),
            user_id=str(user_id),
        )

    async def broadcast(self, *, session_id: uuid.UUID, message: dict[str, Any]) -> None:
        """Broadcast a payload to every connection within the session."""

        async with self._lock:
            targets = list(self._connections.get(session_id, {}).values())
        for connection in targets:
            try:
                await connection.send_json(message)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to broadcast message", error=str(exc))

    async def send_personal_message(
        self,
        *,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        message: dict[str, Any],
    ) -> None:
        """Send a payload to a single learner connection."""

        connection = None
        async with self._lock:
            connection = self._connections.get(session_id, {}).get(user_id)
        if connection is None:
            return
        await connection.send_json(message)

    async def mark_heartbeat(self, *, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Record a heartbeat timestamp in Redis for monitoring."""

        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.hset(
                    self._session_key(session_id),
                    str(user_id),
                    datetime.now(timezone.utc).isoformat(),
                )
            except Exception as exc:  # pragma: no cover - redis optional
                logger.warning("Failed to record heartbeat", error=str(exc))

    async def list_active_users(self, session_id: uuid.UUID) -> list[str]:
        """Return IDs for connected users (from Redis if available)."""

        redis_client = await self._get_redis()
        if redis_client:
            try:
                members = await redis_client.hkeys(self._session_key(session_id))
                if members:
                    return members
            except Exception as exc:  # pragma: no cover - redis optional
                logger.warning("Failed to list Redis connections", error=str(exc))
        async with self._lock:
            return [str(user_id) for user_id in self._connections.get(session_id, {}).keys()]


def build_default_connection_manager() -> SessionConnectionManager:
    """Factory used by API dependencies to create a connection manager."""

    return SessionConnectionManager(redis_url=str(settings.REDIS_URL))
