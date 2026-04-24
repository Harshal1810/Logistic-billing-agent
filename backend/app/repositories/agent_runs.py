from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun


def create_agent_run(
    db: Session,
    run_id: str,
    freight_bill_id: str,
    workflow_status: str,
    state_payload: dict,
    current_node: str | None = None,
) -> AgentRun:
    row = AgentRun(
        run_id=run_id,
        freight_bill_id=freight_bill_id,
        workflow_status=workflow_status,
        current_node=current_node,
        state_payload=state_payload,
    )
    db.add(row)
    return row


def get_agent_run_by_run_id(db: Session, run_id: str) -> AgentRun | None:
    return db.query(AgentRun).filter(AgentRun.run_id == run_id).one_or_none()


def get_latest_agent_run_for_bill(db: Session, freight_bill_id: str) -> AgentRun | None:
    return (
        db.query(AgentRun)
        .filter(AgentRun.freight_bill_id == freight_bill_id)
        .order_by(AgentRun.created_at.desc())
        .first()
    )


def update_agent_run(
    db: Session,
    run_id: str,
    workflow_status: str | None = None,
    current_node: str | None = None,
    state_payload: dict | None = None,
    last_error: str | None = None,
) -> AgentRun:
    row = get_agent_run_by_run_id(db, run_id)
    if row is None:
        raise ValueError(f"Agent run not found: {run_id}")

    if workflow_status is not None:
        row.workflow_status = workflow_status
    if current_node is not None:
        row.current_node = current_node
    if state_payload is not None:
        row.state_payload = state_payload
    if last_error is not None:
        row.last_error = last_error

    db.add(row)
    return row
