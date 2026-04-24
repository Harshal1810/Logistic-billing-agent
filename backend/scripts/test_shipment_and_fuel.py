from pprint import pprint

from app.db.postgres import SessionLocal
from app.graph.shipment_matcher import score_and_persist_shipment_candidates
from app.rules.fuel_surcharge import validate_fuel_surcharge
from app.repositories.validations import save_validation_result, get_validation_results


def run_one(freight_bill_id: str):
    db = SessionLocal()
    try:
        print(f"\n=== {freight_bill_id} shipment candidates ===")
        ranked = score_and_persist_shipment_candidates(db, freight_bill_id)
        pprint(ranked)

        print(f"\n=== {freight_bill_id} fuel validation ===")
        result = validate_fuel_surcharge(db, freight_bill_id)
        pprint(result)

        save_validation_result(db, freight_bill_id, result)
        db.commit()

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
    for freight_bill_id in ["FB-2025-101", "FB-2025-108"]:
        run_one(freight_bill_id)