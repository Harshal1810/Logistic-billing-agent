import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.postgres import SessionLocal
from app.main import app
from app.repositories.decisions import get_latest_decision
from app.repositories.review_tasks import get_pending_review_task_for_bill
import app.services.explanation_service as exp


def get_seed_bill(seed: dict, freight_bill_id: str) -> dict:
    row = next(x for x in seed["freight_bills"] if x["id"] == freight_bill_id)
    payload = dict(row)
    payload["force_reprocess"] = True
    return payload


def assert_non_empty_text(value: str | None) -> None:
    assert isinstance(value, str), value
    assert value.strip(), value


def main() -> None:
    client = TestClient(app)
    seed = json.loads(Path("data/seed data logistics.json").read_text(encoding="utf-8"))

    # Approve, dispute, and review paths should all include decision explanations.
    review_task_id: int | None = None
    for bill_id, expected_decision in (
        ("FB-2025-107", "auto_approve"),
        ("FB-2025-104", "dispute"),
        ("FB-2025-110", "flag_for_review"),
    ):
        resp = client.post("/freight-bills", json=get_seed_bill(seed, bill_id))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["decision"]["decision"] == expected_decision, body
        assert_non_empty_text(body["decision"]["decision_explanation"])
        if bill_id == "FB-2025-110":
            assert body["pending_review_task"] is not None, body
            assert_non_empty_text(body["pending_review_task"]["review_summary"])
            review_task_id = body["pending_review_task"]["review_task_id"]

    # Review queue should include persisted review summary.
    queue_resp = client.get("/review-queue")
    assert queue_resp.status_code == 200, queue_resp.text
    queue_body = queue_resp.json()
    assert review_task_id is not None
    review_item = next(x for x in queue_body["items"] if x["review_task_id"] == review_task_id)
    assert_non_empty_text(review_item["review_summary"])

    # DB persistence for explanation fields.
    db = SessionLocal()
    try:
        latest_approve = get_latest_decision(db, "FB-2025-107")
        assert latest_approve is not None
        assert_non_empty_text(latest_approve.decision_explanation)

        pending_review = get_pending_review_task_for_bill(db, "FB-2025-110")
        assert pending_review is not None
        assert_non_empty_text(pending_review.review_summary)
    finally:
        db.close()

    # Fallback behavior when API key is not configured.
    db = SessionLocal()
    original_openai_key = settings.openai_api_key
    original_groq_key = settings.groq_api_key
    original_openai_generator = exp.generate_grounded_text_openai
    try:
        payload = exp.build_decision_explanation_payload(db, "FB-2025-104")
        settings.openai_api_key = None
        settings.groq_api_key = None
        fallback_text = exp.generate_decision_explanation(payload)
        expected = exp.build_fallback_decision_explanation(payload)
        assert fallback_text == expected
    finally:
        settings.openai_api_key = original_openai_key
        settings.groq_api_key = original_groq_key
        exp.generate_grounded_text_openai = original_openai_generator
        db.close()

    # Fallback behavior when LLM call fails.
    db = SessionLocal()
    original_openai_key = settings.openai_api_key
    original_openai_generator = exp.generate_grounded_text_openai
    original_groq_key = settings.groq_api_key
    original_groq_generator = exp.generate_grounded_text_groq
    try:
        payload = exp.build_review_summary_payload(db, "FB-2025-110")
        settings.openai_api_key = "test-key"

        def _raise(*_args, **_kwargs):
            raise RuntimeError("simulated llm failure")

        exp.generate_grounded_text_openai = _raise
        fallback_text = exp.generate_review_summary(payload)
        expected = exp.build_fallback_review_summary(payload)
        assert fallback_text == expected
    finally:
        settings.openai_api_key = original_openai_key
        exp.generate_grounded_text_openai = original_openai_generator
        settings.groq_api_key = original_groq_key
        exp.generate_grounded_text_groq = original_groq_generator
        db.close()

    # Groq provider should be selected when OpenAI key is missing.
    db = SessionLocal()
    original_openai_key = settings.openai_api_key
    original_groq_key = settings.groq_api_key
    original_groq_generator = exp.generate_grounded_text_groq
    try:
        payload = exp.build_decision_explanation_payload(db, "FB-2025-107")
        settings.openai_api_key = None
        settings.groq_api_key = "groq-test-key"

        def _groq_ok(*_args, **_kwargs):
            return "Groq explanation path works."

        exp.generate_grounded_text_groq = _groq_ok
        text = exp.generate_decision_explanation(payload)
        assert text == "Groq explanation path works."
    finally:
        settings.openai_api_key = original_openai_key
        settings.groq_api_key = original_groq_key
        exp.generate_grounded_text_groq = original_groq_generator
        db.close()

    print("Explanation tests passed: generation, persistence, and fallback behavior.")


if __name__ == "__main__":
    main()
