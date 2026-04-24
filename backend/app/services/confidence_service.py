def compute_confidence(validation_results: list[dict]) -> float:
    score = 1.0

    for result in validation_results:
        rule_name = result["rule_name"]
        rule_result = result["rule_result"]
        severity = result["severity"]

        if rule_result == "pass":
            continue

        if rule_name == "duplicate_bill_check" and severity == "critical":
            score -= 0.60
        elif rule_name == "cumulative_billing_check" and severity == "critical":
            score -= 0.50
        elif rule_name == "weight_reconciliation" and severity == "high":
            score -= 0.35
        elif rule_name == "contract_validity_check" and rule_result == "fail":
            score -= 0.30
        elif rule_name == "lane_match_check" and rule_result == "fail":
            score -= 0.30
        elif rule_name == "rate_validation" and rule_result == "fail":
            score -= 0.30
        elif rule_name == "base_charge_validation" and rule_result == "fail":
            score -= 0.25
        elif rule_name == "unit_reconciliation_check" and rule_result == "fail":
            score -= 0.30
        elif rule_name == "amount_consistency_check" and rule_result == "fail":
            score -= 0.20
        elif severity == "medium":
            score -= 0.15
        elif severity == "low":
            score -= 0.05

    return max(0.0, round(score, 4))
