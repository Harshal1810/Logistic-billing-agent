from sqlalchemy.orm import Session
from app.models.validation_result import FreightBillValidationResult


def delete_validation_results(db: Session, freight_bill_id: str) -> None:
    (
        db.query(FreightBillValidationResult)
        .filter(FreightBillValidationResult.freight_bill_id == freight_bill_id)
        .delete(synchronize_session=False)
    )
    db.flush()


def save_validation_result(db: Session, freight_bill_id: str, result: dict) -> None:
    db.add(
        FreightBillValidationResult(
            freight_bill_id=freight_bill_id,
            rule_name=result["rule_name"],
            rule_result=result["rule_result"],
            severity=result["severity"],
            expected_value=result.get("expected_value"),
            actual_value=result.get("actual_value"),
            details=result["details"],
        )
    )


def get_validation_results(db: Session, freight_bill_id: str) -> list[FreightBillValidationResult]:
    return (
        db.query(FreightBillValidationResult)
        .filter(FreightBillValidationResult.freight_bill_id == freight_bill_id)
        .order_by(FreightBillValidationResult.created_at.asc())
        .all()
    )
