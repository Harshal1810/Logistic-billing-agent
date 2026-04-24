from sqlalchemy.orm import Session

from app.rules.common import get_bill, get_selected_shipment


def validate_shipment_resolution(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    shipment = get_selected_shipment(db, bill)

    if shipment is None:
        return {
            "rule_name": "shipment_resolution_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": bill.shipment_reference,
            "actual_value": None,
            "details": "No selected shipment available",
        }

    if bill.shipment_reference and bill.shipment_reference != shipment.id:
        return {
            "rule_name": "shipment_resolution_check",
            "rule_result": "fail",
            "severity": "medium",
            "expected_value": bill.shipment_reference,
            "actual_value": shipment.id,
            "details": "Selected shipment conflicts with shipment_reference on freight bill",
        }

    if bill.shipment_reference and bill.shipment_reference == shipment.id:
        return {
            "rule_name": "shipment_resolution_check",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": bill.shipment_reference,
            "actual_value": shipment.id,
            "details": "Selected shipment matched shipment_reference exactly",
        }

    return {
        "rule_name": "shipment_resolution_check",
        "rule_result": "warning",
        "severity": "low",
        "expected_value": "shipment inferred from matching signals",
        "actual_value": shipment.id,
        "details": "Shipment selected without explicit shipment_reference; review confidence as needed",
    }
