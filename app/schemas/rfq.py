from datetime import date, datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.models.enums import AuctionEventType, AuctionStatus, ExtensionTrigger
from app.schemas.bid import RankedBidOut
from app.schemas.common import Money, ORMModel


class AuctionConfig(BaseModel):
    trigger_window_minutes: int = Field(ge=1, le=24 * 60, description="X: minutes before close that are monitored")
    extension_minutes: int = Field(ge=1, le=24 * 60, description="Y: minutes added when triggered")
    extension_trigger: ExtensionTrigger = ExtensionTrigger.BID_RECEIVED


class RfqCreate(AuctionConfig):
    reference_id: str | None = Field(
        default=None,
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-/]*$",
        description="Auto-generated when omitted",
    )
    name: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    pickup_date: date
    bid_start_at: AwareDatetime
    bid_close_at: AwareDatetime
    forced_close_at: AwareDatetime

    @model_validator(mode="after")
    def _validate_times(self) -> "RfqCreate":
        if self.bid_close_at <= self.bid_start_at:
            raise ValueError("Bid close time must be later than bid start time")
        if self.forced_close_at <= self.bid_close_at:
            raise ValueError("Forced bid close time must be later than bid close time")
        if self.pickup_date < self.bid_start_at.date():
            raise ValueError("Pickup / service date cannot be before the bid start date")
        return self


class RfqSummaryOut(ORMModel):
    """Row on the auction listing page."""

    id: int
    reference_id: str
    name: str
    status: AuctionStatus
    pickup_date: date
    bid_start_at: datetime
    bid_close_at: datetime
    current_close_at: datetime
    forced_close_at: datetime
    extension_count: int
    lowest_bid: Money | None
    bid_count: int
    supplier_count: int


class AuctionEventOut(ORMModel):
    id: int
    event_type: AuctionEventType
    supplier_id: int | None
    bid_id: int | None
    message: str
    details: dict[str, Any]
    created_at: datetime


class RfqDetailOut(RfqSummaryOut):
    description: str | None
    config: AuctionConfig
    closed_at: datetime | None
    created_at: datetime
    server_time: datetime
    ranking: list[RankedBidOut]
    activity: list[AuctionEventOut]
