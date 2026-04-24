from app.db.neo4j import neo4j_client


def find_candidate_contracts_for_freight_bill(freight_bill_id: str):
    query = """
    MATCH (fb:FreightBill {id: $freight_bill_id})-[:BILLED_BY]->(c:Carrier)-[:HAS_CONTRACT]->(cc:CarrierContract)-[r:COVERS_LANE]->(l:Lane)
    WHERE l.code = fb.lane
      AND date(cc.effective_date) <= date(fb.bill_date)
      AND date(cc.expiry_date) >= date(fb.bill_date)
    RETURN
      cc.id AS contract_id,
      cc.status AS contract_status,
      l.code AS lane,
      r.rate_per_kg AS rate_per_kg,
      r.min_charge AS min_charge,
      r.fuel_surcharge_percent AS fuel_surcharge_percent,
      r.unit AS unit,
      r.alternate_rate_per_kg AS alternate_rate_per_kg,
      r.revised_on AS revised_on,
      r.revised_fuel_surcharge_percent AS revised_fuel_surcharge_percent
    """
    return neo4j_client.run_query(query, {"freight_bill_id": freight_bill_id})

def find_candidate_shipments_for_freight_bill(freight_bill_id: str):
    query = """
    MATCH (fb:FreightBill {id: $freight_bill_id})-[:BILLED_BY]->(c:Carrier)-[:HANDLED]->(s:Shipment)
    WHERE s.lane = fb.lane
    RETURN
      s.id AS shipment_id,
      s.shipment_date AS shipment_date,
      s.status AS shipment_status,
      s.total_weight_kg AS total_weight_kg,
      s.contract_id AS contract_id,
      CASE
        WHEN fb.shipment_reference IS NOT NULL AND s.id = fb.shipment_reference THEN 1
        ELSE 0
      END AS exact_reference_match
    ORDER BY exact_reference_match DESC,
             abs(toFloat(s.total_weight_kg) - toFloat(fb.billed_weight_kg)) ASC
    """
    return neo4j_client.run_query(query, {"freight_bill_id": freight_bill_id})

def find_bol_evidence_for_shipment(shipment_id: str):
    query = """
    MATCH (s:Shipment {id: $shipment_id})-[:HAS_BOL]->(b:BOL)
    RETURN
      b.id AS bol_id,
      b.delivery_date AS delivery_date,
      b.actual_weight_kg AS actual_weight_kg,
      b.notes AS notes
    ORDER BY b.delivery_date ASC
    """
    return neo4j_client.run_query(query, {"shipment_id": shipment_id})
