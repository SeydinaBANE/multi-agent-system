"""Adapter cache/pub-sub — implémente CachePort via Redis."""
from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("cache")


class RedisCache:
    """Implémentation de CachePort adossée à Redis (pub/sub pour le streaming WebSocket)."""

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    def get_client(self) -> aioredis.Redis:
        """Retourne la connexion Redis (singleton lazy, decode_responses=True)."""
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def publish(self, channel: str, message: str) -> None:
        """Publie un message JSON sur le canal Redis spécifié."""
        try:
            r = self.get_client()
            await r.publish(channel, message)
        except Exception as exc:
            log.warning("redis_publish_failed", channel=channel, error=str(exc))
            raise

    async def subscribe(self, channel: str) -> aioredis.client.PubSub:
        """Crée et retourne un abonnement pub/sub sur le canal Redis spécifié."""
        try:
            r = self.get_client()
            pubsub = r.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as exc:
            log.warning("redis_subscribe_failed", channel=channel, error=str(exc))
            raise

    async def close(self) -> None:
        """Ferme la connexion Redis (appelé au shutdown FastAPI)."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
