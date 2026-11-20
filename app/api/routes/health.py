from fastapi import APIRouter
from redis.exceptions import RedisError
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])



@router.get("/health")
async def health(db: DbSession) -> dict:
    # sending test query to check health
    db_ok = (await db.scalar(text("SELECT 1"))) == 1
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
    }
