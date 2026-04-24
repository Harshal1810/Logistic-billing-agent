from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, Numeric, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.postgres import Base


class FreightBillCandidateMatch(Base):
    __tablename__ = "freight_bill_candidate_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    freight_bill_id: Mapped[str] = mapped_column(
        ForeignKey("freight_bills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    candidate_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    match_reasons: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)