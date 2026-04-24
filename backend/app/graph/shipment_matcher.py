from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from app.graph.queries import find_candidate_shipments_for_freight_bill
from app.repositories.freight_bills import (
    get_freight_bill_by_id,
    save_candidate_matches,
    update_selected_matches
)


def score_shipment_candidates(db: Session, freight_bill_id: str) -> list[dict]:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    candidates = find_candidate_shipments_for_freight_bill(freight_bill_id)
    ranked: list[dict] = []

    bill_date = freight_bill.bill_date
    billed_weight = Decimal(str(freight_bill.billed_weight_kg))

    for candidate in candidates:
        score = Decimal("0.00")
        reasons: list[str] = []

        shipment_id = candidate["shipment_id"]
        shipment_weight = Decimal(str(candidate["total_weight_kg"]))
        shipment_date = candidate["shipment_date"]
        contract_id = candidate.get("contract_id")
        exact_reference_match = bool(candidate.get("exact_reference_match"))

        # same carrier/lane already enforced in graph query
        score += Decimal("0.40")
        reasons.append("carrier and lane matched")

        if exact_reference_match or (
            freight_bill.shipment_reference
            and freight_bill.shipment_reference == shipment_id
        ):
            score += Decimal("0.40")
            reasons.append("shipment_reference matched exactly")

        weight_diff = abs(shipment_weight - billed_weight)
        if weight_diff == 0:
            score += Decimal("0.20")
            reasons.append("shipment total weight matched billed weight exactly")
        elif weight_diff <= Decimal("100"):
            score += Decimal("0.10")
            reasons.append("shipment total weight was close to billed weight")

        # Optional mild date proximity scoring
        if isinstance(shipment_date, date):
            delta_days = abs((bill_date - shipment_date).days)
            if delta_days <= 30:
                score += Decimal("0.10")
                reasons.append("shipment date was within 30 days of bill date")

        ranked.append(
            {
                "candidate_id": shipment_id,
                "score": float(min(score, Decimal("1.00"))),
                "reasons": reasons,
                "selected": False,
                "contract_id": contract_id,
                "exact_reference_match": exact_reference_match,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    if ranked:
        # Exact freight-bill shipment reference is strongest signal; pick it directly.
        exact_candidates = [c for c in ranked if c.get("exact_reference_match")]
        if exact_candidates:
            exact_candidates[0]["selected"] = True
        else:
            top = ranked[0]
            second_score = ranked[1]["score"] if len(ranked) > 1 else 0.0

            if top["score"] >= 0.85 and (top["score"] - second_score) >= 0.15:
                top["selected"] = True

    return ranked


def score_and_persist_shipment_candidates(db: Session, freight_bill_id: str) -> list[dict]:
    ranked = score_shipment_candidates(db, freight_bill_id)

    save_candidate_matches(
        db=db,
        freight_bill_id=freight_bill_id,
        candidate_type="shipment",
        ranked_candidates=ranked,
    )

    selected_shipment_id = next(
        (candidate["candidate_id"] for candidate in ranked if candidate.get("selected")),
        None,
    )

    update_selected_matches(
        db=db,
        freight_bill_id=freight_bill_id,
        selected_shipment_id=selected_shipment_id,
    )

    db.commit()
    return ranked
