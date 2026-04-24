from decimal import Decimal
from sqlalchemy.orm import Session

from app.repositories.freight_bills import get_freight_bill_by_id
from app.services.evidence_service import get_selected_shipment_bol_evidence


def validate_weight_reconciliation(db: Session, freight_bill_id: str) -> dict:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    evidence = get_selected_shipment_bol_evidence(db, freight_bill_id)

    if evidence["shipment_id"] is None:
        return {
            "rule_name": "weight_reconciliation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(freight_bill.billed_weight_kg),
            "details": "No selected shipment available for BOL reconciliation",
        }

    billed_weight = Decimal(str(freight_bill.billed_weight_kg))
    total_actual_weight = Decimal(str(evidence["total_actual_weight"]))

    if billed_weight == total_actual_weight:
        return {
            "rule_name": "weight_reconciliation",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": str(total_actual_weight),
            "actual_value": str(billed_weight),
            "details": f"Billed weight matched total BOL-supported delivered weight for shipment {evidence['shipment_id']}",
        }

    if billed_weight < total_actual_weight:
        return {
            "rule_name": "weight_reconciliation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": str(total_actual_weight),
            "actual_value": str(billed_weight),
            "details": f"Billed weight is lower than total BOL-supported delivered weight for shipment {evidence['shipment_id']}; possible partial billing",
        }

    return {
        "rule_name": "weight_reconciliation",
        "rule_result": "fail",
        "severity": "high",
        "expected_value": str(total_actual_weight),
        "actual_value": str(billed_weight),
        "details": f"Billed weight exceeds total BOL-supported delivered weight for shipment {evidence['shipment_id']}",
    }