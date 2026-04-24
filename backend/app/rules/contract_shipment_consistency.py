from sqlalchemy.orm import Session

from app.rules.common import get_bill, get_selected_shipment


def validate_contract_shipment_consistency(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    shipment = get_selected_shipment(db, bill)

    if bill.selected_contract_id is None or shipment is None:
        return {
            "rule_name": "contract_shipment_consistency_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": bill.selected_contract_id,
            "actual_value": shipment.contract_id if shipment is not None else None,
            "details": "Contract/shipment consistency could not be fully evaluated due to missing selections",
        }

    if shipment.contract_id == bill.selected_contract_id:
        return {
            "rule_name": "contract_shipment_consistency_check",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": bill.selected_contract_id,
            "actual_value": shipment.contract_id,
            "details": "Selected shipment contract_id aligns with selected contract",
        }

    return {
        "rule_name": "contract_shipment_consistency_check",
        "rule_result": "warning",
        "severity": "medium",
        "expected_value": bill.selected_contract_id,
        "actual_value": shipment.contract_id,
        "details": "Selected shipment contract_id does not align with selected contract",
    }
