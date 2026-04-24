import json
from pathlib import Path
from typing import Any

import httpx
import streamlit as st


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30.0
SEED_PATH = Path("data/seed data logistics.json")


def _api_get(base_url: str, endpoint: str, timeout: float) -> tuple[bool, dict | list | str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url.rstrip('/')}{endpoint}")
    except Exception as exc:
        return False, f"GET {endpoint} failed: {exc}"

    return _decode_response(response)


def _api_post(
    base_url: str,
    endpoint: str,
    payload: dict[str, Any],
    timeout: float,
) -> tuple[bool, dict | list | str]:
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{base_url.rstrip('/')}{endpoint}", json=payload)
    except Exception as exc:
        return False, f"POST {endpoint} failed: {exc}"

    return _decode_response(response)


def _decode_response(response: httpx.Response) -> tuple[bool, dict | list | str]:
    ok = 200 <= response.status_code < 300
    try:
        payload = response.json()
    except Exception:
        payload = response.text

    if not ok:
        return False, {"status_code": response.status_code, "payload": payload}
    return True, payload


def _load_seed_freight_bills() -> list[dict]:
    if not SEED_PATH.exists():
        return []
    try:
        data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("freight_bills", [])
    if not isinstance(rows, list):
        return []
    return rows


def _status_color(value: str | None) -> str:
    if value == "auto_approve":
        return "green"
    if value == "flag_for_review":
        return "orange"
    if value == "dispute":
        return "red"
    return "gray"


def _count_rules(results: list[dict]) -> tuple[int, int, int]:
    passes = sum(1 for row in results if row.get("rule_result") == "pass")
    warnings = sum(1 for row in results if row.get("rule_result") == "warning")
    fails = sum(1 for row in results if row.get("rule_result") == "fail")
    return passes, warnings, fails


def _render_overview(detail: dict) -> None:
    freight_bill = detail.get("freight_bill") or {}
    decision = detail.get("decision") or {}
    workflow = detail.get("workflow") or {}
    selected = detail.get("selected_matches") or {}
    validations = detail.get("validation_results") or []
    pending_review = detail.get("pending_review_task")

    decision_value = decision.get("decision")
    color = _status_color(decision_value)
    passes, warnings, fails = _count_rules(validations)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bill ID", freight_bill.get("id", "-"))
    c2.metric("Processing", freight_bill.get("processing_status", "-"))
    c3.metric("Decision", decision_value or "-", delta_color="off")
    c4.metric("Confidence", decision.get("confidence_score", "-"))
    st.markdown(f"**Decision status color:** :{color}[{decision_value or 'none'}]")

    c5, c6, c7 = st.columns(3)
    c5.metric("Rule Pass", passes)
    c6.metric("Rule Warning", warnings)
    c7.metric("Rule Fail", fails)

    st.subheader("Selected Matches")
    st.json(selected, expanded=False)

    st.subheader("Workflow")
    st.json(workflow, expanded=False)

    if pending_review:
        st.warning("Pending review task is active.")
        st.write(pending_review.get("review_summary"))


def _render_candidates(detail: dict) -> None:
    matches = detail.get("candidate_matches") or {}
    for candidate_type in ("contract", "shipment", "bol"):
        st.markdown(f"### {candidate_type.capitalize()} candidates")
        rows = matches.get(candidate_type) or []
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.info("No candidates available.")


def _render_validations(detail: dict) -> None:
    rows = detail.get("validation_results") or []
    if not rows:
        st.info("No validations found.")
        return

    severity_filter = st.multiselect(
        "Filter severity",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
        key="severity_filter",
    )
    result_filter = st.multiselect(
        "Filter result",
        options=["pass", "warning", "fail"],
        default=["pass", "warning", "fail"],
        key="result_filter",
    )

    filtered = [
        row
        for row in rows
        if row.get("severity") in severity_filter and row.get("rule_result") in result_filter
    ]
    st.dataframe(filtered, use_container_width=True)


def _render_decision(detail: dict) -> None:
    decision = detail.get("decision")
    if not decision:
        st.info("No decision persisted yet.")
        return
    st.json(decision, expanded=True)


def _render_audit(detail: dict) -> None:
    summary = detail.get("audit_trail_summary") or {}
    events = detail.get("audit_events") or []
    st.write(summary)
    if events:
        st.dataframe(events, use_container_width=True)
    else:
        st.info("No audit events found.")


