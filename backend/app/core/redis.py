from redis.asyncio import Redis, from_url

from app.core.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis


async def publish_event(event_data: dict) -> str:
    """Append event to Redis Stream. Returns stream entry ID."""
    r = await get_redis()
    return await r.xadd(settings.redis_stream_key, event_data)


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
