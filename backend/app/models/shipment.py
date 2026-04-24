from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"), nullable=False, index=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("carrier_contracts.id"), nullable=False, index=True)
    lane: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    shipment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    total_weight_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    carrier = relationship("Carrier", back_populates="shipments")
    contract = relationship("CarrierContract", back_populates="shipments")
    bills_of_lading = relationship("BillOfLading", back_populates="shipment", cascade="all, delete-orphan")