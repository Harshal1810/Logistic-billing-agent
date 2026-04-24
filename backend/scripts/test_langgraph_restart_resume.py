import importlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_mod


def get_seed_bill(seed: dict, freight_bill_id: str) -> dict:
    return next(x for x in seed["freight_bills"] if x["id"] == freight_bill_id)


def main() -> None:
    seed = json.loads(Path("data/seed data logistics.json").read_text(encoding="utf-8"))
    review_payload = get_seed_bill(seed, "FB-2025-102")
    review_payload["force_reprocess"] = True

    client = TestClient(main_mod.app)

    start_resp = client.post("/freight-bills", json=review_payload)
    assert start_resp.status_code == 200, start_resp.text
    start_body = start_resp.json()
    assert start_body["workflow"]["workflow_status"] == "waiting_for_review", start_body
    assert start_body["pending_review_task"] is not None, start_body

    # Simulate process restart by reloading service and FastAPI module.
    import app.agent.service as service_mod

    importlib.reload(service_mod)
    reloaded_main = importlib.reload(main_mod)
    restarted_client = TestClient(reloaded_main.app)

    resume_resp = restarted_client.post(
        "/review/FB-2025-102",
        json={"reviewer_decision": "approve", "notes": "resume after restart"},
    )
    assert resume_resp.status_code == 200, resume_resp.text
    resume_body = resume_resp.json()
    assert resume_body["workflow"]["workflow_status"] == "completed", resume_body
    assert resume_body["freight_bill"]["final_resolution"] == "approved", resume_body
    assert resume_body["pending_review_task"] is None, resume_body
    assert resume_body["latest_review_task"]["status"] == "completed", resume_body

    print("Restart-resume integration path: OK (FB-2025-102)")


if __name__ == "__main__":
    main()
