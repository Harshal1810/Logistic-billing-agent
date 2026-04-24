from sqlalchemy.orm import Session

from app.rules.common import get_bill, get_selected_contract


def validate_contract_validity(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    contract = get_selected_contract(db, bill)

    if contract is None:
        return {
            "rule_name": "contract_validity_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": "selected active contract valid on bill_date",
            "actual_value": None,
            "details": "No selected contract available for contract validity validation",
        }

    in_window = contract.effective_date <= bill.bill_date <= contract.expiry_date
    is_active = contract.status.lower() == "active"

    if in_window and is_active:
        return {
            "rule_name": "contract_validity_check",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": "active and in-date contract",
            "actual_value": f"{contract.id} ({contract.effective_date} to {contract.expiry_date}, {contract.status})",
            "details": f"Selected contract {contract.id} is active and valid on bill date",
        }

    return {
        "rule_name": "contract_validity_check",
        "rule_result": "fail",
        "severity": "high",
        "expected_value": "active and in-date contract",
        "actual_value": f"{contract.id} ({contract.effective_date} to {contract.expiry_date}, {contract.status})",
        "details": f"Selected contract {contract.id} is not valid for bill date {bill.bill_date}",
    }
