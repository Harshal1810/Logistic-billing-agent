from sqlalchemy.orm import Session

from app.db.neo4j import neo4j_client
from app.models.freight_bill import FreightBill


def reset_freight_bill_state(db: Session) -> dict:
    # Count rows before deletion for visibility.
    postgres_before = db.query(FreightBill).count()

    # Delete all freight bill rows; dependent tables cascade by FK ondelete=CASCADE.
    db.query(FreightBill).delete(synchronize_session=False)
    db.commit()

    # Clear projected freight bill nodes in Neo4j.
    labels_rows = neo4j_client.run_query("CALL db.labels() YIELD label RETURN collect(label) AS labels")
    labels = labels_rows[0]["labels"] if labels_rows else []
    if "FreightBill" in labels:
        neo4j_before_rows = neo4j_client.run_query("MATCH (fb:FreightBill) RETURN count(fb) AS count")
        neo4j_before = neo4j_before_rows[0]["count"] if neo4j_before_rows else 0
        neo4j_client.execute_write("MATCH (fb:FreightBill) DETACH DELETE fb")
    else:
        neo4j_before = 0

    return {
        "postgres_deleted_freight_bills": postgres_before,
        "neo4j_deleted_freight_bills": neo4j_before,
    }
