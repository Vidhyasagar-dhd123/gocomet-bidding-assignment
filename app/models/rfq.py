from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AuctionStatus, ExtensionTrigger


class Rfq(Base):

    __tablename__ = "rfqs"
    __table_args__ = (
        CheckConstraint("bid_close_at > bid_start_at", name="close_after_start"),
        CheckConstraint("forced_close_at > bid_close_at", name="forced_after_close"),
        CheckConstraint(
            "current_close_at >= bid_close_at AND current_close_at <= forced_close_at",
            name="current_close_within_bounds",
        ),
        CheckConstraint("trigger_window_minutes > 0", name="trigger_window_positive"),
        CheckConstraint("extension_minutes > 0", name="extension_positive"),
        Index("ix_rfqs_open_close", "current_close_at", postgresql_where=text("closed_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    pickup_date: Mapped[date] = mapped_column(Date)

    bid_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bid_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    forced_close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    
    trigger_window_minutes: Mapped[int] = mapped_column(Integer)  
    extension_minutes: Mapped[int] = mapped_column(Integer)  
    extension_trigger: Mapped[ExtensionTrigger] = mapped_column(
        Enum(ExtensionTrigger, native_enum=False, length=32, create_constraint=True, name="extension_trigger")
    )
    extension_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_status: Mapped[AuctionStatus | None] = mapped_column(
        Enum(AuctionStatus, native_enum=False, length=32, create_constraint=True, name="final_status")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
