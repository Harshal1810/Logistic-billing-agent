from datetime import date, datetime

from sqlalchemy import String, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class Carrier(Base):
    __tablename__ = "carriers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    carrier_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    gstin: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    bank_account: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    onboarded_on: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contracts = relationship("CarrierContract", back_populates="carrier")
    shipments = relationship("Shipment", back_populates="carrier")
    freight_bills = relationship("FreightBill", back_populates="carrier")