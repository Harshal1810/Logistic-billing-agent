from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Date, DateTime, ForeignKey, Numeric, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class FreightBill(Base):
    __tablename__ = "freight_bills"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    carrier_id: Mapped[str | None] = mapped_column(ForeignKey("carriers.id"), nullable=True, index=True)
    carrier_name_raw: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    bill_number: Mapped[str] = mapped_column(String(100), nullable=False)
    bill_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    shipment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    lane: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    billed_weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rate_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    billing_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    base_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    fuel_surcharge: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    processing_status: Mapped[str] = mapped_column(String(50), nullable=False, default="ingested")
    current_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # New fields
    selected_contract_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    selected_shipment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    selected_bol_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    final_resolution: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    carrier = relationship("Carrier", back_populates="freight_bills")

    __table_args__ = (
        Index("ix_freight_bills_bill_number_carrier_id", "bill_number", "carrier_id"),
    )