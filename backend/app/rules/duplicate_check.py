from sqlalchemy.orm import Session

from app.repositories.freight_bills import find_duplicate_freight_bills


def validate_duplicate_bill(db: Session, freight_bill_id: str) -> dict:
    duplicates = find_duplicate_freight_bills(db, freight_bill_id)

    if duplicates:
        duplicate_ids = [d.id for d in duplicates]
        return {
            "rule_name": "duplicate_bill_check",
            "rule_result": "fail",
            "severity": "critical",
            "expected_value": "unique bill_number per carrier",
            "actual_value": ", ".join(duplicate_ids),
            "details": f"Duplicate freight bill(s) found for same carrier and bill number: {duplicate_ids}",
        }

    return {
        "rule_name": "duplicate_bill_check",
        "rule_result": "pass",
        "severity": "low",
        "expected_value": "unique bill_number per carrier",
        "actual_value": "no duplicates found",
        "details": "No duplicate freight bills found for this carrier and bill number",
    }