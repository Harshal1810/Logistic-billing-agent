from sqlalchemy.orm import Session

from app.rules.common import (
    get_bill,
    get_contract_rate_for_lane,
    get_selected_contract,
    normalize_billing_unit,
)


def validate_unit_reconciliation(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    contract = get_selected_contract(db, bill)

    if contract is None:
        return {
            "rule_name": "unit_reconciliation_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": bill.billing_unit,
            "details": "No selected contract available for unit reconciliation",
        }

    rate = get_contract_rate_for_lane(db, contract.id, bill.lane)
    if rate is None:
        return {
            "rule_name": "unit_reconciliation_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": bill.billing_unit,
            "details": f"No contract lane row found for unit reconciliation on lane {bill.lane}",
        }

    bill_unit = normalize_billing_unit(bill.billing_unit, bill.rate_per_kg)
    contract_unit = rate.unit.lower() if rate.unit else "kg"

    if contract_unit == "kg":
        if bill_unit in {"kg", "unknown"}:
            return {
                "rule_name": "unit_reconciliation_check",
                "rule_result": "pass",
                "severity": "low",
                "expected_value": "kg",
                "actual_value": bill_unit,
                "details": "Billing unit is compatible with per-kg contract",
            }
        return {
            "rule_name": "unit_reconciliation_check",
            "rule_result": "fail",
            "severity": "high",
            "expected_value": "kg",
            "actual_value": bill_unit,
            "details": "Billing unit is not supported by per-kg contract",
        }

    if contract_unit == "ftl":
        if bill_unit in {"ftl", "unknown"}:
            return {
                "rule_name": "unit_reconciliation_check",
                "rule_result": "pass",
                "severity": "low",
                "expected_value": "ftl",
                "actual_value": bill_unit,
                "details": "Billing unit is compatible with FTL contract",
            }
        if bill_unit == "kg":
            if rate.alternate_rate_per_kg is not None:
                return {
                    "rule_name": "unit_reconciliation_check",
                    "rule_result": "pass",
                    "severity": "low",
                    "expected_value": "ftl or alternate per-kg",
                    "actual_value": "kg",
                    "details": "Per-kg billing is allowed by FTL contract alternate pricing",
                }
            return {
                "rule_name": "unit_reconciliation_check",
                "rule_result": "fail",
                "severity": "high",
                "expected_value": "ftl",
                "actual_value": "kg",
                "details": "FTL contract does not permit per-kg billing (no alternate rate)",
            }
        return {
            "rule_name": "unit_reconciliation_check",
            "rule_result": "fail",
            "severity": "high",
            "expected_value": "ftl",
            "actual_value": bill_unit,
            "details": "Billing unit is not supported by selected FTL contract",
        }

    return {
        "rule_name": "unit_reconciliation_check",
        "rule_result": "warning",
        "severity": "medium",
        "expected_value": contract_unit,
        "actual_value": bill_unit,
        "details": "Unknown contract unit; manual reconciliation required",
    }
