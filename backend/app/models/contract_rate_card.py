from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Date, DateTime, ForeignKey, Numeric, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class ContractRateCard(Base):
    __tablename__ = "contract_rate_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[str] = mapped_column(ForeignKey("carrier_contracts.id"), nullable=False, index=True)

    lane_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    rate_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_charge: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fuel_surcharge_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    rate_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_capacity_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    alternate_rate_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    revised_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    revised_fuel_surcharge_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contract = relationship("CarrierContract", back_populates="rate_cards")