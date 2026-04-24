from sqlalchemy.orm import Session

from app.repositories.validations import save_validation_result, delete_validation_results
from app.rules.amount_consistency import validate_amount_consistency
from app.rules.base_charge_validation import validate_base_charge
from app.rules.carrier_resolution import validate_carrier_resolution
from app.rules.contract_shipment_consistency import validate_contract_shipment_consistency
from app.rules.contract_validity import validate_contract_validity
from app.rules.duplicate_check import validate_duplicate_bill
from app.rules.fuel_surcharge import validate_fuel_surcharge
from app.rules.lane_match import validate_lane_match
from app.rules.rate_validation import validate_rate_per_kg
from app.rules.shipment_resolution import validate_shipment_resolution
from app.rules.unit_reconciliation import validate_unit_reconciliation
from app.rules.cumulative_billing import validate_cumulative_billing
from app.rules.weight_reconciliation import validate_weight_reconciliation


def run_core_validations(db: Session, freight_bill_id: str) -> list[dict]:
    delete_validation_results(db, freight_bill_id)

    results = [
        validate_carrier_resolution(db, freight_bill_id),
        validate_duplicate_bill(db, freight_bill_id),
        validate_contract_validity(db, freight_bill_id),
        validate_lane_match(db, freight_bill_id),
        validate_unit_reconciliation(db, freight_bill_id),
        validate_rate_per_kg(db, freight_bill_id),
        validate_base_charge(db, freight_bill_id),
        validate_fuel_surcharge(db, freight_bill_id),
        validate_amount_consistency(db, freight_bill_id),
        validate_shipment_resolution(db, freight_bill_id),
        validate_contract_shipment_consistency(db, freight_bill_id),
        validate_weight_reconciliation(db, freight_bill_id),
        validate_cumulative_billing(db, freight_bill_id),
    ]

    for result in results:
        save_validation_result(db, freight_bill_id, result)

    db.commit()
    return results
