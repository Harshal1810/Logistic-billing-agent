from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class FreightBillDecision(Base):
    __tablename__ = "freight_bill_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    freight_bill_id: Mapped[str] = mapped_column(
        ForeignKey("freight_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=False)
    decision_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_source: Mapped[str] = mapped_column(String(50), nullable=False, default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
