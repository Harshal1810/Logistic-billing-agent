import json
from datetime import date
from pathlib import Path

from app.db.postgres import SessionLocal
from app.models.carrier import Carrier
from app.models.carrier_contract import CarrierContract
from app.models.contract_rate_card import ContractRateCard
from app.models.shipment import Shipment
from app.models.bill_of_lading import BillOfLading
from app.models.freight_bill import FreightBill


DATE_FIELDS = {
    "onboarded_on",
    "effective_date",
    "expiry_date",
    "revised_on",
    "shipment_date",
    "delivery_date",
    "bill_date",
}


def parse_iso_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    raise TypeError(f"Unsupported date value type: {type(value)!r}")


def normalize_payload_dates(payload: dict) -> dict:
    normalized = dict(payload)
    for field in DATE_FIELDS:
        if field in normalized and normalized[field] is not None:
            normalized[field] = parse_iso_date(normalized[field]).isoformat()
    return normalized


def load_seed_data(file_path: str, include_freight_bills: bool = False) -> None:
    path = Path(file_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        # Carriers
        for row in data.get("carriers", []):
            db.merge(
                Carrier(
                    id=row["id"],
                    name=row["name"],
                    carrier_code=row["carrier_code"],
                    gstin=row["gstin"],
                    bank_account=row["bank_account"],
                    status=row["status"],
                    onboarded_on=parse_iso_date(row["onboarded_on"]),
                )
            )

        # Contracts + Rate Cards
        for row in data.get("carrier_contracts", []):
            db.merge(
                CarrierContract(
                    id=row["id"],
                    carrier_id=row["carrier_id"],
                    effective_date=parse_iso_date(row["effective_date"]),
                    expiry_date=parse_iso_date(row["expiry_date"]),
                    status=row["status"],
                    notes=row.get("notes"),
                )
            )
            db.flush()

            for rc in row.get("rate_card", []):
                db.add(
                    ContractRateCard(
                        contract_id=row["id"],
                        lane_code=rc["lane"],
                        description=rc["description"],
                        rate_per_kg=rc.get("rate_per_kg"),
                        min_charge=rc.get("min_charge"),
                        fuel_surcharge_percent=rc.get("fuel_surcharge_percent"),
                        rate_per_unit=rc.get("rate_per_unit"),
                        unit=rc.get("unit"),
                        unit_capacity_kg=rc.get("unit_capacity_kg"),
                        alternate_rate_per_kg=rc.get("alternate_rate_per_kg"),
                        revised_on=parse_iso_date(rc.get("revised_on")),
                        revised_fuel_surcharge_percent=rc.get("revised_fuel_surcharge_percent"),
                    )
                )

        # Shipments
        for row in data.get("shipments", []):
            db.merge(
                Shipment(
                    id=row["id"],
                    carrier_id=row["carrier_id"],
                    contract_id=row["contract_id"],
                    lane=row["lane"],
                    shipment_date=parse_iso_date(row["shipment_date"]),
                    status=row["status"],
                    total_weight_kg=row["total_weight_kg"],
                    notes=row.get("notes"),
                )
            )

        # Bills of lading
        for row in data.get("bills_of_lading", []):
            db.merge(
                BillOfLading(
                    id=row["id"],
                    shipment_id=row["shipment_id"],
                    delivery_date=parse_iso_date(row["delivery_date"]),
                    actual_weight_kg=row["actual_weight_kg"],
                    notes=row.get("notes") or row.get("_note"),
                )
            )

        if include_freight_bills:
            # Freight bills (optional to keep workflow ingestion user-driven by default)
            for row in data.get("freight_bills", []):
                db.merge(
                    FreightBill(
                        id=row["id"],
                        carrier_id=row.get("carrier_id"),
                        carrier_name_raw=row["carrier_name"],
                        bill_number=row["bill_number"],
                        bill_date=parse_iso_date(row["bill_date"]),
                        shipment_reference=row.get("shipment_reference"),
                        lane=row["lane"],
                        billed_weight_kg=row["billed_weight_kg"],
                        rate_per_kg=row.get("rate_per_kg"),
                        billing_unit=row.get("billing_unit"),
                        base_charge=row["base_charge"],
                        fuel_surcharge=row["fuel_surcharge"],
                        gst_amount=row["gst_amount"],
                        total_amount=row["total_amount"],
                        raw_payload=normalize_payload_dates(row),
                        processing_status="ingested",
                        current_decision=None,
                        confidence_score=None,
                    )
                )

        db.commit()
        msg = "Seed data loaded successfully into Postgres."
        if include_freight_bills:
            msg += " (including freight_bills)"
        else:
            msg += " (excluding freight_bills; ingest via POST /freight-bills)"
        print(msg)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
