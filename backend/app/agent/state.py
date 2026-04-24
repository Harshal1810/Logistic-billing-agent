from typing import NotRequired, TypedDict


class FreightBillAgentState(TypedDict):
    freight_bill_id: str
    run_id: str
    workflow_status: NotRequired[str]
    current_node: NotRequired[str]
    decision: NotRequired[str]
    confidence_score: NotRequired[float]
    requires_review: NotRequired[bool]
    reviewer_decision: NotRequired[str]
    reviewer_notes: NotRequired[str]
    last_error: NotRequired[str]
