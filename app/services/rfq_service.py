import secrets
from datetime import datetime

from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models import AuctionEvent, AuctionEventType, AuctionStatus, Bid, Rfq
from app.schemas.bid import BidOut, RankedBidOut
from app.schemas.rfq import AuctionConfig, AuctionEventOut, RfqCreate, RfqDetailOut, RfqSummaryOut
from app.services import auction_rules as rules



def rfq_status(rfq: Rfq, now: datetime) -> AuctionStatus:
    return rules.compute_status(
        bid_start_at=rfq.bid_start_at,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        now=now,
    )


def status_condition(status: AuctionStatus, now: datetime):
    if status is AuctionStatus.SCHEDULED:
        return Rfq.bid_start_at > now
    if status is AuctionStatus.ACTIVE:
        return and_(Rfq.bid_start_at <= now, Rfq.current_close_at > now)
    if status is AuctionStatus.CLOSED:
        return and_(Rfq.current_close_at <= now, Rfq.current_close_at < Rfq.forced_close_at)
    return and_(Rfq.current_close_at <= now, Rfq.current_close_at >= Rfq.forced_close_at)


def bid_to_out(bid: Bid) -> BidOut:
    return BidOut(
        id=bid.id,
        rfq_id=bid.rfq_id,
        supplier_id=bid.supplier_id,
        supplier_name=bid.supplier.name,
        carrier_name=bid.carrier_name,
        freight_charges=bid.freight_charges,
        origin_charges=bid.origin_charges,
        destination_charges=bid.destination_charges,
        total_amount=bid.total_amount,
        transit_time_days=bid.transit_time_days,
        quote_validity_date=bid.quote_validity_date,
        remarks=bid.remarks,
        created_at=bid.created_at,
    )


def _generate_reference(now: datetime) -> str:
    return f"RFQ-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"



async def get_rfq(db: AsyncSession, rfq_id: int, *, for_update: bool = False) -> Rfq:
    rfq = await db.get(Rfq, rfq_id, with_for_update=for_update or None, populate_existing=for_update)
    if rfq is None:
        raise NotFoundError(f"RFQ {rfq_id} not found")
    return rfq


async def standing_bids(db: AsyncSession, rfq_id: int) -> list[Bid]:
    stmt = (
        select(Bid)
        .where(Bid.rfq_id == rfq_id)
        .distinct(Bid.supplier_id)
        .order_by(Bid.supplier_id, Bid.total_amount, Bid.created_at)
    )
    bids = list((await db.scalars(stmt)).unique())
    order = rules.rank_order(to_rank_entries(bids))
    by_supplier = {b.supplier_id: b for b in bids}
    return [by_supplier[sid] for sid in order]


def to_rank_entries(bids: list[Bid]) -> list[rules.RankEntry]:
    return [rules.RankEntry(b.supplier_id, b.total_amount, b.created_at) for b in bids]


async def ranking(db: AsyncSession, rfq_id: int) -> list[RankedBidOut]:
    standing = await standing_bids(db, rfq_id)
    counts = dict(
        (
            await db.execute(
                select(Bid.supplier_id, func.count()).where(Bid.rfq_id == rfq_id).group_by(Bid.supplier_id)
            )
        ).all()
    )
    return [
        RankedBidOut(
            rank=idx + 1,
            rank_label=rules.rank_label(idx + 1),
            bid_count=counts.get(bid.supplier_id, 1),
            bid=bid_to_out(bid),
        )
        for idx, bid in enumerate(standing)
    ]


async def all_bids(db: AsyncSession, rfq_id: int) -> list[BidOut]:
    await get_rfq(db, rfq_id)
    stmt = select(Bid).where(Bid.rfq_id == rfq_id).order_by(Bid.total_amount, Bid.created_at, Bid.id)
    return [bid_to_out(b) for b in (await db.scalars(stmt)).unique()]


async def activity(db: AsyncSession, rfq_id: int) -> list[AuctionEventOut]:
    stmt = (
        select(AuctionEvent)
        .where(AuctionEvent.rfq_id == rfq_id)
        .order_by(AuctionEvent.created_at.desc(), AuctionEvent.id.desc())
    )
    return [AuctionEventOut.model_validate(e) for e in await db.scalars(stmt)]


