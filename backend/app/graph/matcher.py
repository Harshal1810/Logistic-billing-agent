from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session

from app.graph.queries import find_candidate_contracts_for_freight_bill
from app.repositories.freight_bills import (
    get_freight_bill_by_id,
    save_candidate_matches,
    update_selected_matches
)


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def score_contract_candidates(db: Session, freight_bill_id: str) -> list[dict]:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    candidates = find_candidate_contracts_for_freight_bill(freight_bill_id)
    ranked: list[dict] = []

    billed_weight = Decimal(str(freight_bill.billed_weight_kg))
    billed_rate = Decimal(str(freight_bill.rate_per_kg)) if freight_bill.rate_per_kg is not None else None
    billed_base = Decimal(str(freight_bill.base_charge))
    billed_fuel = Decimal(str(freight_bill.fuel_surcharge))

    for candidate in candidates:
        score = Decimal("0.00")
        reasons: list[str] = []

        # Candidate already passed graph filters for carrier/date/lane
        score += Decimal("0.30")
        reasons.append("carrier, lane, and contract date window matched")

        candidate_rate = candidate.get("rate_per_kg")
        candidate_fuel_pct = candidate.get("fuel_surcharge_percent")
        min_charge = candidate.get("min_charge") or 0

        expected_base = None
        expected_fuel = None

        if candidate_rate is not None and billed_rate is not None:
            candidate_rate_dec = Decimal(str(candidate_rate))
            min_charge_dec = Decimal(str(min_charge))
            candidate_fuel_pct_dec = Decimal(str(candidate_fuel_pct or 0))

            expected_base = max(billed_weight * candidate_rate_dec, min_charge_dec)
            expected_base = q2(expected_base)

            expected_fuel = expected_base * (candidate_fuel_pct_dec / Decimal("100"))
            expected_fuel = q2(expected_fuel)

            if candidate_rate_dec == billed_rate:
                score += Decimal("0.30")
                reasons.append(f"rate_per_kg matched exactly at {candidate_rate_dec}")

            if expected_base == billed_base:
                score += Decimal("0.25")
                reasons.append(f"base_charge matched expected amount {expected_base}")

            if expected_fuel == billed_fuel:
                score += Decimal("0.15")
                reasons.append(f"fuel_surcharge matched expected amount {expected_fuel}")

        ranked.append(
            {
                "candidate_id": candidate["contract_id"],
                "score": float(score),
                "reasons": reasons,
                "selected": False,
                "expected_base": float(expected_base) if expected_base is not None else None,
                "expected_fuel": float(expected_fuel) if expected_fuel is not None else None,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    if ranked:
        if len(ranked) == 1:
            ranked[0]["selected"] = True
        else:
            top = ranked[0]
            second_score = ranked[1]["score"]

            if top["score"] >= 0.85 and (top["score"] - second_score) >= 0.20:
                top["selected"] = True

    return ranked


def score_and_persist_contract_candidates(db: Session, freight_bill_id: str) -> list[dict]:
    ranked = score_contract_candidates(db, freight_bill_id)

    save_candidate_matches(
        db=db,
        freight_bill_id=freight_bill_id,
        candidate_type="contract",
        ranked_candidates=ranked,
    )

    selected_contract_id = next(
        (candidate["candidate_id"] for candidate in ranked if candidate.get("selected")),
        None,
    )

    update_selected_matches(
        db=db,
        freight_bill_id=freight_bill_id,
        selected_contract_id=selected_contract_id,
    )

    db.commit()
    return ranked
