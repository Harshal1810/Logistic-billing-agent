import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def get_seed_bill(seed: dict, freight_bill_id: str) -> dict:
    return next(x for x in seed["freight_bills"] if x["id"] == freight_bill_id)


def main() -> None:
    client = TestClient(app)
    seed = json.loads(Path("data/seed data logistics.json").read_text(encoding="utf-8"))

    # 1) Auto-approve path
    approve_payload = get_seed_bill(seed, "FB-2025-107")
    approve_payload["force_reprocess"] = True
    approve_resp = client.post("/freight-bills", json=approve_payload)
    assert approve_resp.status_code == 200, approve_resp.text
    approve_body = approve_resp.json()
    assert approve_body["decision"]["decision"] == "auto_approve", approve_body
    assert approve_body["workflow"]["workflow_status"] == "completed", approve_body
    print("Auto-approve path: OK (FB-2025-107)")

    # 2) Dispute path
    dispute_payload = get_seed_bill(seed, "FB-2025-104")
    dispute_payload["force_reprocess"] = True
    dispute_resp = client.post("/freight-bills", json=dispute_payload)
    assert dispute_resp.status_code == 200, dispute_resp.text
    dispute_body = dispute_resp.json()
    assert dispute_body["decision"]["decision"] == "dispute", dispute_body
    assert dispute_body["workflow"]["workflow_status"] == "completed", dispute_body
    print("Dispute path: OK (FB-2025-104)")

    # 3) Interrupt/resume review path
    review_payload = get_seed_bill(seed, "FB-2025-102")
    review_payload["force_reprocess"] = True
    review_start_resp = client.post("/freight-bills", json=review_payload)
    assert review_start_resp.status_code == 200, review_start_resp.text
    review_start_body = review_start_resp.json()
    assert review_start_body["decision"]["decision"] == "flag_for_review", review_start_body
    assert review_start_body["workflow"]["workflow_status"] == "waiting_for_review", review_start_body

    queue_resp = client.get("/review-queue")
    assert queue_resp.status_code == 200, queue_resp.text
    queue_body = queue_resp.json()
    queue_ids = [item["freight_bill_id"] for item in queue_body["items"]]
    assert "FB-2025-102" in queue_ids, queue_body

    review_resume_resp = client.post(
        "/review/FB-2025-102",
        json={"reviewer_decision": "approve", "notes": "Approved in workflow test"},
    )
    assert review_resume_resp.status_code == 200, review_resume_resp.text
    review_resume_body = review_resume_resp.json()
    assert review_resume_body["freight_bill"]["current_decision"] == "auto_approve", review_resume_body
    assert review_resume_body["workflow"]["workflow_status"] == "completed", review_resume_body

    queue_after_resp = client.get("/review-queue")
    assert queue_after_resp.status_code == 200, queue_after_resp.text
    queue_after_body = queue_after_resp.json()
    queue_after_ids = [item["freight_bill_id"] for item in queue_after_body["items"]]
    assert "FB-2025-102" not in queue_after_ids, queue_after_body

    # Idempotent repeat of same reviewer action should be accepted.
    review_resume_repeat_resp = client.post(
        "/review/FB-2025-102",
        json={"reviewer_decision": "approve", "notes": "Approved in workflow test"},
    )
    assert review_resume_repeat_resp.status_code == 200, review_resume_repeat_resp.text
    print("Interrupt/resume path: OK (FB-2025-102)")

    print("All LangGraph workflow tests passed.")


if __name__ == "__main__":
    main()
