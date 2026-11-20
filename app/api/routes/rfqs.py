import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import ClockDep, DbSession, RedisDep
from app.core.config import settings
from app.core.errors import DomainError
from app.models import AuctionStatus
from app.schemas.bid import BidCreate, BidOut, BidPlacedOut, RankedBidOut
from app.schemas.common import Page
from app.schemas.rfq import AuctionEventOut, RfqCreate, RfqDetailOut, RfqSummaryOut
from app.services import bid_service, rfq_service
from app.services.events import ALL_AUCTIONS_CHANNEL, publish_events, rfq_channel

router = APIRouter(prefix="/rfqs", tags=["rfqs"])


@router.post("", response_model=RfqDetailOut, status_code=status.HTTP_201_CREATED)
async def create_rfq(payload: RfqCreate, db: DbSession, clock: ClockDep, redis: RedisDep) -> RfqDetailOut:
    now = clock()
    rfq, event = await rfq_service.create_rfq(db, payload, now=now)
    await publish_events(redis, [event])
    return await rfq_service.get_rfq_detail(db, rfq.id, now=now)


@router.get("", response_model=Page[RfqSummaryOut])
async def list_rfqs(
    db: DbSession,
    clock: ClockDep,
    status_filter: AuctionStatus | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[RfqSummaryOut]:
    items, total = await rfq_service.list_rfqs(
        db, now=clock(), status=status_filter, search=search, limit=limit, offset=offset
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{rfq_id}", response_model=RfqDetailOut)
async def get_rfq(rfq_id: int, db: DbSession, clock: ClockDep) -> RfqDetailOut:
    return await rfq_service.get_rfq_detail(db, rfq_id, now=clock())


@router.get("/{rfq_id}/ranking", response_model=list[RankedBidOut])
async def get_ranking(rfq_id: int, db: DbSession) -> list[RankedBidOut]:
    await rfq_service.get_rfq(db, rfq_id)
    return await rfq_service.ranking(db, rfq_id)


@router.get("/{rfq_id}/bids", response_model=list[BidOut])
async def list_bids(rfq_id: int, db: DbSession) -> list[BidOut]:
    return await rfq_service.all_bids(db, rfq_id)


@router.post("/{rfq_id}/bids", response_model=BidPlacedOut, status_code=status.HTTP_201_CREATED)
async def place_bid(
    rfq_id: int, payload: BidCreate, db: DbSession, clock: ClockDep, redis: RedisDep
) -> BidPlacedOut:
    result, events = await bid_service.place_bid(db, rfq_id, payload, clock=clock)
    await publish_events(redis, events)
    return result


@router.get("/{rfq_id}/activity", response_model=list[AuctionEventOut])
async def get_activity(rfq_id: int, db: DbSession) -> list[AuctionEventOut]:
    await rfq_service.get_rfq(db, rfq_id)
    return await rfq_service.activity(db, rfq_id)


@router.get("/{rfq_id}/stream", response_class=StreamingResponse)
async def stream_rfq_events(rfq_id: int, request: Request, db: DbSession, redis: RedisDep) -> StreamingResponse:
    """Server-sent events for one auction (bids, extensions, close)."""
    await rfq_service.get_rfq(db, rfq_id)
    await db.close()  # don't hold a DB connection for the lifetime of the stream
    return _sse_response(request, redis, rfq_channel(rfq_id))


events_router = APIRouter(prefix="/events", tags=["events"])


@events_router.get("/stream", response_class=StreamingResponse)
async def stream_all_events(request: Request, redis: RedisDep) -> StreamingResponse:
    """Server-sent events for every auction (used by the listing page)."""
    return _sse_response(request, redis, ALL_AUCTIONS_CHANNEL)


def _sse_response(request: Request, redis, channel: str) -> StreamingResponse:
    if redis is None:
        raise DomainError("Real-time updates are unavailable (Redis not configured)")

    async def gen() -> AsyncIterator[str]:
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            yield "retry: 3000\n\n"
            while not await request.is_disconnected():
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=settings.sse_heartbeat_seconds
                )
                if msg is None:
                    yield ": keep-alive\n\n"
                    continue
                data = msg["data"]
                event_type = json.loads(data).get("event_type", "message")
                yield f"event: {event_type}\ndata: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
