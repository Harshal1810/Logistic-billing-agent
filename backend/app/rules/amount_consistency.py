from decimal import Decimal

from sqlalchemy.orm import Session

from app.rules.common import get_bill, q2


def validate_amount_consistency(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)

    expected_total = q2(
        Decimal(str(bill.base_charge))
        + Decimal(str(bill.fuel_surcharge))
        + Decimal(str(bill.gst_amount))
    )
    actual_total = q2(Decimal(str(bill.total_amount)))

    if expected_total == actual_total:
        return {
            "rule_name": "amount_consistency_check",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": str(expected_total),
            "actual_value": str(actual_total),
            "details": "Invoice arithmetic is consistent: total = base + fuel + gst",
        }

    return {
        "rule_name": "amount_consistency_check",
        "rule_result": "fail",
        "severity": "high",
        "expected_value": str(expected_total),
        "actual_value": str(actual_total),
        "details": "Invoice arithmetic mismatch: total does not equal base + fuel + gst",
    }
