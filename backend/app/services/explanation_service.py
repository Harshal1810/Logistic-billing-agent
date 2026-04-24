import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.llm_client import (
    LLMClientError,
    generate_grounded_text_groq,
    generate_grounded_text_openai,
)
from app.repositories.decisions import get_latest_decision
from app.repositories.freight_bills import get_candidate_matches, get_freight_bill_by_id
from app.repositories.review_tasks import get_latest_review_task_for_bill
from app.repositories.validations import get_validation_results


def build_decision_explanation_payload(db: Session, freight_bill_id: str) -> dict[str, Any]:
    bill = get_freight_bill_by_id(db, freight_bill_id)
    decision = get_latest_decision(db, freight_bill_id)
    validations = get_validation_results(db, freight_bill_id)
    contract_candidates = get_candidate_matches(db, freight_bill_id, "contract")
    shipment_candidates = get_candidate_matches(db, freight_bill_id, "shipment")

    if bill is None or decision is None:
        raise ValueError(f"Missing bill/decision for explanation payload: {freight_bill_id}")

    return {
        "freight_bill_id": freight_bill_id,
        "decision": decision.decision,
        "confidence_score": float(decision.confidence_score),
        "selected_contract_id": bill.selected_contract_id,
        "selected_shipment_id": bill.selected_shipment_id,
        "selected_bol_id": bill.selected_bol_id,
        "top_contract_candidates": _to_candidate_summary(contract_candidates),
        "top_shipment_candidates": _to_candidate_summary(shipment_candidates),
        "validation_results": _to_validation_summary(validations),
    }


def build_review_summary_payload(
    db: Session,
    freight_bill_id: str,
    review_task_id: int | None = None,
) -> dict[str, Any]:
    bill = get_freight_bill_by_id(db, freight_bill_id)
    decision = get_latest_decision(db, freight_bill_id)
    validations = get_validation_results(db, freight_bill_id)
    contract_candidates = get_candidate_matches(db, freight_bill_id, "contract")
    shipment_candidates = get_candidate_matches(db, freight_bill_id, "shipment")
    task = get_latest_review_task_for_bill(db, freight_bill_id)

    if bill is None:
        raise ValueError(f"Missing bill for review summary payload: {freight_bill_id}")
    if task is None:
        raise ValueError(f"Missing review task for review summary payload: {freight_bill_id}")
    if review_task_id is not None and task.id != review_task_id:
        raise ValueError(
            f"Review task mismatch for {freight_bill_id}: expected {review_task_id}, got {task.id}"
        )

    return {
        "freight_bill_id": freight_bill_id,
        "review_task_id": task.id,
        "decision": decision.decision if decision is not None else bill.current_decision,
        "confidence_score": (
            float(decision.confidence_score)
            if decision is not None
            else (float(bill.confidence_score) if bill.confidence_score is not None else None)
        ),
        "selected_contract_id": bill.selected_contract_id,
        "selected_shipment_id": bill.selected_shipment_id,
        "selected_bol_id": bill.selected_bol_id,
        "interrupt_payload": task.interrupt_payload,
        "top_contract_candidates": _to_candidate_summary(contract_candidates),
        "top_shipment_candidates": _to_candidate_summary(shipment_candidates),
        "validation_results": _to_validation_summary(validations),
    }


def generate_decision_explanation(payload: dict) -> str:
    fallback = build_fallback_decision_explanation(payload)
    prompt = _build_prompt(
        context="decision_explanation",
        payload=payload,
        requested_output=(
            "Write 2-4 sentences explaining the final decision to a reviewer. "
            "Start with the main reason, then cite strongest evidence from failed/warning rules or selected matches."
        ),
    )
    return _generate_with_fallback(prompt, fallback)


def generate_review_summary(payload: dict) -> str:
    fallback = build_fallback_review_summary(payload)
    prompt = _build_prompt(
        context="review_summary",
        payload=payload,
        requested_output=(
            "Write 2-4 sentences guiding a human reviewer on what to verify next. "
            "Start with the main unresolved risk and mention the most relevant evidence fields."
        ),
    )
    return _generate_with_fallback(prompt, fallback)


