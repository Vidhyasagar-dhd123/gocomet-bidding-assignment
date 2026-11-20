from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuctionNotOpenError, NotFoundError, ValidationError
from app.models import AuctionEvent, AuctionEventType, AuctionStatus, Bid, Supplier
from app.schemas.bid import BidCreate, BidPlacedOut
from app.services import auction_rules as rules
from app.services.rfq_service import bid_to_out, get_rfq, rfq_status, standing_bids, to_rank_entries


def _fmt_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S %Z")


async def place_bid(
    db: AsyncSession, rfq_id: int, data: BidCreate, *, clock
) -> tuple[BidPlacedOut, list[AuctionEvent]]:
    rfq = await get_rfq(db, rfq_id, for_update=True)
    now: datetime = clock()

    status = rfq_status(rfq, now)
    if status is AuctionStatus.SCHEDULED:
        raise AuctionNotOpenError(
            "Auction has not started yet", details={"bid_start_at": rfq.bid_start_at.isoformat()}
        )
    if status in (AuctionStatus.CLOSED, AuctionStatus.FORCE_CLOSED):
        raise AuctionNotOpenError(
            "Auction is closed", details={"status": status.value, "closed_at": rfq.current_close_at.isoformat()}
        )

    supplier = await db.get(Supplier, data.supplier_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {data.supplier_id} not found")

    if data.quote_validity_date < now.date():
        raise ValidationError("Quote validity date cannot be in the past")

    standing = await standing_bids(db, rfq.id)
    total = data.total_amount
    own = next((b for b in standing if b.supplier_id == supplier.id), None)
    if own is not None and total >= own.total_amount:
        raise ValidationError(
            f"New bid must be lower than your current bid of {own.total_amount:.2f}",
            details={"current_bid": float(own.total_amount), "submitted": float(total)},
        )

    ranking_before = rules.rank_order(to_rank_entries(standing))

    bid = Bid(
        rfq_id=rfq.id,
        supplier_id=supplier.id,
        carrier_name=data.carrier_name.strip(),
        freight_charges=data.freight_charges,
        origin_charges=data.origin_charges,
        destination_charges=data.destination_charges,
        total_amount=total,
        transit_time_days=data.transit_time_days,
        quote_validity_date=data.quote_validity_date,
        remarks=data.remarks,
        created_at=now,
    )
    bid.supplier = supplier
    db.add(bid)
    await db.flush()

    after_entries = [e for e in to_rank_entries(standing) if e.supplier_id != supplier.id]
    after_entries.append(rules.RankEntry(supplier.id, total, now))
    ranking_after = rules.rank_order(after_entries)
    new_rank = rules.rank_map(ranking_after)[supplier.id]
    previous_rank = rules.rank_map(ranking_before).get(supplier.id)

    decision = rules.evaluate_extension(
        trigger=rfq.extension_trigger,
        now=now,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        window_minutes=rfq.trigger_window_minutes,
        extension_minutes=rfq.extension_minutes,
        ranking_before=ranking_before,
        ranking_after=ranking_after,
    )

    rank_msg = f"{rules.rank_label(new_rank)}"
    if previous_rank and previous_rank != new_rank:
        rank_msg += f" (was {rules.rank_label(previous_rank)})"
    events = [
        AuctionEvent(
            rfq_id=rfq.id,
            event_type=AuctionEventType.BID_SUBMITTED,
            supplier_id=supplier.id,
            bid_id=bid.id,
            message=f"{supplier.name} submitted a bid of {total:.2f} - now {rank_msg}",
            details={
                "supplier_name": supplier.name,
                "carrier_name": bid.carrier_name,
                "total_amount": float(total),
                "previous_amount": float(own.total_amount) if own else None,
                "rank": new_rank,
                "previous_rank": previous_rank,
                "ranking_before": ranking_before,
                "ranking_after": ranking_after,
                "in_trigger_window": decision.in_window,
                "extension_triggered": decision.triggered,
            },
            created_at=now,
        )
    ]

    if decision.extended:
        rfq.current_close_at = decision.new_close_at
        rfq.extension_count += 1
        reason = decision.reason or ""
        if decision.capped_at_forced_close:
            reason += " (extension capped at forced close time)"
        events.append(
            AuctionEvent(
                rfq_id=rfq.id,
                event_type=AuctionEventType.AUCTION_EXTENDED,
                supplier_id=supplier.id,
                bid_id=bid.id,
                message=f"Auction extended from {_fmt_time(decision.previous_close_at)} "
                f"to {_fmt_time(decision.new_close_at)}: {reason}",
                details={
                    "trigger": rfq.extension_trigger.value,
                    "reason": reason,
                    "previous_close_at": decision.previous_close_at.isoformat(),
                    "new_close_at": decision.new_close_at.isoformat(),
                    "extension_minutes": rfq.extension_minutes,
                    "applied_minutes": (decision.new_close_at - decision.previous_close_at).total_seconds() / 60,
                    "capped_at_forced_close": decision.capped_at_forced_close,
                    "forced_close_at": rfq.forced_close_at.isoformat(),
                    "extension_number": rfq.extension_count,
                },
                created_at=now,
            )
        )
    elif decision.triggered:
        events[0].details["extension_skipped_reason"] = "Auction already at forced close time"

    db.add_all(events)
    await db.commit()

    result = BidPlacedOut(
        bid=bid_to_out(bid),
        rank=new_rank,
        rank_label=rules.rank_label(new_rank),
        auction_extended=decision.extended,
        extension_reason=events[1].details["reason"] if decision.extended else None,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
    )
    return result, events
