import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.models import AuctionEvent

logger = logging.getLogger(__name__)

ALL_AUCTIONS_CHANNEL = "auctions:events"


def rfq_channel(rfq_id: int) -> str:
    return f"auctions:{rfq_id}:events"


def serialize_event(event: AuctionEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "rfq_id": event.rfq_id,
        "event_type": event.event_type.value,
        "supplier_id": event.supplier_id,
        "bid_id": event.bid_id,
        "message": event.message,
        "details": event.details,
        "created_at": event.created_at.isoformat(),
    }


async def publish_events(redis: Redis | None, events: list[AuctionEvent]) -> None:
    if redis is None or not events:
        return
    try:
        async with redis.pipeline(transaction=False) as pipe:
            for event in events:
                payload = json.dumps(serialize_event(event), default=str)
                pipe.publish(rfq_channel(event.rfq_id), payload)
                pipe.publish(ALL_AUCTIONS_CHANNEL, payload)
            await pipe.execute()
    except RedisError:
        logger.warning("Failed to publish %d auction event(s) to Redis", len(events), exc_info=True)
