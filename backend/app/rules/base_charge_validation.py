from decimal import Decimal

from sqlalchemy.orm import Session

from app.rules.common import (
    get_bill,
    get_contract_rate_for_lane,
    get_selected_contract,
    normalize_billing_unit,
    q2,
)


def validate_base_charge(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    contract = get_selected_contract(db, bill)

    if contract is None:
        return {
            "rule_name": "base_charge_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(bill.base_charge),
            "details": "No selected contract available for base charge validation",
        }

    rate = get_contract_rate_for_lane(db, contract.id, bill.lane)
    if rate is None:
        return {
            "rule_name": "base_charge_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(bill.base_charge),
            "details": f"No contract rate card row found for lane {bill.lane}",
        }

    bill_unit = normalize_billing_unit(bill.billing_unit, bill.rate_per_kg)
    billed_weight = Decimal(str(bill.billed_weight_kg))
    actual_base = q2(Decimal(str(bill.base_charge)))

    expected_base: Decimal | None = None

    if rate.unit is None or rate.unit.lower() == "kg":
        if rate.rate_per_kg is None:
            return {
                "rule_name": "base_charge_validation",
                "rule_result": "warning",
                "severity": "medium",
                "expected_value": None,
                "actual_value": str(actual_base),
                "details": "Per-kg contract row missing rate_per_kg",
            }
        min_charge = Decimal(str(rate.min_charge or 0))
        expected_base = q2(max(billed_weight * Decimal(str(rate.rate_per_kg)), min_charge))
    elif rate.unit and rate.unit.lower() == "ftl":
        if bill_unit == "kg":
            if rate.alternate_rate_per_kg is None:
                return {
                    "rule_name": "base_charge_validation",
                    "rule_result": "warning",
                    "severity": "medium",
                    "expected_value": None,
                    "actual_value": str(actual_base),
                    "details": "FTL contract has no alternate per-kg pricing for per-kg billed invoice",
                }
            min_charge = Decimal(str(rate.min_charge or 0))
            expected_base = q2(
                max(billed_weight * Decimal(str(rate.alternate_rate_per_kg)), min_charge)
            )
        elif rate.rate_per_unit is not None:
            expected_base = q2(Decimal(str(rate.rate_per_unit)))
        else:
            return {
                "rule_name": "base_charge_validation",
                "rule_result": "warning",
                "severity": "medium",
                "expected_value": None,
                "actual_value": str(actual_base),
                "details": "FTL contract missing both rate_per_unit and alternate per-kg pricing",
            }
    else:
        return {
            "rule_name": "base_charge_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(actual_base),
            "details": f"Unsupported contract billing unit {rate.unit}",
        }

    if expected_base == actual_base:
        return {
            "rule_name": "base_charge_validation",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": str(expected_base),
            "actual_value": str(actual_base),
            "details": "Base charge matched selected contract pricing model",
        }

    return {
        "rule_name": "base_charge_validation",
        "rule_result": "fail",
        "severity": "high",
        "expected_value": str(expected_base),
        "actual_value": str(actual_base),
        "details": "Base charge did not match selected contract pricing model",
    }