def _build_graphviz(detail: dict) -> str:
    freight_bill = detail.get("freight_bill") or {}
    selected = detail.get("selected_matches") or {}
    candidates = detail.get("candidate_matches") or {}

    bill_id = freight_bill.get("id", "UnknownBill")
    carrier_id = freight_bill.get("carrier_id")
    contract_id = selected.get("contract_id")
    shipment_id = selected.get("shipment_id")
    bol_id = selected.get("bol_id")

    lines = [
        "digraph FreightBillContext {",
        '  rankdir=LR;',
        '  node [shape=box, style=filled, fillcolor="#F8F9FB", color="#5B6B7A"];',
        f'  fb [label="FreightBill\\n{bill_id}", fillcolor="#D7EEFF"];',
    ]

    if carrier_id:
        lines.append(f'  carrier [label="Carrier\\n{carrier_id}", fillcolor="#E7F6E7"];')
        lines.append("  fb -> carrier [label=\"BILLED_BY\"];")

    if contract_id:
        lines.append(f'  contract_selected [label="Selected Contract\\n{contract_id}", fillcolor="#CCF5D9"];')
        lines.append("  fb -> contract_selected [label=\"selected_contract\"];")

    if shipment_id:
        lines.append(
            f'  shipment_selected [label="Selected Shipment\\n{shipment_id}", fillcolor="#CCF5D9"];'
        )
        lines.append("  fb -> shipment_selected [label=\"selected_shipment\"];")

    if bol_id:
        lines.append(f'  bol_selected [label="Selected BOL\\n{bol_id}", fillcolor="#CCF5D9"];')
        lines.append("  fb -> bol_selected [label=\"selected_bol\"];")

    top_contracts = (candidates.get("contract") or [])[:3]
    for idx, row in enumerate(top_contracts, start=1):
        cid = row.get("candidate_id")
        score = row.get("score")
        if not cid:
            continue
        lines.append(
            f'  contract_{idx} [label="Contract Candidate\\n{cid}\\nscore={score}", fillcolor="#FFF7CC"];'
        )
        lines.append(f'  fb -> contract_{idx} [style=dashed, label="candidate"];')

    top_shipments = (candidates.get("shipment") or [])[:3]
    for idx, row in enumerate(top_shipments, start=1):
        sid = row.get("candidate_id")
        score = row.get("score")
        if not sid:
            continue
        lines.append(
            f'  shipment_{idx} [label="Shipment Candidate\\n{sid}\\nscore={score}", fillcolor="#FFF7CC"];'
        )
        lines.append(f'  fb -> shipment_{idx} [style=dashed, label="candidate"];')

    lines.append("}")
    return "\n".join(lines)


def _render_bill_explorer(base_url: str, timeout: float) -> None:
    st.header("Bill Explorer")
    default_bill_id = st.session_state.get("selected_bill_id", "")
    bill_id = st.text_input("Freight bill ID", value=default_bill_id, key="bill_id_input")
    fetch = st.button("Fetch bill state", type="primary")

    if fetch and bill_id:
        ok, payload = _api_get(base_url, f"/freight-bills/{bill_id}", timeout)
        if not ok:
            st.error(payload)
            return
        st.session_state["selected_bill_id"] = bill_id
        st.session_state["selected_bill_detail"] = payload

    detail = st.session_state.get("selected_bill_detail")
    if not detail:
        st.info("Fetch a bill to see current state.")
        return

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Overview", "Candidates", "Validations", "Decision", "Audit + Raw"]
    )
    with tab1:
        _render_overview(detail)
    with tab2:
        _render_candidates(detail)
    with tab3:
        _render_validations(detail)
    with tab4:
        _render_decision(detail)
    with tab5:
        _render_audit(detail)
        with st.expander("Raw payload"):
            st.json(detail, expanded=False)


