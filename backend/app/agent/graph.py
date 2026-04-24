from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    apply_reviewer_input_node,
    compute_decision_node,
    finalize_node,
    load_bill_node,
    match_contract_node,
    match_shipment_node,
    review_gate_node,
    run_validations_node,
)
from app.agent.state import FreightBillAgentState


def _route_after_review_gate(state: FreightBillAgentState) -> str:
    if state.get("workflow_status") == "waiting_for_review":
        return "pause"
    if state.get("reviewer_decision"):
        return "apply_reviewer"
    return "finalize"


def build_workflow_graph() -> StateGraph:
    graph = StateGraph(FreightBillAgentState)

    graph.add_node("load_bill", load_bill_node)
    graph.add_node("match_contract", match_contract_node)
    graph.add_node("match_shipment", match_shipment_node)
    graph.add_node("run_validations", run_validations_node)
    graph.add_node("compute_decision", compute_decision_node)
    graph.add_node("review_gate", review_gate_node)
    graph.add_node("apply_reviewer_input", apply_reviewer_input_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "load_bill")
    graph.add_edge("load_bill", "match_contract")
    graph.add_edge("match_contract", "match_shipment")
    graph.add_edge("match_shipment", "run_validations")
    graph.add_edge("run_validations", "compute_decision")
    graph.add_edge("compute_decision", "review_gate")
    graph.add_conditional_edges(
        "review_gate",
        _route_after_review_gate,
        {
            "pause": END,
            "apply_reviewer": "apply_reviewer_input",
            "finalize": "finalize",
        },
    )
    graph.add_edge("apply_reviewer_input", "finalize")
    graph.add_edge("finalize", END)

    return graph


def build_review_resume_graph() -> StateGraph:
    graph = StateGraph(FreightBillAgentState)

    graph.add_node("review_gate", review_gate_node)
    graph.add_node("apply_reviewer_input", apply_reviewer_input_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "review_gate")
    graph.add_conditional_edges(
        "review_gate",
        _route_after_review_gate,
        {
            "pause": END,
            "apply_reviewer": "apply_reviewer_input",
            "finalize": "finalize",
        },
    )
    graph.add_edge("apply_reviewer_input", "finalize")
    graph.add_edge("finalize", END)

    return graph
