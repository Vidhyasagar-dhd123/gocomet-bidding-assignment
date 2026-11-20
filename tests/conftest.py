"""Integration-test fixtures.

Tests run against a real PostgreSQL database (schema built with the Alembic
migrations) and a real Redis, with a controllable clock injected into the app.
"""
import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

os.environ.setdefault("ENABLE_CLOSER", "false")

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_redis
from app.core.clock import get_clock
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://bidding:bidding@localhost:5434/bidding_test"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/15")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeClock:
    def __init__(self, start: datetime):
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def set(self, value: datetime) -> None:
        self.current = value

    def advance(self, **kwargs) -> datetime:
        self.current += timedelta(**kwargs)
        return self.current


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema() -> None:
    """Rebuild the test schema from the Alembic migrations once per run."""
    async def reset_schema() -> None:
        eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with eng.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await eng.dispose()

    asyncio.run(reset_schema())
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")  # make sure the downgrade path works too
    command.upgrade(cfg, "head")


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with eng.begin() as conn:
        await conn.execute(text("TRUNCATE auction_events, bids, rfqs, suppliers RESTART IDENTITY CASCADE"))
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2030, 1, 15, 17, 0, tzinfo=timezone.utc))


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def client(session_factory, clock: FakeClock, redis: Redis) -> AsyncIterator[AsyncClient]:
    async def _get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_clock] = lambda: clock
    app.dependency_overrides[get_redis] = lambda: redis
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ----------------------------------------------------------------- data helpers
API = "/api/v1"


def iso(value: datetime) -> str:
    return value.isoformat()


@pytest.fixture
def make_rfq(client: AsyncClient, clock: FakeClock):
    """Create an RFQ. Defaults: started now, closes 18:00, forced close 18:30, X=10, Y=5."""

    async def _make(**overrides) -> dict:
        now = clock()
        payload = {
            "name": "Mumbai to Rotterdam FCL",
            "pickup_date": (now + timedelta(days=7)).date().isoformat(),
            "bid_start_at": iso(now),
            "bid_close_at": iso(now.replace(hour=18, minute=0)),
            "forced_close_at": iso(now.replace(hour=18, minute=30)),
            "trigger_window_minutes": 10,
            "extension_minutes": 5,
            "extension_trigger": "BID_RECEIVED",
        }
        payload.update(overrides)
        resp = await client.post(f"{API}/rfqs", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make


@pytest.fixture
def make_supplier(client: AsyncClient):
    async def _make(name: str) -> dict:
        resp = await client.post(f"{API}/suppliers", json={"name": name})
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make


@pytest.fixture
def bid(client: AsyncClient, clock: FakeClock):
    async def _bid(rfq_id: int, supplier_id: int, freight: float, *, expect: int = 201, **extra) -> dict:
        payload = {
            "supplier_id": supplier_id,
            "carrier_name": "Maersk",
            "freight_charges": freight,
            "origin_charges": 0,
            "destination_charges": 0,
            "transit_time_days": 20,
            "quote_validity_date": (clock() + timedelta(days=30)).date().isoformat(),
        }
        payload.update(extra)
        resp = await client.post(f"{API}/rfqs/{rfq_id}/bids", json=payload)
        assert resp.status_code == expect, resp.text
        return resp.json()

    return _bid
