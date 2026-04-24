from decimal import Decimal
from sqlalchemy.orm import Session

from app.repositories.freight_bills import (
    get_freight_bill_by_id,
    get_prior_freight_bills_for_selected_shipment,
)
from app.services.evidence_service import get_selected_shipment_bol_evidence


def validate_cumulative_billing(db: Session, freight_bill_id: str) -> dict:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    shipment_id = freight_bill.selected_shipment_id
    if shipment_id is None:
        return {
            "rule_name": "cumulative_billing_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(freight_bill.billed_weight_kg),
            "details": "No selected shipment available for cumulative billing analysis",
        }

    evidence = get_selected_shipment_bol_evidence(db, freight_bill_id)
    supported_delivered_weight = Decimal(str(evidence["total_actual_weight"]))
    current_billed_weight = Decimal(str(freight_bill.billed_weight_kg))

    prior = get_prior_freight_bills_for_selected_shipment(db, freight_bill_id, shipment_id)

    confirmed_prior_weight = sum(
        Decimal(str(b.billed_weight_kg)) for b in prior["confirmed"]
    )
    pending_prior_weight = sum(
        Decimal(str(b.billed_weight_kg)) for b in prior["pending"]
    )

    confirmed_total = current_billed_weight + confirmed_prior_weight
    possible_total = confirmed_total + pending_prior_weight

    if confirmed_total > supported_delivered_weight:
        return {
            "rule_name": "cumulative_billing_check",
            "rule_result": "fail",
            "severity": "critical",
            "expected_value": str(supported_delivered_weight),
            "actual_value": str(confirmed_total),
            "details": (
                f"Confirmed cumulative billed weight exceeds BOL-supported delivered weight "
                f"for shipment {shipment_id}"
            ),
        }

    if possible_total > supported_delivered_weight:
        pending_ids = [b.id for b in prior["pending"]]
        return {
            "rule_name": "cumulative_billing_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": str(supported_delivered_weight),
            "actual_value": str(possible_total),
            "details": (
                f"Potential cumulative over-billing for shipment {shipment_id} if pending "
                f"bills are later approved; pending bills considered: {pending_ids}"
            ),
        }

    return {
        "rule_name": "cumulative_billing_check",
        "rule_result": "pass",
        "severity": "low",
        "expected_value": str(supported_delivered_weight),
        "actual_value": str(confirmed_total),
        "details": (
            f"Confirmed cumulative billed weight is within BOL-supported delivered weight "
            f"for shipment {shipment_id}"
        ),
    }