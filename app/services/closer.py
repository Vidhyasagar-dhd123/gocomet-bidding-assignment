import asyncio
import logging
from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import Clock
from app.models import AuctionEvent, AuctionEventType, AuctionStatus, Rfq
from app.services import auction_rules as rules
from app.services.events import publish_events
from app.services.rfq_service import standing_bids

logger = logging.getLogger(__name__)

CLOSER_LOCK_KEY = "auctions:closer:lock"


async def close_due_auctions(db: AsyncSession, *, now: datetime, batch_size: int = 100) -> list[AuctionEvent]:
    stmt = (
        select(Rfq)
        .where(Rfq.closed_at.is_(None), Rfq.current_close_at <= now)
        .order_by(Rfq.current_close_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rfqs = list(await db.scalars(stmt))
    events: list[AuctionEvent] = []
    for rfq in rfqs:
        status = rules.compute_status(
            bid_start_at=rfq.bid_start_at,
            current_close_at=rfq.current_close_at,
            forced_close_at=rfq.forced_close_at,
            now=now,
        )
        standing = await standing_bids(db, rfq.id)
        winner = standing[0] if standing else None
        forced = status is AuctionStatus.FORCE_CLOSED

        rfq.closed_at = rfq.current_close_at
        rfq.final_status = status

        if winner:
            outcome = f"L1: {winner.supplier.name} at {winner.total_amount:.2f}"
        else:
            outcome = "no bids received"
        label = "force closed (forced close time reached)" if forced else "closed"
        events.append(
            AuctionEvent(
                rfq_id=rfq.id,
                event_type=AuctionEventType.AUCTION_FORCE_CLOSED if forced else AuctionEventType.AUCTION_CLOSED,
                supplier_id=winner.supplier_id if winner else None,
                bid_id=winner.id if winner else None,
                message=f"Auction {label}; {outcome}",
                details={
                    "status": status.value,
                    "closed_at": rfq.current_close_at.isoformat(),
                    "original_close_at": rfq.bid_close_at.isoformat(),
                    "forced_close_at": rfq.forced_close_at.isoformat(),
                    "extension_count": rfq.extension_count,
                    "winning_amount": float(winner.total_amount) if winner else None,
                    "winning_supplier": winner.supplier.name if winner else None,
                    "supplier_count": len(standing),
                    "processed_at": now.isoformat(),
                },
                created_at=rfq.current_close_at,
            )
        )
    db.add_all(events)
    await db.commit()
    return events


async def run_closer_loop(
    session_factory: async_sessionmaker[AsyncSession],
    redis: Redis | None,
    clock: Clock,
    interval_seconds: float,
) -> None:
    
    lock_ttl_ms = max(int(interval_seconds * 900), 100)
    while True:
        try:
            have_lock = True
            if redis is not None:
                try:
                    have_lock = bool(await redis.set(CLOSER_LOCK_KEY, "1", nx=True, px=lock_ttl_ms))
                except RedisError:
                    have_lock = True  
            if have_lock:
                async with session_factory() as db:
                    events = await close_due_auctions(db, now=clock())
                if events:
                    logger.info("Closed %d auction(s)", len(events))
                    await publish_events(redis, events)
        except asyncio.CancelledError:
            raise
        except Exception:  
            logger.exception("Auction closer iteration failed")
        await asyncio.sleep(interval_seconds)
