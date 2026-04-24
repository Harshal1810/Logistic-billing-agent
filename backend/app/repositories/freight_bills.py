from sqlalchemy.orm import Session
from datetime import datetime

# Ensure all ORM models are imported/registered before mapper configuration.
from app.db import base as _model_registry  # noqa: F401
from app.models.freight_bill import FreightBill
from app.models.candidate_match import FreightBillCandidateMatch

_UNSET = object()


def get_freight_bill_by_id(db: Session, freight_bill_id: str) -> FreightBill | None:
    return (
        db.query(FreightBill)
        .filter(FreightBill.id == freight_bill_id)
        .one_or_none()
    )


def list_freight_bills(
    db: Session,
    limit: int = 100,
) -> list[FreightBill]:
    return (
        db.query(FreightBill)
        .order_by(FreightBill.updated_at.desc())
        .limit(limit)
        .all()
    )


def delete_candidate_matches(
    db: Session,
    freight_bill_id: str,
    candidate_type: str,
) -> None:
    (
        db.query(FreightBillCandidateMatch)
        .filter(
            FreightBillCandidateMatch.freight_bill_id == freight_bill_id,
            FreightBillCandidateMatch.candidate_type == candidate_type,
        )
        .delete(synchronize_session=False)
    )


def save_candidate_matches(
    db: Session,
    freight_bill_id: str,
    candidate_type: str,
    ranked_candidates: list[dict],
) -> None:
    delete_candidate_matches(db, freight_bill_id, candidate_type)

    for candidate in ranked_candidates:
        db.add(
            FreightBillCandidateMatch(
                freight_bill_id=freight_bill_id,
                candidate_type=candidate_type,
                candidate_id=candidate["candidate_id"],
                score=candidate["score"],
                match_reasons={"reasons": candidate.get("reasons", [])},
                selected=candidate.get("selected", False),
            )
        )

def update_selected_matches(
    db: Session,
    freight_bill_id: str,
    selected_contract_id: str | None | object = _UNSET,
    selected_shipment_id: str | None | object = _UNSET,
    selected_bol_id: str | None | object = _UNSET,
) -> FreightBill:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    if selected_contract_id is not _UNSET:
        freight_bill.selected_contract_id = selected_contract_id
    if selected_shipment_id is not _UNSET:
        freight_bill.selected_shipment_id = selected_shipment_id
    if selected_bol_id is not _UNSET:
        freight_bill.selected_bol_id = selected_bol_id

    db.add(freight_bill)
    return freight_bill


def update_bill_resolution(
    db: Session,
    freight_bill_id: str,
    processing_status: str | None = None,
    current_decision: str | None = None,
    final_resolution: str | None | object = _UNSET,
    confidence_score: float | None = None,
) -> FreightBill:
    freight_bill = get_freight_bill_by_id(db, freight_bill_id)
    if freight_bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")

    if processing_status is not None:
        freight_bill.processing_status = processing_status

    if current_decision is not None:
        freight_bill.current_decision = current_decision

    if confidence_score is not None:
        freight_bill.confidence_score = confidence_score

    if final_resolution is not _UNSET:
        freight_bill.final_resolution = final_resolution
        if final_resolution is not None:
            freight_bill.finalized_at = datetime.utcnow()
        else:
            freight_bill.finalized_at = None

    db.add(freight_bill)
    return freight_bill

def get_candidate_matches(
    db: Session,
    freight_bill_id: str,
    candidate_type: str,
) -> list[FreightBillCandidateMatch]:
    return (
        db.query(FreightBillCandidateMatch)
        .filter(
            FreightBillCandidateMatch.freight_bill_id == freight_bill_id,
            FreightBillCandidateMatch.candidate_type == candidate_type,
        )
        .order_by(FreightBillCandidateMatch.score.desc())
        .all()
    )

def find_duplicate_freight_bills(
    db: Session,
    freight_bill_id: str,
) -> list[FreightBill]:
    current = get_freight_bill_by_id(db, freight_bill_id)
    if current is None:
        return []

    query = db.query(FreightBill).filter(
        FreightBill.id != freight_bill_id,
        FreightBill.bill_number == current.bill_number,
    )

    if current.carrier_id is not None:
        query = query.filter(FreightBill.carrier_id == current.carrier_id)
    else:
        query = query.filter(FreightBill.carrier_name_raw == current.carrier_name_raw)

    return query.all()

def get_selected_candidate_match(
    db: Session,
    freight_bill_id: str,
    candidate_type: str,
):
    return (
        db.query(FreightBillCandidateMatch)
        .filter(
            FreightBillCandidateMatch.freight_bill_id == freight_bill_id,
            FreightBillCandidateMatch.candidate_type == candidate_type,
            FreightBillCandidateMatch.selected.is_(True),
        )
        .one_or_none()
    )

def get_prior_freight_bills_for_selected_shipment(
    db: Session,
    freight_bill_id: str,
    shipment_id: str,
) -> dict:
    current = get_freight_bill_by_id(db, freight_bill_id)
    if current is None:
        return {"confirmed": [], "pending": [], "excluded": []}

    rows = (
        db.query(FreightBill)
        .filter(
            FreightBill.id != freight_bill_id,
            FreightBill.selected_shipment_id == shipment_id,
        )
        .all()
    )

    confirmed = []
    pending = []
    excluded = []

    for row in rows:
        same_bill_number = row.bill_number == current.bill_number
        same_carrier = (
            row.carrier_id == current.carrier_id
            if current.carrier_id is not None
            else row.carrier_name_raw == current.carrier_name_raw
        )

        # Exclude obvious duplicates from cumulative computation
        if same_bill_number and same_carrier:
            excluded.append(row)
            continue

        if row.final_resolution == "approved":
            confirmed.append(row)
        elif row.final_resolution in {"disputed", "rejected"}:
            excluded.append(row)
        else:
            pending.append(row)

    return {
        "confirmed": confirmed,
        "pending": pending,
        "excluded": excluded,
    }
