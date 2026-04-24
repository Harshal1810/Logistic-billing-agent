from sqlalchemy.orm import Session

from app.models.decision import FreightBillDecision


def save_decision(
    db: Session,
    freight_bill_id: str,
    decision: str,
    confidence_score: float,
    decision_reason: str,
    decision_explanation: str | None = None,
    decision_source: str = "agent",
) -> FreightBillDecision:
    row = FreightBillDecision(
        freight_bill_id=freight_bill_id,
        decision=decision,
        confidence_score=confidence_score,
        decision_reason=decision_reason,
        decision_explanation=decision_explanation,
        decision_source=decision_source,
    )
    db.add(row)
    return row


def get_latest_decision(db: Session, freight_bill_id: str) -> FreightBillDecision | None:
    return (
        db.query(FreightBillDecision)
        .filter(FreightBillDecision.freight_bill_id == freight_bill_id)
        .order_by(FreightBillDecision.created_at.desc())
        .first()
    )


def update_decision_explanation(
    db: Session,
    decision: FreightBillDecision,
    decision_explanation: str,
) -> FreightBillDecision:
    decision.decision_explanation = decision_explanation
    db.add(decision)
    return decision
