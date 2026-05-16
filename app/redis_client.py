import redis.asyncio as aioredis
from app.config import settings

redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

async def blacklist_token(token: str, expire_seconds: int):
    await redis.setex(f"blacklist:{token}", expire_seconds, "1")

async def is_blacklisted(token: str) -> bool:
    return await redis.exists(f"blacklist:{token}") == 1