def _render_ingest(base_url: str, timeout: float) -> None:
    st.header("Ingest Freight Bill")
    seed_rows = _load_seed_freight_bills()
    seed_map = {row.get("id", f"row-{idx}"): row for idx, row in enumerate(seed_rows)}

    selected_seed_id = st.selectbox(
        "Pick seed bill",
        options=[""] + sorted(seed_map.keys()),
        index=0,
        key="seed_selector",
    )

    default_payload = {}
    if selected_seed_id:
        default_payload = dict(seed_map[selected_seed_id])
    payload_text = st.text_area(
        "Payload JSON",
        value=json.dumps(default_payload, indent=2) if default_payload else "{}",
        height=320,
    )
    force_reprocess = st.checkbox("force_reprocess", value=True)

    if st.button("POST /freight-bills", type="primary"):
        try:
            payload = json.loads(payload_text)
            if not isinstance(payload, dict):
                raise ValueError("Payload must be a JSON object")
        except Exception as exc:
            st.error(f"Invalid JSON payload: {exc}")
            return

        payload["force_reprocess"] = force_reprocess
        ok, response = _api_post(base_url, "/freight-bills", payload, timeout)
        if not ok:
            st.error(response)
            return

        st.success("Bill ingested and workflow executed.")
        st.json(response, expanded=False)
        bill_id = (response.get("freight_bill") or {}).get("id")
        if bill_id:
            st.session_state["selected_bill_id"] = bill_id
            st.session_state["selected_bill_detail"] = response


def _render_review_queue(base_url: str, timeout: float) -> None:
    st.header("Review Queue")
    if st.button("Refresh queue", type="primary"):
        ok, payload = _api_get(base_url, "/review-queue", timeout)
        if not ok:
            st.error(payload)
            return
        st.session_state["review_queue_payload"] = payload

    queue = st.session_state.get("review_queue_payload")
    if not queue:
        st.info("Load the review queue.")
        return

    items = queue.get("items", [])
    st.write(f"Pending tasks: {queue.get('count', len(items))}")
    if not items:
        st.success("No pending review tasks.")
        return

    for item in items:
        bill_id = item.get("freight_bill_id")
        task_id = item.get("review_task_id")
        with st.expander(f"{bill_id} | task #{task_id}", expanded=False):
            st.write(f"Suggested decision: `{item.get('suggested_agent_decision')}`")
            st.write(f"Review summary: {item.get('review_summary') or '-'}")
            st.write(
                {
                    "selected_contract_id": item.get("selected_contract_id"),
                    "selected_shipment_id": item.get("selected_shipment_id"),
                    "selected_bol_id": item.get("selected_bol_id"),
                }
            )
            st.markdown("**Top validation issues**")
            st.dataframe(item.get("validation_issues") or [], use_container_width=True)

            c1, c2 = st.columns([1, 2])
            decision = c1.selectbox(
                "Reviewer decision",
                options=item.get("allowed_reviewer_decisions", ["approve", "dispute", "modify"]),
                key=f"review_decision_{task_id}",
            )
            notes = c2.text_input("Notes", key=f"review_notes_{task_id}")

            if st.button(f"Submit review for {bill_id}", key=f"submit_review_{task_id}"):
                ok, response = _api_post(
                    base_url,
                    f"/review/{bill_id}",
                    {"reviewer_decision": decision, "notes": notes or None},
                    timeout,
                )
                if not ok:
                    st.error(response)
                else:
                    st.success(f"Review submitted for {bill_id}.")
                    st.session_state["selected_bill_id"] = bill_id
                    st.session_state["selected_bill_detail"] = response
                    # Refresh queue after successful review action.
                    ok_q, payload_q = _api_get(base_url, "/review-queue", timeout)
                    if ok_q:
                        st.session_state["review_queue_payload"] = payload_q
                    st.rerun()


def _render_graph() -> None:
    st.header("Graph View")
    detail = st.session_state.get("selected_bill_detail")
    if not detail:
        st.info("Fetch a bill first in Bill Explorer or ingest flow.")
        return

    dot = _build_graphviz(detail)
    st.graphviz_chart(dot, use_container_width=True)
    with st.expander("DOT source"):
        st.code(dot, language="dot")


def main() -> None:
    st.set_page_config(page_title="Logistics Billing Ops Console", layout="wide")
    st.title("Logistics Billing Ops Console")

    with st.sidebar:
        st.header("Connection")
        base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL)
        timeout = st.number_input("HTTP timeout (seconds)", min_value=5.0, value=DEFAULT_TIMEOUT)
        if st.button("Health check"):
            ok, payload = _api_get(base_url, "/health", timeout)
            if ok:
                st.success(payload)
            else:
                st.error(payload)

    tab_ingest, tab_bill, tab_queue, tab_graph = st.tabs(
        ["Ingest", "Bill Explorer", "Review Queue", "Graph"]
    )
    with tab_ingest:
        _render_ingest(base_url, timeout)
    with tab_bill:
        _render_bill_explorer(base_url, timeout)
    with tab_queue:
        _render_review_queue(base_url, timeout)
    with tab_graph:
        _render_graph()


if __name__ == "__main__":
    main()