def build_fallback_decision_explanation(payload: dict) -> str:
    decision = payload.get("decision")
    selected_contract_id = payload.get("selected_contract_id")
    selected_shipment_id = payload.get("selected_shipment_id")
    failed = _top_rules(payload, target_result="fail", top_n=3)
    warnings = _top_rules(payload, target_result="warning", top_n=3)

    if decision == "auto_approve":
        return (
            "Auto-approved because selected matches were resolved and core validations passed without "
            "blocking issues."
        )
    if decision == "dispute":
        issues = ", ".join(failed) if failed else "critical validation failures"
        return f"Disputed because blocking validation failures were found. Main issues: {issues}."

    ambiguity: list[str] = []
    if not selected_contract_id:
        ambiguity.append("no selected contract")
    if not selected_shipment_id:
        ambiguity.append("no selected shipment")
    ambiguity_text = ", ".join(ambiguity) if ambiguity else "non-blocking ambiguity"
    issues = ", ".join(warnings or failed) if (warnings or failed) else "warnings and unresolved context"
    return (
        "Flagged for review because the bill could not be resolved with high confidence. "
        f"Main issues: {issues}. Current ambiguity: {ambiguity_text}."
    )


def build_fallback_review_summary(payload: dict) -> str:
    warnings = _top_rules(payload, target_result="warning", top_n=3)
    fails = _top_rules(payload, target_result="fail", top_n=2)
    issues = warnings + fails
    issue_text = ", ".join(issues) if issues else "unresolved ambiguity or risk"
    return (
        "Review required because the workflow found unresolved ambiguity or risk. "
        f"Please verify selected contract/shipment and the highlighted validation issues: {issue_text}."
    )


def _generate_with_fallback(prompt: str, fallback: str) -> str:
    result = None

    # Provider precedence: OpenAI first, then Groq if OpenAI key is unavailable.
    if settings.openai_api_key:
        try:
            result = generate_grounded_text_openai(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                prompt=prompt,
                timeout_seconds=settings.openai_timeout_seconds,
            )
        except (LLMClientError, Exception):
            result = None
    elif settings.groq_api_key:
        try:
            result = generate_grounded_text_groq(
                api_key=settings.groq_api_key,
                model=settings.groq_model,
                prompt=prompt,
                timeout_seconds=settings.groq_timeout_seconds,
            )
        except (LLMClientError, Exception):
            result = None
    else:
        return fallback

    result = (result or "").strip()
    if not result:
        return fallback
    return result


def _build_prompt(context: str, payload: dict[str, Any], requested_output: str) -> str:
    serialized_payload = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return (
        "You are a logistics billing assistant that writes grounded explanations.\n"
        f"Task: {context}\n"
        "Rules:\n"
        "1) Use only facts in the JSON payload.\n"
        "2) Do not invent missing fields or infer hidden data.\n"
        "3) Do not change decisions, scores, selected IDs, or rule outcomes.\n"
        "4) Keep the explanation concise and operationally useful.\n"
        "5) Plain English; avoid markdown formatting.\n"
        f"Output: {requested_output}\n"
        f"Payload JSON: {serialized_payload}"
    )


def _to_candidate_summary(rows: list[Any]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows[:3]:
        reasons = []
        if isinstance(row.match_reasons, dict):
            maybe_reasons = row.match_reasons.get("reasons")
            if isinstance(maybe_reasons, list):
                reasons = [str(x) for x in maybe_reasons][:3]
        summary.append(
            {
                "candidate_id": row.candidate_id,
                "score": float(row.score),
                "selected": bool(row.selected),
                "reasons": reasons,
            }
        )
    return summary


def _to_validation_summary(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "rule_name": row.rule_name,
            "rule_result": row.rule_result,
            "severity": row.severity,
            "details": row.details,
        }
        for row in rows
    ]


def _top_rules(payload: dict[str, Any], target_result: str, top_n: int) -> list[str]:
    results = payload.get("validation_results", [])
    if not isinstance(results, list):
        return []
    names = [
        x.get("rule_name")
        for x in results
        if isinstance(x, dict) and x.get("rule_result") == target_result and x.get("rule_name")
    ]
    return [str(x) for x in names[:top_n]]