def _summary_query() -> Select:
    stats = (
        select(
            Bid.rfq_id.label("rfq_id"),
            func.min(Bid.total_amount).label("lowest_bid"),
            func.count(Bid.id).label("bid_count"),
            func.count(func.distinct(Bid.supplier_id)).label("supplier_count"),
        )
        .group_by(Bid.rfq_id)
        .subquery()
    )
    return select(
        Rfq,
        stats.c.lowest_bid,
        func.coalesce(stats.c.bid_count, 0),
        func.coalesce(stats.c.supplier_count, 0),
    ).outerjoin(stats, stats.c.rfq_id == Rfq.id)


def _to_summary(rfq: Rfq, lowest, bid_count: int, supplier_count: int, now: datetime) -> RfqSummaryOut:
    return RfqSummaryOut(
        id=rfq.id,
        reference_id=rfq.reference_id,
        name=rfq.name,
        status=rfq_status(rfq, now),
        pickup_date=rfq.pickup_date,
        bid_start_at=rfq.bid_start_at,
        bid_close_at=rfq.bid_close_at,
        current_close_at=rfq.current_close_at,
        forced_close_at=rfq.forced_close_at,
        extension_count=rfq.extension_count,
        lowest_bid=lowest,
        bid_count=bid_count,
        supplier_count=supplier_count,
    )


async def list_rfqs(
    db: AsyncSession,
    *,
    now: datetime,
    status: AuctionStatus | None,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[RfqSummaryOut], int]:
    filters = []
    if status is not None:
        filters.append(status_condition(status, now))
    if search:
        like = f"%{search.strip()}%"
        filters.append(Rfq.name.ilike(like) | Rfq.reference_id.ilike(like))

    total = await db.scalar(select(func.count()).select_from(Rfq).where(*filters))
    stmt = _summary_query().where(*filters).order_by(Rfq.created_at.desc(), Rfq.id.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()
    return [_to_summary(r[0], r[1], r[2], r[3], now) for r in rows], total or 0


async def get_rfq_detail(db: AsyncSession, rfq_id: int, *, now: datetime) -> RfqDetailOut:
    row = (await db.execute(_summary_query().where(Rfq.id == rfq_id))).first()
    if row is None:
        raise NotFoundError(f"RFQ {rfq_id} not found")
    rfq = row[0]
    summary = _to_summary(rfq, row[1], row[2], row[3], now)
    return RfqDetailOut(
        **summary.model_dump(),
        description=rfq.description,
        config=AuctionConfig(
            trigger_window_minutes=rfq.trigger_window_minutes,
            extension_minutes=rfq.extension_minutes,
            extension_trigger=rfq.extension_trigger,
        ),
        closed_at=rfq.closed_at,
        created_at=rfq.created_at,
        server_time=now,
        ranking=await ranking(db, rfq_id),
        activity=await activity(db, rfq_id),
    )



async def create_rfq(db: AsyncSession, data: RfqCreate, *, now: datetime) -> tuple[Rfq, AuctionEvent]:
    if data.bid_close_at <= now:
        raise ValidationError("Bid close time must be in the future")

    rfq = Rfq(
        reference_id=data.reference_id or _generate_reference(now),
        name=data.name.strip(),
        description=data.description,
        pickup_date=data.pickup_date,
        bid_start_at=data.bid_start_at,
        bid_close_at=data.bid_close_at,
        current_close_at=data.bid_close_at,
        forced_close_at=data.forced_close_at,
        trigger_window_minutes=data.trigger_window_minutes,
        extension_minutes=data.extension_minutes,
        extension_trigger=data.extension_trigger,
        extension_count=0,
    )
    db.add(rfq)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"RFQ reference '{rfq.reference_id}' already exists") from exc

    event = AuctionEvent(
        rfq_id=rfq.id,
        event_type=AuctionEventType.RFQ_CREATED,
        message=f"RFQ {rfq.reference_id} created with British auction "
        f"(X={rfq.trigger_window_minutes} min, Y={rfq.extension_minutes} min, "
        f"trigger={rfq.extension_trigger.value})",
        details={
            "bid_start_at": rfq.bid_start_at.isoformat(),
            "bid_close_at": rfq.bid_close_at.isoformat(),
            "forced_close_at": rfq.forced_close_at.isoformat(),
            "trigger_window_minutes": rfq.trigger_window_minutes,
            "extension_minutes": rfq.extension_minutes,
            "extension_trigger": rfq.extension_trigger.value,
        },
        created_at=now,
    )
    db.add(event)
    await db.commit()
    await db.refresh(rfq)
    return rfq, event
