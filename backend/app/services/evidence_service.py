from sqlalchemy.orm import Session

from app.graph.queries import find_bol_evidence_for_shipment
from app.repositories.freight_bills import (
    get_freight_bill_by_id
)


def get_selected_shipment_bol_evidence(db: Session, freight_bill_id: str) -> dict:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    shipment_id = freight_bill.selected_shipment_id
    if shipment_id is None:
        return {
            "freight_bill_id": freight_bill_id,
            "shipment_id": None,
            "bols": [],
            "bol_count": 0,
            "total_actual_weight": 0.0,
            "details": "No selected shipment available",
        }

    bols = find_bol_evidence_for_shipment(shipment_id)
    total_actual_weight = sum(float(b["actual_weight_kg"]) for b in bols)

    return {
        "freight_bill_id": freight_bill_id,
        "shipment_id": shipment_id,
        "bols": bols,
        "bol_count": len(bols),
        "total_actual_weight": total_actual_weight,
        "details": f"Loaded {len(bols)} BOL(s) for shipment {shipment_id}",
    }