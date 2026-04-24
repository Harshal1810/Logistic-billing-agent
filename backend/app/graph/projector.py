from sqlalchemy.orm import Session

from app.db.neo4j import neo4j_client
from app.models.carrier import Carrier
from app.models.carrier_contract import CarrierContract
from app.models.contract_rate_card import ContractRateCard
from app.models.shipment import Shipment
from app.models.bill_of_lading import BillOfLading
from app.models.freight_bill import FreightBill


class GraphProjector:
    def __init__(self, db: Session):
        self.db = db

    def project_all(self) -> None:
        self.project_carriers()
        self.project_contracts_and_lanes()
        self.project_shipments()
        self.project_bols()
        self.project_freight_bills()

    def project_carriers(self) -> None:
        carriers = self.db.query(Carrier).all()
        query = """
        MERGE (c:Carrier {id: $id})
        SET c.name = $name,
            c.carrier_code = $carrier_code,
            c.gstin = $gstin,
            c.status = $status
        """
        for c in carriers:
            neo4j_client.execute_write(
                query,
                {
                    "id": c.id,
                    "name": c.name,
                    "carrier_code": c.carrier_code,
                    "gstin": c.gstin,
                    "status": c.status,
                },
            )

    def project_contracts_and_lanes(self) -> None:
        contracts = self.db.query(CarrierContract).all()
        for contract in contracts:
            neo4j_client.execute_write(
                """
                MATCH (c:Carrier {id: $carrier_id})
                MERGE (cc:CarrierContract {id: $id})
                SET cc.carrier_id = $carrier_id,
                    cc.effective_date = $effective_date,
                    cc.expiry_date = $expiry_date,
                    cc.status = $status,
                    cc.notes = $notes
                MERGE (c)-[:HAS_CONTRACT]->(cc)
                """,
                {
                    "id": contract.id,
                    "carrier_id": contract.carrier_id,
                    "effective_date": str(contract.effective_date),
                    "expiry_date": str(contract.expiry_date),
                    "status": contract.status,
                    "notes": contract.notes,
                },
            )

        rate_cards = self.db.query(ContractRateCard).all()
        for rc in rate_cards:
            neo4j_client.execute_write(
                """
                MATCH (cc:CarrierContract {id: $contract_id})
                MERGE (l:Lane {code: $lane_code})
                SET l.description = $description
                MERGE (cc)-[r:COVERS_LANE]->(l)
                SET r.rate_per_kg = $rate_per_kg,
                    r.min_charge = $min_charge,
                    r.fuel_surcharge_percent = $fuel_surcharge_percent,
                    r.rate_per_unit = $rate_per_unit,
                    r.unit = $unit,
                    r.unit_capacity_kg = $unit_capacity_kg,
                    r.alternate_rate_per_kg = $alternate_rate_per_kg,
                    r.revised_on = $revised_on,
                    r.revised_fuel_surcharge_percent = $revised_fuel_surcharge_percent
                """,
                {
                    "contract_id": rc.contract_id,
                    "lane_code": rc.lane_code,
                    "description": rc.description,
                    "rate_per_kg": float(rc.rate_per_kg) if rc.rate_per_kg is not None else None,
                    "min_charge": float(rc.min_charge) if rc.min_charge is not None else None,
                    "fuel_surcharge_percent": float(rc.fuel_surcharge_percent) if rc.fuel_surcharge_percent is not None else None,
                    "rate_per_unit": float(rc.rate_per_unit) if rc.rate_per_unit is not None else None,
                    "unit": rc.unit,
                    "unit_capacity_kg": float(rc.unit_capacity_kg) if rc.unit_capacity_kg is not None else None,
                    "alternate_rate_per_kg": float(rc.alternate_rate_per_kg) if rc.alternate_rate_per_kg is not None else None,
                    "revised_on": str(rc.revised_on) if rc.revised_on is not None else None,
                    "revised_fuel_surcharge_percent": float(rc.revised_fuel_surcharge_percent) if rc.revised_fuel_surcharge_percent is not None else None,
                },
            )

    def project_shipments(self) -> None:
        shipments = self.db.query(Shipment).all()
        for s in shipments:
            neo4j_client.execute_write(
                """
                MATCH (c:Carrier {id: $carrier_id})
                MATCH (cc:CarrierContract {id: $contract_id})
                MERGE (s:Shipment {id: $id})
                SET s.carrier_id = $carrier_id,
                    s.contract_id = $contract_id,
                    s.lane = $lane,
                    s.shipment_date = $shipment_date,
                    s.status = $status,
                    s.total_weight_kg = $total_weight_kg
                MERGE (c)-[:HANDLED]->(s)
                MERGE (cc)-[:GOVERNS]->(s)
                """,
                {
                    "id": s.id,
                    "carrier_id": s.carrier_id,
                    "contract_id": s.contract_id,
                    "lane": s.lane,
                    "shipment_date": str(s.shipment_date),
                    "status": s.status,
                    "total_weight_kg": float(s.total_weight_kg),
                },
            )

    def project_bols(self) -> None:
        bols = self.db.query(BillOfLading).all()
        for b in bols:
            neo4j_client.execute_write(
                """
                MATCH (s:Shipment {id: $shipment_id})
                MERGE (b:BOL {id: $id})
                SET b.shipment_id = $shipment_id,
                    b.delivery_date = $delivery_date,
                    b.actual_weight_kg = $actual_weight_kg,
                    b.notes = $notes
                MERGE (s)-[:HAS_BOL]->(b)
                """,
                {
                    "id": b.id,
                    "shipment_id": b.shipment_id,
                    "delivery_date": str(b.delivery_date),
                    "actual_weight_kg": float(b.actual_weight_kg),
                    "notes": b.notes,
                },
            )

    def project_freight_bills(self) -> None:
        freight_bills = self.db.query(FreightBill).all()
        for fb in freight_bills:
            neo4j_client.execute_write(
                """
                MERGE (fb:FreightBill {id: $id})
                SET fb.carrier_id = $carrier_id,
                    fb.carrier_name_raw = $carrier_name_raw,
                    fb.bill_number = $bill_number,
                    fb.bill_date = $bill_date,
                    fb.shipment_reference = $shipment_reference,
                    fb.lane = $lane,
                    fb.billed_weight_kg = $billed_weight_kg,
                    fb.rate_per_kg = $rate_per_kg,
                    fb.billing_unit = $billing_unit,
                    fb.total_amount = $total_amount
                """,
                {
                    "id": fb.id,
                    "carrier_id": fb.carrier_id,
                    "carrier_name_raw": fb.carrier_name_raw,
                    "bill_number": fb.bill_number,
                    "bill_date": str(fb.bill_date),
                    "shipment_reference": fb.shipment_reference,
                    "lane": fb.lane,
                    "billed_weight_kg": float(fb.billed_weight_kg),
                    "rate_per_kg": float(fb.rate_per_kg) if fb.rate_per_kg is not None else None,
                    "billing_unit": fb.billing_unit,
                    "total_amount": float(fb.total_amount),
                },
            )

            if fb.carrier_id:
                neo4j_client.execute_write(
                    """
                    MATCH (fb:FreightBill {id: $freight_bill_id})
                    MATCH (c:Carrier {id: $carrier_id})
                    MERGE (fb)-[:BILLED_BY]->(c)
                    """,
                    {
                        "freight_bill_id": fb.id,
                        "carrier_id": fb.carrier_id,
                    },
                )

            if fb.shipment_reference:
                neo4j_client.execute_write(
                    """
                    MATCH (fb:FreightBill {id: $freight_bill_id})
                    MATCH (s:Shipment {id: $shipment_id})
                    MERGE (fb)-[:REFERENCES_SHIPMENT]->(s)
                    """,
                    {
                        "freight_bill_id": fb.id,
                        "shipment_id": fb.shipment_reference,
                    },
                )