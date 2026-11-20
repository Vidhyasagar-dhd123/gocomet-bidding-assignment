from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AuctionEventType


class AuctionEvent(Base):
   

    __tablename__ = "auction_events"
    __table_args__ = (Index("ix_auction_events_rfq_created", "rfq_id", "created_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    event_type: Mapped[AuctionEventType] = mapped_column(
        Enum(AuctionEventType, native_enum=False, length=32, create_constraint=True, name="event_type")
    )
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    bid_id: Mapped[int | None] = mapped_column(ForeignKey("bids.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
