from app.agent.resume import apply_reviewer_decision
from app.agent.state import FreightBillAgentState
from app.agent.logging_utils import log_event
from app.db.postgres import SessionLocal
from app.graph.matcher import score_and_persist_contract_candidates
from app.graph.shipment_matcher import score_and_persist_shipment_candidates
from app.repositories.freight_bills import get_freight_bill_by_id
from app.repositories.review_tasks import create_review_task, update_review_summary
from app.services.decision_service import decide_freight_bill
from app.services.explanation_service import (
    build_review_summary_payload,
    generate_review_summary,
)
from app.services.validation_service import run_core_validations


def load_bill_node(state: FreightBillAgentState) -> FreightBillAgentState:
    db = SessionLocal()
    try:
        bill = get_freight_bill_by_id(db, state["freight_bill_id"])
        if bill is None:
            raise ValueError(f"Freight bill not found: {state['freight_bill_id']}")

        if bill.processing_status in {"ingested", "waiting_for_review"}:
            bill.processing_status = "processing"
            db.add(bill)
            db.commit()
        log_event(
            "workflow.load_bill",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            processing_status=bill.processing_status,
        )

        return {"current_node": "load_bill", "workflow_status": "running"}
    finally:
        db.close()


def match_contract_node(state: FreightBillAgentState) -> FreightBillAgentState:
    db = SessionLocal()
    try:
        ranked = score_and_persist_contract_candidates(db, state["freight_bill_id"])
        selected = next((x["candidate_id"] for x in ranked if x.get("selected")), None)
        log_event(
            "workflow.contract_matched",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            selected_contract_id=selected,
            candidate_count=len(ranked),
        )
        return {"current_node": "match_contract"}
    finally:
        db.close()


def match_shipment_node(state: FreightBillAgentState) -> FreightBillAgentState:
    db = SessionLocal()
    try:
        ranked = score_and_persist_shipment_candidates(db, state["freight_bill_id"])
        selected = next((x["candidate_id"] for x in ranked if x.get("selected")), None)
        log_event(
            "workflow.shipment_matched",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            selected_shipment_id=selected,
            candidate_count=len(ranked),
        )
        return {"current_node": "match_shipment"}
    finally:
        db.close()


def run_validations_node(state: FreightBillAgentState) -> FreightBillAgentState:
    db = SessionLocal()
    try:
        results = run_core_validations(db, state["freight_bill_id"])
        fails = sum(1 for r in results if r["rule_result"] == "fail")
        warns = sum(1 for r in results if r["rule_result"] == "warning")
        log_event(
            "workflow.validations_completed",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            fail_count=fails,
            warning_count=warns,
            total=len(results),
        )
        return {"current_node": "run_validations"}
    finally:
        db.close()


def compute_decision_node(state: FreightBillAgentState) -> FreightBillAgentState:
    db = SessionLocal()
    try:
        result = decide_freight_bill(db, state["freight_bill_id"])
        log_event(
            "workflow.decision_computed",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            decision=result["decision"],
            confidence_score=result["confidence_score"],
        )
        return {
            "current_node": "compute_decision",
            "decision": result["decision"],
            "confidence_score": result["confidence_score"],
            "requires_review": result["decision"] == "flag_for_review",
        }
    finally:
        db.close()


def review_gate_node(state: FreightBillAgentState) -> FreightBillAgentState:
    if not state.get("requires_review", False):
        return {"current_node": "review_gate", "workflow_status": "running"}

    # Resume path: reviewer input supplied in state_payload -> continue workflow.
    if state.get("reviewer_decision"):
        log_event(
            "workflow.review_resumed",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            reviewer_decision=state.get("reviewer_decision"),
        )
        return {"current_node": "review_gate", "workflow_status": "running"}

    db = SessionLocal()
    try:
        payload = {
            "type": "human_review_required",
            "freight_bill_id": state["freight_bill_id"],
            "run_id": state["run_id"],
            "decision": state.get("decision"),
            "confidence_score": state.get("confidence_score"),
        }
        task = create_review_task(
            db=db,
            run_id=state["run_id"],
            freight_bill_id=state["freight_bill_id"],
            interrupt_payload=payload,
        )
        db.flush()
        review_payload = build_review_summary_payload(
            db=db,
            freight_bill_id=state["freight_bill_id"],
            review_task_id=task.id,
        )
        review_summary = generate_review_summary(review_payload)
        update_review_summary(db=db, task=task, review_summary=review_summary)
        db.commit()
        log_event(
            "workflow.review_interrupt",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            decision=state.get("decision"),
            confidence_score=state.get("confidence_score"),
        )
    finally:
        db.close()

    return {
        "current_node": "review_gate",
        "workflow_status": "waiting_for_review",
    }


def apply_reviewer_input_node(state: FreightBillAgentState) -> FreightBillAgentState:
    reviewer_decision = state.get("reviewer_decision")
    if not reviewer_decision:
        return {"current_node": "apply_reviewer_input"}

    db = SessionLocal()
    try:
        apply_reviewer_decision(
            db=db,
            freight_bill_id=state["freight_bill_id"],
            reviewer_decision=reviewer_decision,
            reviewer_notes=state.get("reviewer_notes"),
        )
        db.commit()
        log_event(
            "workflow.review_submitted",
            run_id=state.get("run_id"),
            freight_bill_id=state.get("freight_bill_id"),
            reviewer_decision=reviewer_decision,
        )
        return {"current_node": "apply_reviewer_input"}
    finally:
        db.close()


def finalize_node(state: FreightBillAgentState) -> FreightBillAgentState:
    log_event(
        "workflow.finalized",
        run_id=state.get("run_id"),
        freight_bill_id=state.get("freight_bill_id"),
        workflow_status="completed",
    )
    return {"current_node": "finalize", "workflow_status": "completed"}
