from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.decisions import save_decision
from app.repositories.freight_bills import get_freight_bill_by_id, update_bill_resolution


def apply_reviewer_decision(
    db: Session,
    freight_bill_id: str,
    reviewer_decision: str,
    reviewer_notes: str | None,
) -> None:
    bill = get_freight_bill_by_id(db, freight_bill_id)
    if bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    if reviewer_decision == "approve":
        current_decision = "auto_approve"
        final_resolution = "approved"
        processing_status = "completed"
        reason = "Reviewer approved after manual review"
    elif reviewer_decision == "dispute":
        current_decision = "dispute"
        final_resolution = "disputed"
        processing_status = "completed"
        reason = "Reviewer disputed after manual review"
    else:
        current_decision = "modify"
        final_resolution = "modified"
        processing_status = "completed"
        reason = "Reviewer marked bill as modified after manual review"

    if reviewer_notes:
        reason = f"{reason}. Notes: {reviewer_notes}"

    save_decision(
        db=db,
        freight_bill_id=freight_bill_id,
        decision=reviewer_decision,
        confidence_score=float(bill.confidence_score) if bill.confidence_score is not None else 0.0,
        decision_reason=reason,
        decision_source="reviewer",
    )

    update_bill_resolution(
        db=db,
        freight_bill_id=freight_bill_id,
        processing_status=processing_status,
        current_decision=current_decision,
        final_resolution=final_resolution,
        confidence_score=float(bill.confidence_score) if bill.confidence_score is not None else 0.0,
    )
    bill.finalized_at = datetime.utcnow()
    db.add(bill)
