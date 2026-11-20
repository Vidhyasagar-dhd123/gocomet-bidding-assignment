from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.enums import AuctionStatus, ExtensionTrigger



def compute_status(
    *, bid_start_at: datetime, current_close_at: datetime, forced_close_at: datetime, now: datetime
) -> AuctionStatus:
    if now < bid_start_at:
        return AuctionStatus.SCHEDULED
    if now < current_close_at:
        return AuctionStatus.ACTIVE
    if current_close_at >= forced_close_at:
        return AuctionStatus.FORCE_CLOSED
    return AuctionStatus.CLOSED



@dataclass(frozen=True)
class RankEntry:
    supplier_id: int
    total_amount: Decimal
    submitted_at: datetime


def rank_order(entries: Iterable[RankEntry]) -> list[int]:
    ordered = sorted(entries, key=lambda e: (e.total_amount, e.submitted_at, e.supplier_id))
    return [e.supplier_id for e in ordered]


def rank_label(rank: int) -> str:
    return f"L{rank}"


def rank_map(order: Sequence[int]) -> dict[int, int]:
    return {supplier_id: idx + 1 for idx, supplier_id in enumerate(order)}



def in_trigger_window(*, now: datetime, current_close_at: datetime, window_minutes: int) -> bool:
    return current_close_at - timedelta(minutes=window_minutes) <= now < current_close_at


def ranking_changed(before: Sequence[int], after: Sequence[int]) -> bool:
    if not before:
        return bool(after)
    before_ranks, after_ranks = rank_map(before), rank_map(after)
    return any(after_ranks.get(sid) != rank for sid, rank in before_ranks.items())


def l1_changed(before: Sequence[int], after: Sequence[int]) -> bool:
    return (before[0] if before else None) != (after[0] if after else None)


@dataclass(frozen=True)
class ExtensionDecision:
    in_window: bool
    triggered: bool
    extended: bool
    previous_close_at: datetime
    new_close_at: datetime
    capped_at_forced_close: bool
    reason: str | None


def evaluate_extension(
    *,
    trigger: ExtensionTrigger,
    now: datetime,
    current_close_at: datetime,
    forced_close_at: datetime,
    window_minutes: int,
    extension_minutes: int,
    ranking_before: Sequence[int],
    ranking_after: Sequence[int],
) -> ExtensionDecision:
    in_window = in_trigger_window(now=now, current_close_at=current_close_at, window_minutes=window_minutes)

    reason: str | None = None
    if in_window:
        if trigger is ExtensionTrigger.BID_RECEIVED:
            reason = f"Bid received within the last {window_minutes} min of the auction"
        elif trigger is ExtensionTrigger.ANY_RANK_CHANGE and ranking_changed(ranking_before, ranking_after):
            reason = f"Supplier ranking changed within the last {window_minutes} min of the auction"
        elif trigger is ExtensionTrigger.L1_RANK_CHANGE and l1_changed(ranking_before, ranking_after):
            reason = f"Lowest bidder (L1) changed within the last {window_minutes} min of the auction"

    triggered = reason is not None
    new_close = current_close_at
    capped = False
    if triggered:
        proposed = current_close_at + timedelta(minutes=extension_minutes)
        capped = proposed > forced_close_at
        new_close = min(proposed, forced_close_at)

    return ExtensionDecision(
        in_window=in_window,
        triggered=triggered,
        extended=new_close > current_close_at,
        previous_close_at=current_close_at,
        new_close_at=new_close,
        capped_at_forced_close=capped,
        reason=reason,
    )
