from pprint import pprint

from app.db.postgres import SessionLocal
from app.graph.matcher import score_and_persist_contract_candidates
from app.graph.shipment_matcher import score_and_persist_shipment_candidates
from app.services.validation_service import run_core_validations
from app.repositories.validations import get_validation_results


def prepare_candidates(db, freight_bill_id: str):
    score_and_persist_contract_candidates(db, freight_bill_id)
    score_and_persist_shipment_candidates(db, freight_bill_id)


def run_one(freight_bill_id: str):
    db = SessionLocal()
    try:
        print(f"\n=== {freight_bill_id} ===")
        prepare_candidates(db, freight_bill_id)

        results = run_core_validations(db, freight_bill_id)
        pprint(results)

        print("\nPersisted validations:")
        rows = get_validation_results(db, freight_bill_id)
        for row in rows:
            print(
                {
                    "rule_name": row.rule_name,
                    "rule_result": row.rule_result,
                    "severity": row.severity,
                    "expected_value": row.expected_value,
                    "actual_value": row.actual_value,
                    "details": row.details,
                }
            )
    finally:
        db.close()


if __name__ == "__main__":
    for freight_bill_id in [
        "FB-2025-101",
        "FB-2025-104",
        "FB-2025-105",
        "FB-2025-106",
        "FB-2025-107",
        "FB-2025-108",
        "FB-2025-109",
        "FB-2025-110",
    ]:
        run_one(freight_bill_id)
