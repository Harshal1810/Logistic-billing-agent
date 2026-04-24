from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agent.service import get_workflow_run_for_bill, resume_workflow, start_workflow
from app.db.postgres import SessionLocal
from app.models.freight_bill import FreightBill
from app.repositories.decisions import get_latest_decision
from app.repositories.freight_bills import get_candidate_matches, get_freight_bill_by_id
from app.repositories.review_tasks import (
    get_latest_review_task_for_bill,
    get_pending_review_task_for_bill,
    list_pending_review_tasks,
)
from app.repositories.validations import get_validation_results

app = FastAPI()


class ReviewDecisionEnum(str, Enum):
    approve = "approve"
    dispute = "dispute"
    modify = "modify"


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class FreightBillIngestRequest(BaseModel):
    id: str
    carrier_id: str | None = None
    carrier_name: str
    bill_number: str
    bill_date: date
    shipment_reference: str | None = None
    lane: str
    billed_weight_kg: Decimal
    rate_per_kg: Decimal | None = None
    billing_unit: str | None = None
    base_charge: Decimal
    fuel_surcharge: Decimal
    gst_amount: Decimal
    total_amount: Decimal
    force_reprocess: bool = False


class ReviewSubmissionRequest(BaseModel):
    reviewer_decision: ReviewDecisionEnum
    notes: str | None = None


class FreightBillCoreResponse(BaseModel):
    id: str
    carrier_id: str | None
    carrier_name_raw: str
    bill_number: str
    bill_date: str
    shipment_reference: str | None
    lane: str
    billed_weight_kg: float
    rate_per_kg: float | None
    billing_unit: str | None
    base_charge: float
    fuel_surcharge: float
    gst_amount: float
    total_amount: float
    processing_status: str
    current_decision: str | None
    final_resolution: str | None
    confidence_score: float | None
    created_at: str
    updated_at: str


class SelectedMatchesResponse(BaseModel):
    contract_id: str | None
    shipment_id: str | None
    bol_id: str | None


class CandidateMatchResponse(BaseModel):
    candidate_id: str
    score: float
    selected: bool
    reasons: list[str]
    created_at: str


class CandidateMatchesResponse(BaseModel):
    contract: list[CandidateMatchResponse]
    shipment: list[CandidateMatchResponse]
    bol: list[CandidateMatchResponse]


class ValidationResultResponse(BaseModel):
    rule_name: str
    rule_result: str
    severity: str
    expected_value: str | None
    actual_value: str | None
    details: str
    created_at: str


class DecisionResponse(BaseModel):
    decision: str
    confidence_score: float
    decision_reason: str
    decision_explanation: str | None
    decision_source: str
    created_at: str


class WorkflowResponse(BaseModel):
    run_id: str
    workflow_status: str
    current_node: str | None
    last_error: str | None
    updated_at: str


class PendingReviewTaskResponse(BaseModel):
    review_task_id: int
    run_id: str
    status: str
    created_at: str
    review_summary: str | None
    interrupt_payload: dict[str, Any]


class LatestReviewTaskResponse(BaseModel):
    review_task_id: int
    run_id: str
    status: str
    review_summary: str | None
    reviewer_decision: str | None
    reviewer_notes: str | None
    created_at: str
    resolved_at: str | None


class AuditEventResponse(BaseModel):
    event: str
    at: str
    details: str


class AuditTrailSummaryResponse(BaseModel):
    total_events: int
    last_event: str | None
    last_event_at: str | None


class FreightBillDetailResponse(BaseModel):
    freight_bill: FreightBillCoreResponse
    selected_matches: SelectedMatchesResponse
    candidate_matches: CandidateMatchesResponse
    validation_results: list[ValidationResultResponse]
    decision: DecisionResponse | None
    workflow: WorkflowResponse | None
    pending_review_task: PendingReviewTaskResponse | None
    latest_review_task: LatestReviewTaskResponse | None
    audit_events: list[AuditEventResponse]
    audit_trail_summary: AuditTrailSummaryResponse


class ReviewQueueCandidateResponse(BaseModel):
    candidate_id: str
    score: float
    selected: bool
    reasons: list[str]


class ReviewQueueValidationResponse(BaseModel):
    rule_name: str
    rule_result: str
    severity: str
    details: str


