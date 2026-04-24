from sqlalchemy.orm import Session

from app.rules.common import get_bill, get_carrier


def validate_carrier_resolution(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    carrier = get_carrier(db, bill)

    if bill.carrier_id is None:
        return {
            "rule_name": "carrier_resolution_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": "known active carrier",
            "actual_value": bill.carrier_name_raw,
            "details": "Freight bill has no resolved carrier_id; manual review required",
        }

    if carrier is None:
        return {
            "rule_name": "carrier_resolution_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": "known active carrier",
            "actual_value": bill.carrier_id,
            "details": f"Carrier {bill.carrier_id} was not found in master data",
        }

    if carrier.status.lower() != "active":
        return {
            "rule_name": "carrier_resolution_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": "active",
            "actual_value": carrier.status,
            "details": f"Carrier {carrier.id} is resolved but status is not active",
        }

    return {
        "rule_name": "carrier_resolution_check",
        "rule_result": "pass",
        "severity": "low",
        "expected_value": "known active carrier",
        "actual_value": carrier.id,
        "details": f"Carrier {carrier.id} resolved and active",
    }
