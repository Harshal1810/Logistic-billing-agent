import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def get_seed_bill(seed: dict, freight_bill_id: str) -> dict:
    row = next(x for x in seed["freight_bills"] if x["id"] == freight_bill_id)
    payload = dict(row)
    payload["force_reprocess"] = True
    return payload


def by_rule(results: list[dict], rule_name: str) -> dict:
    return next(x for x in results if x["rule_name"] == rule_name)


def main() -> None:
    client = TestClient(app)
    seed = json.loads(Path("data/seed data logistics.json").read_text(encoding="utf-8"))

    # FB-2025-105: rate drift
    r105 = client.post("/freight-bills", json=get_seed_bill(seed, "FB-2025-105"))
    assert r105.status_code == 200, r105.text
    b105 = r105.json()
    assert b105["decision"]["decision"] in {"flag_for_review", "dispute"}, b105
    assert by_rule(b105["validation_results"], "rate_validation")["rule_result"] == "fail", b105

    # FB-2025-106: expired-contract-ish mismatch scenario (handled via contract/rate/base checks)
    r106 = client.post("/freight-bills", json=get_seed_bill(seed, "FB-2025-106"))
    assert r106.status_code == 200, r106.text
    b106 = r106.json()
    assert b106["decision"]["decision"] in {"flag_for_review", "dispute"}, b106
    assert by_rule(b106["validation_results"], "rate_validation")["rule_result"] == "fail", b106
    assert by_rule(b106["validation_results"], "base_charge_validation")["rule_result"] == "fail", b106

    # FB-2025-107: unit reconciliation approve path
    r107 = client.post("/freight-bills", json=get_seed_bill(seed, "FB-2025-107"))
    assert r107.status_code == 200, r107.text
    b107 = r107.json()
    assert b107["decision"]["decision"] == "auto_approve", b107
    assert by_rule(b107["validation_results"], "unit_reconciliation_check")["rule_result"] == "pass", b107

    # FB-2025-108: surcharge revision approve path
    r108 = client.post("/freight-bills", json=get_seed_bill(seed, "FB-2025-108"))
    assert r108.status_code == 200, r108.text
    b108 = r108.json()
    assert b108["decision"]["decision"] == "auto_approve", b108
    assert by_rule(b108["validation_results"], "fuel_surcharge_validation")["rule_result"] == "pass", b108

    # FB-2025-110: unknown carrier -> review
    r110 = client.post("/freight-bills", json=get_seed_bill(seed, "FB-2025-110"))
    assert r110.status_code == 200, r110.text
    b110 = r110.json()
    assert b110["decision"]["decision"] == "flag_for_review", b110
    assert by_rule(b110["validation_results"], "carrier_resolution_check")["rule_result"] == "warning", b110

    print("Business scenario tests passed: 105, 106, 107, 108, 110.")


if __name__ == "__main__":
    main()