class ReviewQueueItemResponse(BaseModel):
    review_task_id: int
    run_id: str
    freight_bill_id: str
    created_at: str
    interrupt_payload: dict[str, Any]
    suggested_agent_decision: str | None
    review_summary: str | None
    selected_contract_id: str | None
    selected_shipment_id: str | None
    selected_bol_id: str | None
    top_candidate_contracts: list[ReviewQueueCandidateResponse]
    top_candidate_shipments: list[ReviewQueueCandidateResponse]
    validation_issues: list[ReviewQueueValidationResponse]
    reviewer_notes: str | None
    allowed_reviewer_decisions: list[str]
    optional_overrides: dict[str, Any]


class ReviewQueueResponse(BaseModel):
    count: int
    items: list[ReviewQueueItemResponse]


class ResumeMetaResponse(BaseModel):
    reviewer_decision: ReviewDecisionEnum
    workflow_status: str
    run_id: str


class ReviewSubmitResponse(FreightBillDetailResponse):
    resume: ResumeMetaResponse


def _as_float(value: Any) -> float | Any | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _raise_api_error(status_code: int, code: str, message: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": str(exc.detail)}},
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
            },
            "details": exc.errors(),
        },
    )


def _build_audit_events(
    bill: FreightBill,
    contract_candidates: list[Any],
    shipment_candidates: list[Any],
    validations: list[Any],
    latest_decision: Any,
    workflow_run: Any,
    pending_task: Any,
    latest_task: Any,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    events: list[dict[str, str]] = []

    def add_event(event: str, at: Any, details: str) -> None:
        iso_at = _iso(at)
        if iso_at is None:
            return
        events.append({"event": event, "at": iso_at, "details": details})

    add_event("ingested", bill.created_at, "Freight bill ingested")
    if contract_candidates:
        add_event(
            "contract matched",
            min(x.created_at for x in contract_candidates),
            f"{len(contract_candidates)} contract candidate(s) persisted",
        )
    if shipment_candidates:
        add_event(
            "shipment matched",
            min(x.created_at for x in shipment_candidates),
            f"{len(shipment_candidates)} shipment candidate(s) persisted",
        )
    if validations:
        fails = sum(1 for v in validations if v.rule_result == "fail")
        warns = sum(1 for v in validations if v.rule_result == "warning")
        add_event(
            "validations completed",
            max(v.created_at for v in validations),
            f"Validation summary: {fails} fail(s), {warns} warning(s)",
        )
    if latest_decision is not None and latest_decision.decision_source == "agent":
        add_event(
            "decision computed",
            latest_decision.created_at,
            f"Agent decision={latest_decision.decision}, confidence={_as_float(latest_decision.confidence_score)}",
        )
    if pending_task is not None:
        add_event(
            "sent for review",
            pending_task.created_at,
            "Workflow paused for manual review",
        )
    if latest_task is not None and latest_task.status == "completed":
        add_event(
            "review submitted",
            latest_task.resolved_at or latest_task.created_at,
            f"Reviewer decision={latest_task.reviewer_decision}",
        )
        if workflow_run is not None and workflow_run.workflow_status == "completed":
            add_event("resumed", workflow_run.updated_at, "Workflow resumed and completed")
    if bill.finalized_at is not None:
        add_event("finalized", bill.finalized_at, f"Final resolution={bill.final_resolution}")

    events.sort(key=lambda x: x["at"])
    summary = {
        "total_events": len(events),
        "last_event": events[-1]["event"] if events else None,
        "last_event_at": events[-1]["at"] if events else None,
    }
    return events, summary


def _build_freight_bill_response(db: Any, freight_bill_id: str) -> dict[str, Any]:
    bill = get_freight_bill_by_id(db, freight_bill_id)
    if bill is None:
        _raise_api_error(404, "freight_bill_not_found", f"Freight bill not found: {freight_bill_id}")

    contract_candidates = get_candidate_matches(db, freight_bill_id, "contract")
    shipment_candidates = get_candidate_matches(db, freight_bill_id, "shipment")
    bol_candidates = get_candidate_matches(db, freight_bill_id, "bol")

    validations = get_validation_results(db, freight_bill_id)
    latest_decision = get_latest_decision(db, freight_bill_id)
    latest_run = get_workflow_run_for_bill(freight_bill_id)
    pending_task = get_pending_review_task_for_bill(db, freight_bill_id)
    latest_task = get_latest_review_task_for_bill(db, freight_bill_id)

    audit_events, audit_summary = _build_audit_events(
        bill=bill,
        contract_candidates=contract_candidates,
        shipment_candidates=shipment_candidates,
        validations=validations,
        latest_decision=latest_decision,
        workflow_run=latest_run,
        pending_task=pending_task,
        latest_task=latest_task,
    )

    return {
        "freight_bill": {
            "id": bill.id,
            "carrier_id": bill.carrier_id,
            "carrier_name_raw": bill.carrier_name_raw,
            "bill_number": bill.bill_number,
            "bill_date": _iso(bill.bill_date),
            "shipment_reference": bill.shipment_reference,
            "lane": bill.lane,
            "billed_weight_kg": _as_float(bill.billed_weight_kg),
            "rate_per_kg": _as_float(bill.rate_per_kg),
            "billing_unit": bill.billing_unit,
            "base_charge": _as_float(bill.base_charge),
            "fuel_surcharge": _as_float(bill.fuel_surcharge),
            "gst_amount": _as_float(bill.gst_amount),
            "total_amount": _as_float(bill.total_amount),
            "processing_status": bill.processing_status,
            "current_decision": bill.current_decision,
            "final_resolution": bill.final_resolution,
            "confidence_score": _as_float(bill.confidence_score),
            "created_at": _iso(bill.created_at),
            "updated_at": _iso(bill.updated_at),
        },
        "selected_matches": {
            "contract_id": bill.selected_contract_id,
            "shipment_id": bill.selected_shipment_id,
            "bol_id": bill.selected_bol_id,
        },
        "candidate_matches": {
            "contract": [
                {
                    "candidate_id": row.candidate_id,
                    "score": _as_float(row.score),
                    "selected": row.selected,
                    "reasons": row.match_reasons.get("reasons", []),
                    "created_at": _iso(row.created_at),
                }
                for row in contract_candidates
            ],
            "shipment": [
                {
                    "candidate_id": row.candidate_id,
                    "score": _as_float(row.score),
                    "selected": row.selected,
                    "reasons": row.match_reasons.get("reasons", []),
                    "created_at": _iso(row.created_at),
                }
                for row in shipment_candidates
            ],
            "bol": [
                {
                    "candidate_id": row.candidate_id,
                    "score": _as_float(row.score),
                    "selected": row.selected,
                    "reasons": row.match_reasons.get("reasons", []),
                    "created_at": _iso(row.created_at),
                }
                for row in bol_candidates
            ],
        },
        "validation_results": [
            {
                "rule_name": row.rule_name,
                "rule_result": row.rule_result,
                "severity": row.severity,
                "expected_value": row.expected_value,
                "actual_value": row.actual_value,
                "details": row.details,
                "created_at": _iso(row.created_at),
            }
            for row in validations
        ],
        "decision": (
            {
                "decision": latest_decision.decision,
                "confidence_score": _as_float(latest_decision.confidence_score),
                "decision_reason": latest_decision.decision_reason,
                "decision_explanation": latest_decision.decision_explanation,
                "decision_source": latest_decision.decision_source,
                "created_at": _iso(latest_decision.created_at),
            }
            if latest_decision is not None
            else None
        ),
        "workflow": (
            {
                "run_id": latest_run.run_id,
                "workflow_status": latest_run.workflow_status,
                "current_node": latest_run.current_node,
                "last_error": latest_run.last_error,
                "updated_at": _iso(latest_run.updated_at),
            }
            if latest_run is not None
            else None
        ),
        "pending_review_task": (
            {
                "review_task_id": pending_task.id,
                "run_id": pending_task.run_id,
                "status": pending_task.status,
                "created_at": _iso(pending_task.created_at),
                "review_summary": pending_task.review_summary,
                "interrupt_payload": pending_task.interrupt_payload,
            }
            if pending_task is not None
            else None
        ),
        "latest_review_task": (
            {
                "review_task_id": latest_task.id,
                "run_id": latest_task.run_id,
                "status": latest_task.status,
                "review_summary": latest_task.review_summary,
                "reviewer_decision": latest_task.reviewer_decision,
                "reviewer_notes": latest_task.reviewer_notes,
                "created_at": _iso(latest_task.created_at),
                "resolved_at": _iso(latest_task.resolved_at),
            }
            if latest_task is not None
            else None
        ),
        "audit_events": audit_events,
        "audit_trail_summary": audit_summary,
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    finally:
        db.close()


@app.get(
    "/freight-bills/{freight_bill_id}",
    response_model=FreightBillDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_freight_bill(freight_bill_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return _build_freight_bill_response(db, freight_bill_id)
    finally:
        db.close()


@app.post(
    "/freight-bills",
    response_model=FreightBillDetailResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def ingest_freight_bill(payload: FreightBillIngestRequest) -> dict[str, Any]:
    db = SessionLocal()
    try:
        raw_payload = payload.model_dump(mode="json")
        existing = get_freight_bill_by_id(db, payload.id)

        if (
            existing is not None
            and existing.raw_payload == raw_payload
            and not payload.force_reprocess
        ):
            return _build_freight_bill_response(db, payload.id)

        db.merge(
            FreightBill(
                id=payload.id,
                carrier_id=payload.carrier_id,
                carrier_name_raw=payload.carrier_name,
                bill_number=payload.bill_number,
                bill_date=payload.bill_date,
                shipment_reference=payload.shipment_reference,
                lane=payload.lane,
                billed_weight_kg=payload.billed_weight_kg,
                rate_per_kg=payload.rate_per_kg,
                billing_unit=payload.billing_unit,
                base_charge=payload.base_charge,
                fuel_surcharge=payload.fuel_surcharge,
                gst_amount=payload.gst_amount,
                total_amount=payload.total_amount,
                raw_payload=raw_payload,
                processing_status="ingested",
                current_decision=None,
                confidence_score=None,
                selected_contract_id=None,
                selected_shipment_id=None,
                selected_bol_id=None,
                final_resolution=None,
                finalized_at=None,
            )
        )
        db.commit()
    finally:
        db.close()

    start_workflow(
        freight_bill_id=payload.id,
        force_reprocess=payload.force_reprocess,
    )

    response_db = SessionLocal()
    try:
        return _build_freight_bill_response(response_db, payload.id)
    finally:
        response_db.close()


@app.get(
    "/review-queue",
    response_model=ReviewQueueResponse,
)
def get_review_queue() -> dict[str, Any]:
    db = SessionLocal()
    try:
        tasks = list_pending_review_tasks(db)
        items: list[dict[str, Any]] = []

        for task in tasks:
            bill = get_freight_bill_by_id(db, task.freight_bill_id)
            contract_candidates = get_candidate_matches(db, task.freight_bill_id, "contract")
            shipment_candidates = get_candidate_matches(db, task.freight_bill_id, "shipment")
            validations = get_validation_results(db, task.freight_bill_id)
            latest_decision = get_latest_decision(db, task.freight_bill_id)

            items.append(
                {
                    "review_task_id": task.id,
                    "run_id": task.run_id,
                    "freight_bill_id": task.freight_bill_id,
                    "created_at": _iso(task.created_at),
                    "interrupt_payload": task.interrupt_payload,
                    "suggested_agent_decision": latest_decision.decision if latest_decision else None,
                    "review_summary": task.review_summary,
                    "selected_contract_id": bill.selected_contract_id if bill else None,
                    "selected_shipment_id": bill.selected_shipment_id if bill else None,
                    "selected_bol_id": bill.selected_bol_id if bill else None,
                    "top_candidate_contracts": [
                        {
                            "candidate_id": row.candidate_id,
                            "score": _as_float(row.score),
                            "selected": row.selected,
                            "reasons": row.match_reasons.get("reasons", []),
                        }
                        for row in contract_candidates[:3]
                    ],
                    "top_candidate_shipments": [
                        {
                            "candidate_id": row.candidate_id,
                            "score": _as_float(row.score),
                            "selected": row.selected,
                            "reasons": row.match_reasons.get("reasons", []),
                        }
                        for row in shipment_candidates[:3]
                    ],
                    "validation_issues": [
                        {
                            "rule_name": row.rule_name,
                            "rule_result": row.rule_result,
                            "severity": row.severity,
                            "details": row.details,
                        }
                        for row in validations
                        if row.rule_result in {"fail", "warning"}
                    ],
                    "reviewer_notes": None,
                    "allowed_reviewer_decisions": [x.value for x in ReviewDecisionEnum],
                    "optional_overrides": {
                        "selected_contract_id": None,
                        "selected_shipment_id": None,
                        "selected_bol_id": None,
                    },
                }
            )

        return {"count": len(items), "items": items}
    finally:
        db.close()


@app.post(
    "/review/{freight_bill_id}",
    response_model=ReviewSubmitResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def submit_review(
    freight_bill_id: str,
    payload: ReviewSubmissionRequest,
) -> dict[str, Any]:
    try:
        workflow_state = resume_workflow(
            freight_bill_id=freight_bill_id,
            reviewer_decision=payload.reviewer_decision.value,
            reviewer_notes=payload.notes,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not waiting for review" in msg or "already" in msg:
            _raise_api_error(409, "invalid_review_transition", msg)
        _raise_api_error(404, "review_task_not_found", msg)

    db = SessionLocal()
    try:
        response = _build_freight_bill_response(db, freight_bill_id)
        response["resume"] = {
            "reviewer_decision": payload.reviewer_decision.value,
            "workflow_status": workflow_state["workflow_status"],
            "run_id": workflow_state["run_id"],
        }
        return response
    finally:
        db.close()
