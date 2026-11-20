from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, get_clock
from app.db.session import get_db


def get_redis(request: Request) -> Redis | None:
    return getattr(request.app.state, "redis", None)


DbSession = Annotated[AsyncSession, Depends(get_db)]
ClockDep = Annotated[Clock, Depends(get_clock)]
RedisDep = Annotated[Redis | None, Depends(get_redis)]
