from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.supplier import Supplier

MONEY = Numeric(14, 2)


class Bid(Base):
   

    __tablename__ = "bids"
    __table_args__ = (
        CheckConstraint(
            "freight_charges >= 0 AND origin_charges >= 0 AND destination_charges >= 0",
            name="charges_non_negative",
        ),
        CheckConstraint(
            "total_amount = freight_charges + origin_charges + destination_charges", name="total_matches"
        ),
        CheckConstraint("total_amount > 0", name="total_positive"),
        CheckConstraint("transit_time_days > 0", name="transit_time_positive"),
        Index("ix_bids_rfq_supplier_created", "rfq_id", "supplier_id", "created_at"),
        Index("ix_bids_rfq_total", "rfq_id", "total_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="RESTRICT"))

    carrier_name: Mapped[str] = mapped_column(String(120))
    freight_charges: Mapped[Decimal] = mapped_column(MONEY)
    origin_charges: Mapped[Decimal] = mapped_column(MONEY)
    destination_charges: Mapped[Decimal] = mapped_column(MONEY)
    total_amount: Mapped[Decimal] = mapped_column(MONEY)
    transit_time_days: Mapped[int] = mapped_column(Integer)
    quote_validity_date: Mapped[date] = mapped_column(Date)
    remarks: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    supplier: Mapped[Supplier] = relationship(lazy="joined")
