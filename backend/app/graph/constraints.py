from app.db.neo4j import neo4j_client


CONSTRAINTS = [
    """
    CREATE CONSTRAINT carrier_id IF NOT EXISTS
    FOR (c:Carrier) REQUIRE c.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT contract_id IF NOT EXISTS
    FOR (cc:CarrierContract) REQUIRE cc.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT shipment_id IF NOT EXISTS
    FOR (s:Shipment) REQUIRE s.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT bol_id IF NOT EXISTS
    FOR (b:BOL) REQUIRE b.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT freight_bill_id IF NOT EXISTS
    FOR (fb:FreightBill) REQUIRE fb.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT lane_code IF NOT EXISTS
    FOR (l:Lane) REQUIRE l.code IS UNIQUE
    """,
]


def create_constraints() -> None:
    for query in CONSTRAINTS:
        neo4j_client.execute_write(query)