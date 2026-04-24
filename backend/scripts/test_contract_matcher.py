from pprint import pprint

from app.db.postgres import SessionLocal
from app.graph.matcher import score_and_persist_contract_candidates
from app.repositories.freight_bills import get_candidate_matches


def run_one(freight_bill_id: str) -> None:
    db = SessionLocal()
    try:
        print(f"\n=== {freight_bill_id} ===")
        ranked = score_and_persist_contract_candidates(db, freight_bill_id)
        pprint(ranked)

        print("\nPersisted rows:")
        rows = get_candidate_matches(db, freight_bill_id, "contract")
        for row in rows:
            print(
                {
                    "candidate_id": row.candidate_id,
                    "score": float(row.score),
                    "selected": row.selected,
                    "reasons": row.match_reasons,
                }
            )
    finally:
        db.close()


if __name__ == "__main__":
    for freight_bill_id in ["FB-2025-101", "FB-2025-102", "FB-2025-108"]:
        run_one(freight_bill_id)