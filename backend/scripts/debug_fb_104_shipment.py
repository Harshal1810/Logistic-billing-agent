from pprint import pprint

from app.db.postgres import SessionLocal
from app.graph.queries import find_candidate_shipments_for_freight_bill
from app.graph.shipment_matcher import score_and_persist_shipment_candidates
from app.repositories.freight_bills import get_freight_bill_by_id


def main():
    db = SessionLocal()
    try:
        freight_bill_id = "FB-2025-104"

        fb = get_freight_bill_by_id(db, freight_bill_id)
        if fb is None:
            raise ValueError(f"Freight bill not found: {freight_bill_id}")

        print("Freight bill:")
        print(
            {
                "id": fb.id,
                "shipment_reference": fb.shipment_reference,
                "selected_shipment_id": fb.selected_shipment_id,
                "lane": fb.lane,
                "billed_weight_kg": float(fb.billed_weight_kg),
                "bill_date": str(fb.bill_date),
            }
        )

        print("\nRaw shipment candidates:")
        pprint(find_candidate_shipments_for_freight_bill(freight_bill_id))

        print("\nRanked shipment candidates:")
        ranked = score_and_persist_shipment_candidates(db, freight_bill_id)
        pprint(ranked)

        db.refresh(fb)
        print("\nFreight bill after ranking:")
        print(
            {
                "id": fb.id,
                "shipment_reference": fb.shipment_reference,
                "selected_shipment_id": fb.selected_shipment_id,
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
