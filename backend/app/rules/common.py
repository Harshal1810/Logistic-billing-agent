from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.carrier import Carrier
from app.models.carrier_contract import CarrierContract
from app.models.contract_rate_card import ContractRateCard
from app.models.freight_bill import FreightBill
from app.models.shipment import Shipment
from app.repositories.freight_bills import get_freight_bill_by_id


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_bill(db: Session, freight_bill_id: str) -> FreightBill:
    bill = get_freight_bill_by_id(db, freight_bill_id)
    if bill is None:
        raise ValueError(f"Freight bill not found: {freight_bill_id}")
    return bill


def get_selected_contract(db: Session, bill: FreightBill) -> CarrierContract | None:
    if not bill.selected_contract_id:
        return None
    return (
        db.query(CarrierContract)
        .filter(CarrierContract.id == bill.selected_contract_id)
        .one_or_none()
    )


def get_selected_shipment(db: Session, bill: FreightBill) -> Shipment | None:
    if not bill.selected_shipment_id:
        return None
    return (
        db.query(Shipment)
        .filter(Shipment.id == bill.selected_shipment_id)
        .one_or_none()
    )


def get_carrier(db: Session, bill: FreightBill) -> Carrier | None:
    if bill.carrier_id is None:
        return None
    return db.query(Carrier).filter(Carrier.id == bill.carrier_id).one_or_none()


def get_contract_rate_for_lane(
    db: Session, contract_id: str, lane: str
) -> ContractRateCard | None:
    return (
        db.query(ContractRateCard)
        .filter(
            ContractRateCard.contract_id == contract_id,
            ContractRateCard.lane_code == lane,
        )
        .first()
    )


def normalize_billing_unit(billing_unit: str | None, rate_per_kg: Decimal | None) -> str:
    if billing_unit:
        return billing_unit.strip().lower()
    if rate_per_kg is not None:
        return "kg"
    return "unknown"
