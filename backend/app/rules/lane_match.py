from sqlalchemy.orm import Session

from app.rules.common import get_bill, get_contract_rate_for_lane, get_selected_contract


def validate_lane_match(db: Session, freight_bill_id: str) -> dict:
    bill = get_bill(db, freight_bill_id)
    contract = get_selected_contract(db, bill)

    if contract is None:
        return {
            "rule_name": "lane_match_check",
            "rule_result": "warning",
            "severity": "medium",
            "expected_value": bill.lane,
            "actual_value": None,
            "details": "No selected contract available for lane validation",
        }

    rate = get_contract_rate_for_lane(db, contract.id, bill.lane)
    if rate is not None:
        return {
            "rule_name": "lane_match_check",
            "rule_result": "pass",
            "severity": "low",
            "expected_value": bill.lane,
            "actual_value": rate.lane_code,
            "details": f"Selected contract {contract.id} covers lane {bill.lane}",
        }

    return {
        "rule_name": "lane_match_check",
        "rule_result": "fail",
        "severity": "high",
        "expected_value": bill.lane,
        "actual_value": None,
        "details": f"Selected contract {contract.id} does not cover lane {bill.lane}",
    }
