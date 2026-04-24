from pprint import pprint

from app.db.postgres import SessionLocal
from app.graph.matcher import score_and_persist_contract_candidates
from app.graph.shipment_matcher import score_and_persist_shipment_candidates
from app.repositories.decisions import get_latest_decision
from app.repositories.freight_bills import get_freight_bill_by_id
from app.services.decision_service import decide_freight_bill
from app.services.validation_service import run_core_validations


def prepare(db, freight_bill_id: str):
    score_and_persist_contract_candidates(db, freight_bill_id)
    score_and_persist_shipment_candidates(db, freight_bill_id)
    run_core_validations(db, freight_bill_id)


def run_one(freight_bill_id: str):
    db = SessionLocal()
    try:
        print(f"\n=== {freight_bill_id} ===")
        prepare(db, freight_bill_id)
        result = decide_freight_bill(db, freight_bill_id)
        pprint(result)

        latest = get_latest_decision(db, freight_bill_id)
        bill = get_freight_bill_by_id(db, freight_bill_id)

        print("\nStored decision:")
        print(
            {
                "decision": latest.decision,
                "confidence_score": float(latest.confidence_score),
                "decision_reason": latest.decision_reason,
            }
        )

        print("\nFreight bill state:")
        print(
            {
                "processing_status": bill.processing_status,
                "current_decision": bill.current_decision,
                "final_resolution": bill.final_resolution,
                "confidence_score": float(bill.confidence_score),
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
        "FB-2025-109",
        "FB-2025-110",
    ]:
        run_one(freight_bill_id)
