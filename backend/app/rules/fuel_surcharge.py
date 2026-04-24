from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.repositories.freight_bills import get_freight_bill_by_id, get_candidate_matches
from app.graph.queries import find_candidate_contracts_for_freight_bill


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_fuel_surcharge(db: Session, freight_bill_id: str) -> dict:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    selected_contract_rows = [
        row for row in get_candidate_matches(db, freight_bill_id, "contract") if row.selected
    ]
    if not selected_contract_rows:
        return {
            "rule_name": "fuel_surcharge_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(freight_bill.fuel_surcharge),
            "details": "No selected contract candidate available",
        }

    selected_contract_id = selected_contract_rows[0].candidate_id
    candidates = find_candidate_contracts_for_freight_bill(freight_bill_id)
    contract = next((c for c in candidates if c["contract_id"] == selected_contract_id), None)

    if contract is None:
        return {
            "rule_name": "fuel_surcharge_validation",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": None,
            "actual_value": str(freight_bill.fuel_surcharge),
            "details": f"Selected contract {selected_contract_id} not found in graph candidates",
        }

    bill_date = freight_bill.bill_date
    base_charge = Decimal(str(freight_bill.base_charge))
    billed_fuel = Decimal(str(freight_bill.fuel_surcharge))

    applicable_percent = Decimal(str(contract.get("fuel_surcharge_percent") or 0))
    revised_on = contract.get("revised_on")
    revised_percent = contract.get("revised_fuel_surcharge_percent")

    if revised_on and revised_percent:
        revised_on_date = date.fromisoformat(str(revised_on))
        if bill_date >= revised_on_date:
            applicable_percent = Decimal(str(revised_percent))

    expected_fuel = q2(base_charge * (applicable_percent / Decimal("100")))

    if expected_fuel == billed_fuel:
        return {
            "rule_name": "fuel_surcharge_validation",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": str(expected_fuel),
            "actual_value": str(billed_fuel),
            "details": f"Fuel surcharge matched applicable contract percent {applicable_percent}%",
        }

    return {
        "rule_name": "fuel_surcharge_validation",
        "rule_result": "fail",
        "severity": "high",
        "expected_value": str(expected_fuel),
        "actual_value": str(billed_fuel),
        "details": f"Fuel surcharge did not match applicable contract percent {applicable_percent}%",
    }