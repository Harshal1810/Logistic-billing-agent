from sqlalchemy.orm import Session

from app.repositories.decisions import save_decision, update_decision_explanation
from app.repositories.freight_bills import (
    get_candidate_matches,
    get_freight_bill_by_id,
    update_bill_resolution,
)
from app.repositories.validations import get_validation_results
from app.services.confidence_service import compute_confidence
from app.services.explanation_service import (
    build_decision_explanation_payload,
    generate_decision_explanation,
)


def decide_freight_bill(db: Session, freight_bill_id: str) -> dict:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    rows = get_validation_results(db, freight_bill_id)
    validation_results = [
        {
            "rule_name": row.rule_name,
            "rule_result": row.rule_result,
            "severity": row.severity,
            "details": row.details,
        }
        for row in rows
    ]

    confidence = compute_confidence(validation_results)

    failed_rules = {row["rule_name"] for row in validation_results if row["rule_result"] == "fail"}
    critical_failed_rules = {
        row["rule_name"]
        for row in validation_results
        if row["rule_result"] == "fail" and row["severity"] == "critical"
    }
    high_failed_rules = {
        row["rule_name"]
        for row in validation_results
        if row["rule_result"] == "fail" and row["severity"] == "high"
    }
    has_warning = any(row["rule_result"] == "warning" for row in validation_results)

    contract_matches = get_candidate_matches(db, freight_bill_id, "contract")
    no_valid_contract = len(contract_matches) == 0
    missing_contract_selection = freight_bill.selected_contract_id is None
    missing_shipment_selection = freight_bill.selected_shipment_id is None
    unknown_carrier = freight_bill.carrier_id is None

    ambiguous_contract = False
    if len(contract_matches) > 1:
        selected_count = sum(1 for m in contract_matches if m.selected)
        top_score = float(contract_matches[0].score)
        second_score = float(contract_matches[1].score)
        ambiguous_contract = selected_count == 0 and (top_score - second_score) < 0.20

    hard_fail_critical_rules = {"duplicate_bill_check", "cumulative_billing_check"}
    hard_fail_high_rules = {
        "weight_reconciliation",
        "contract_validity_check",
        "lane_match_check",
        "unit_reconciliation_check",
    }
    has_hard_fail = (
        bool(critical_failed_rules.intersection(hard_fail_critical_rules))
        or bool(high_failed_rules.intersection(hard_fail_high_rules))
        or (no_valid_contract and not unknown_carrier)
    )
    has_any_fail = len(failed_rules) > 0

    if has_hard_fail:
        decision = "dispute"
        final_resolution = "disputed"
        reason = "One or more critical/high validation failures were found"
        processing_status = "completed"
    elif (
        has_any_fail
        or has_warning
        or missing_shipment_selection
        or missing_contract_selection
        or unknown_carrier
        or ambiguous_contract
    ):
        decision = "flag_for_review"
        final_resolution = None
        reason = "Validation completed but non-blocking failures or ambiguity remain"
        processing_status = "waiting_for_review"
    else:
        decision = "auto_approve"
        final_resolution = "approved"
        reason = "All core validations passed with no blocking issues"
        processing_status = "completed"

    saved_decision = save_decision(
        db=db,
        freight_bill_id=freight_bill_id,
        decision=decision,
        confidence_score=confidence,
        decision_reason=reason,
        decision_source="agent",
    )
    db.flush()

    explanation_payload = build_decision_explanation_payload(db, freight_bill_id)
    decision_explanation = generate_decision_explanation(explanation_payload)
    update_decision_explanation(
        db=db,
        decision=saved_decision,
        decision_explanation=decision_explanation,
    )

    update_bill_resolution(
        db=db,
        freight_bill_id=freight_bill_id,
        processing_status=processing_status,
        current_decision=decision,
        final_resolution=final_resolution,
        confidence_score=confidence,
    )
    db.commit()

    return {
        "freight_bill_id": freight_bill_id,
        "decision": decision,
        "confidence_score": confidence,
        "reason": reason,
        "decision_explanation": decision_explanation,
    }
