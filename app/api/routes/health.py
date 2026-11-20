from fastapi import APIRouter
from redis.exceptions import RedisError
from sqlalchemy import text

from app.api.deps import ClockDep, DbSession, RedisDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DbSession, redis: RedisDep, clock: ClockDep) -> dict:
    db_ok = (await db.scalar(text("SELECT 1"))) == 1
    redis_ok = False
    if redis is not None:
        try:
            redis_ok = bool(await redis.ping())
        except RedisError:
            redis_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "redis": redis_ok,
        "server_time": clock().isoformat(),
    }
