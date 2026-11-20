import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.api.router import api_router
from app.core.clock import utcnow
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.db.session import SessionLocal, engine
from app.services.closer import run_closer_loop

# setting up loggin
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Redis client used by SSE streams, event publishing and the closer lock.
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    closer_task = None
    if settings.enable_closer:
        closer_task = asyncio.create_task(
            run_closer_loop(SessionLocal, app.state.redis, utcnow, settings.closer_interval_seconds)
        )
    try:
        yield
    finally:
        if closer_task is not None:
            closer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await closer_task
        await app.state.redis.aclose()
        await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
