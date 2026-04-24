from decimal import Decimal

from sqlalchemy.orm import Session

from app.rules.common import (
    get_bill,
    get_contract_rate_for_lane,
    get_selected_contract,
    normalize_billing_unit,
)


def validate_rate_per_kg(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    contract = get_selected_contract(db, bill)

    if contract is None:
        return {
            "rule_name": "rate_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(bill.rate_per_kg) if bill.rate_per_kg is not None else None,
            "details": "No selected contract available for rate validation",
        }

    rate = get_contract_rate_for_lane(db, contract.id, bill.lane)
    if rate is None:
        return {
            "rule_name": "rate_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(bill.rate_per_kg) if bill.rate_per_kg is not None else None,
            "details": f"No contract rate card row found for lane {bill.lane}",
        }

    bill_unit = normalize_billing_unit(bill.billing_unit, bill.rate_per_kg)

    # Standard per-kg contracts
    if rate.unit is None or rate.unit.lower() == "kg":
        if bill.rate_per_kg is None or rate.rate_per_kg is None:
            return {
                "rule_name": "rate_validation",
                "rule_result": "warning",
                "severity": "medium",
                "expected_value": str(rate.rate_per_kg) if rate.rate_per_kg is not None else None,
                "actual_value": str(bill.rate_per_kg) if bill.rate_per_kg is not None else None,
                "details": "Insufficient per-kg inputs to validate billed rate",
            }

        expected = Decimal(str(rate.rate_per_kg))
        actual = Decimal(str(bill.rate_per_kg))
        if expected == actual:
            return {
                "rule_name": "rate_validation",
                "rule_result": "pass",
                "severity": "low",
                "expected_value": str(expected),
                "actual_value": str(actual),
                "details": "Billed per-kg rate matched contract rate",
            }

        return {
            "rule_name": "rate_validation",
            "rule_result": "fail",
            "severity": "high",
            "expected_value": str(expected),
            "actual_value": str(actual),
            "details": "Billed per-kg rate did not match selected contract rate",
        }

    # FTL contracts with optional alternate per-kg pricing
    if rate.unit.lower() == "ftl":
        if bill_unit == "kg":
            if rate.alternate_rate_per_kg is None:
                return {
                    "rule_name": "rate_validation",
                    "rule_result": "warning",
                    "severity": "medium",
                    "expected_value": None,
                    "actual_value": str(bill.rate_per_kg) if bill.rate_per_kg is not None else None,
                    "details": "FTL contract has no alternate per-kg pricing for a per-kg billed invoice",
                }
            if bill.rate_per_kg is None:
                return {
                    "rule_name": "rate_validation",
                    "rule_result": "warning",
                    "severity": "medium",
                    "expected_value": str(rate.alternate_rate_per_kg),
                    "actual_value": None,
                    "details": "Per-kg billed invoice missing billed rate_per_kg",
                }

            expected = Decimal(str(rate.alternate_rate_per_kg))
            actual = Decimal(str(bill.rate_per_kg))
            if expected == actual:
                return {
                    "rule_name": "rate_validation",
                    "rule_result": "pass",
                    "severity": "low",
                    "expected_value": str(expected),
                    "actual_value": str(actual),
                    "details": "Billed per-kg rate matched FTL alternate per-kg pricing",
                }

            return {
                "rule_name": "rate_validation",
                "rule_result": "fail",
                "severity": "high",
                "expected_value": str(expected),
                "actual_value": str(actual),
                "details": "Billed per-kg rate did not match FTL alternate per-kg pricing",
            }

        return {
            "rule_name": "rate_validation",
            "rule_result": "warning",
            "severity": "low",
            "expected_value": str(rate.rate_per_unit) if rate.rate_per_unit is not None else None,
            "actual_value": bill_unit,
            "details": "FTL contract detected; rate validation is deferred to unit/base-charge checks",
        }

    return {
        "rule_name": "rate_validation",
        "rule_result": "warning",
        "severity": "medium",
        "expected_value": str(rate.unit),
        "actual_value": bill_unit,
        "details": "Unsupported contract unit encountered during rate validation",
    }
