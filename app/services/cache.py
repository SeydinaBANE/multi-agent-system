"""Client Redis asynchrone — cache applicatif et pub/sub pour le streaming WebSocket."""

import redis.asyncio as aioredis
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("cache")

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Retourne la connexion Redis (singleton lazy, decode_responses=True)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def publish(channel: str, message: str) -> None:
    """Publie un message JSON sur le canal Redis spécifié."""
    try:
        r = await get_redis()
        await r.publish(channel, message)
    except Exception as exc:
        log.warning("redis_publish_failed", channel=channel, error=str(exc))
        raise


async def subscribe(channel: str) -> aioredis.client.PubSub:
    """Crée et retourne un abonnement pub/sub sur le canal Redis spécifié."""
    try:
        r = await get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
    except Exception as exc:
        log.warning("redis_subscribe_failed", channel=channel, error=str(exc))
        raise
