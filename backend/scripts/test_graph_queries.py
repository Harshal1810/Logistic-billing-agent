from pprint import pprint
from app.graph.queries import find_candidate_contracts_for_freight_bill


if __name__ == "__main__":
    for freight_bill_id in ["FB-2025-101", "FB-2025-102", "FB-2025-108"]:
        print(f"\n=== {freight_bill_id} ===")
        pprint(find_candidate_contracts_for_freight_bill(freight_bill_id))