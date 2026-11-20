from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Money, ORMModel

class BidCreate(BaseModel):
    supplier_id: int = Field(gt=0)
    carrier_name: str = Field(min_length=1, max_length=120)
    freight_charges: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    origin_charges: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    destination_charges: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    transit_time_days: int = Field(ge=1, le=365)
    quote_validity_date: date
    remarks: str | None = Field(default=None, max_length=1000)

    @property
    def total_amount(self) -> Decimal:
        return self.freight_charges + self.origin_charges + self.destination_charges

    @model_validator(mode="after")
    def _total_positive(self) -> "BidCreate":
        if self.total_amount <= 0:
            raise ValueError("Total of freight, origin and destination charges must be greater than 0")
        return self


class BidOut(ORMModel):
    id: int
    rfq_id: int
    supplier_id: int
    supplier_name: str
    carrier_name: str
    freight_charges: Money
    origin_charges: Money
    destination_charges: Money
    total_amount: Money
    transit_time_days: int
    quote_validity_date: date
    remarks: str | None
    created_at: datetime


class RankedBidOut(BaseModel):
   

    rank: int
    rank_label: str
    bid_count: int
    bid: BidOut


class BidPlacedOut(BaseModel):
    bid: BidOut
    rank: int
    rank_label: str
    auction_extended: bool
    extension_reason: str | None
    current_close_at: datetime
    forced_close_at: datetime
