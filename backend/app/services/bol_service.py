from app.graph.queries import find_bol_evidence_for_shipment


def get_bol_evidence(shipment_id: str) -> dict:
    bols = find_bol_evidence_for_shipment(shipment_id)

    total_actual_weight = sum(float(b["actual_weight_kg"]) for b in bols)

    return {
        "shipment_id": shipment_id,
        "bols": bols,
        "bol_count": len(bols),
        "total_actual_weight": total_actual_weight,
    }